import unittest

from tools.elementarno.answer import answer, classify
from tools.elementarno.facts import enrich, facts, object_features
from tools.elementarno.paths import PathError, parse_path, resolve
from tools.elementarno.rules import evaluate_all, load_packs

SCENE = {
    "surfaces": [{"id": "s1", "name": "table", "material": "wood"}],
    "objects": [
        {"id": "o1", "category": "person", "visible": True},
        {"id": "o2", "category": "mug", "material": "ceramic", "fill_level": 0.3, "on": "s1"},
        {"id": "o3", "category": "lighter", "material": "metal"},
        {"id": "o4", "category": "tobacco_pouch", "material": "plastic"},
        {"id": "o5", "category": "laptop", "material": "metal", "state": "closed"},
        {"id": "o6", "category": "phone_stand", "material": "metal"},
        {"id": "o7", "category": "open_container", "material": "metal"},
        {"id": "o8", "category": "flowerpot", "material": "plastic"},
    ],
    "regions": [{"id": "r1", "kind": "food_remains", "note": "крошки"}],
    "observations": [{"id": "x1", "about": "o6", "feature": "empty", "value": "подставка без телефона",
                      "confidence": 0.9}],
}


class PathsTest(unittest.TestCase):
    def test_comparison_filter(self):
        scene = {"objects": [{"id": "a", "fill_level": 0.3}, {"id": "b", "fill_level": 0.9}]}
        found = resolve(scene, "objects[fill_level>0][fill_level<0.6]")
        self.assertEqual([i["id"] for i in found], ["a"])

    def test_membership_filter_for_feature_lists(self):
        scene = {"objects": [{"id": "a", "features": ["drinkware", "full"]}, {"id": "b", "features": ["tool"]}]}
        found = resolve(scene, "objects[features=drinkware]")
        self.assertEqual([i["id"] for i in found], ["a"])

    def test_inequality_filter(self):
        scene = {"objects": [{"id": "a", "state": "closed"}, {"id": "b", "state": "open"}]}
        found = resolve(scene, "objects[state!=closed]")
        self.assertEqual([i["id"] for i in found], ["b"])

    def test_parse_path_reports_operators(self):
        collection, filters, field = parse_path("objects[fill_level>=0.5]")
        self.assertEqual(collection, "objects")
        self.assertEqual(filters, [("fill_level", ">=", "0.5")])
        self.assertIsNone(field)

    def test_malformed_path_raises(self):
        with self.assertRaises(PathError):
            parse_path("objects[]")


class FactsTest(unittest.TestCase):
    def test_features_do_not_match_inside_words(self):
        self.assertNotIn("writing", object_features({"category": "open_container"}))
        self.assertNotIn("cookware", object_features({"category": "flowerpot"}))
        self.assertIn("plant", object_features({"category": "flowerpot"}))

    def test_lexicon_covers_expected_categories(self):
        self.assertIn("drinkware", object_features({"category": "coffee mug"}))
        self.assertIn("ignition", object_features({"category": "matchbox"}))
        self.assertIn("tobacco", object_features({"category": "tobacco_pouch"}))

    def test_fill_level_becomes_state(self):
        features = object_features({"category": "mug", "fill_level": 0.3})
        self.assertIn("partially_filled", features)
        self.assertNotIn("full", features)

    def test_enrich_adds_features_and_observation_states(self):
        scene = enrich({"objects": [dict(o) for o in SCENE["objects"]], "observations": SCENE["observations"]})
        stand = next(o for o in scene["objects"] if o["id"] == "o6")
        self.assertIn("empty", stand["features"])

    def test_facts_are_numbered_and_carry_basis(self):
        fs = facts(enrich(SCENE))
        self.assertTrue(fs)
        self.assertEqual(fs[0]["fact_id"], "FACT-001")
        for fact in fs:
            self.assertIn("basis", fact)
            self.assertIn("confidence", fact)

    def test_empty_holder_produces_absence_fact(self):
        fs = facts(enrich(SCENE))
        self.assertTrue(any(f["kind"] == "absence" for f in fs))


