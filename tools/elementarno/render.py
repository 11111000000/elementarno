"""Rendering layer: personas, modes, report assembly.

A persona is a renderer over an already validated ledger. It may change tone,
ordering and rhetoric. It may not change a confidence, add an evidence or
soften a refusal. Every sentence keeps its citation.
"""

PERSONAS = {}


def _persona(name):
    def wrap(fn):
        PERSONAS[name] = fn
        return fn
    return wrap


@_persona("doyle")
def _doyle():
    return {
        "label": "Артур Конан Дойл",
        "open": "Позвольте представить вам, мой дорогой Уотсон, наши улики. Фотография молчит, но молчит она не зря.",
        "fact": "{title} — доказательство [{rule_id}], уверенность {confidence:.0%}. Отсюда следует: {claim}",
        "caveat": "Однако же — {confounds}.",
        "hypothesis": "Отсюда версия: {text} [{rule_id}]",
        "refused": "Увы, мой дорогой Уотсон, улик здесь недостаточно. Доказательство требует фактов, а не догадок, и я откажусь строить версии на дыму.",
        "close": "Итак, {count} улик(и) ведут нас к версии: {hypothesis}. Проверить её надлежит так: {test}",
        "footer": "Повествование воспроизведено в стиле Артура Конан Дойла по данным протокола доказательности. Стиль не есть источник утверждений: каждая строка привязана к помеченной улике.",
    }


@_persona("plain")
def _plain():
    return {
        "label": "нейтральный",
        "open": "Что видно на фотографии и что из этого следует.",
        "fact": "{claim} (основание: {title} [{rule_id}], уверенность {confidence:.0%})",
        "caveat": "Оговорки: {confounds}.",
        "hypothesis": "Версия: {text} [{rule_id}]",
        "refused": "Улик недостаточно для вывода.",
        "close": "Итог: {count} улик(и), ведущая версия — {hypothesis}. Проверка: {test}",
        "footer": "Текст построен протоколом доказательности: каждое утверждение связано с правилом и источником.",
    }


@_persona("forensic")
def _forensic():
    return {
        "label": "криминалистический",
        "open": "Протокол осмотра фотографии. Ниже — только то, что подтверждается уликами.",
        "fact": "{claim} Правовое основание: {title} [{rule_id}], достоверность {confidence:.0%}.",
        "caveat": "Ограничения вывода: {confounds}.",
        "hypothesis": "Объяснительная версия: {text} [{rule_id}]",
        "refused": "Совокупность улик недостаточна для формулирования вывода.",
        "close": "Итого {count} улик(и). Приоритетная версия: {hypothesis}. Проверочная процедура: {test}",
        "footer": "Выводы носят вероятностный характер и предназначены для проверки человеком.",
    }


def render(mode, findings, claims, hypotheses, verdict, persona=None, validation=None):
    if persona and persona in PERSONAS:
        templates = PERSONAS[persona]()
    else:
        templates = PERSONAS["plain"]()
    findings_by_id = {f["finding_id"]: f for f in findings}
    lines = [templates["open"], ""]

    for claim in claims:
        support = claim.get("support") or []
        if not support:
            continue
        finding = findings_by_id.get(support[0]["finding_id"])
        if not finding:
            continue
        lines.append(templates["fact"].format(
            claim=claim["text"],
            title=finding["title"],
            rule_id=finding["rule_id"],
            confidence=claim["confidence"],
        ))
        confounds = finding.get("confounds") or []
        if confounds:
            lines.append(templates["caveat"].format(confounds="; ".join(confounds)))
        if claim.get("falsification"):
            lines.append(f"Проверка: {claim['falsification']}")
        lines.append("")

    if verdict == "insufficient_evidence":
        lines.append(templates["refused"])
    elif hypotheses:
        top = hypotheses[0]
        support = [findings_by_id[f] for f in (top.get("support_findings") or []) if f in findings_by_id]
        strongest = max(support, key=lambda f: f["confidence_prior"]) if support else None
        test = (strongest or {}).get("falsification", {}).get("physical_test", "—")
        lines.append(templates["close"].format(
            count=len(findings),
            hypothesis=top["text"],
            test=test,
        ))
        rejected = [h for h in hypotheses if h.get("status") == "rejected"]
        if rejected:
            lines.append(f"Отвергнуто версий: {len(rejected)} (см. kill-log).")

    lines.append("")
    if validation and validation.get("errors"):
        lines.append(f"Предупреждение протокола: отклонено утверждений — {len(validation['errors'])}.")
    lines.append(templates["footer"])
    return "\n".join(lines)
