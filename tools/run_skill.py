#!/usr/bin/env python3
"""Харнесс скилла detective: кейс → фазы скилла → артефакты → метрики.

Раннер исполняет скилл против кейса из `eval/skill-cases/cases.json` и считает
метрики по `docs/PROTOCOL.md` §10. Текст фаз берётся из
`.opencode/skills/detective/SKILL.md`, поэтому правка скилла меняет харнесс
без правки кода: код знает только номера фаз, а не их содержание.

Фазы:

  1–2  сцена-граф      — `elementarno.perception.MiniMaxPerception.scene_graph`
  3    улики            — `elementarno.rules.evaluate_all`
  4–6  проверка, утверждения, версии — вызов модели с текстом фаз скилла
  7    вопрос           — `elementarno.nextshot`
  8    ответ            — `elementarno.render`
  9    журнал           — артефакты прогона

    python3 tools/run_skill.py --limit 2
    python3 tools/run_skill.py --offline
"""

import argparse
import base64
import json
import mimetypes
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from elementarno.ledger import Verdict, score_hypotheses, validate  # noqa: E402
from elementarno.ledger import verdict as decide_verdict  # noqa: E402
from elementarno.nextshot import (  # noqa: E402
    discriminator_questions,
    hypothesis_tags,
    kind_tags_from_rules,
    rank_questions,
)
from elementarno.perception import MiniMaxPerception, PerceptionError  # noqa: E402
from elementarno.render import render  # noqa: E402
from elementarno.rules import evaluate_all, load_packs  # noqa: E402

SKILL_PATH = ROOT / ".opencode/skills/detective/SKILL.md"
CASES_PATH = ROOT / "eval/skill-cases/cases.json"
OUT_DIR = ROOT / "eval/skill-runs"
RULES_DIR = ROOT / "rules"

PHASE_HEADING = re.compile(r"^###[ \t]+(\d+)\.[ \t]*(.+?)[ \t]*$", re.MULTILINE)
SECTION_HEADING = re.compile(r"^##[ \t]+", re.MULTILINE)

PHASES_IN_PROMPT = (4, 5, 6)
REFUTATION_OUTCOMES = ("survived", "refuted", "undetermined")

OUTPUT_CONTRACT = """ФОРМАТ ОТВЕТА — ТОЛЬКО JSON, без markdown и без пояснений:

{
  "claims": [
    {"claim_id": "C-1",
     "kind": "observation|inference|hypothesis|interpretation",
     "text": "утверждение по-русски",
     "support": [{"finding_id": "F-ABS-001"}],
     "confidence": 0.4,
     "step": "scene|activity|presence|role|action",
     "confounds": ["оговорка"],
     "falsification": "что опровергло бы утверждение",
     "provisional": false,
     "speculative": false,
     "refutation": {"negation": "что проверял в отрицательной форме",
                   "outcome": "survived|refuted|undetermined",
                   "note": "чем кончилось"}}
  ],
  "hypotheses": [
    {"hypothesis_id": "H-1",
     "text": "версия по-русски",
     "claims": ["C-1"],
     "status": "open|rejected",
     "step": "presence",
     "discriminator": {"question": "что развело бы версии",
                      "would_confirm": "что подтвердило бы",
                      "would_refute": "что опровергло бы"},
     "kill_log": [{"rule_id": "F-ABS-001", "note": "чем убита версия"}]}
  ]
}

ТРЕБОВАНИЯ К ОТВЕТУ:

1. support ссылается только на перечисленные ниже finding_id. Несуществующих
   идентификаторов не бывает: улики создаёт движок, а не ты.
2. confidence не выше confidence_ceiling своей улики; если улика черновиковая
   (provisional), то confidence не выше 0.5 и у утверждения стоит provisional.
3. refutation обязателен у каждого утверждения, которое идёт дальше вывода
   улики. Утверждение, которое дословно повторяет вывод улики, отрицать не
   нужно: работает опровержение самого правила.
4. outcome "refuted" — такое утверждение не выдавай вовсе.
5. discriminator обязателен у каждой версии: без него версии неразличимы.
6. Никаких обвинений и никаких выводов о характере: допустимы присутствие,
   действие, роль или привычка.
7. Улик нет — claims и hypotheses пустые, и это правильный ответ."""


class HarnessError(RuntimeError):
    pass


class ManifestError(HarnessError):
    pass


class SkillError(HarnessError):
    pass


