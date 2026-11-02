import unittest

from elementarno.dialog import Session, merge_scenes
from elementarno.puzzle import build_claims
from elementarno.rules import evaluate_all
from elementarno.nextshot import (hypothesis_tags, information_gain, kind_tags_from_rules,
                                  rank_questions)
from elementarno.reasoning import sanitize_claims, sanitize_hypotheses
from elementarno.rules import load_packs

RULES = load_packs("rules")


def make_finding(finding_id, rule_id="ABS-001", ceiling=0.5, provisional=True, step="activity", tags=None):
    return {
        "finding_id": finding_id,
        "rule_id": rule_id,
        "rule_version": 1,
        "pack": "absence",
        "title": "Пылевой контур",
        "layer": "epistemic",
        "step": step,
        "inference": "контур",
        "anchors": ["r1"],
        "tags": tags if tags is not None else ["removal"],
        "sources": [{"ref": "test", "note": "", "verified": False}],
        "confounds": ["конфаунд"],
        "exceptions": ["исключение"],
        "falsification": {"refuted_by": [], "physical_test": "посветить"},
        "confidence_prior": 0.6,
        "confidence_ceiling": ceiling,
        "provisional": provisional,
    }


class ReasoningTests(unittest.TestCase):
    def test_unknown_finding_is_dropped(self):
        claims, dropped = sanitize_claims([
            {"claim_id": "C-1", "kind": "observation", "text": "что-то",
             "support": [{"finding_id": "F-NOPE"}], "confidence": 0.3, "step": "action"},
        ], [make_finding("F-ABS-001")])
        self.assertEqual(claims, [])
        self.assertEqual(dropped["unknown_finding"], 1)

    def test_confidence_is_capped_by_ceiling(self):
        claims, _ = sanitize_claims([
            {"claim_id": "C-1", "kind": "observation", "text": "что-то",
             "support": [{"finding_id": "F-ABS-001"}], "confidence": 0.95, "step": "activity"},
        ], [make_finding("F-ABS-001", ceiling=0.5)])
        self.assertEqual(claims[0]["confidence"], 0.5)

    def test_draft_rule_caps_at_half(self):
        claims, _ = sanitize_claims([
            {"claim_id": "C-1", "kind": "observation", "text": "что-то",
             "support": [{"finding_id": "F-ABS-001"}], "confidence": 0.9, "step": "activity"},
        ], [make_finding("F-ABS-001", ceiling=0.85, provisional=True)])
        self.assertEqual(claims[0]["confidence"], 0.5)
        self.assertTrue(claims[0]["provisional"])

    def test_accusatory_claim_is_dropped(self):
        claims, dropped = sanitize_claims([
            {"claim_id": "C-1", "kind": "hypothesis", "text": "Дворецкий виновен",
             "support": [{"finding_id": "F-ABS-001"}], "confidence": 0.4, "step": "action",
             "falsification": "проверить"},
        ], [make_finding("F-ABS-001")])
        self.assertEqual(claims, [])
        self.assertEqual(dropped["accusatory_framing"], 1)

    def test_personality_claim_is_dropped(self):
        claims, dropped = sanitize_claims([
            {"claim_id": "C-1", "kind": "inference", "text": "по фото виден характер",
             "support": [{"finding_id": "F-ABS-001"}], "confidence": 0.3, "step": "activity"},
        ], [make_finding("F-ABS-001")])
        self.assertEqual(claims, [])
        self.assertEqual(dropped["personality_inference"], 1)

    def test_ladder_break_is_dropped(self):
        claims, dropped = sanitize_claims([
            {"claim_id": "C-1", "kind": "inference", "text": "это кухня",
             "support": [{"finding_id": "F-ABS-001"}], "confidence": 0.3, "step": "scene"},
        ], [make_finding("F-ABS-001", step="activity")])
        self.assertEqual(claims, [])
        self.assertEqual(dropped["ladder_break"], 1)

    def test_interpretation_is_capped_and_marked(self):
        claims, _ = sanitize_claims([
            {"claim_id": "C-1", "kind": "interpretation", "text": "книга значит что-то",
             "support": [{"finding_id": "F-ABS-001"}], "confidence": 0.9, "step": "activity"},
        ], [make_finding("F-ABS-001", ceiling=0.85)])
        self.assertEqual(claims[0]["confidence"], 0.4)
        self.assertTrue(claims[0]["speculative"])

    def test_hypothesis_without_falsification_is_dropped(self):
        claims, dropped = sanitize_claims([
            {"claim_id": "C-1", "kind": "hypothesis", "text": "здесь был кто-то",
             "support": [{"finding_id": "F-ABS-001"}], "confidence": 0.4, "step": "presence"},
        ], [make_finding("F-ABS-001")])
        self.assertEqual(claims, [])
        self.assertEqual(dropped["hypothesis_without_falsification"], 1)

    def test_rejected_hypothesis_needs_kill_log(self):
        kept, dropped = sanitize_hypotheses([
            {"hypothesis_id": "H-1", "text": "версия", "claims": ["C-1"], "status": "rejected"},
        ], [{"claim_id": "C-1"}])
        self.assertEqual(kept, [])
        self.assertEqual(dropped["rejected_without_kill_log"], 1)

    def test_valid_ledger_survives(self):
        claims, _ = sanitize_claims([
            {"claim_id": "C-1", "kind": "inference", "text": "предмет убрали недавно",
             "support": [{"finding_id": "F-ABS-001"}], "confidence": 0.4, "step": "activity",
             "falsification": "посветить"},
        ], [make_finding("F-ABS-001")])
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["support"][0]["finding_id"], "F-ABS-001")


