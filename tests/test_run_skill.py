import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import run_skill  # noqa: E402
from elementarno.ledger import validate  # noqa: E402

SCENE = json.loads(
    (ROOT / "eval/benchmarks/protocol-core/scenes/absence-dust-outline.json").read_text(encoding="utf-8")
)


def finding(finding_id, ceiling=0.8, provisional=False):
    return {
        "finding_id": finding_id,
        "confidence_ceiling": ceiling,
        "provisional": provisional,
        "step": "activity",
    }


def metrics_for(case, findings, ledger, verdict="sufficient_evidence"):
    report = validate(findings, ledger)
    return run_skill.case_metrics(case, findings, ledger, report, verdict, 1.0, 3)


class SkillParsingTests(unittest.TestCase):
    def test_phases_are_parsed(self):
        phases = run_skill.load_skill()["phases"]
        self.assertEqual(sorted(phases), list(range(10)))
        self.assertEqual(phases[4]["title"], "Проверка и отрицание")
        self.assertEqual(phases[6]["title"], "Версии")

    def test_phase_bodies_carry_the_protocol(self):
        phases = run_skill.load_skill()["phases"]
        self.assertIn("refutation", phases[4]["text"])
        self.assertIn("finding_id", phases[5]["text"])
        self.assertIn("discriminator", phases[6]["text"])

    def test_skill_text_reaches_the_prompt(self):
        phases = run_skill.load_skill()["phases"]
        prompt = run_skill.build_prompt(phases, [], {})
        for number in run_skill.PHASES_IN_PROMPT:
            self.assertIn(phases[number]["text"], prompt)

    def test_skill_without_phases_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "SKILL.md"
            path.write_text("# Скилл\n\nФаз нет.\n", encoding="utf-8")
            with self.assertRaises(run_skill.SkillError):
                run_skill.load_skill(path)


class ManifestTests(unittest.TestCase):
    def test_repository_manifest_is_valid(self):
        cases = run_skill.load_cases()
        self.assertEqual(
            [case["id"] for case in cases],
            ["mold-wall", "footprints-mud", "clean-kitchen-dining"],
        )
        for case in cases:
            self.assertTrue(case["packs"])
            self.assertIn("verdict", case["expect"])

    def test_missing_fields_are_reported(self):
        problems = run_skill.validate_manifest({"cases": [{"id": "пусто"}]})
        joined = " ".join(problems)
        self.assertIn("image", joined)
        self.assertIn("packs", joined)
        self.assertIn("expect", joined)

    def test_unknown_verdict_is_reported(self):
        problems = run_skill.validate_manifest({"cases": [{
            "id": "x",
            "image": "eval/real/images/clean-kitchen-dining.jpg",
            "packs": ["core"],
            "expect": {"verdict": "maybe"},
        }]})
        self.assertTrue(any("вердикт" in problem for problem in problems))

    def test_missing_image_is_reported(self):
        problems = run_skill.validate_manifest({"cases": [{
            "id": "x",
            "image": "eval/real/images/нет-такого.jpg",
            "packs": ["core"],
            "expect": {},
        }]})
        self.assertTrue(any("изображения" in problem for problem in problems))

    def test_broken_manifest_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cases.json"
            path.write_text('{"cases": [{"id": "x"}]}', encoding="utf-8")
            with self.assertRaises(run_skill.ManifestError):
                run_skill.load_cases(path)


class LedgerTests(unittest.TestCase):
    def test_nothing_is_dropped_from_the_answer(self):
        data = {
            "claims": [{"claim_id": "C-1", "kind": "inference", "text": "Утверждение",
                        "support": [{"finding_id": "F-ABS-001"}], "confidence": 0.4}],
            "hypotheses": [{"hypothesis_id": "H-1", "text": "Версия", "claims": ["C-1"]}],
        }
        ledger = run_skill.normalize_ledger(data)
        self.assertEqual(len(ledger["claims"]), 1)
        self.assertIsNone(ledger["claims"][0]["refutation"])
        self.assertIsNone(ledger["hypotheses"][0]["discriminator"])

    def test_protocol_violations_are_counted(self):
        findings = [finding("F-ABS-001", ceiling=0.5, provisional=True)]
        ledger = run_skill.normalize_ledger({"claims": [{
            "claim_id": "C-1", "text": "Утверждение", "support": [{"finding_id": "F-ABS-001"}],
            "confidence": 0.4, "step": "activity",
        }]})
        report = validate(findings, ledger)
        codes = {error["code"] for error in report["errors"]}
        self.assertIn("missing_refutation", codes)


