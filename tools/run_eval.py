#!/usr/bin/env python3
"""Benchmark harness: quality metrics of the engine, not of the prose.

Metrics follow docs/PROTOCOL.md:
  citation completeness — доля утверждений с разрешающимися ссылками
  Brier               — калибровка: (уверенность − истина)²
  refusal accuracy    — доля верно выбранных отказов
  hypothesis top-k    — ранг верной версии
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from elementarno.ledger import validate, verdict as decide_verdict  # noqa: E402
from elementarno.puzzle import build_claims, load_puzzle, solve  # noqa: E402
from elementarno.rules import evaluate_all, load_packs  # noqa: E402
from elementarno.scene import validate_scene  # noqa: E402

RULES_DIR = ROOT / "rules"


def discover_benchmarks(root):
    root = Path(root)
    if not root.exists():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir() and (p / "cases.json").exists())


def _rules_for(packs):
    rules = load_packs(RULES_DIR)
    if not packs:
        return rules
    wanted = set(packs)
    return [rule for rule in rules if rule.pack in wanted]


def run_benchmark(name, root="eval/benchmarks"):
    base = Path(root) / name
    spec = json.loads((base / "cases.json").read_text(encoding="utf-8"))
    case_results = []
    brier_values = []
    citation_values = []
    refusal_hits = 0
    refusal_total = 0
    top1_hits = 0
    top3_hits = 0
    suspect_total = 0

    for case in spec.get("cases", []):
        expect = case.get("expect", {})
        packs = case.get("packs")
        details = []

        if "puzzle" in case:
            puzzle, scenes = load_puzzle(base / case["puzzle"])
            result = solve(puzzle, scenes, _rules_for(packs), mode="detective")
            findings = result["findings"]
            claims = result["claims"]
            hypotheses = result["hypotheses"]
            suspects = result["suspects"]
            state = "sufficient_evidence" if findings else "insufficient_evidence"
        else:
            scene = json.loads((base / case["scene"]).read_text(encoding="utf-8"))
            problems = validate_scene(scene)
            if problems:
                details.append(f"сцена невалидна: {problems[0]}")
            findings = evaluate_all(_rules_for(packs), scene)
            claims = build_claims(findings)
            hypotheses = []
            suspects = []
            state = decide_verdict(findings, claims, 1, "detective")

        found_ids = {f["finding_id"] for f in findings}
        expected_ids = set(expect.get("finding_ids", []))
        missing = expected_ids - found_ids
        if missing:
            details.append(f"не сработали правила: {sorted(missing)}")

        if expect.get("verdict") and expect["verdict"] != state:
            details.append(f"вердикт {state} вместо {expect['verdict']}")

        if "suspect" in expect:
            suspect_total += 1
            ranking = [s["suspect_id"] for s in suspects]
            if expect["suspect"] in ranking:
                rank = ranking.index(expect["suspect"]) + 1
                if rank == 1:
                    top1_hits += 1
                if rank <= 3:
                    top3_hits += 1
            else:
                details.append("верной версии нет в рейтинге")

        if state == "insufficient_evidence" or expect.get("verdict") == "insufficient_evidence":
            refusal_total += 1
            if state == expect.get("verdict", state):
                refusal_hits += 1

        report = validate(findings, {"claims": claims, "hypotheses": hypotheses})
        citation_values.append(report["citation_completeness"])
        for claim in claims:
            correct = 1.0 if any(
                s["finding_id"] in expected_ids for s in claim.get("support", [])
            ) else 0.0
            brier_values.append((claim["confidence"] - correct) ** 2)

        case_results.append({
            "id": case["id"],
            "passed": not details,
            "detail": "; ".join(details) or "ок",
            "findings": sorted(found_ids),
            "verdict": state,
        })

    failed = sum(1 for c in case_results if not c["passed"])
    return {
        "benchmark": name,
        "cases": len(case_results),
        "failed_cases": failed,
        "citation_completeness": sum(citation_values) / len(citation_values) if citation_values else 0.0,
        "brier": sum(brier_values) / len(brier_values) if brier_values else 0.0,
        "refusal_accuracy": refusal_hits / refusal_total if refusal_total else None,
        "suspect_top1": top1_hits / suspect_total if suspect_total else None,
        "suspect_top3": top3_hits / suspect_total if suspect_total else None,
        "case_results": case_results,
    }


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    root = "eval/benchmarks"
    only = None
    if argv:
        root = argv[0]
        if len(argv) > 1:
            only = argv[1]
    names = [only] if only else discover_benchmarks(root)
    failures = 0
    for name in names:
        report = run_benchmark(name, root)
        failures += report["failed_cases"]
        print(f"[{name}] случаев: {report['cases']}, провалено: {report['failed_cases']}, "
              f"цитаты: {report['citation_completeness']:.2f}, Brier: {report['brier']:.3f}")
        for case in report["case_results"]:
            mark = "✓" if case["passed"] else "✗"
            print(f"   {mark} {case['id']}: {case['detail']}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