class NextshotTests(unittest.TestCase):
    def setUp(self):
        self.findings = [
            make_finding("F-PUZ-004", rule_id="PUZ-004", step="presence", tags=["muddy_boots"]),
            make_finding("F-PRES-001", rule_id="PRES-001", step="presence", tags=["two_people"]),
        ]
        self.hypotheses = [
            {"hypothesis_id": "H-1", "text": "Садовник", "log_odds": 1.2, "support_findings": ["F-PUZ-004"]},
            {"hypothesis_id": "H-2", "text": "Горничная", "log_odds": 0.3, "support_findings": ["F-PRES-001"]},
        ]

    def test_kind_tags_are_derived_from_rules(self):
        mapping = kind_tags_from_rules(RULES)
        self.assertIn("dust_outline", mapping)
        self.assertIn("removal", mapping["dust_outline"])

    def test_hypothesis_tags_index(self):
        index = hypothesis_tags(self.hypotheses, self.findings)
        self.assertEqual(index["H-1"], {"muddy_boots"})

    def test_information_gain_is_positive_for_distinguishable_versions(self):
        index = hypothesis_tags(self.hypotheses, self.findings)
        kinds = kind_tags_from_rules(RULES)
        gain = information_gain(self.hypotheses, "mud_footprint", index, kinds)
        self.assertGreater(gain, 0.0)

    def test_single_hypothesis_has_no_information_gain(self):
        index = hypothesis_tags(self.hypotheses[:1], self.findings)
        kinds = kind_tags_from_rules(RULES)
        self.assertEqual(information_gain(self.hypotheses[:1], "mud_footprint", index, kinds), 0.0)

    def test_ranked_questions_have_reasons(self):
        index = hypothesis_tags(self.hypotheses, self.findings)
        kinds = kind_tags_from_rules(RULES)
        questions = rank_questions(self.hypotheses, index, kinds, limit=3)
        self.assertEqual(len(questions), 3)
        for question in questions:
            self.assertTrue(question["question"])
            self.assertTrue(question["why"])
            self.assertIn("eig", question)

    def test_questions_are_sorted_by_value(self):
        index = hypothesis_tags(self.hypotheses, self.findings)
        kinds = kind_tags_from_rules(RULES)
        questions = rank_questions(self.hypotheses, index, kinds, limit=5)
        values = [q["eig"] for q in questions]
        self.assertEqual(values, sorted(values, reverse=True))


class SessionTests(unittest.TestCase):
    def scene(self, regions=None, objects=None):
        return {
            "surfaces": [{"id": "s1", "name": "floor"}],
            "objects": objects or [],
            "regions": regions or [],
            "observations": [],
        }

    def test_merge_keeps_earlier_regions(self):
        base = self.scene(regions=[{"id": "r1", "kind": "dust_outline", "bbox": [0, 0, 1, 1]}])
        addition = self.scene(regions=[{"id": "r2", "kind": "footprint", "bbox": [0.2, 0.2, 0.3, 0.3]}])
        merged = merge_scenes(base, addition)
        kinds = {r["kind"] for r in merged["regions"]}
        self.assertEqual(kinds, {"dust_outline", "footprint"})

    def test_session_accumulates_scenes_and_asks_questions(self):
        session = Session(RULES, [{"id": "p1", "label": "Садовник", "traits": ["muddy_boots"]},
                                  {"id": "p2", "label": "Горничная", "traits": ["wet_boots"]}])
        session.add_scene(self.scene(regions=[{"id": "r1", "kind": "mud_footprint", "bbox": [0.1, 0.1, 0.2, 0.2]}]))
        session.add_scene(self.scene(regions=[{"id": "r2", "kind": "water_line", "bbox": [0.3, 0.3, 0.4, 0.4]}]))
        result = session.analyze()
        self.assertEqual(len(session.rounds), 2)
        self.assertEqual(result["verdict"], "sufficient_evidence")
        self.assertTrue(result["questions"])
        self.assertTrue(all("question" in q for q in result["questions"]))

    def test_session_without_evidence_refuses(self):
        session = Session(RULES, [])
        session.add_scene(self.scene())
        result = session.analyze()
        self.assertEqual(result["verdict"], "insufficient_evidence")

    def test_session_state_roundtrip(self):
        import json
        import tempfile
        from pathlib import Path

        session = Session(RULES, [])
        session.add_scene(self.scene(regions=[{"id": "r1", "kind": "mud_footprint"}]))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.json"
            session.save(path)
            restored = Session.load(path, RULES)
            self.assertEqual(len(restored.rounds), 1)
            self.assertEqual(json.loads(path.read_text())["rounds"], restored.rounds)


