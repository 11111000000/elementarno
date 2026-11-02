import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from elementarno.diff import diff_scenes  # noqa: E402
from elementarno.ledger import validate  # noqa: E402
from elementarno.paths import resolve  # noqa: E402
from elementarno.providers import StdioMcpClient  # noqa: E402
from elementarno.puzzle import build_claims, load_puzzle, solve  # noqa: E402
from elementarno.render import render  # noqa: E402
from elementarno.rules import RuleError, evaluate_all, load_packs  # noqa: E402
from elementarno.scene import validate_scene  # noqa: E402

RULES = load_packs(ROOT / "rules")
BENCH = ROOT / "eval" / "benchmarks"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class PathTests(unittest.TestCase):
    def test_filter_and_field(self):
        scene = load(BENCH / "protocol-core/scenes/absence-dust-outline.json")
        self.assertEqual(len(resolve(scene, "regions[kind=dust_outline]")), 1)
        self.assertEqual(resolve(scene, "regions[kind=dust_outline].id"), ["r1"])
        self.assertEqual(resolve(scene, "regions[kind=burn]"), [])

    def test_boolean_matching_is_strict(self):
        scene = load(BENCH / "mystery-study/scene-before.json")
        self.assertEqual(len(resolve(scene, "surfaces[dust_present=true]")), 3)
        self.assertEqual(len(resolve(scene, "surfaces[dust_present=false]")), 0)


class DiffTests(unittest.TestCase):
    def test_detects_removal_addition_and_link(self):
        before = load(BENCH / "mystery-study/scene-before.json")
        after = load(BENCH / "mystery-study/scene-after.json")
        changes = diff_scenes(before, after)
        kinds = {c["kind"] for c in changes}
        self.assertIn("object_removed", kinds)
        self.assertIn("object_added", kinds)
        self.assertIn("object_moved", kinds)
        self.assertIn("surface_changed", kinds)
        removal = next(c for c in changes if c["kind"] == "object_removed")
        self.assertEqual(removal["matched_region"], "r1")
        added = next(c for c in changes if c["kind"] == "object_added")
        self.assertTrue(added["wet"])