class GeneralPackTest(unittest.TestCase):
    def setUp(self):
        self.rules = [r for r in load_packs("rules") if r.pack in ("general", "core", "presence", "home")]

    def test_connections_from_facts_are_found(self):
        scene = enrich(SCENE)
        found = {f["rule_id"]: f for f in evaluate_all(self.rules, scene)}
        self.assertIn("GEN-001", found)
        self.assertIn("GEN-003", found)
        self.assertIn("GEN-005", found)
        self.assertEqual(found["GEN-003"]["anchors"], ["o4", "o3"])

    def test_general_rules_have_confounds_and_sources(self):
        for rule in load_packs("rules"):
            if rule.pack != "general":
                continue
            self.assertTrue(rule.confounds)
            self.assertTrue(rule.sources)
            self.assertIn(rule.review_status, ("draft", "reviewed"))

    def test_general_rules_stay_under_the_black_draft_ceiling(self):
        for rule in load_packs("rules"):
            if rule.pack == "general":
                self.assertLessEqual(rule.ceiling, 0.5)


class CommandsAgreeTest(unittest.TestCase):
    """Команды обязаны считать одни и те же улики: обогащение — в одном месте."""

    def setUp(self):
        import json
        import tempfile
        from pathlib import Path

        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "scene.json"
        self.path.write_text(json.dumps(SCENE), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_findings_and_verify_see_the_same_general_findings(self):
        import json
        from contextlib import redirect_stdout
        from io import StringIO

        from tools.elementarno.cli import main

        out = StringIO()
        with redirect_stdout(out):
            main(["--rules", "rules", "findings", str(self.path), "--pack", "general", "--json"])
        findings = json.loads(out.getvalue())
        ids = {f["finding_id"] for f in findings}
        self.assertIn("F-GEN-001", ids)

        out = StringIO()
        with redirect_stdout(out):
            code = main(["--rules", "rules", "verify", str(self.path),
                         "--pack", "general", "--json"])
        report = json.loads(out.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(report["errors"], [])


class AnswerTest(unittest.TestCase):
    def setUp(self):
        self.scene = enrich(SCENE)
        self.findings = evaluate_all([r for r in load_packs("rules") if r.pack == "general"], self.scene)

    def test_classify_routes_questions(self):
        self.assertEqual(classify("что здесь происходило?"), "activity")
        self.assertEqual(classify("кто был в кадре?"), "presence")
        self.assertEqual(classify("что проверить дальше?"), "check")
        self.assertEqual(classify("когда это было?"), "when")
        self.assertEqual(classify("а погода?"), "default")

    def test_activity_answer_without_claims_refuses(self):
        result = answer("что здесь происходило", self.scene, self.findings, [], [])
        self.assertIn("нельзя сказать", result["answer"])
        self.assertEqual(result["uncertainty"], 1.0)

    def test_activity_answer_uses_claim(self):
        claim = {
            "claim_id": "C-1", "kind": "inference",
            "text": "В сцене кружка с напитком", "support": [{"finding_id": "F-GEN-001"}],
            "confidence": 0.5, "step": "activity", "confounds": ["уровень виден, время нет"],
            "falsification": "снять крупно",
        }
        result = answer("что здесь происходило", self.scene, self.findings, [claim], [])
        self.assertIn("кружка", result["answer"])
        self.assertEqual(result["basis"], ["F-GEN-001"])
        self.assertGreater(result["uncertainty"], 0.4)

    def test_time_question_is_refused(self):
        result = answer("когда это было", self.scene, self.findings, [], [])
        self.assertIn("Время по кадру не видно", result["answer"])

    def test_identity_question_lists_facts(self):
        result = answer("что лежит на столе?", self.scene, self.findings, [], [])
        self.assertIn("mug", result["answer"])
        self.assertTrue(result["basis"])


if __name__ == "__main__":
    unittest.main()