def parse_phases(text):
    """Разбор скилла на фазы: заголовок «### N. Заголовок» и текст под ним."""
    matches = list(PHASE_HEADING.finditer(text))
    phases = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = len(text)
        if index + 1 < len(matches):
            end = matches[index + 1].start()
        section = SECTION_HEADING.search(text, start)
        if section:
            end = min(end, section.start())
        number = int(match.group(1))
        phases[number] = {
            "number": number,
            "title": match.group(2).strip(),
            "text": text[start:end].strip(),
        }
    return phases


def load_skill(path=SKILL_PATH):
    path = Path(path)
    if not path.exists():
        raise SkillError(f"скилл не найден: {path}")
    phases = parse_phases(path.read_text(encoding="utf-8"))
    if not phases:
        raise SkillError(f"в скилле нет заголовков «### N. Заголовок»: {path}")
    missing = [number for number in PHASES_IN_PROMPT if number not in phases]
    if missing:
        raise SkillError(f"в скилле нет фаз {missing}: {path}")
    return {"path": str(path), "phases": phases, "order": sorted(phases)}


def validate_manifest(payload, root=ROOT):
    """Проверка манифеста кейсов. Возвращает список проблем (пустой — всё в порядке)."""
    problems = []
    if not isinstance(payload, dict):
        return ["манифест должен быть объектом"]
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        return ["в манифесте нет кейсов"]
    seen = set()
    for index, case in enumerate(cases):
        label = f"кейс #{index + 1}"
        if not isinstance(case, dict):
            problems.append(f"{label}: не объект")
            continue
        for field in ("id", "image"):
            if not isinstance(case.get(field), str) or not case[field].strip():
                problems.append(f"{label}: нет поля «{field}»")
        case_id = case.get("id")
        if isinstance(case_id, str) and case_id.strip():
            if case_id in seen:
                problems.append(f"кейс {case_id}: повторяется")
            seen.add(case_id)
        image = case.get("image")
        if isinstance(image, str) and image.strip():
            if not (Path(root) / image).exists():
                problems.append(f"{label}: нет файла изображения {image}")
        packs = case.get("packs")
        if not isinstance(packs, list) or not packs or not all(isinstance(p, str) for p in packs):
            problems.append(f"{label}: нет поля «packs»")
        expect = case.get("expect")
        if not isinstance(expect, dict):
            problems.append(f"{label}: нет поля «expect»")
            continue
        finding_ids = expect.get("finding_ids")
        if finding_ids is not None:
            if not isinstance(finding_ids, list) or not all(isinstance(f, str) for f in finding_ids):
                problems.append(f"{label}: expect.finding_ids должен быть списком строк")
        verdict = expect.get("verdict")
        known = (Verdict.SUFFICIENT, Verdict.INSUFFICIENT, Verdict.CONFLICT)
        if verdict is not None and verdict not in known:
            problems.append(f"{label}: неизвестный вердикт {verdict!r}")
    return problems


