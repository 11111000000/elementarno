import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

from elementarno.render import render  # noqa: E402
from elementarno.rules import evaluate_all, load_packs  # noqa: E402

RULES = load_packs(ROOT / 'rules')
BENCH = ROOT / 'eval' / 'benchmarks'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


class ProfileTests(unittest.TestCase):
    def test_explicit_flag_beats_profile(self):
        from types import SimpleNamespace

        from elementarno.cli import apply_profile
        args = SimpleNamespace(pack=None, mode="detective", persona="plain", min_findings=1)
        apply_profile(args, {"packs": ["home"], "mode": "detective",
                             "persona": "doyle", "min_findings": 2})
        self.assertEqual(args.min_findings, 1)
        self.assertEqual(args.pack, ["home"])

    def test_profile_fills_unset_values(self):
        from types import SimpleNamespace

        from elementarno.cli import apply_profile
        args = SimpleNamespace(pack=None, mode="detective", persona="plain", min_findings=None)
        apply_profile(args, {"packs": ["home"], "mode": "detective",
                             "persona": "doyle", "min_findings": 2})
        self.assertEqual(args.min_findings, 2)
        self.assertEqual(args.persona, "doyle")

    def test_without_profile_min_findings_has_a_default(self):
        from types import SimpleNamespace

        from elementarno.cli import apply_profile
        args = SimpleNamespace(pack=None, mode="detective", persona="plain", min_findings=None,
                               config="/nonexistent/profiles.json", profile=None)
        apply_profile(args)
        self.assertEqual(args.min_findings, 1)


class NextshotCliTests(unittest.TestCase):
    def ledger(self, with_discriminator=True):
        hypotheses = [
            {"hypothesis_id": "H-1", "text": "после использования", "claims": ["C-1"],
             "status": "open", "step": "activity"},
            {"hypothesis_id": "H-2", "text": "давно пустое", "claims": ["C-1"],
             "status": "open", "step": "activity"},
        ]
        if with_discriminator:
            hypotheses[0]["discriminator"] = {"question": "что в коробке: блистер или пусто?"}
        return {
            "claims": [{"claim_id": "C-1", "kind": "inference", "text": "контур",
                        "support": [{"finding_id": "F-ABS-001"}], "confidence": 0.4,
                        "step": "activity", "provisional": True}],
            "hypotheses": hypotheses,
        }

    def run_nextshot(self, ledger):
        import contextlib
        import io
        from types import SimpleNamespace

        from elementarno.cli import cmd_nextshot
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
            args = SimpleNamespace(
                scene=str(BENCH / "protocol-core/scenes/absence-dust-outline.json"),
                hypotheses=str(path), rules=str(ROOT / "rules"), pack=None, profile=None,
                config=str(ROOT / "config/profiles.json"), limit=3, json=True)
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                cmd_nextshot(args)
        return json.loads(buffer.getvalue())

    def test_nextshot_reads_claims_from_the_ledger(self):
        payload = self.run_nextshot(self.ledger())
        self.assertTrue(payload["discriminators"])
        self.assertEqual(payload["discriminators"][0]["splits"], 1)

    def test_ledger_without_discriminator_gives_no_discriminator_questions(self):
        payload = self.run_nextshot(self.ledger(with_discriminator=False))
        self.assertEqual(payload["discriminators"], [])


class RenderHonestyTests(unittest.TestCase):
    """Ответ не должен подписывать улику тем, чего на фотографии нет."""

    def setUp(self):
        self.scene = load(BENCH / "protocol-core/scenes/absence-dust-outline.json")
        self.findings = evaluate_all(RULES, self.scene)
        self.claims = [{
            "claim_id": "C-1", "kind": "inference", "text": "контур оставлен предметом",
            "support": [{"finding_id": "F-ABS-001"}], "confidence": 0.4, "step": "activity",
            "provisional": True,
            "confounds": ["уборка могла размазать контур"],
            "refutation": {"negation": "контура на столе не было", "outcome": "survived"},
        }]

    def test_evidence_is_named_by_rule_id_not_by_rule_title(self):
        text = render("detective", self.findings, self.claims, [], "sufficient_evidence", "plain")
        finding = self.findings[0]
        self.assertNotIn(f"{finding['title']} — доказательство", text)
        self.assertIn(f"Правило {finding['rule_id']}: {finding['title']}", text)
        self.assertIn(f"[{finding['rule_id']}]", text)

    def test_claim_confounds_are_printed_next_to_the_finding_ones(self):
        text = render("detective", self.findings, self.claims, [], "sufficient_evidence", "plain")
        self.assertIn("Оговорки улики:", text)
        self.assertIn("Оговорки вывода:", text)
        self.assertIn("уборка могла размазать контур", text)

    def test_refutation_is_printed_with_its_outcome(self):
        text = render("detective", self.findings, self.claims, [], "sufficient_evidence", "plain")
        self.assertIn("контура на столе не было", text)
        self.assertIn("вывод устоял", text)

    def test_thin_evidence_does_not_contradict_printed_claims(self):
        text = render("detective", self.findings, self.claims, [], "insufficient_evidence", "plain")
        self.assertNotIn("Улик недостаточно для вывода.", text)
        self.assertIn("Улик мало для версии", text)
