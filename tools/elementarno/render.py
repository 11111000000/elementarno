"""Рендеринг: персоны, режимы, лестница обобщения.

Лестница идёт от общего к частному: сцена → активность → присутствие →
действие. Каждая ступень опирается на свои улики, и ни одна ступень не
перескакивает через следующую.

Персона — рендерер над уже проверенным леджером. Она меняет тон, но не
содержание: утверждения, уверенности и цитаты остаются теми же.
"""

LADDER = ["scene", "activity", "presence", "role", "action"]

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
        "steps": {
            "scene": "Место действия:",
            "activity": "Чем здесь занимались:",
            "presence": "Кто был в сцене:",
            "role": "Чем он занимался:",
            "action": "Что именно делали:",
        },
        "fact": "{title} — доказательство [{rule_id}], уверенность {confidence:.0%}. Отсюда следует: {claim}",
        "caveat": "Однако же — {confounds}.",
        "hypothesis": "{text} [{rule_id}]",
        "refused": "Увы, мой дорогой Уотсон, улик здесь недостаточно. Доказательство требует фактов, а не догадок, и я откажусь строить версии на дыму.",
        "close": "Итак, {count} улик(и) ведут нас к версии: {hypothesis}. Проверить её надлежит так: {test}",
        "footer": "Повествование воспроизведено в стиле Артура Конан Дойла по данным протокола доказательности. Стиль не есть источник утверждений: каждая строка привязана к помеченной улике.",
    }


@_persona("plain")
def _plain():
    return {
        "label": "нейтральный",
        "open": "Что видно на фотографии и что из этого следует.",
        "steps": {
            "scene": "Место:",
            "activity": "Активность:",
            "presence": "Присутствовали:",
            "role": "Чем занимались:",
            "action": "Действия:",
        },
        "fact": "{claim} (основание: {title} [{rule_id}], уверенность {confidence:.0%})",
        "caveat": "Оговорки: {confounds}.",
        "hypothesis": "{text} [{rule_id}]",
        "refused": "Улик недостаточно для вывода.",
        "close": "Итог: {count} улик(и), ведущая версия — {hypothesis}. Проверка: {test}",
        "footer": "Текст построен протоколом доказательности: каждое утверждение связано с правилом и источником.",
    }


@_persona("forensic")
def _forensic():
    return {
        "label": "исследовательский",
        "open": "Протокол разбора фотографии. Ниже — только то, что подтверждается уликами.",
        "steps": {
            "scene": "Объект съёмки:",
            "activity": "Активность:",
            "presence": "Присутствовали:",
            "role": "Чем занимались:",
            "action": "Действия:",
        },
        "fact": "{claim} Основание: {title} [{rule_id}], достоверность {confidence:.0%}.",
        "caveat": "Ограничения вывода: {confounds}.",
        "hypothesis": "{text} [{rule_id}]",
        "refused": "Совокупность улик недостаточна для формулирования вывода.",
        "close": "Итого {count} улик(и). Приоритетная версия: {hypothesis}. Проверочная процедура: {test}",
        "footer": "Выводы носят вероятностный характер и предназначены для проверки человеком.",
    }


AUDIT_TEMPLATES = {
    "label": "аудит",
    "open": "Протокол осмотра фотографии. Ниже — только то, что подтверждается уликами.",
    "steps": {
        "scene": "Объект съёмки:",
        "activity": "Активность:",
        "presence": "Присутствовали:",
        "role": "Чем занимались:",
        "action": "Действия:",
    },
    "fact": "{claim} [{rule_id}], уверенность {confidence:.0%}",
    "caveat": "Оговорки: {confounds}.",
    "hypothesis": "{text} [{rule_id}]",
    "refused": "Совокупность улик недостаточна для формулирования вывода.",
    "close": "Итого {count} улик(и).",
    "footer": "Режим аудита: без гипотез и без персонажа — только утверждения со ссылками на правила.",
}


def render(mode, findings, claims, hypotheses, verdict, persona=None, validation=None):
    if mode == "audit":
        templates = AUDIT_TEMPLATES
        claims = [c for c in claims if c.get("kind") in ("observation", "inference")]
        hypotheses = []
    else:
        templates = PERSONAS[persona]() if persona in PERSONAS else PERSONAS["plain"]()
    findings_by_id = {f["finding_id"]: f for f in findings}
    lines = [templates["open"], ""]

    for step in LADDER:
        group = [c for c in claims if (c.get("step") or "action") == step]
        group_hypotheses = [h for h in hypotheses if (h.get("step") or "action") == step]
        if not group and not group_hypotheses:
            continue
        lines.append(templates["steps"][step])
        for claim in group:
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
        for hypothesis in group_hypotheses:
            support = [findings_by_id[f] for f in (hypothesis.get("support_findings") or [])
                       if f in findings_by_id]
            rule_ids = ", ".join(sorted({f["rule_id"] for f in support})) or "—"
            lines.append(templates["hypothesis"].format(text=hypothesis["text"], rule_id=rule_ids))
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
