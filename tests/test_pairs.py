"""Пары «до/после»: генератор, скорер и целостность манифеста.

Проверяется контур, который должен работать до настоящей съёмки: генератор
собирает пары ожидаемой структуры, скорер отличает «нашёл» от «не нашёл» и от
ложного срабатывания, манифест остаётся валидным. Сети здесь нет: всё считается
по готовым сценам.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import make_pairs  # noqa: E402
import score_pairs  # noqa: E402
from elementarno.rules import evaluate_all, load_packs  # noqa: E402
from elementarno.scene import validate_scene  # noqa: E402

RULES = load_packs(ROOT / "rules")
PAIRS_DIR = ROOT / "eval" / "pairs"
MANIFEST_PATH = PAIRS_DIR / "manifest.json"

REGION_OF_RULE = {
    "ABS-001": "dust_outline",
    "ABS-002": "unfaded_patch",
    "ABS-003": "empty_hook",
}


def kinds(scene):
    return {region.get("kind") for region in scene.get("regions", [])}


def fired(scene):
    return {finding["rule_id"] for finding in evaluate_all(RULES, scene)}


class GeneratorTests(unittest.TestCase):
    def test_every_pair_has_three_valid_frames(self):
        self.assertTrue(make_pairs.BUILDERS)
        for pair_id in make_pairs.BUILDERS:
            spec = make_pairs.build_pair(pair_id)
            for frame in make_pairs.FRAMES:
                with self.subTest(pair=pair_id, frame=frame):
                    self.assertEqual(validate_scene(spec[frame]), [])

    def test_trace_lives_on_the_frame_with_the_evidence(self):
        for pair_id in make_pairs.BUILDERS:
            spec = make_pairs.build_pair(pair_id)
            for finding_id in spec["expect"]["finding_ids"]:
                rule = finding_id.removeprefix("F-")
                kind = REGION_OF_RULE[rule]
                with self.subTest(pair=pair_id, rule=rule):
                    self.assertIn(kind, kinds(spec["before"]))
                    self.assertNotIn(kind, kinds(spec["after"]))
                    self.assertNotIn(kind, kinds(spec["clean"]))

    def test_expected_rule_fires_only_on_the_evidence_frame(self):
        for pair_id in make_pairs.BUILDERS:
            spec = make_pairs.build_pair(pair_id)
            expected = {item.removeprefix("F-") for item in spec["expect"]["finding_ids"]}
            with self.subTest(pair=pair_id):
                self.assertTrue(expected <= fired(spec["before"]))
                self.assertFalse(expected & fired(spec["after"]))
                self.assertFalse(expected & fired(spec["clean"]))

    def test_generator_writes_scenes_and_pictures(self):
        spec = make_pairs.build_pair("syn-dust-outline-shelf")
        with tempfile.TemporaryDirectory() as tmp:
            entry = make_pairs.write_pair(spec, Path(tmp))
            folder = Path(tmp) / spec["id"]
            for frame in make_pairs.FRAMES:
                self.assertTrue((folder / f"{frame}.json").exists())
                self.assertTrue((folder / f"{frame}.png").exists())
                scene = json.loads((folder / f"{frame}.json").read_text(encoding="utf-8"))
                self.assertEqual(validate_scene(scene), [])
            self.assertTrue((folder / "before.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertEqual(entry["before"], f"synthetic/{spec['id']}/before.json")
            self.assertFalse(entry["real"])
            self.assertTrue(entry["synthetic"])

    def test_manifest_update_keeps_foreign_pairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps({"pairs": [
                {"id": "real-1", "before": "a.json", "after": "b.json",
                 "expect": {"finding_ids": ["F-ABS-001"]}, "truth": "настоящая",
                 "real": True, "synthetic": False},
            ]}), encoding="utf-8")
            spec = make_pairs.build_pair("syn-empty-hook-door")
            entry = make_pairs.write_pair(spec, Path(tmp) / "scenes")
            manifest = make_pairs.update_manifest([entry], path)
            ids = [pair["id"] for pair in manifest["pairs"]]
            self.assertIn("real-1", ids)
            self.assertIn(spec["id"], ids)
            self.assertIn("синтетические", manifest["note"].lower())


class ScorerTests(unittest.TestCase):
    def pair(self, spec, **changes):
        entry = make_pairs.manifest_entry(spec)
        entry.update(changes)
        return entry

    def scenes(self, spec):
        return {frame: spec[frame] for frame in make_pairs.FRAMES}

    def test_finds_the_evidence(self):
        spec = make_pairs.build_pair("syn-dust-outline-shelf")
        result = score_pairs.score_pair(self.pair(spec), self.scenes(spec), RULES,
                                        {rule.id: rule.pack for rule in RULES})
        self.assertTrue(result["negative_detected"])
        self.assertTrue(result["consistency"])
        self.assertEqual(result["false_positive"], [])
        self.assertTrue(result["passed"])

    def test_reports_missed_evidence(self):
        spec = make_pairs.build_pair("syn-dust-outline-shelf")
        spec["before"]["regions"] = []
        result = score_pairs.score_pair(self.pair(spec), self.scenes(spec), RULES,
                                        {rule.id: rule.pack for rule in RULES})
        self.assertFalse(result["negative_detected"])
        self.assertIn("ABS-001", result["missing"])
        self.assertFalse(result["passed"])

    def test_reports_false_positive_on_clean_scene(self):
        spec = make_pairs.build_pair("syn-dust-outline-shelf")
        spec["clean"]["regions"].append({
            "id": "r1", "kind": "dust_outline", "shape": "round",
            "freshness": "sharp", "edges": "concave",
        })
        result = score_pairs.score_pair(self.pair(spec), self.scenes(spec), RULES,
                                        {rule.id: rule.pack for rule in RULES})
        self.assertIn("ABS-001", result["false_positive"])
        self.assertFalse(result["passed"])

    def test_reports_leak_on_second_frame(self):
        spec = make_pairs.build_pair("syn-dust-outline-shelf")
        spec["after"]["regions"].append({
            "id": "r1", "kind": "dust_outline", "shape": "round",
            "freshness": "sharp", "edges": "concave",
        })
        result = score_pairs.score_pair(self.pair(spec), self.scenes(spec), RULES,
                                        {rule.id: rule.pack for rule in RULES})
        self.assertFalse(result["negative_detected"])
        self.assertIn("ABS-001", result["leaked"])
        self.assertFalse(result["consistency"])

    def test_invalid_scene_is_a_problem(self):
        spec = make_pairs.build_pair("syn-dust-outline-shelf")
        spec["after"]["regions"].append({"id": "r1", "kind": "неизвестный"})
        result = score_pairs.score_pair(self.pair(spec), self.scenes(spec), RULES,
                                        {rule.id: rule.pack for rule in RULES})
        self.assertFalse(result["passed"])
        self.assertTrue(any("невалидна" in problem for problem in result["problems"]))

    def test_trace_frame_may_be_after(self):
        spec = make_pairs.build_pair("syn-dust-outline-shelf")
        spec["before"]["regions"] = []
        spec["after"]["regions"] = [{
            "id": "r1", "kind": "dust_outline", "shape": "round",
            "freshness": "sharp", "edges": "concave",
        }]
        entry = self.pair(spec)
        entry["expect"] = {"finding_ids": ["F-ABS-001"], "trace_frame": "after"}
        result = score_pairs.score_pair(entry, self.scenes(spec), RULES,
                                        {rule.id: rule.pack for rule in RULES})
        self.assertTrue(result["negative_detected"])
        self.assertEqual(result["missing"], [])

    def test_cli_fails_on_broken_manifest(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        broken = dict(manifest["pairs"][0])
        broken["expect"] = {"finding_ids": ["F-ABS-002"], "trace_frame": "before"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps({"pairs": [broken]}, ensure_ascii=False), encoding="utf-8")
            done = subprocess.run(
                [sys.executable, str(ROOT / "tools/score_pairs.py"), "--manifest", str(path)],
                capture_output=True, text=True, cwd=str(ROOT),
            )
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("ABS-002", done.stdout)

    def test_cli_passes_on_repository_manifest(self):
        done = subprocess.run(
            [sys.executable, str(ROOT / "tools/score_pairs.py")],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_manifest_has_pairs_and_a_note(self):
        self.assertTrue(self.manifest["pairs"])
        self.assertIn("синтетические", self.manifest["note"].lower())

    def test_every_pair_has_required_fields(self):
        for pair in self.manifest["pairs"]:
            with self.subTest(pair=pair.get("id")):
                for field in ("id", "before", "after", "clean", "expect", "truth",
                              "real", "synthetic"):
                    self.assertIn(field, pair)
                self.assertTrue(pair["truth"].strip())
                self.assertTrue(pair["expect"]["finding_ids"])
                self.assertIn(pair["expect"].get("trace_frame", "before"), ("before", "after"))

    def test_ids_are_unique(self):
        ids = [pair["id"] for pair in self.manifest["pairs"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_scene_files_exist(self):
        for pair in self.manifest["pairs"]:
            for frame in ("before", "after", "clean"):
                with self.subTest(pair=pair["id"], frame=frame):
                    self.assertTrue((PAIRS_DIR / pair[frame]).exists())

    def test_flags_are_consistent(self):
        for pair in self.manifest["pairs"]:
            with self.subTest(pair=pair["id"]):
                self.assertNotEqual(bool(pair["real"]), bool(pair["synthetic"]))

    def test_expected_rules_exist_in_the_rule_base(self):
        known = {rule.id for rule in RULES}
        for pair in self.manifest["pairs"]:
            for finding_id in pair["expect"]["finding_ids"]:
                with self.subTest(pair=pair["id"], finding=finding_id):
                    self.assertIn(finding_id.removeprefix("F-"), known)

    def test_all_three_absence_rules_are_covered(self):
        covered = {finding_id.removeprefix("F-")
                   for pair in self.manifest["pairs"]
                   for finding_id in pair["expect"]["finding_ids"]}
        self.assertEqual(covered, set(REGION_OF_RULE))


if __name__ == "__main__":
    unittest.main()
