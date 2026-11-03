import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from elementarno.rules import evaluate_all, load_packs  # noqa: E402

RULES = load_packs(ROOT / 'rules')
BENCH = ROOT / 'eval' / 'benchmarks'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


class SemioticsTests(unittest.TestCase):
    def test_symbol_built_by_model_gives_two_findings(self):
        scene = load(BENCH / "semiotics/scenes/symbol-by-model.json")
        findings = evaluate_all(RULES, scene)
        ids = {f["rule_id"] for f in findings}
        self.assertIn("SEM-003", ids)
        self.assertIn("SEM-004", ids)

    def test_freehand_scribble_is_not_a_sign(self):
        scene = load(BENCH / "semiotics/scenes/symbol-freehand.json")
        findings = evaluate_all(RULES, scene)
        ids = {f["rule_id"] for f in findings}
        self.assertNotIn("SEM-003", ids)
        self.assertNotIn("SEM-004", ids)

    def test_interpretation_finding_stays_speculative(self):
        scene = load(BENCH / "semiotics/scenes/symbol-by-model.json")
        findings = evaluate_all(RULES, scene)
        interpretation = next(f for f in findings if f["rule_id"] == "SEM-004")
        self.assertEqual(interpretation["layer"], "interpretive")
        self.assertLessEqual(interpretation["confidence_ceiling"], 0.4)