class MetricTests(unittest.TestCase):
    def test_recall_and_extra_findings(self):
        case = {"expect": {"finding_ids": ["F-A-001", "F-C-003"], "verdict": "sufficient_evidence"}}
        findings = [finding("F-A-001"), finding("F-B-002")]
        ledger = {"claims": [], "hypotheses": []}
        metrics = metrics_for(case, findings, ledger)
        self.assertEqual(metrics["finding_recall"], 0.5)
        self.assertEqual(metrics["extra_findings"], 1)
        self.assertEqual(metrics["extra_finding_ids"], ["F-B-002"])
        self.assertEqual(metrics["missing_finding_ids"], ["F-C-003"])
        self.assertEqual(metrics["refusal_accuracy"], 1.0)

    def test_refutation_and_discriminator_coverage(self):
        case = {"expect": {"finding_ids": [], "verdict": "insufficient_evidence"}}
        findings = [finding("F-A-001")]
        ledger = {
            "claims": [
                {"claim_id": "C-1", "text": "а", "support": [{"finding_id": "F-A-001"}],
                 "confidence": 0.4, "step": "activity",
                 "refutation": {"negation": "не было", "outcome": "survived"}},
                {"claim_id": "C-2", "text": "б", "support": [{"finding_id": "F-A-001"}],
                 "confidence": 0.4, "step": "activity"},
            ],
            "hypotheses": [
                {"hypothesis_id": "H-1", "discriminator": {"question": "что?"}},
                {"hypothesis_id": "H-2"},
            ],
        }
        metrics = metrics_for(case, findings, ledger, verdict="insufficient_evidence")
        self.assertEqual(metrics["refutation_coverage"], 0.5)
        self.assertEqual(metrics["claims_without_refutation"], 1)
        self.assertEqual(metrics["discriminator_coverage"], 0.5)
        self.assertEqual(metrics["hypotheses_without_discriminator"], 1)
        self.assertEqual(metrics["refusal_accuracy"], 1.0)

    def test_wrong_verdict_is_counted(self):
        case = {"expect": {"finding_ids": [], "verdict": "insufficient_evidence"}}
        metrics = metrics_for(case, [], {"claims": [], "hypotheses": []}, verdict="sufficient_evidence")
        self.assertEqual(metrics["refusal_accuracy"], 0.0)

    def test_aggregate_skips_failed_cases(self):
        good = {
            "status": "ok",
            "metrics": {
                "protocol_violations": 2,
                "citation_completeness": 0.5,
                "finding_recall": 1.0,
                "extra_findings": 1,
                "refutation_coverage": 0.5,
                "claims_without_refutation": 1,
                "discriminator_coverage": 0.0,
                "hypotheses_without_discriminator": 2,
                "refusal_accuracy": 0.0,
                "latency_s": 10.0,
                "calls": 5,
            },
        }
        partial = json.loads(json.dumps(good))
        partial["status"] = "partial"
        partial["errors"] = ["сеть отвалилась"]
        partial["metrics"]["protocol_violations"] = 1
        summary = run_skill.aggregate_records([good, partial, {"status": "error", "metrics": {}}])
        self.assertEqual(summary["cases"], 3)
        self.assertEqual(summary["processed"], 2)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["failed_attempts"], 1)
        self.assertEqual(summary["protocol_violations"], 3)
        self.assertEqual(summary["claims_without_refutation"], 2)
        self.assertEqual(summary["hypotheses_without_discriminator"], 4)


class StubPerception:
    """Подмена модели: сцена и ответ заданы заранее, сети нет."""

    def __init__(self, scene, answer):
        self.scene = scene
        self.answer = answer
        self.prompts = []

    def scene_graph(self, image_path, save_raw=None):
        if save_raw:
            Path(save_raw).write_text(
                json.dumps({"calls": [{"pass": "inventory"}], "scene": self.scene}, ensure_ascii=False),
                encoding="utf-8",
            )
        return self.scene, {"calls": 2, "latency_ms": 10, "model": "stub"}

    def call(self, image_b64, media_type, prompt, max_tokens=3000):
        self.prompts.append(prompt)
        return {"content": [{"type": "text", "text": self.answer}], "usage": {}}, 11

    def text_of(self, payload):
        return payload["content"][0]["text"]

    def extract_json(self, text):
        return json.loads(text)


