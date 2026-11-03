"""Сверка ведомости источников (docs/SOURCES.md) с правилами (rules/*.json).

Ведомость отвечает на вопрос «существует ли источник и подтверждает ли он
своё note». Правило, ссылающееся на источник, которого в ведомости нет, —
это ссылка, которую никто не проверил: она молча удерживает потолок
уверенности на 0.5.

Проверка работает без сети: читаются только файлы репозитория.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES_DIR = ROOT / "rules"
LEDGER_PATH = ROOT / "docs" / "SOURCES.md"

VERDICTS = ("confirmed", "partial", "not_found")
RAISABLE_HEADING = "правила, потолок которых можно поднять"
LEDGER_HEADING = "реестр источников"
VERDICT_RE = re.compile(r"^-\s+\*\*вердикт:\*\*\s*(\S+)")
RULES_RE = re.compile(r"^-\s+\*\*правила:\*\*\s*(.+)$")
NOTE_RE = re.compile(r"^-\s+\*\*note в правилах:\*\*\s*(.+)$")
ALIAS_RE = re.compile(r"^-\s+\*\*входит в запись:\*\*\s*`(.+)`")
RULE_ID_RE = re.compile(r"\b[A-Z]{2,6}-\d{3}\b")


def load_rules(rules_dir=RULES_DIR, aliases=None):
    """Собрать источники из всех паков: ref -> {notes, rules, verified}.

    `aliases` сопоставляет варианты строки ref одной записи ведомости:
    правила могут ссылаться на один документ разными строками, а запись в
    ведомости — одна.
    """
    if aliases is None:
        aliases = ledger_aliases()
    sources = {}
    for path in sorted(Path(rules_dir).glob("*.json")):
        if path.name == "registry.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for rule in payload.get("rules", []):
            for source in rule.get("sources", []):
                ref = source.get("ref")
                if not ref:
                    continue
                ref = aliases.get(ref, ref)
                entry = sources.setdefault(ref, {"notes": [], "rules": [], "verified": set()})
                note = source.get("note")
                if note and note not in entry["notes"]:
                    entry["notes"].append(note)
                if rule["id"] not in entry["rules"]:
                    entry["rules"].append(rule["id"])
                entry["verified"].add(source.get("verified"))
    return sources


def _section(text, heading):
    """Вырезать кусок документа по заголовку раздела (## ...)."""
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.startswith("## ") and heading in line.lower():
            start = index + 1
            break
    if start is None:
        return []
    chunk = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        chunk.append(line)
    return chunk


def parse_ledger(text):
    """Разобрать ведомость: ref -> {verdict, rules, notes, aliases}."""
    entries = {}
    order = []
    current = None
    field = None
    for line in _section(text, LEDGER_HEADING):
        if line.startswith("### "):
            head = line[4:].strip()
            if "`" in head:
                ref = head.split("`")[1].strip()
            else:
                ref = head.split(". ", 1)[-1].strip()
            current = {"ref": ref, "verdict": None, "rules": [], "notes": [], "aliases": []}
            entries.setdefault(ref, current)
            order.append(ref)
            continue
        if current is None:
            continue
        stripped = line.strip()
        match = VERDICT_RE.match(stripped)
        if match:
            current["verdict"] = match.group(1).strip("`*")
            field = "verdict"
            continue
        match = RULES_RE.match(stripped)
        if match:
            for token in RULE_ID_RE.findall(match.group(1)):
                if token not in current["rules"]:
                    current["rules"].append(token)
            field = "rules"
            continue
        match = NOTE_RE.match(stripped)
        if match:
            current["notes"].append(match.group(1).strip())
            field = "notes"
            continue
        match = ALIAS_RE.match(stripped)
        if match:
            current["aliases"].append(match.group(1).strip())
            field = "aliases"
            continue
        if stripped and line.startswith("  ") and field == "rules":
            for token in RULE_ID_RE.findall(stripped):
                if token not in current["rules"]:
                    current["rules"].append(token)
    return entries, order


def ledger_aliases(text=None, ledger_path=LEDGER_PATH):
    """Варианты строки ref, которые ведут в одну запись ведомости."""
    if text is None:
        text = Path(ledger_path).read_text(encoding="utf-8")
    entries, _ = parse_ledger(text)
    aliases = {}
    for ref, entry in entries.items():
        for alias in entry.get("aliases", []):
            aliases[alias] = ref
    return aliases


def parse_raisable(text):
    """Правила, перечисленные в разделе «потолок которых можно поднять»."""
    rules = []
    for line in _section(text, RAISABLE_HEADING):
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        for token in RULE_ID_RE.findall(stripped):
            if token not in rules:
                rules.append(token)
    return rules


def rule_source_map(rules_dir=RULES_DIR, aliases=None):
    """Правило -> список источников (в канонической записи ведомости)."""
    if aliases is None:
        aliases = ledger_aliases()
    mapping = {}
    for path in sorted(Path(rules_dir).glob("*.json")):
        if path.name == "registry.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for rule in payload.get("rules", []):
            refs = []
            for source in rule.get("sources", []):
                ref = source.get("ref")
                if not ref:
                    continue
                ref = aliases.get(ref, ref)
                if ref not in refs:
                    refs.append(ref)
            mapping[rule["id"]] = refs
    return mapping


def raw_refs(rules_dir=RULES_DIR):
    """Все строки ref из правил, без приведения к канонической записи."""
    refs = set()
    for path in sorted(Path(rules_dir).glob("*.json")):
        if path.name == "registry.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for rule in payload.get("rules", []):
            for source in rule.get("sources", []):
                if source.get("ref"):
                    refs.add(source["ref"])
    return refs


def check(rules_dir=RULES_DIR, ledger_path=LEDGER_PATH):
    """Сверить ведомость с правилами. Возвращает (ошибки, таблица, сводка)."""
    text = Path(ledger_path).read_text(encoding="utf-8")
    entries, _ = parse_ledger(text)
    aliases = ledger_aliases(text)
    sources = load_rules(rules_dir, aliases)
    raisable = parse_raisable(text)
    mapping = rule_source_map(rules_dir, aliases)
    raw = raw_refs(rules_dir)

    errors = []
    for ref in sources:
        if ref not in entries:
            errors.append(f"источник из правил отсутствует в ведомости: {ref!r}")
    for ref in entries:
        if ref not in sources:
            errors.append(f"ведомость ссылается на несуществующий источник: {ref!r}")
    for ref, entry in entries.items():
        if entry["verdict"] is None:
            errors.append(f"у записи нет вердикта: {ref!r}")
        elif entry["verdict"] not in VERDICTS:
            errors.append(f"недопустимый вердикт {entry['verdict']!r} у {ref!r}")
        for alias in entry.get("aliases", []):
            if alias in entries:
                errors.append(f"псевдоним записи совпадает с другой записью: {alias!r}")
            if alias not in raw:
                errors.append(f"псевдоним не соответствует ни одной ссылке правил: {alias!r}")

    verdict_of = {ref: entries[ref]["verdict"] for ref in entries if entries[ref]["verdict"]}
    confirmed_rules = []
    rows = []
    for rule_id in sorted(mapping):
        refs = mapping[rule_id]
        verdicts = [verdict_of.get(ref) for ref in refs]
        all_confirmed = bool(verdicts) and all(v == "confirmed" for v in verdicts)
        if all_confirmed:
            confirmed_rules.append(rule_id)
        for ref, verdict in zip(refs, verdicts, strict=True):
            rows.append((rule_id, ref, verdict, all_confirmed))

    for rule_id in confirmed_rules:
        if rule_id not in raisable:
            errors.append(f"правило с confirmed-источником не попало в раздел «{RAISABLE_HEADING}»: {rule_id}")
    for rule_id in raisable:
        if rule_id not in confirmed_rules:
            errors.append(f"в разделе «{RAISABLE_HEADING}» лишнее правило: {rule_id}")

    summary = {
        "sources": len(sources),
        "raw_refs": len(raw),
        "ledger_entries": len(entries),
        "rules": len(mapping),
        "confirmed": sum(1 for v in verdict_of.values() if v == "confirmed"),
        "partial": sum(1 for v in verdict_of.values() if v == "partial"),
        "not_found": sum(1 for v in verdict_of.values() if v == "not_found"),
        "raisable": confirmed_rules,
    }
    return errors, rows, summary


def render(rows, summary):
    """Таблица «правило — источник — вердикт — можно ли поднимать потолок»."""
    width_rule = max([len("правило")] + [len(r[0]) for r in rows]) + 2
    width_source = max([len("источник")] + [min(len(r[1]), 60) for r in rows]) + 2
    lines = []
    lines.append(
        f"{'правило':<{width_rule}}{'источник':<{width_source}}{'вердикт':<12}потолок"
    )
    lines.append("-" * (width_rule + width_source + 22))
    for rule_id, ref, verdict, raisable in rows:
        mark = "да" if raisable else "нет"
        lines.append(
            f"{rule_id:<{width_rule}}{ref[:60]:<{width_source}}{str(verdict):<12}{mark}"
        )
    lines.append("")
    lines.append(
        "источников: {sources} (в ведомости {ledger_entries}; строк ref в правилах — {raw_refs}), правил: {rules}".format(
            **summary
        )
    )
    lines.append(
        "вердикты: confirmed {confirmed}, partial {partial}, not_found {not_found}".format(**summary)
    )
    lines.append("потолок можно поднять по источникам: " + (", ".join(summary["raisable"]) or "нет"))
    return "\n".join(lines)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    rules_dir = Path(argv[0]) if argv else RULES_DIR
    ledger_path = Path(argv[1]) if len(argv) > 1 else LEDGER_PATH
    errors, rows, summary = check(rules_dir, ledger_path)
    print(render(rows, summary))
    if errors:
        print("\nВЕДОМОСТЬ НЕПОЛНА:")
        for error in errors:
            print("  -", error)
        return 1
    print("\nВедомость полна и согласована с правилами.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
