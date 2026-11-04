import json
import tempfile
import unittest
from pathlib import Path

from tools.elementarno.board import build, implicit_anchors
from tools.elementarno.cli import main
from tools.elementarno.rules import load_packs


def scene_fixture():
    return {
        "surfaces": [{"id": "s1", "name": "table", "material": "wood"}],
        "objects": [
            {"id": "o1", "category": "person", "visible": True, "note": "торс в кадре"},
            {"id": "o2", "category": "open_container", "visible": True, "note": "жестяная коробка"},
            {"id": "o3", "category": "mug", "visible": True, "note": "кружка"},
        ],
        "regions": [
            {"id": "r1", "kind": "food_remains", "note": "хлеб в пакете"},
            {"id": "r2", "kind": "stain", "note": "белесый след"},
        ],
        "observations": [],
    }


def ledger_fixture():
    return {
        "claims": [
            {
                "claim_id": "C-1",
                "kind": "inference",
                "text": "В кадре виден человек",
                "support": [{"finding_id": "F-PRES-004"}],
                "confidence": 0.5,
                "step": "presence",
                "provisional": True,
                "refutation": {"negation": "человека нет", "outcome": "survived", "note": "объёмный силуэт"},
            }
        ],
        "hypotheses": [
            {
                "hypothesis_id": "H-1",
                "text": "За столом кто-то был",
                "claims": ["C-1"],
                "status": "open",
                "discriminator": {"question": "кто это был?", "would_confirm": "лицо", "would_refute": "манекен"},
            }
        ],
    }


class BoardTest(unittest.TestCase):
    def test_build_is_self_contained_page(self):
        doc = build(scene_fixture(), [], ledger_fixture(), title="Доска")
        self.assertIn("<!DOCTYPE html>", doc)
        self.assertIn("УТВЕРЖДЕНИЕ C-1", doc)
        self.assertIn("В кадре виден человек", doc)
        self.assertNotIn("<link", doc)
        self.assertNotIn("<img", doc)
        self.assertNotIn("src=\"http", doc)

    def test_build_escapes_markup_in_ledger(self):
        ledger = ledger_fixture()
        ledger["claims"][0]["text"] = "<script>alert(1)</script>"
        doc = build(scene_fixture(), [], ledger)
        self.assertNotIn("<script>alert(1)</script>", doc)
        self.assertIn("&lt;script&gt;", doc)

    def test_links_connect_finding_claim_and_hypothesis(self):
        finding = {
            "finding_id": "F-PRES-004",
            "rule_id": "PRES-004",
            "rule_version": 2,
            "title": "Человек виден в кадре",
            "step": "presence",
            "inference": "В кадре виден человек",
            "anchors": ["o1"],
            "confidence_prior": 0.45,
            "confidence_ceiling": 0.5,
            "provisional": True,
            "sources": [],
            "confounds": [],
            "exceptions": [],
            "falsification": {},
        }
        doc = build(scene_fixture(), [finding], ledger_fixture(),
                    hypotheses=[{"hypothesis_id": "H-1", "text": "x", "claims": ["C-1"], "status": "open"}])
        self.assertIn('"from": "o1"', doc)
        self.assertIn('"to": "F-PRES-004"', doc)
        self.assertIn('"from": "F-PRES-004"', doc)
        self.assertIn('"to": "C-1"', doc)
        self.assertIn('"from": "C-1"', doc)
        self.assertIn('"to": "H-1"', doc)

    def test_region_without_rule_is_marked_as_gap(self):
        doc = build(scene_fixture(), [], ledger_fixture())
        self.assertIn("след без правила", doc)
        self.assertIn("Ни одно правило не сработало", doc)

    def test_implicit_anchor_comes_from_predicate(self):
        rules = {rule.id: rule for rule in load_packs("rules")}
        scene = scene_fixture()
        anchors = implicit_anchors(scene, rules["HOME-003"])
        self.assertEqual(anchors, ["o2"])
        self.assertEqual(implicit_anchors(scene, rules["PRES-004"]), [])

    def test_cli_writes_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene_path = Path(tmp) / "scene.json"
            ledger_path = Path(tmp) / "ledger.json"
            out_path = Path(tmp) / "board.html"
            scene_path.write_text(json.dumps(scene_fixture()), encoding="utf-8")
            ledger_path.write_text(json.dumps(ledger_fixture()), encoding="utf-8")
            code = main([
                "--rules", "rules",
                "board", str(scene_path), "--ledger", str(ledger_path),
                "--out", str(out_path),
            ])
            self.assertEqual(code, 0)
            self.assertTrue(out_path.exists())
            self.assertIn("Доска", out_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