if __name__ == "__main__":
    unittest.main()


class AuditFixTests(unittest.TestCase):
    """Проверки исправлений по итогам аудита (docs/AUDIT-2026-11.md)."""

    def test_audit_mode_differs_from_detective(self):
        from elementarno.render import render

        scene = {"surfaces": [{"id": "s1", "name": "table", "dust_present": True}],
                 "objects": [], "regions": [{"id": "r1", "kind": "dust_outline"}], "observations": []}
        findings = evaluate_all(RULES, scene)
        claims = build_claims(findings)
        audit = render("audit", findings, claims, [], "sufficient_evidence", "doyle")
        detective = render("detective", findings, claims, [], "sufficient_evidence", "doyle")
        self.assertNotEqual(audit, detective)
        self.assertNotIn("Уотсон", audit)

    def test_hypothesis_without_evidence_cannot_lead(self):
        from elementarno.ledger import score_hypotheses

        finding = make_finding("F-X", ceiling=0.5)
        finding["confidence_prior"] = 0.4
        claims = [{"claim_id": "C-1", "kind": "inference", "text": "x",
                   "support": [{"finding_id": "F-X"}], "confidence": 0.4, "step": "action"}]
        hypotheses = [{"hypothesis_id": "H-1", "text": "с уликами", "claims": ["C-1"], "status": "open"},
                      {"hypothesis_id": "H-2", "text": "без улик", "claims": [], "status": "open"}]
        scored = score_hypotheses([finding], claims, hypotheses)
        self.assertEqual(scored[0]["hypothesis_id"], "H-1")
        self.assertIsNone(scored[1]["log_odds"])

    def test_ladder_allows_only_one_rung_jump(self):
        finding = make_finding("F-1", step="scene")
        claims, dropped = sanitize_claims([
            {"claim_id": "C-1", "kind": "inference", "text": "здесь кто-то был",
             "support": [{"finding_id": "F-1"}], "confidence": 0.3, "step": "presence"},
        ], [finding])
        self.assertEqual(claims, [])
        self.assertEqual(dropped["ladder_break"], 1)

    def test_ladder_allows_adjacent_rung(self):
        finding = make_finding("F-1", step="activity")
        claims, dropped = sanitize_claims([
            {"claim_id": "C-1", "kind": "inference", "text": "здесь кто-то был",
             "support": [{"finding_id": "F-1"}], "confidence": 0.3, "step": "presence"},
        ], [finding])
        self.assertEqual(len(claims), 1)
        self.assertNotIn("ladder_break", dropped)

    def test_personality_check_is_context_aware(self):
        from elementarno.ledger import mentions_personality

        self.assertTrue(mentions_personality("по фото виден характер"))
        self.assertFalse(mentions_personality("изменился характер пыли"))
        self.assertFalse(mentions_personality("характер следа изменился"))

    def test_grounding_precision_checks_anchors(self):
        from elementarno.ledger import grounding_precision

        scene = {"surfaces": [], "objects": [], "regions": [{"id": "r1"}]}
        finding = make_finding("F-1")
        finding["anchors"] = ["r1"]
        claims = [{"claim_id": "C-1", "support": [{"finding_id": "F-1"}]}]
        self.assertEqual(grounding_precision(scene, claims, [finding]), 1.0)
        finding["anchors"] = ["r_missing"]
        self.assertEqual(grounding_precision(scene, claims, [finding]), 0.0)

    def test_shadow_unknown_is_not_a_direction(self):
        scene = {
            "surfaces": [{"id": "s1", "name": "floor"}],
            "objects": [{"id": "o1", "shadow_dir": "unknown"}, {"id": "o2", "shadow_dir": "west"}],
            "regions": [], "observations": [],
        }
        findings = evaluate_all(RULES, scene)
        self.assertNotIn("PHY-003", {f["rule_id"] for f in findings})
