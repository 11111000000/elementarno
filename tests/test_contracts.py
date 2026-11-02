"""Контракты: схемы, код и правила не должны расходиться.

Схемы в schemas/*.json — нормативный документ, а валидатор в коде — его
исполнение. Если они разойдутся, реальные данные начнут отвергаться по
причинам, которые никто не видит. Тест ниже ловит такое расхождение.
"""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys_path = str(ROOT / "tools")
import sys  # noqa: E402

if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from elementarno import rules as rules_module  # noqa: E402
from elementarno import scene as scene_module  # noqa: E402
from elementarno.perception import TRACE_CHECKLIST, normalize_kind  # noqa: E402

SCENE_SCHEMA = json.loads((ROOT / "schemas/scene-graph.schema.json").read_text(encoding="utf-8"))
RULE_SCHEMA = json.loads((ROOT / "schemas/rule.schema.json").read_text(encoding="utf-8"))
CLAIM_SCHEMA = json.loads((ROOT / "schemas/claim.schema.json").read_text(encoding="utf-8"))


class SchemaDriftTests(unittest.TestCase):
    def test_region_kinds_match_validator(self):
        schema_kinds = set(SCENE_SCHEMA["properties"]["regions"]["items"]["properties"]["kind"]["enum"])
        self.assertEqual(schema_kinds, scene_module.VALID_REGIONS)

    def test_object_states_match_validator(self):
        schema_states = set(SCENE_SCHEMA["properties"]["objects"]["items"]["properties"]["state"]["enum"])
        self.assertEqual(schema_states, scene_module.VALID_OBJECT_STATES)

    def test_required_ids_are_enforced(self):
        for collection in ("surfaces", "objects", "regions"):
            required = SCENE_SCHEMA["properties"][collection]["items"].get("required", [])
            self.assertIn("id", required)

    def test_rule_required_fields_match_loader(self):
        schema_required = set(RULE_SCHEMA["required"])
        self.assertEqual(schema_required, set(rules_module.REQUIRED_FIELDS))

    def test_rule_predicate_kinds_match_implementation(self):
        schema_kinds = set(RULE_SCHEMA["$defs"]["predicate"]["properties"]["kind"]["enum"])
        implemented = {"all", "any", "not", "present", "count", "absent", "rule",
                       "dangling", "mismatch", "max", "distinct"}
        self.assertEqual(schema_kinds, implemented)

    def test_claim_schema_requires_support(self):
        required = CLAIM_SCHEMA["properties"]["claims"]["items"]["required"]
        for field in ("claim_id", "kind", "text", "support", "confidence"):
            self.assertIn(field, required)

    def test_trace_checklist_kinds_exist_in_schema(self):
        schema_kinds = set(SCENE_SCHEMA["properties"]["regions"]["items"]["properties"]["kind"]["enum"])
        for kind, _ in TRACE_CHECKLIST:
            self.assertIn(kind, schema_kinds)


class DeterminismTests(unittest.TestCase):
    def test_normalize_kind_is_order_independent(self):
        known = {kind for kind, _ in TRACE_CHECKLIST}
        results = {normalize_kind("dust", known) for _ in range(50)}
        self.assertLessEqual(len(results), 1)

    def test_ambiguous_kind_is_rejected(self):
        known = {kind for kind, _ in TRACE_CHECKLIST}
        self.assertIsNone(normalize_kind("dust", known))

    def test_most_specific_alias_wins(self):
        known = {kind for kind, _ in TRACE_CHECKLIST}
        self.assertEqual(normalize_kind("mud_footprints", known), "mud_footprint")
        self.assertEqual(normalize_kind("paint_splashes", known), "paint_splash")


class RulePathTests(unittest.TestCase):
    def test_typo_in_path_breaks_loading(self):
        bad = {
            "pack": "t",
            "rules": [{
                "id": "TST-001", "version": 1, "pack": "t", "title": "x", "domain": "t",
                "predicate": {"kind": "count", "path": "regions[kind=burm]", "gte": 1},
                "inference": {"claim": "y", "confidence_prior": 0.5, "confidence_ceiling": 0.5},
                "confounds": ["c"], "exceptions": ["e"],
                "falsification": {"refuted_by": [], "physical_test": "t"},
                "sources": [{"ref": "s", "note": "", "verified": False}],
                "review_status": "draft",
            }],
        }
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "t.json").write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(rules_module.RuleError):
                rules_module.load_packs(tmp)

    def test_all_real_rules_load(self):
        loaded = rules_module.load_packs(ROOT / "rules")
        self.assertGreater(len(loaded), 40)


if __name__ == "__main__":
    unittest.main()
