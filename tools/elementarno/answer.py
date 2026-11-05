"""Ответы на вопросы по разбору.

Разбор — не отчёт, а диалог: на вопрос «что здесь происходило», «кто был»,
«что это за предмет», «что проверить» должен быть ответ, собранный из того,
что уже установлено: фактов, улик, утверждений и версий.

Три правила ответа:

* ответ опирается на улики и утверждения и называет их;
* уверенность ответа равна уверенности его основания, а не уверенности тона;
* на вопрос, на который в разборе нет ответа, ответа нет: это честный
  результат, а не отказ по умолчанию.
"""

import re

from .facts import facts

QUESTION_KINDS = [
    ("activity", ["происходило", "происходило", "делали", "занимались", "деятельность", "чем занимались",
                  "что делали", "активност", "происходил"]),
    ("presence", ["кто был", "кто там", "есть ли кто", "кто-то", "присутств", "кто это был",
                  "кто-нибудь", "кем работал", "кто работал", "кем занят", "кто здесь",
                  "кем здесь", "кто такой"]),
    ("identity", ["что это", "что за", "какой предмет", "из чего", "какие предметы", "что лежит",
                  "что стоит", "что в кадре", "перечисл"]),
    ("check", ["проверить", "проверк", "что снять", "дальше", "следующ", "опроверг", "тест",
               "как узнать", "как проверить"]),
    ("why", ["почему", "зачем", "из-за чего", "причин"]),
    ("when", ["когда", "время", "сколько времени", "давно", "недавно", "вчера", "сегодня"]),
]

REFUSAL = {
    "activity": "По разбору нельзя сказать, что именно здесь делали: следов деятельности в кадре не найдено.",
    "presence": "В кадре нет подтверждённого присутствия человека: утверждать обратное оснований нет.",
    "identity": "Состав сцены есть в фактах, но на этот вопрос ответа в разборе нет.",
    "check": "Проверять пока нечего: утверждений, которые можно опровергнуть, нет.",
    "why": "Причину по фотографии не установить: в разборе нет ни одного утверждения о причине.",
    "when": "Время по кадру не видно: ни даты, ни свежести следов, ни состояния напитка измерить нечем.",
    "default": "На этот вопрос в разборе нет ответа: ни одно утверждение его не касается.",
}


def classify(question):
    low = (question or "").lower()
    for kind, words in QUESTION_KINDS:
        if any(word in low for word in words):
            return kind
    return "default"


STOP_WORDS = {"как", "что", "кто", "где", "когда", "почему", "зачем", "какой", "какая",
              "был", "была", "было", "тут", "там", "этот", "эта", "это", "для", "или",
              "работали", "работал", "видно", "кадре", "сцене", "фото", "фотографии"}


def _mentions(question, text):
    """Есть ли в утверждении слово из вопроса — грубое, но честное совпадение."""
    words = {w for w in re.findall(r"[\wа-яё]+", (question or "").lower()) if len(w) > 3}
    words -= STOP_WORDS
    if not words:
        return False
    haystack = (text or "").lower()
    return any(word in haystack for word in words)


def _claim_line(claim, findings_by_id):
    rules = sorted({findings_by_id[s["finding_id"]]["rule_id"]
                    for s in claim.get("support") or [] if s.get("finding_id") in findings_by_id})
    return {
        "claim_id": claim.get("claim_id"),
        "text": claim.get("text"),
        "step": claim.get("step"),
        "confidence": claim.get("confidence"),
        "rules": rules,
        "finding_ids": [s.get("finding_id") for s in claim.get("support") or []],
        "caveats": claim.get("confounds") or [],
        "refutation": claim.get("refutation") or {},
        "falsification": claim.get("falsification") or "",
    }