def load_cases(path=CASES_PATH, root=ROOT):
    path = Path(path)
    if not path.exists():
        raise ManifestError(f"манифест кейсов не найден: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"манифест не разобран: {exc}") from exc
    problems = validate_manifest(payload, root=root)
    if problems:
        raise ManifestError("; ".join(problems))
    return payload["cases"]


def load_rules(packs=None, rules_dir=RULES_DIR):
    rules = load_packs(rules_dir)
    if not packs:
        return rules
    wanted = set(packs)
    return [rule for rule in rules if rule.pack in wanted]


def findings_digest(findings):
    return [
        {
            "finding_id": f["finding_id"],
            "rule_id": f["rule_id"],
            "title": f["title"],
            "inference": f["inference"],
            "confounds": f.get("confounds", []),
            "confidence_ceiling": f["confidence_ceiling"],
            "provisional": f.get("provisional", False),
            "tags": f.get("tags", []),
            "step": f.get("step", "action"),
            "anchors": f.get("anchors", []),
        }
        for f in findings
    ]


def scene_digest(scene):
    return {
        "objects": [{"id": o.get("id"), "category": o.get("category"), "on": o.get("on")}
                    for o in scene.get("objects", [])][:20],
        "surfaces": [{"id": s.get("id"), "name": s.get("name"), "dust_present": s.get("dust_present")}
                     for s in scene.get("surfaces", [])][:10],
        "regions": [{"id": r.get("id"), "kind": r.get("kind"), "note": (r.get("note") or "")[:120]}
                    for r in scene.get("regions", [])][:20],
    }


def build_prompt(phases, findings, scene):
    """Промпт фаз 4–6: текст скилла, улики и сцена."""
    parts = [
        "Ты работаешь по протоколу доказательности ЭЛЕМЕНТАРНО. "
        "Ниже — инструкции фаз из скилла detective, дословно.",
    ]
    for number in PHASES_IN_PROMPT:
        phase = phases[number]
        parts.append(f"### Фаза {number}. {phase['title']}\n{phase['text']}")
    parts.append(OUTPUT_CONTRACT)
    parts.append("УЛИКИ:\n" + json.dumps(findings_digest(findings), ensure_ascii=False, indent=1))
    parts.append("СЦЕНА (кратко):\n" + json.dumps(scene_digest(scene), ensure_ascii=False))
    parts.append("Верни ТОЛЬКО JSON.")
    return "\n\n".join(parts)


def normalize_ledger(data):
    """Привести ответ модели к форме леджера.

    Ничего не выбрасывается: отброшенное утверждение — это нарушение протокола,
    и харнесс обязан его посчитать, а не спрятать.
    """
    claims = []
    for index, raw in enumerate(data.get("claims") or []):
        if not isinstance(raw, dict):
            continue
        support = []
        for item in raw.get("support") or []:
            # модель пишет ссылку то объектом, то строкой: форма перевозки, а не протокол
            if isinstance(item, dict) and isinstance(item.get("finding_id"), str):
                support.append({"finding_id": item["finding_id"]})
            elif isinstance(item, str) and item.strip():
                support.append({"finding_id": item.strip()})
        refutation = raw.get("refutation")
        if not isinstance(refutation, dict):
            refutation = None
        try:
            confidence = float(raw.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        claims.append({
            "claim_id": raw.get("claim_id") or f"C-{index + 1}",
            "kind": raw.get("kind") or "inference",
            "text": str(raw.get("text") or ""),
            "support": support,
            "confidence": confidence,
            "step": raw.get("step") or "action",
            "confounds": raw.get("confounds") if isinstance(raw.get("confounds"), list) else [],
            "falsification": raw.get("falsification"),
            "provisional": bool(raw.get("provisional")),
            "speculative": bool(raw.get("speculative")),
            "refutation": refutation,
        })

    hypotheses = []
    for index, raw in enumerate(data.get("hypotheses") or []):
        if not isinstance(raw, dict):
            continue
        discriminator = raw.get("discriminator")
        if not isinstance(discriminator, dict):
            discriminator = None
        hypotheses.append({
            "hypothesis_id": raw.get("hypothesis_id") or f"H-{index + 1}",
            "text": str(raw.get("text") or ""),
            "claims": [c for c in (raw.get("claims") or []) if isinstance(c, str)],
            "status": raw.get("status") or "open",
            "step": raw.get("step") or "action",
            "discriminator": discriminator,
            "kill_log": raw.get("kill_log") if isinstance(raw.get("kill_log"), list) else [],
        })
    return {"claims": claims, "hypotheses": hypotheses}


def has_refutation(claim):
    refutation = claim.get("refutation")
    if not isinstance(refutation, dict):
        return False
    return bool((refutation.get("negation") or "").strip())


def has_discriminator(hypothesis):
    discriminator = hypothesis.get("discriminator")
    if not isinstance(discriminator, dict):
        return False
    return bool((discriminator.get("question") or "").strip())


def next_questions(scene, findings, hypotheses, rules, limit=3):
    found_kinds = {r.get("kind") for r in scene.get("regions", [])}
    return {
        "discriminators": discriminator_questions(hypotheses)[:limit],
        "catalogue": rank_questions(
            hypotheses,
            hypothesis_tags(hypotheses, findings),
            kind_tags_from_rules(rules),
            found_kinds,
            limit=limit,
        ),
    }


def compose_answer(rendered, questions):
    lines = [rendered, "", "---", "", "Следующий шаг (фаза 7):"]
    if not questions["discriminators"] and not questions["catalogue"]:
        lines.append("Спросить нечего: различимых версий нет.")
    for item in questions["discriminators"]:
        lines.append(f"- {item['question']}")
        lines.append(f"  зачем: {item['why']}")
    for item in questions["catalogue"]:
        lines.append(f"- {item['question']} (ценность информации {item['eig']:.3f} бит)")
    return "\n".join(lines)


def case_metrics(case, findings, ledger, report, verdict, latency_s, calls):
    """Метрики одного кейса."""
    fired = {f["finding_id"] for f in findings}
    expected = set(case["expect"].get("finding_ids") or [])
    claims = ledger.get("claims", [])
    hypotheses = ledger.get("hypotheses", [])
    with_refutation = [c for c in claims if has_refutation(c)]
    with_discriminator = [h for h in hypotheses if has_discriminator(h)]
    expected_verdict = case["expect"].get("verdict")
    verdict_match = None if expected_verdict is None else (verdict == expected_verdict)
    return {
        "protocol_violations": len(report["errors"]),
        "protocol_errors": report["errors"],
        "citation_completeness": report["citation_completeness"],
        "finding_recall": (len(expected & fired) / len(expected)) if expected else None,
        "extra_findings": len(fired - expected),
        "extra_finding_ids": sorted(fired - expected),
        "missing_finding_ids": sorted(expected - fired),
        "fired_finding_ids": sorted(fired),
        "refutation_coverage": (len(with_refutation) / len(claims)) if claims else None,
        "claims_without_refutation": len(claims) - len(with_refutation),
        "discriminator_coverage": (len(with_discriminator) / len(hypotheses)) if hypotheses else None,
        "hypotheses_without_discriminator": len(hypotheses) - len(with_discriminator),
        "claims": len(claims),
        "hypotheses": len(hypotheses),
        "verdict": verdict,
        "expected_verdict": expected_verdict,
        "refusal_accuracy": None if verdict_match is None else (1.0 if verdict_match else 0.0),
        "latency_s": latency_s,
        "calls": calls,
    }


def run_case(case, phases, rules, perception, run_dir, persona="doyle", mode="detective"):
    """Один прогон кейса: фазы 1–9 и запись артефактов."""
    image = ROOT / case["image"]
    started = time.monotonic()
    run_dir.mkdir(parents=True, exist_ok=True)
    raw_path = run_dir / "raw.json"

    scene, meta = perception.scene_graph(image, save_raw=raw_path)
    findings = evaluate_all(rules, scene)

    prompt = build_prompt(phases, findings, scene)
    image_b64 = base64.b64encode(image.read_bytes()).decode("ascii")
    media_type = mimetypes.guess_type(image.name)[0] or "image/jpeg"
    payload, latency_ms = perception.call(image_b64, media_type, prompt, max_tokens=6000)
    text = perception.text_of(payload)
    data = perception.extract_json(text)

    ledger = normalize_ledger(data)
    report = validate(findings, ledger)
    usable = [c for c in ledger["claims"]
              if not any(e.get("claim_id") == c["claim_id"] for e in report["errors"])]
    hypotheses = score_hypotheses(findings, usable, ledger["hypotheses"])
    state = decide_verdict(findings, usable, 1, mode)
    rendered = render(mode, findings, usable, hypotheses, state, persona, report)
    questions = next_questions(scene, findings, hypotheses, rules)

    (run_dir / "scene.json").write_text(
        json.dumps(scene, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "findings.json").write_text(
        json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "ledger.json").write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "answer.txt").write_text(compose_answer(rendered, questions), encoding="utf-8")

    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    raw.setdefault("calls", []).append({
        "pass": "phases-4-6",
        "prompt": prompt,
        "payload": payload,
        "latency_ms": latency_ms,
    })
    raw["skill_phases"] = {str(number): phases[number]["title"] for number in PHASES_IN_PROMPT}
    raw["ledger"] = ledger
    raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    metrics = case_metrics(case, findings, ledger, report, state,
                            round(time.monotonic() - started, 1),
                            int(meta.get("calls") or 0) + 1)
    metrics["questions"] = len(questions["discriminators"]) + len(questions["catalogue"])
    return metrics


def aggregate_attempts(attempts):
    """Метрики кейса по нескольким попыткам."""
    def mean(values):
        values = [v for v in values if v is not None]
        return round(sum(values) / len(values), 3) if values else None

    return {
        "protocol_violations": sum(a["protocol_violations"] for a in attempts),
        "protocol_errors": [error for a in attempts for error in a["protocol_errors"]],
        "citation_completeness": mean([a["citation_completeness"] for a in attempts]),
        "finding_recall": mean([a["finding_recall"] for a in attempts]),
        "extra_findings": mean([a["extra_findings"] for a in attempts]),
        "extra_finding_ids": sorted({fid for a in attempts for fid in a["extra_finding_ids"]}),
        "missing_finding_ids": sorted({fid for a in attempts for fid in a["missing_finding_ids"]}),
        "fired_finding_ids": sorted({fid for a in attempts for fid in a["fired_finding_ids"]}),
        "refutation_coverage": mean([a["refutation_coverage"] for a in attempts]),
        "claims_without_refutation": sum(a["claims_without_refutation"] for a in attempts),
        "discriminator_coverage": mean([a["discriminator_coverage"] for a in attempts]),
        "hypotheses_without_discriminator": sum(a["hypotheses_without_discriminator"] for a in attempts),
        "claims": mean([a["claims"] for a in attempts]),
        "hypotheses": mean([a["hypotheses"] for a in attempts]),
        "verdict": attempts[0]["verdict"],
        "expected_verdict": attempts[0]["expected_verdict"],
        "refusal_accuracy": mean([a["refusal_accuracy"] for a in attempts]),
        "latency_s": mean([a["latency_s"] for a in attempts]),
        "calls": mean([a["calls"] for a in attempts]),
    }


def aggregate_records(records):
    """Сводка по кейсам."""
    done = [r for r in records if r["status"] in ("ok", "partial")]
    failed = [r for r in records if r["status"] == "error"]

    def mean(values):
        values = [v for v in values if v is not None]
        return round(sum(values) / len(values), 3) if values else None

    return {
        "cases": len(records),
        "processed": len(done),
        "failed": len(failed),
        "failed_attempts": sum(len(r.get("errors") or []) for r in records),
        "protocol_violations": sum(r["metrics"]["protocol_violations"] for r in done),
        "citation_completeness": mean([r["metrics"]["citation_completeness"] for r in done]),
        "finding_recall": mean([r["metrics"]["finding_recall"] for r in done]),
        "extra_findings": sum(r["metrics"]["extra_findings"] for r in done),
        "refutation_coverage": mean([r["metrics"]["refutation_coverage"] for r in done]),
        "claims_without_refutation": sum(r["metrics"]["claims_without_refutation"] for r in done),
        "discriminator_coverage": mean([r["metrics"]["discriminator_coverage"] for r in done]),
        "hypotheses_without_discriminator": sum(r["metrics"]["hypotheses_without_discriminator"] for r in done),
        "refusal_accuracy": mean([r["metrics"]["refusal_accuracy"] for r in done]),
        "latency_s": mean([r["metrics"]["latency_s"] for r in done]),
        "calls": mean([r["metrics"]["calls"] for r in done]),
    }


def build_plan(cases, skill, root=ROOT):
    """План прогона: что именно будет сделано и что ожидается."""
    return {
        "skill": skill["path"],
        "phases": [
            {"number": number, "title": skill["phases"][number]["title"]}
            for number in skill["order"]
        ],
        "phases_in_prompt": list(PHASES_IN_PROMPT),
        "cases": [
            {
                "id": case["id"],
                "image": case["image"],
                "image_exists": (Path(root) / case["image"]).exists(),
                "packs": case["packs"],
                "expected_finding_ids": case["expect"].get("finding_ids", []),
                "expected_verdict": case["expect"].get("verdict"),
                "note": case.get("note", ""),
            }
            for case in cases
        ],
    }


def print_plan(plan):
    print(f"скилл: {plan['skill']}")
    print("фазы скилла: " + ", ".join(f"{p['number']}. {p['title']}" for p in plan["phases"]))
    print(f"в промпт идут фазы: {', '.join(str(n) for n in plan['phases_in_prompt'])}")
    print(f"кейсов в плане: {len(plan['cases'])}")
    for case in plan["cases"]:
        mark = "✓" if case["image_exists"] else "✗"
        print(f"  {mark} {case['id']}: {case['image']}, паки {', '.join(case['packs'])}; "
              f"ожидаются улики {case['expected_finding_ids'] or '—'}, "
              f"вердикт {case['expected_verdict'] or '—'}")
        if case["note"]:
            print(f"      {case['note']}")


def print_summary(summary):
    print("\n" + "=" * 64)
    print(f"кейсов: {summary['cases']}, обработано: {summary['processed']}, "
          f"провалено: {summary['failed']}")
    print(f"нарушений протокола: {summary['protocol_violations']}")
    print(f"полнота цитат: {_fmt(summary['citation_completeness'])}")
    print(f"recall улик: {_fmt(summary['finding_recall'])}, лишних улик: {summary['extra_findings']}")
    print(f"покрытие отрицаниями: {_fmt(summary['refutation_coverage'])}, "
          f"утверждений без отрицания: {summary['claims_without_refutation']}")
    print(f"покрытие дискриминаторами: {_fmt(summary['discriminator_coverage'])}, "
          f"версий без дискриминатора: {summary['hypotheses_without_discriminator']}")
    print(f"верность отказа: {_fmt(summary['refusal_accuracy'])}")
    print(f"время: {_fmt(summary['latency_s'])} с, вызовов модели: {_fmt(summary['calls'])}")


def _fmt(value):
    return "—" if value is None else f"{value:.3f}"


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="run_skill",
        description="Прогнать скилл detective по кейсам и посчитать метрики.",
    )
    parser.add_argument("--cases", default=str(CASES_PATH), help="манифест кейсов")
    parser.add_argument("--limit", type=int, default=0, help="сколько кейсов взять")
    parser.add_argument("--repeat", type=int, default=1, help="сколько раз прогнать каждый кейс")
    parser.add_argument("--out", default=str(OUT_DIR), help="каталог артефактов")
    parser.add_argument("--model", default="MiniMax-M3")
    parser.add_argument("--persona", default="doyle", choices=["doyle", "plain", "forensic"])
    parser.add_argument("--offline", action="store_true",
                        help="не звать модель: проверить манифест и напечатать план")
    parser.add_argument("--json", action="store_true", help="печатать сводку в JSON")
    args = parser.parse_args(argv)

    try:
        skill = load_skill()
        cases = load_cases(args.cases)
    except HarnessError as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 2

    if args.limit:
        cases = cases[:args.limit]

    if args.offline:
        plan = build_plan(cases, skill)
        if args.json:
            print(json.dumps(plan, ensure_ascii=False, indent=2))
        else:
            print_plan(plan)
        return 0

    try:
        perception = MiniMaxPerception(model=args.model)
    except PerceptionError as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        print("ключ MiniMax нужен для фаз 1–2 и 4–6; без него доступен только --offline",
              file=sys.stderr)
        return 2

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for index, case in enumerate(cases, start=1):
        rules = load_rules(case["packs"])
        attempts = []
        errors = []
        for attempt in range(1, max(1, args.repeat) + 1):
            suffix = "" if args.repeat == 1 else f".{attempt}"
            run_dir = out_dir / f"{case['id']}{suffix}"
            try:
                attempts.append(run_case(case, skill["phases"], rules, perception, run_dir,
                                         persona=args.persona))
            except Exception as exc:  # noqa: BLE001 — один кадр не должен ронять прогон
                errors.append(str(exc))
        if not attempts:
            records.append({
                "id": case["id"],
                "image": case["image"],
                "packs": case["packs"],
                "status": "error",
                "errors": errors,
                "error": errors[0] if errors else "неизвестная ошибка",
                "metrics": {},
            })
            print(f"[{index}/{len(cases)}] ✗ {case['id']}: {records[-1]['error']}")
            continue
        metrics = aggregate_attempts(attempts)
        record = {
            "id": case["id"],
            "image": case["image"],
            "packs": case["packs"],
            "status": "ok" if not errors else "partial",
            "errors": errors,
            "error": "; ".join(errors) if errors else None,
            "note": case.get("note", ""),
            "run_dir": str(out_dir / f"{case['id']}{'' if args.repeat == 1 else '.1'}"),
            "metrics": metrics,
            "attempts": attempts,
        }
        records.append(record)
        verdict = metrics["verdict"]
        expected = metrics["expected_verdict"] or "—"
        mark = "✓" if metrics["protocol_violations"] == 0 else "✗"
        print(f"[{index}/{len(cases)}] {mark} {case['id']}: вердикт {verdict} (ожидался {expected}), "
              f"улики {metrics['fired_finding_ids'] or '—'}, "
              f"нарушений протокола: {metrics['protocol_violations']}, "
              f"без отрицания: {metrics['claims_without_refutation']}, "
              f"без дискриминатора: {metrics['hypotheses_without_discriminator']}")

    summary = aggregate_records(records)
    payload = {
        "skill": skill["path"],
        "model": args.model,
        "cases_path": str(args.cases),
        "summary": summary,
        "results": records,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_summary(summary)

    if summary["failed"] or summary["failed_attempts"]:
        return 3
    if summary["protocol_violations"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
