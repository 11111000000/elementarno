#!/usr/bin/env python3
"""Скорер пар «до/после»: нашёл, не нашёл, ложное срабатывание.

На каждой паре прогоняются три сцены — «до», «после» и «чистая» — и считается:

  negative_detected — правило отсутствия сработало на кадре, где улика видна,
                      и не сработало на втором кадре пары;
  false_positive    — правило сработало на контрольной «чистой» сцене;
  consistency       — наборы сработавших правил «после» и «чистой» совпали,
                      то есть уборка предмета не оставила лишних улик.

Сейчас в манифесте только синтетические пары: метрика ложных срабатываний
измеряет работу движка, а не мир. Настоящие пары добавятся тем же скорером.

    python3 tools/score_pairs.py
    python3 tools/score_pairs.py --json
    python3 tools/score_pairs.py --out /tmp/pairs-report.json
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from elementarno.rules import evaluate_all, load_packs  # noqa: E402
from elementarno.scene import validate_scene  # noqa: E402
from make_pairs import build_pair, write_pair  # noqa: E402

PAIRS_DIR = ROOT / "eval" / "pairs"
MANIFEST_PATH = PAIRS_DIR / "manifest.json"
FRAMES = ("before", "after", "clean")


def rule_of(finding_id):
    return finding_id[2:] if finding_id.startswith("F-") else finding_id


def fired_rules(rules, scene):
    return {finding["rule_id"] for finding in evaluate_all(rules, scene)}


def restore_synthetic(pair, base):
    spec = build_pair(pair["id"])
    folder = (base / pair["before"]).parent
    write_pair(spec, folder.parent)
    return folder


def load_scenes(pair, base):
    paths = {frame: base / pair[frame] for frame in FRAMES}
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing and pair.get("synthetic"):
        restore_synthetic(pair, base)
        missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("нет файлов сцены: " + ", ".join(missing))
    scenes = {frame: json.loads(path.read_text(encoding="utf-8")) for frame, path in paths.items()}
    return scenes


def score_pair(pair, scenes, rules, packs_by_rule):
    problems = []
    for frame, scene in scenes.items():
        issues = validate_scene(scene)
        if issues:
            problems.append(f"{frame}: сцена невалидна ({issues[0]['code']}: {issues[0]['detail']})")

    before = fired_rules(rules, scenes["before"])
    after = fired_rules(rules, scenes["after"])
    clean = fired_rules(rules, scenes["clean"])

    expect = pair.get("expect", {})
    expected = {rule_of(item) for item in expect.get("finding_ids", [])}
    trace_frame = expect.get("trace_frame", "before")
    if trace_frame not in ("before", "after"):
        raise ValueError(f"пара {pair['id']}: неизвестный trace_frame {trace_frame!r}")
    on_trace = before if trace_frame == "before" else after
    on_other = after if trace_frame == "before" else before

    missing = sorted(expected - on_trace)
    leaked = sorted(expected & on_other)
    packs = {packs_by_rule.get(rule) for rule in expected}
    packs.discard(None)
    false_positive = sorted(rule for rule in clean if not packs or packs_by_rule.get(rule) in packs)
    clean_extra = sorted(rule for rule in clean if rule not in false_positive)

    consistency = after == clean
    negative_detected = not missing and not leaked
    if not expected:
        problems.append("в expect нет ни одного правила: пара ничего не проверяет")
    if missing:
        problems.append("не сработали на кадре с уликой: " + ", ".join(missing))
    if leaked:
        problems.append("сработали на втором кадре: " + ", ".join(leaked))
    if false_positive:
        problems.append("ложные срабатывания на чистой сцене: " + ", ".join(false_positive))
    if not consistency:
        problems.append("«после» и «чистая» дали разные наборы правил")

    return {
        "id": pair["id"],
        "truth": pair.get("truth"),
        "real": bool(pair.get("real")),
        "synthetic": bool(pair.get("synthetic")),
        "expect": expect,
        "trace_frame": trace_frame,
        "fired": {
            "before": sorted(before),
            "after": sorted(after),
            "clean": sorted(clean),
        },
        "negative_detected": negative_detected,
        "missing": missing,
        "leaked": leaked,
        "false_positive": false_positive,
        "clean_extra": clean_extra,
        "consistency": consistency,
        "passed": not problems,
        "problems": problems,
    }


def summarize(results):
    total = len(results)
    passed = sum(1 for item in results if item["passed"])
    detected = sum(1 for item in results if item["negative_detected"])
    consistent = sum(1 for item in results if item["consistency"])
    false_positives = sum(len(item["false_positive"]) for item in results)
    per_rule = {}
    for item in results:
        for finding_id in item["expect"].get("finding_ids", []):
            rule = rule_of(finding_id)
            entry = per_rule.setdefault(rule, {"expected": 0, "detected": 0})
            entry["expected"] += 1
            if rule not in item["missing"] and rule not in item["leaked"]:
                entry["detected"] += 1
    return {
        "pairs": total,
        "synthetic_pairs": sum(1 for item in results if item["synthetic"]),
        "real_pairs": sum(1 for item in results if item["real"]),
        "passed": passed,
        "failed": total - passed,
        "negative_detected": detected,
        "negative_detection_rate": round(detected / total, 3) if total else None,
        "false_positives": false_positives,
        "pairs_with_false_positive": sum(1 for item in results if item["false_positive"]),
        "consistency": consistent,
        "consistency_rate": round(consistent / total, 3) if total else None,
        "per_rule": per_rule,
    }


def print_summary(summary, results):
    print(f"пар: {summary['pairs']} (синтетических: {summary['synthetic_pairs']}, "
          f"реальных: {summary['real_pairs']})")
    if summary["real_pairs"] == 0:
        print("внимание: реальных пар нет — ложные срабатывания измеряются на синтетике, "
              "то есть на работе движка, а не на мире")
    print(f"улика найдена: {summary['negative_detected']}/{summary['pairs']} "
          f"(ставка {summary['negative_detection_rate']})")
    print(f"ложных срабатываний на чистых сценах: {summary['false_positives']} "
          f"(пар с ложными срабатываниями: {summary['pairs_with_false_positive']})")
    print(f"согласованность «после» и «чистой»: {summary['consistency']}/{summary['pairs']} "
          f"(ставка {summary['consistency_rate']})")
    for rule, entry in sorted(summary["per_rule"].items()):
        print(f"  {rule}: найдено {entry['detected']}/{entry['expected']}")
    print()
    for item in results:
        mark = "✓" if item["passed"] else "✗"
        print(f"{mark} {item['id']}")
        print(f"    истина: {item['truth']}")
        print(f"    сработало: до {item['fired']['before'] or '—'}; "
              f"после {item['fired']['after'] or '—'}; чистая {item['fired']['clean'] or '—'}")
        if item["problems"]:
            for problem in item["problems"]:
                print(f"    проблема: {problem}")
    print()
    print(f"итог: прошло {summary['passed']}, провалено {summary['failed']}")


def run(manifest_path=MANIFEST_PATH, base=PAIRS_DIR):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    rules = load_packs(ROOT / "rules")
    packs_by_rule = {rule.id: rule.pack for rule in rules}
    results = []
    for pair in manifest.get("pairs", []):
        try:
            scenes = load_scenes(pair, base)
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            expected = {rule_of(item) for item in pair.get("expect", {}).get("finding_ids", [])}
            results.append({
                "id": pair.get("id"),
                "truth": pair.get("truth"),
                "real": bool(pair.get("real")),
                "synthetic": bool(pair.get("synthetic")),
                "expect": pair.get("expect", {}),
                "trace_frame": pair.get("expect", {}).get("trace_frame", "before"),
                "fired": {"before": [], "after": [], "clean": []},
                "negative_detected": False,
                "missing": sorted(expected),
                "leaked": [],
                "false_positive": [],
                "clean_extra": [],
                "consistency": False,
                "passed": False,
                "problems": [str(exc)],
            })
            continue
        results.append(score_pair(pair, scenes, rules, packs_by_rule))
    summary = summarize(results)
    return {"summary": summary, "results": results}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Скорер пар «до/после»")
    parser.add_argument("--manifest", default=str(MANIFEST_PATH))
    parser.add_argument("--out", help="куда записать JSON-отчёт")
    parser.add_argument("--json", action="store_true", help="печатать JSON вместо сводки")
    args = parser.parse_args(argv)

    report = run(args.manifest)
    if args.out:
        Path(args.out).write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_summary(report["summary"], report["results"])
    return 1 if report["summary"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