def answer(question, scene, findings, claims=None, hypotheses=None):
    """Ответ на вопрос: текст, основание, уверенность, что дальше проверить."""
    claims = claims or []
    hypotheses = hypotheses or []
    findings_by_id = {f["finding_id"]: f for f in findings or []}
    kind = classify(question)
    prepared = [_claim_line(c, findings_by_id) for c in claims if c.get("support")]

    if kind == "identity":
        scene_facts = [f for f in facts(scene) if f["kind"] in ("presence", "state", "fill", "quantity")]
        if not scene_facts:
            return {"question": question, "kind": kind, "answer": REFUSAL["identity"],
                    "basis": [], "uncertainty": 1.0, "caveats": [], "next": []}
        lines = [f["text"] for f in scene_facts[:12]]
        return {
            "question": question, "kind": kind,
            "answer": "В кадре: " + "; ".join(lines),
            "basis": [f["fact_id"] for f in scene_facts[:12]],
            "uncertainty": round(1 - max(f["confidence"] for f in scene_facts), 3),
            "caveats": ["перечень предметов — это то, что модель смогла опознать, а не полный список"],
            "next": [],
        }

    if kind == "check":
        steps = []
        for claim in prepared:
            if claim["falsification"]:
                steps.append(f"{claim['text']} — {claim['falsification']}")
        for hypothesis in hypotheses:
            disc = (hypothesis.get("discriminator") or {})
            if disc.get("question"):
                steps.append(f"развести версии: {disc['question']}")
        if not steps:
            return {"question": question, "kind": kind, "answer": REFUSAL["check"],
                    "basis": [], "uncertainty": 1.0, "caveats": [], "next": []}
        return {
            "question": question, "kind": kind,
            "answer": "Что проверить: " + "; ".join(steps[:6]),
            "basis": [c["claim_id"] for c in prepared[:6]],
            "uncertainty": 0.4,
            "caveats": ["проверка убирает неопределённость, а не подтверждает версию целиком"],
            "next": steps[:6],
        }

    if kind == "when":
        return {"question": question, "kind": kind, "answer": REFUSAL["when"],
                "basis": [], "uncertainty": 1.0,
                "caveats": ["свежесть видна только там, где есть для этого след: пыль, засохшая жидкость, смятая ткань"],
                "next": ["снять след, который высох и оставил границу: сухое пятно на плитке, примятая подушка"]}

    if kind == "default":
        matched = [claim for claim in prepared if _mentions(question, claim["text"])]
        if not matched:
            return {"question": question, "kind": kind, "answer": REFUSAL["default"],
                    "basis": [], "uncertainty": 1.0, "caveats": [], "next": []}
        best = max(matched, key=lambda claim: claim["confidence"] or 0.0)
        return {
            "question": question, "kind": kind,
            "answer": best["text"] + (f" И ещё: {matched[0]['text']}" if len(matched) > 1 else ""),
            "basis": best["finding_ids"],
            "uncertainty": round(1 - (best["confidence"] or 0), 3),
            "caveats": best["caveats"],
            "next": [best["falsification"]] if best["falsification"] else [],
        }

    step_filter = {"activity": ("activity", "presence", "role", "action"),
                   "presence": ("presence", "role", "action"),
                   "why": ("scene", "activity", "presence", "role", "action")}[kind]

    ranked = []
    for claim in prepared:
        if (claim["step"] or "action") not in step_filter:
            continue
        weight = claim["confidence"] or 0.0
        if kind == "presence" and claim["step"] == "presence":
            weight += 0.1
        ranked.append((weight, claim))
    ranked.sort(key=lambda item: -item[0])

    if not ranked:
        return {"question": question, "kind": kind, "answer": REFUSAL.get(kind, REFUSAL["default"]),
                "basis": [], "uncertainty": 1.0, "caveats": [], "next": []}

    top = ranked[0][1]
    if kind == "why":
        return {
            "question": question, "kind": kind,
            "answer": "Причина прямо не установлена. Ближайшее, что разбор позволяет: " + top["text"],
            "basis": top["finding_ids"],
            "uncertainty": round(1 - (top["confidence"] or 0), 3),
            "caveats": top["caveats"] + ["причина — это всегда гипотеза; здесь она не выдвинута"],
            "next": [top["falsification"]] if top["falsification"] else [],
        }

    alternatives = []
    for hypothesis in hypotheses:
        if (hypothesis.get("step") or "action") not in step_filter:
            continue
        alternatives.append(hypothesis.get("text"))

    answer_text = top["text"]
    also = [claim for _, claim in ranked[1:3]]
    if also:
        answer_text += " И ещё: " + "; ".join(c["text"] for c in also)
    if alternatives:
        answer_text += " (версии: " + "; ".join(alternatives[:3]) + ")"

    uncertainty = 1 - (top["confidence"] or 0)
    if top["refutation"].get("outcome") == "undetermined":
        uncertainty = min(1.0, uncertainty + 0.15)

    return {
        "question": question,
        "kind": kind,
        "answer": answer_text,
        "basis": top["finding_ids"] + [fid for c in also for fid in c["finding_ids"]],
        "uncertainty": round(uncertainty, 3),
        "caveats": top["caveats"],
        "next": [top["falsification"]] if top["falsification"] else [],
    }


def digest(scene, findings, claims=None, hypotheses=None, questions=None):
    """Короткая сводка разбора: факты, связи, версии, ответы."""
    claims = claims or []
    hypotheses = hypotheses or []
    scene_facts = facts(scene)
    return {
        "facts": scene_facts,
        "connections": findings,
        "claims": claims,
        "hypotheses": hypotheses,
        "answers": [answer(q, scene, findings, claims, hypotheses) for q in (questions or [])],
    }
