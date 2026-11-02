"""Puzzle pipeline: series of frames -> diff -> evidence -> ranked suspects.

This is the entertainment face of the engine, and it runs on the same
protocol as everything else: differences become evidence, evidence becomes
claims, claims become competing hypotheses with a kill-log.

The suspect link is explicit, not vibes: a rule carries trait tags, a suspect
carries traits, and a hypothesis scores only where they meet.
"""

import json
from pathlib import Path

from .diff import diff_scenes, attach_changes
from .ledger import score_hypotheses
from .rules import evaluate_all


def load_puzzle(path):
    puzzle = json.loads(Path(path).read_text(encoding="utf-8"))
    base = Path(path).parent
    scenes = []
    for entry in puzzle.get("scenes", []):
        graph_path = base / entry["graph"] if not Path(entry["graph"]).is_absolute() else Path(entry["graph"])
        scene = json.loads(graph_path.read_text(encoding="utf-8"))
        scene.setdefault("meta", {})["image_id"] = entry.get("id")
        scenes.append(scene)
    return puzzle, scenes


def compute_changes(scenes):
    changes = []
    for index in range(len(scenes) - 1):
        pair = diff_scenes(scenes[index], scenes[index + 1])
        for change in pair:
            change["id"] = f"c{len(changes) + 1}"
            change["between"] = [index, index + 1]
        changes.extend(pair)
    return changes


def build_claims(findings):
    claims = []
    for finding in findings:
        interpretive = finding.get("layer") == "interpretive"
        ceiling = finding["confidence_ceiling"]
        confidence = min(finding["confidence_prior"], ceiling)
        if interpretive:
            confidence = min(confidence, 0.4)
        claim = {
            "claim_id": f"C-{finding['rule_id']}",
            "kind": "interpretation" if interpretive else "inference",
            "text": finding["inference"],
            "support": [{"finding_id": finding["finding_id"]}],
            "confidence": confidence,
            "provisional": finding["provisional"],
            "confounds": finding.get("confounds", []),
            "falsification": finding.get("falsification", {}).get("physical_test"),
        }
        if interpretive:
            claim["speculative"] = True
        claims.append(claim)
    return claims


def score_suspects(suspects, findings):
    """Trait tags are the only bridge between an observation and a suspect."""
    scored = []
    for suspect in suspects:
        traits = set(suspect.get("traits", []))
        matched = []
        for finding in findings:
            overlap = traits & set(finding.get("tags", []))
            if overlap:
                matched.append({
                    "finding_id": finding["finding_id"],
                    "rule_id": finding["rule_id"],
                    "tags": sorted(overlap),
                    "weight": finding["confidence_prior"],
                })
        score = sum(m["weight"] for m in matched)
        scored.append({
            "suspect_id": suspect["id"],
            "label": suspect.get("label", suspect["id"]),
            "score": round(score, 3),
            "matches": matched,
            "explanation": "; ".join(
                f"{m['rule_id']} → {', '.join(m['tags'])}" for m in matched
            ) or "нет совпадений по меткам",
        })
    scored.sort(key=lambda s: s["score"], reverse=True)
    return scored


def solve(puzzle, scenes, rules, mode="detective"):
    changes = compute_changes(scenes)
    merged = attach_changes(scenes[-1], changes)
    findings = evaluate_all(rules, merged)
    claims = build_claims(findings)
    suspects = puzzle.get("suspects", [])

    hypotheses = []
    for suspect in suspects:
        matched = [
            f for f in findings
            if set(suspect.get("traits", [])) & set(f.get("tags", []))
        ]
        hypothesis_claims = [f"C-{f['rule_id']}" for f in matched]
        hypotheses.append({
            "hypothesis_id": f"H-{suspect['id']}",
            "text": f"След ведёт к подозреваемому: {suspect.get('label', suspect['id'])}",
            "claims": hypothesis_claims,
            "status": "open",
            "kill_log": [],
            "suspect_id": suspect["id"],
        })

    scored_hypotheses = score_hypotheses(findings, claims, hypotheses)
    scored_suspects = score_suspects(suspects, findings)

    answer = puzzle.get("answer", {})
    result = {
        "puzzle_id": puzzle.get("puzzle_id"),
        "title": puzzle.get("title"),
        "changes": changes,
        "findings": findings,
        "claims": claims,
        "hypotheses": scored_hypotheses,
        "suspects": scored_suspects,
        "answer": answer,
    }
    if answer.get("suspect"):
        expected = answer["suspect"]
        top = scored_suspects[0]["suspect_id"] if scored_suspects else None
        result["evaluation"] = {
            "expected": expected,
            "predicted": top,
            "correct": top == expected,
        }
    return result
