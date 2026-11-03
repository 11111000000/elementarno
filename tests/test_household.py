"""Бытовые правила: следы еды и видимый человек.

Два адреса, которых в базе не было: еда на месте и человек в кадре. Тесты
держат оба: правило еды не должно срабатывать на чистой посуде, правило
человека — только на видимом человеке, а оба — оставаться черновыми.
"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from elementarno.ledger import validate  # noqa: E402
from elementarno.perception import TRACE_CHECKLIST, normalize_kind  # noqa: E402
from elementarno.puzzle import build_claims  # noqa: E402
from elementarno.rules import evaluate_all, load_packs  # noqa: E402
from elementarno.scene import VALID_REGIONS, validate_scene  # noqa: E402

RULES = load_packs(ROOT / "rules")
BENCH = ROOT / "eval" / "benchmarks" / "household"
SCHEMA = json.loads((ROOT / "schemas" / "scene-graph.schema.json").read_text(encoding="utf-8"))


def load(name):
    return json.loads((BENCH / "scenes" / f"{name}.json").read_text(encoding="utf-8"))


def rule_by_id(rule_id):
    return next(rule for rule in RULES if rule.id == rule_id)


def fired(scene, rule_id):
    return {f["rule_id"] for f in evaluate_all(RULES, scene)}


class FoodRemainsTests(unittest.TestCase):
    def test_food_remains_is_a_known_region_kind(self):
        schema_kinds = set(SCHEMA["properties"]["regions"]["items"]["properties"]["kind"]["enum"])
        self.assertIn("food_remains", schema_kinds)
        self.assertIn("food_remains", VALID_REGIONS)

    def test_checklist_asks_about_food(self):
        questions = dict(TRACE_CHECKLIST)
        self.assertIn("food_remains", questions)
        self.assertIn("крошки", questions["food_remains"])

    def test_model_synonyms_map_to_food_remains(self):
        known = {kind for kind, _ in TRACE_CHECKLIST}
        for raw in ("crumbs", "leftovers", "food_waste"):
            self.assertEqual(normalize_kind(raw, known), "food_remains")

    def test_food_rule_fires_on_food_remains(self):
        scene = load("food-remains-on-table")
        self.assertIn("HOME-005", fired(scene, "HOME-005"))

    def test_food_rule_is_silent_without_food_remains(self):
        scene = load("clean-dishes-no-food-trace")
        self.assertNotIn("HOME-005", fired(scene, "HOME-005"))

    def test_food_finding_is_bound_to_the_region(self):
        scene = load("food-remains-on-table")
        finding = next(f for f in evaluate_all(RULES, scene) if f["rule_id"] == "HOME-005")
        self.assertEqual(finding["anchors"], ["r1"])
        self.assertEqual(finding["step"], "activity")


class VisiblePersonTests(unittest.TestCase):
    def test_person_rule_fires_when_person_is_visible(self):
        scene = load("person-visible-in-frame")
        self.assertIn("PRES-004", fired(scene, "PRES-004"))

    def test_person_rule_is_silent_without_person(self):
        scene = load("empty-room-no-person")
        self.assertNotIn("PRES-004", fired(scene, "PRES-004"))

    def test_person_rule_is_silent_when_person_is_not_visible(self):
        scene = load("person-out-of-frame")
        self.assertNotIn("PRES-004", fired(scene, "PRES-004"))

    def test_person_finding_is_bound_to_the_object(self):
        scene = load("person-visible-in-frame")
        finding = next(f for f in evaluate_all(RULES, scene) if f["rule_id"] == "PRES-004")
        self.assertEqual(finding["anchors"], ["o1"])
        self.assertEqual(finding["step"], "presence")

    def test_person_claim_says_nothing_about_the_person(self):
        scene = load("person-visible-in-frame")
        findings = evaluate_all(RULES, scene)
        claims = build_claims(findings)
        report = validate(findings, {"claims": claims})
        codes = {e["code"] for e in report["errors"]}
        self.assertNotIn("accusatory_framing", codes)
        self.assertNotIn("personality_inference", codes)
        self.assertNotIn("ladder_break", codes)
        self.assertEqual(report["errors"], [])


class NewRuleContractTests(unittest.TestCase):
    def test_new_rules_carry_the_required_parts(self):
        for rule_id in ("HOME-005", "PRES-004"):
            rule = rule_by_id(rule_id)
            self.assertTrue(rule.confounds, rule_id)
            self.assertTrue(rule.exceptions, rule_id)
            self.assertTrue(rule.sources, rule_id)
            self.assertTrue(rule.falsification.get("physical_test"), rule_id)

    def test_new_rules_stay_provisional_while_draft(self):
        for rule_id in ("HOME-005", "PRES-004"):
            rule = rule_by_id(rule_id)
            self.assertEqual(rule.review_status, "draft")
            self.assertLessEqual(rule.ceiling, 0.5)

    def test_new_sources_carry_a_link(self):
        for rule_id in ("HOME-005", "PRES-004"):
            for source in rule_by_id(rule_id).sources:
                self.assertTrue(source.get("url", "").startswith("https://"), source)

    def test_verified_flag_reflects_the_source_not_the_rule(self):
        """Флаг verified — про источник, а не про зрелость правила.

        Проверка источника и рецензия правила — разные дела. Источник,
        текст которого прочитан, помечается verified независимо от того,
        что правило остаётся черновиком; потолок от этого не растёт.
        """
        for rule_id in ("HOME-005", "PRES-004"):
            rule = rule_by_id(rule_id)
            self.assertEqual(rule.review_status, "draft")
            self.assertLessEqual(rule.ceiling, 0.5)
            for source in rule.sources:
                self.assertIn("verified", source)

    def test_benchmark_scenes_are_valid(self):
        for path in sorted((BENCH / "scenes").glob("*.json")):
            problems = validate_scene(json.loads(path.read_text(encoding="utf-8")))
            self.assertEqual(problems, [], path.name)


if __name__ == "__main__":
    unittest.main()