class RuleTests(unittest.TestCase):
    def test_finding_cites_rule_and_source(self):
        scene = load(BENCH / "protocol-core/scenes/absence-dust-outline.json")
        findings = evaluate_all(RULES, scene)
        ids = {f["rule_id"] for f in findings}
        self.assertIn("ABS-001", ids)
        finding = next(f for f in findings if f["rule_id"] == "ABS-001")
        self.assertTrue(finding["sources"])
        self.assertTrue(finding["confounds"])
        self.assertEqual(finding["anchors"], ["r1"])

    def test_draft_rule_caps_confidence(self):
        scene = load(BENCH / "protocol-core/scenes/absence-dust-outline.json")
        findings = evaluate_all(RULES, scene)
        finding = next(f for f in findings if f["rule_id"] == "ABS-001")
        self.assertTrue(finding["provisional"])
        self.assertLessEqual(finding["confidence_ceiling"], 0.5)

    def test_rule_without_source_is_rejected(self):
        bad = {
            "pack": "test",
            "rules": [{
                "id": "TST-001", "version": 1, "pack": "test", "title": "x",
                "domain": "test", "predicate": {"kind": "absent", "path": "objects"},
                "inference": {"claim": "y", "confidence_prior": 0.5, "confidence_ceiling": 0.5},
                "confounds": ["c"], "exceptions": ["e"],
                "falsification": {"refuted_by": [], "physical_test": "t"},
                "sources": [], "review_status": "draft",
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "t.json").write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(RuleError):
                load_packs(tmp)


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.scene = load(BENCH / "protocol-core/scenes/absence-dust-outline.json")
        self.findings = evaluate_all(RULES, self.scene)

    def test_claim_without_finding_is_rejected(self):
        report = validate(self.findings, {"claims": [{
            "claim_id": "C-X", "kind": "observation", "text": "что-то",
            "support": [{"finding_id": "F-NOPE"}], "confidence": 0.3,
        }]})
        codes = {e["code"] for e in report["errors"]}
        self.assertIn("unresolved_citation", codes)

    def test_overconfidence_is_rejected(self):
        report = validate(self.findings, {"claims": [{
            "claim_id": "C-1", "kind": "observation", "text": "что-то",
            "support": [{"finding_id": "F-ABS-001"}], "confidence": 0.95,
        }]})
        codes = {e["code"] for e in report["errors"]}
        self.assertIn("overconfidence", codes)

    def test_draft_rule_cannot_back_strong_claim(self):
        report = validate(self.findings, {"claims": [{
            "claim_id": "C-1", "kind": "observation", "text": "что-то",
            "support": [{"finding_id": "F-ABS-001"}], "confidence": 0.8,
        }]})
        codes = {e["code"] for e in report["errors"]}
        self.assertIn("draft_backs_strong_claim", codes)
        self.assertIn("missing_provisional_flag", codes)

    def test_hypothesis_requires_falsification(self):
        report = validate(self.findings, {"claims": [{
            "claim_id": "C-1", "kind": "hypothesis", "text": "что-то",
            "support": [{"finding_id": "F-ABS-001"}], "confidence": 0.4, "provisional": True,
        }]})
        codes = {e["code"] for e in report["errors"]}
        self.assertIn("hypothesis_without_falsification", codes)

    def test_rejected_hypothesis_needs_kill_log(self):
        report = validate(self.findings, {"claims": [], "hypotheses": [{
            "hypothesis_id": "H-1", "text": "версия", "claims": [], "status": "rejected",
        }]})
        codes = {e["code"] for e in report["errors"]}
        self.assertIn("rejected_without_kill_log", codes)

    def test_interpretation_is_capped_and_marked(self):
        report = validate(self.findings, {"claims": [{
            "claim_id": "C-1", "kind": "interpretation", "text": "что-то",
            "support": [{"finding_id": "F-ABS-001"}], "confidence": 0.9, "speculative": True,
        }]})
        codes = {e["code"] for e in report["errors"]}
        self.assertIn("interpretation_too_confident", codes)


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.scene = load(BENCH / "protocol-core/scenes/absence-dust-outline.json")
        self.findings = evaluate_all(RULES, self.scene)
        self.claims = build_claims(self.findings)

    def test_persona_keeps_citations_and_confidence(self):
        text = render("detective", self.findings, self.claims, [], "sufficient_evidence", "doyle")
        self.assertIn("[ABS-001]", text)
        self.assertIn("доказательство", text)
        for claim in self.claims:
            self.assertLessEqual(claim["confidence"], 0.5)
        self.assertIn("Уотсон", text)

    def test_refusal_is_rendered_in_persona(self):
        text = render("detective", [], [], [], "insufficient_evidence", "doyle")
        self.assertIn("Уотсон", text)
        self.assertIn("недостаточно", text)

    def test_audit_persona_is_not_doyle(self):
        text = render("audit", self.findings, self.claims, [], "sufficient_evidence", "forensic")
        self.assertNotIn("Уотсон", text)

    def test_ladder_goes_from_general_to_particular(self):
        claims = [
            {"claim_id": "C-1", "kind": "inference", "text": "сцена — кабинет",
             "support": [{"finding_id": "F-ABS-001"}], "confidence": 0.4, "step": "scene"},
            {"claim_id": "C-2", "kind": "inference", "text": "здесь переставляли вещи",
             "support": [{"finding_id": "F-ABS-001"}], "confidence": 0.4, "step": "activity"},
            {"claim_id": "C-3", "kind": "inference", "text": "здесь ходили",
             "support": [{"finding_id": "F-ABS-001"}], "confidence": 0.4, "step": "presence"},
        ]
        text = render("detective", self.findings, claims, [], "sufficient_evidence", "plain")
        positions = [text.index(label) for label in ("Место:", "Активность:", "Присутствовали:")]
        self.assertEqual(positions, sorted(positions))


class PuzzleTests(unittest.TestCase):
    def test_participant_is_ranked_by_matching_tags(self):
        puzzle, scenes = load_puzzle(BENCH / "mystery-study/puzzle.json")
        result = solve(puzzle, scenes, RULES)
        self.assertTrue(result["evaluation"]["correct"])
        self.assertEqual(result["participants"][0]["participant_id"], "s1")
        self.assertLess(result["participants"][1]["score"], result["participants"][0]["score"])

    def test_participant_without_matching_tags_scores_zero(self):
        puzzle, scenes = load_puzzle(BENCH / "mystery-study/puzzle.json")
        result = solve(puzzle, scenes, RULES)
        other = next(p for p in result["participants"] if p["participant_id"] == "s2")
        self.assertEqual(other["score"], 0.0)

    def test_legacy_suspects_key_is_accepted(self):
        puzzle, scenes = load_puzzle(BENCH / "mystery-study/puzzle.json")
        puzzle["suspects"] = puzzle.pop("participants")
        result = solve(puzzle, scenes, RULES)
        self.assertEqual(len(result["participants"]), 3)

    def test_hypothesis_states_presence_not_guilt(self):
        puzzle, scenes = load_puzzle(BENCH / "mystery-study/puzzle.json")
        result = solve(puzzle, scenes, RULES)
        for hypothesis in result["hypotheses"]:
            self.assertIn("Присутствовал", hypothesis["text"])


class PresenceTests(unittest.TestCase):
    def test_two_shoe_sizes_imply_two_people(self):
        scene = {
            "surfaces": [{"id": "s1", "name": "floor"}],
            "objects": [],
            "regions": [
                {"id": "r1", "kind": "footprint", "size_m": 0.24},
                {"id": "r2", "kind": "footprint", "size_m": 0.29},
            ],
            "observations": [],
        }
        findings = evaluate_all(RULES, scene)
        ids = {f["rule_id"] for f in findings}
        self.assertIn("PRES-001", ids)
        finding = next(f for f in findings if f["rule_id"] == "PRES-001")
        self.assertEqual(finding["step"], "presence")

    def test_fingerprint_in_dust_is_recent_touch(self):
        scene = {
            "surfaces": [{"id": "s1", "name": "shelf", "dust_present": True}],
            "objects": [],
            "regions": [{"id": "r1", "kind": "fingerprint"}],
            "observations": [],
        }
        findings = evaluate_all(RULES, scene)
        ids = {f["rule_id"] for f in findings}
        self.assertIn("PRES-003", ids)


class FramingTests(unittest.TestCase):
    def setUp(self):
        self.scene = load(BENCH / "protocol-core/scenes/absence-dust-outline.json")
        self.findings = evaluate_all(RULES, self.scene)

    def test_accusatory_claim_is_rejected(self):
        report = validate(self.findings, {"claims": [{
            "claim_id": "C-1", "kind": "hypothesis", "text": "Дворецкий виновен в краже",
            "support": [{"finding_id": "F-ABS-001"}], "confidence": 0.4, "provisional": True,
            "falsification": "проверить алиби",
        }]})
        codes = {e["code"] for e in report["errors"]}
        self.assertIn("accusatory_framing", codes)

    def test_personality_claim_is_rejected(self):
        report = validate(self.findings, {"claims": [{
            "claim_id": "C-1", "kind": "inference", "text": "По фотографии виден характер человека",
            "support": [{"finding_id": "F-ABS-001"}], "confidence": 0.4, "provisional": True,
        }]})
        codes = {e["code"] for e in report["errors"]}
        self.assertIn("personality_inference", codes)

    def test_presence_claim_passes(self):
        report = validate(self.findings, {"claims": [{
            "claim_id": "C-1", "kind": "hypothesis", "text": "Присутствовал в сцене: садовник",
            "support": [{"finding_id": "F-ABS-001"}], "confidence": 0.4, "provisional": True,
            "falsification": "сверить след с обувью",
        }]})
        codes = {e["code"] for e in report["errors"]}
        self.assertNotIn("accusatory_framing", codes)
        self.assertNotIn("personality_inference", codes)

    def test_ladder_break_is_rejected(self):
        report = validate(self.findings, {"claims": [{
            "claim_id": "C-1", "kind": "inference", "text": "это кабинет",
            "support": [{"finding_id": "F-ABS-001"}], "confidence": 0.4, "provisional": True,
            "step": "scene",
        }]})
        codes = {e["code"] for e in report["errors"]}
        self.assertIn("ladder_break", codes)

    def test_ladder_connectivity_passes(self):
        report = validate(self.findings, {"claims": [{
            "claim_id": "C-1", "kind": "inference", "text": "здесь переставляли вещи",
            "support": [{"finding_id": "F-ABS-001"}], "confidence": 0.4, "provisional": True,
            "step": "presence",
        }]})
        codes = {e["code"] for e in report["errors"]}
        self.assertNotIn("ladder_break", codes)


class SceneTests(unittest.TestCase):
    def test_dangling_reference_is_detected(self):
        scene = load(BENCH / "mystery-study/scene-before.json")
        scene["objects"][0]["on"] = "missing"
        problems = validate_scene(scene)
        codes = {p["code"] for p in problems}
        self.assertIn("dangling_surface", codes)

    def test_clean_scene_has_no_problems(self):
        scene = load(BENCH / "mystery-study/scene-after.json")
        self.assertEqual(validate_scene(scene), [])


class PerceptionTests(unittest.TestCase):
    def test_normalize_drops_dangling_and_duplicate_surfaces(self):
        from elementarno.perception import normalize_scene

        scene = {
            "surfaces": [{"id": "s1", "name": "table"}],
            "objects": [
                {"id": "o1", "category": "table", "on": None},
                {"id": "o2", "category": "mug", "on": "s9", "fill_level": None},
            ],
            "regions": [],
        }
        normalized, notes = normalize_scene(scene)
        categories = [o["category"] for o in normalized["objects"]]
        self.assertEqual(categories, ["mug"])
        self.assertNotIn("on", normalized["objects"][0])
        self.assertNotIn("fill_level", normalized["objects"][0])
        self.assertTrue(notes)

    def test_dangling_ignores_null_references(self):
        scene = load(BENCH / "mystery-study/scene-before.json")
        scene["objects"][0]["on"] = None
        findings = evaluate_all(RULES, scene)
        self.assertNotIn("PHY-001", {f["rule_id"] for f in findings})

    def test_extract_json_from_fenced_answer(self):
        from elementarno.perception import MiniMaxPerception

        text = '```json\n{"surfaces": [], "objects": []}\n```'
        parsed = MiniMaxPerception.extract_json(text)
        self.assertEqual(parsed["surfaces"], [])


class FixtureTests(unittest.TestCase):
    def test_fixture_generator_writes_png(self):
        import subprocess

        out = Path(tempfile.mkdtemp()) / "scene.png"
        subprocess.run(
            [sys.executable, str(ROOT / "tools/make_fixture.py"), "--preset", "study", "--out", str(out)],
            check=True,
            capture_output=True,
        )
        data = out.read_bytes()
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertGreater(len(data), 100)


class McpTests(unittest.TestCase):
    def test_stdio_client_roundtrip(self):
        client = StdioMcpClient(sys.executable, [str(ROOT / "tools/mcp/demo_server.py")])
        try:
            client.start()
            tools = client.list_tools()
            names = {t["name"] for t in tools}
            self.assertIn("solar_elevation", names)
            result = client.call_tool("solar_elevation", {"latitude": 55.75, "day_of_year": 172, "hour": 12})
            self.assertIn("value", result)
            self.assertLess(result["value"], 90)
        finally:
            client.stop()

    def test_unknown_tool_raises(self):
        client = StdioMcpClient(sys.executable, [str(ROOT / "tools/mcp/demo_server.py")])
        try:
            client.start()
            with self.assertRaises(Exception):
                client.call_tool("nope", {})
        finally:
            client.stop()


if __name__ == "__main__":
    unittest.main()
