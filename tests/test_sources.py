"""Ведомость источников обязано совпадать с правилами.

Правило со ссылкой на непроверенный источник молча удерживает потолок
уверенности на 0.5. Ведомость (`docs/SOURCES.md`) — единственное место, где
зафиксировано, что источник проверен. Если ведомость отстаёт от правил, эта
защита исчезает незаметно.

Тесты работают без сети: читаются только файлы репозитория.
"""

import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import check_sources  # noqa: E402

LEDGER_PATH = ROOT / "docs" / "SOURCES.md"
VERDICTS = ("confirmed", "partial", "not_found")


def ledger_text():
    return LEDGER_PATH.read_text(encoding="utf-8")


class LedgerCoverageTests(unittest.TestCase):
    def test_ledger_covers_every_source_used_by_rules(self):
        sources = check_sources.load_rules()
        entries, _ = check_sources.parse_ledger(ledger_text())
        missing = sorted(ref for ref in sources if ref not in entries)
        self.assertEqual(missing, [], f"источники правил без записи в ведомости: {missing}")

    def test_ledger_has_no_entries_for_unknown_sources(self):
        sources = check_sources.load_rules()
        entries, _ = check_sources.parse_ledger(ledger_text())
        stale = sorted(ref for ref in entries if ref not in sources)
        self.assertEqual(stale, [], f"ведомость ссылается на несуществующие источники: {stale}")

    def test_every_entry_has_exactly_one_valid_verdict(self):
        entries, _ = check_sources.parse_ledger(ledger_text())
        self.assertTrue(entries, "ведомость пуста")
        for ref, entry in entries.items():
            self.assertIn(entry["verdict"], VERDICTS, f"недопустимый вердикт у {ref!r}")

    def test_entry_rules_match_the_rules_that_use_the_source(self):
        sources = check_sources.load_rules()
        entries, _ = check_sources.parse_ledger(ledger_text())
        for ref, entry in entries.items():
            self.assertEqual(
                sorted(entry["rules"]),
                sorted(sources[ref]["rules"]),
                f"перечень правил в ведомости разошёлся с правилами для {ref!r}",
            )

    def test_entry_carries_note_and_date(self):
        entries, _ = check_sources.parse_ledger(ledger_text())
        for ref, entry in entries.items():
            self.assertTrue(entry["notes"], f"у записи {ref!r} нет note из правил")


class RaisableSectionTests(unittest.TestCase):
    def setUp(self):
        self.text = ledger_text()
        self.entries, _ = check_sources.parse_ledger(self.text)
        self.mapping = check_sources.rule_source_map()

    def _confirmed_rules(self):
        found = []
        for rule_id, refs in self.mapping.items():
            verdicts = [self.entries.get(ref, {}).get("verdict") for ref in refs]
            if verdicts and all(v == "confirmed" for v in verdicts):
                found.append(rule_id)
        return sorted(found)

    def test_rules_with_confirmed_source_are_listed_as_raisable(self):
        raisable = check_sources.parse_raisable(self.text)
        expected = self._confirmed_rules()
        self.assertEqual(
            sorted(raisable),
            expected,
            "раздел «потолок которых можно поднять» разошёлся с confirmed-источниками",
        )

    def test_raisable_section_has_no_rules_without_confirmed_source(self):
        raisable = check_sources.parse_raisable(self.text)
        expected = set(self._confirmed_rules())
        self.assertEqual(sorted(set(raisable) - expected), [])


class CheckerBehaviourTests(unittest.TestCase):
    def test_checker_reports_a_consistent_ledger(self):
        errors, rows, summary = check_sources.check()
        self.assertEqual(errors, [], f"ведомость противоречит правилам: {errors}")
        self.assertTrue(rows)
        self.assertEqual(summary["ledger_entries"], summary["sources"])

    def test_checker_fails_on_incomplete_ledger(self):
        text = ledger_text()
        broken = re.sub(r"^### 3\.32 .*$", "", text, flags=re.M)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "SOURCES.md"
            path.write_text(broken, encoding="utf-8")
            errors, _, _ = check_sources.check(ledger_path=path)
        self.assertTrue(errors, "пропуск записи в ведомости должен давать ошибку")

    def test_checker_fails_on_unknown_verdict(self):
        text = ledger_text()
        broken = text.replace("- **вердикт:** confirmed", "- **вердикт:** maybe", 1)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "SOURCES.md"
            path.write_text(broken, encoding="utf-8")
            errors, _, _ = check_sources.check(ledger_path=path)
        self.assertTrue(any("вердикт" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