class RunCaseTests(unittest.TestCase):
    def test_artifacts_are_written_and_metrics_counted(self):
        answer = json.dumps({
            "claims": [{
                "claim_id": "C-1", "kind": "inference", "text": "На столе пылевой контур",
                "support": [{"finding_id": "F-ABS-001"}], "confidence": 0.4, "step": "activity",
                "provisional": True, "falsification": "Посветить боковым светом",
                "refutation": {"negation": "контура не было", "outcome": "survived", "note": "виден"},
            }],
            "hypotheses": [{
                "hypothesis_id": "H-1", "text": "Предмет убрали недавно", "claims": ["C-1"],
                "status": "open", "step": "activity",
                "discriminator": {"question": "вогнутый контур или выпуклый?",
                                 "would_confirm": "вогнутый", "would_refute": "выпуклый"},
            }],
        }, ensure_ascii=False)
        stub = StubPerception(SCENE, answer)
        phases = run_skill.load_skill()["phases"]
        rules = run_skill.load_rules(["absence"])
        case = {
            "id": "fixture",
            "image": "eval/real/images/clean-kitchen-dining.jpg",
            "packs": ["absence"],
            "expect": {"finding_ids": ["F-ABS-001"], "verdict": "sufficient_evidence"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "fixture"
            metrics = run_skill.run_case(case, phases, rules, stub, run_dir)
            for name in ("scene.json", "findings.json", "ledger.json", "answer.txt", "raw.json"):
                self.assertTrue((run_dir / name).exists(), name)
            raw = json.loads((run_dir / "raw.json").read_text(encoding="utf-8"))
            self.assertIn("phases-4-6", [entry["pass"] for entry in raw["calls"]])
            self.assertIn("дискриминатор", stub.prompts[0])
        self.assertEqual(metrics["protocol_violations"], 0)
        self.assertEqual(metrics["citation_completeness"], 1.0)
        self.assertEqual(metrics["finding_recall"], 1.0)
        self.assertEqual(metrics["refutation_coverage"], 1.0)
        self.assertEqual(metrics["discriminator_coverage"], 1.0)
        self.assertEqual(metrics["claims_without_refutation"], 0)
        self.assertEqual(metrics["hypotheses_without_discriminator"], 0)
        self.assertEqual(metrics["verdict"], "sufficient_evidence")
        self.assertEqual(metrics["refusal_accuracy"], 1.0)

    def test_missing_refutation_is_visible_in_the_metrics(self):
        answer = json.dumps({
            "claims": [{
                "claim_id": "C-1", "text": "Утверждение без отрицания",
                "support": [{"finding_id": "F-ABS-001"}], "confidence": 0.4, "step": "activity",
                "provisional": True,
            }],
            "hypotheses": [],
        }, ensure_ascii=False)
        stub = StubPerception(SCENE, answer)
        case = {
            "id": "fixture",
            "image": "eval/real/images/clean-kitchen-dining.jpg",
            "packs": ["absence"],
            "expect": {"finding_ids": ["F-ABS-001"], "verdict": "sufficient_evidence"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            metrics = run_skill.run_case(
                case, run_skill.load_skill()["phases"], run_skill.load_rules(["absence"]),
                stub, Path(tmp) / "fixture")
        self.assertGreaterEqual(metrics["protocol_violations"], 1)
        self.assertEqual(metrics["refutation_coverage"], 0.0)
        self.assertEqual(metrics["claims_without_refutation"], 1)


class CliTests(unittest.TestCase):
    def _run(self, args):
        environ = dict(os.environ)
        for name in ("MINIMAX2_API_KEY", "MINIMAX_API_KEY", "MINIMAX_API_KEY_2"):
            environ.pop(name, None)
        return subprocess.run(
            [sys.executable, str(ROOT / "tools/run_skill.py")] + args,
            capture_output=True, text=True, env=environ, cwd=str(ROOT), check=False,
        )

    def test_offline_prints_the_plan_and_exits_zero(self):
        result = self._run(["--offline"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("кейсов в плане", result.stdout)
        self.assertIn("Фаза", result.stdout.replace("фазы", "Фаза"))

    def test_missing_key_gives_a_clear_error(self):
        result = self._run(["--limit", "1"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MINIMAX2_API_KEY", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
