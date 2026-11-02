#!/usr/bin/env python3
"""Измерение на реальных фотографиях.

Главный вопрос, который этот харнесс честно отвечает: работает ли
восприятие на живых снимках, а не только на синтетике. Метрики:

  recall      — доля случаев, где ожидаемое правило сработало
  false_pos   — срабатывания на «чистых» кадрах и лишние правила
  latency     — секунд на снимок
  calls       — вызовов модели на снимок
  cost        — токенов на снимок

Артефакты каждого прогона сохраняются рядом: сырой ответ модели, сцена-граф,
найденные улики. Без сырого ответа результат невоспроизводим.

    python3 tools/run_real.py --limit 12
"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from elementarno.ledger import validate  # noqa: E402
from elementarno.perception import MiniMaxPerception  # noqa: E402
from elementarno.puzzle import build_claims  # noqa: E402
from elementarno.rules import evaluate_all, load_packs  # noqa: E402

MANIFEST = ROOT / "eval/real/manifest.json"
RUNS = ROOT / "eval/real/runs"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--model", default="MiniMax-M3")
    parser.add_argument("--packs", action="append")
    parser.add_argument("--out", default=str(RUNS))
    parser.add_argument("--repeat", type=int, default=1,
                        help="сколько раз прогнать каждый случай: устойчивость важнее одного удачного прогона")
    args = parser.parse_args(argv)

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    cases = manifest["cases"][:args.limit] if args.limit else manifest["cases"]
    rules = load_packs(ROOT / "rules")
    if args.packs:
        wanted = set(args.packs)
        rules = [rule for rule in rules if rule.pack in wanted]

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    perception = MiniMaxPerception(model=args.model)

    results = []
    attempts = []
    for index, case in enumerate(cases, start=1):
        image = ROOT / case.get("image") or ROOT / "eval/real/images" / f"{case['id']}.jpg"
        expected = set(case.get("expect_rules", []))
        record = {
            "id": case["id"],
            "trace_type": case.get("trace_type"),
            "advisory": bool(case.get("expect_advisory")),
            "expected": sorted(expected),
            "ground_truth": case.get("ground_truth"),
        }
        if not image.exists():
            record.update({"status": "no_image", "fired": [], "recall": 0.0, "false_pos": 0})
            results.append(record)
            print(f"[{index}/{len(cases)}] {case['id']}: нет файла изображения")
            continue

        hits = []
        for attempt in range(1, args.repeat + 1):
            started = time.monotonic()
            suffix = "" if args.repeat == 1 else f".{attempt}"
            try:
                scene, meta = perception.scene_graph(
                    image, save_raw=out_dir / f"{case['id']}{suffix}.raw.json")
            except Exception as exc:  # noqa: BLE001 — прогон не должен падать на одном кадре
                hits.append({"error": str(exc), "fired": [], "recall": 0.0, "false_pos": 0})
                continue
            wall = round(time.monotonic() - started, 1)

            findings = evaluate_all(rules, scene)
            fired = {f["finding_id"] for f in findings}
            claims = build_claims(findings)
            report = validate(findings, {"claims": claims})

            expected_hits = expected & fired
            recall = 1.0 if (expected and expected_hits == expected) else (0.0 if expected else None)
            extra = fired - expected
            false_pos = len(extra)

            (out_dir / f"{case['id']}{suffix}.scene.json").write_text(
                json.dumps(scene, ensure_ascii=False, indent=2), encoding="utf-8")
            (out_dir / f"{case['id']}{suffix}.findings.json").write_text(
                json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")

            hits.append({
                "error": None,
                "fired": sorted(fired),
                "expected_hit": sorted(expected_hits),
                "missing": sorted(expected - fired),
                "extra": sorted(extra),
                "recall": recall,
                "false_pos": false_pos,
                "latency_s": wall,
                "calls": meta.get("calls"),
                "regions_found": len(scene.get("regions", [])),
                "protocol_errors": len(report["errors"]),
            })
            attempts.append(hits[-1])

        good = [h for h in hits if h.get("error") is None]
        if not good:
            record.update({"status": f"perception_error: {hits[0]['error']}", "fired": [], "recall": 0.0,
                           "false_pos": 0, "attempts": len(hits)})
        else:
            recall_values = [h["recall"] for h in good if h["recall"] is not None]
            record.update({
                "status": "ok",
                "fired": good[0]["fired"],
                "missing": good[0]["missing"],
                "extra": good[0]["extra"],
                "recall": (sum(recall_values) / len(recall_values)) if recall_values else None,
                "recall_stable": len(set(recall_values)) == 1 if recall_values else None,
                "false_pos": sum(h["false_pos"] for h in good) / len(good),
                "latency_s": round(sum(h["latency_s"] for h in good) / len(good), 1),
                "attempts": len(good),
                "errors": [h["error"] for h in hits if h.get("error")],
            })
        results.append(record)
        mark = "✓" if (record.get("recall") == 1.0 or (record.get("recall") is None and record.get("false_pos") == 0)) else "✗"
        stability = ""
        if record.get("attempts", 1) > 1:
            stability = f", попыток {record['attempts']}, стабильность {record.get('recall_stable')}"
        print(f"[{index}/{len(cases)}] {mark} {case['id']}: "
              f"ожидалось {sorted(expected) or '—'}, сработало {record.get('fired') or '—'}{stability}")

    summary = summarize(results)
    (out_dir / "summary.json").write_text(json.dumps(
        {"summary": summary, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n" + "=" * 64)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def summarize(results):
    done = [r for r in results if r.get("status") == "ok"]
    trace_cases = [r for r in done if r.get("recall") is not None and not r.get("advisory")]
    clean_cases = [r for r in done if r.get("recall") is None]
    hits = sum(1 for r in trace_cases if r["recall"] == 1.0)
    fp_clean = sum(r["false_pos"] for r in clean_cases)
    fp_extra = sum(len(r.get("extra", [])) for r in trace_cases)
    latencies = [r["latency_s"] for r in done]
    return {
        "cases": len(results),
        "processed": len(done),
        "trace_cases": len(trace_cases),
        "advisory_cases": sum(1 for r in done if r.get("advisory")),
        "trace_hits": hits,
        "recall": round(hits / len(trace_cases), 3) if trace_cases else None,
        "clean_cases": len(clean_cases),
        "false_positives_on_clean": fp_clean,
        "extra_rules_on_trace": fp_extra,
        "latency_mean_s": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "latency_max_s": max(latencies) if latencies else None,
        "unstable_cases": [r["id"] for r in done if r.get("recall_stable") is False],
    }


if __name__ == "__main__":
    raise SystemExit(main())
