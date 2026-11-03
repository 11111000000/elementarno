"""Слой рассуждения: из улик — связные утверждения и версии.

Модель не решает, что правда: она формулирует. Правда устанавливается
правилами, а модель связывает улики в утверждения и версии, предлагает
проверки и формулирует оговорки.

Поэтому всё, что модель вернула, проходит через `sanitize_claims`: ссылка на
несуществующую улику, уверенность выше потолка, обвинительная формулировка,
разрыв лестницы — всё это отбрасывается в коде, а не просьбой к модели.
"""

import json
import time

from .ledger import ACCUSATORY_TERMS, LADDER_ORDER, REFUTATION_OUTCOMES, ladder_jump, mentions_personality
from .perception import MiniMaxPerception, PerceptionError

REASONING_PROMPT = """Ты — аналитик, который восстанавливает картину по найденным уликам.

ТЫ НЕ ВЫДУМЫВАЕШЬ УЛИК. Ты можешь использовать только перечисленные улики
(со своими идентификаторами). Каждое утверждение обязано ссылаться на
существующие улики через support.

ГРАНИЦЫ ВЫВОДА О ЛЮДЯХ: допустимы только присутствие, действие, роль или
привычка. Запрещены вина, намерение, мотив и черты характера.

ОГОВОРКИ: у каждой улики есть confounds — альтернативные объяснения. Учитывай
их и переноси в confounds утверждения.

ПРОВЕРКА: у каждого утверждения укажи falsification — что конкретно надо
посмотреть или переснять, чтобы это утверждение опроверглось.

ОТРИЦАНИЕ — обязательная часть протокола. Утверждение, которое идёт дальше
вывода улики, должно нести refutation:
  "negation" — что ты проверял в отрицательной форме («в кадре НЕ было...»);
  "outcome" — "survived" (отрицание не подтвердилось), "refuted" (отрицание
  подтвердилось, утверждение падает) или "undetermined" (не разобрал).
Если outcome="refuted" — не выдавай это утверждение вовсе: выброси его и
запиши, что его убило. Утверждение, которое дословно повторяет вывод улики,
отрицать не нужно: работает опровержение самого правила.

ДИСКРИМИНАТОР: у каждой версии укажи discriminator — вопрос, который её
разведёт с конкурирующими («что было в коробке: блистер или пусто?»), и
что он подтвердил бы (would_confirm) и что опроверг (would_refute). Версии,
которые различаются только словами, неразличимы — их различает вопрос.

ЛЕСТНИЦА: step — одна из: scene, activity, presence, role, action. Утверждение
не может быть «мельче» ступени своих улик.

ФОРМАТ (ТОЛЬКО JSON, без markdown):
{
  "claims": [
    {"claim_id":"C-1","kind":"observation|inference|hypothesis|interpretation",
     "text":"утверждение по-русски, осторожно",
     "support":[{"finding_id":"F-ABS-001"}],
     "confidence":0.4,"step":"activity",
     "confounds":["оговорка"],"falsification":"что проверить","speculative":false,
     "refutation":{"negation":"что проверял в отрицательной форме",
                   "outcome":"survived|refuted|undetermined","note":"чем кончилось"}}
  ],
  "hypotheses": [
    {"hypothesis_id":"H-1","text":"версия по-русски",
     "claims":["C-1","C-2"],"status":"open|rejected","step":"presence",
     "discriminator":{"question":"что развело бы версии",
                      "would_confirm":"что подтвердило бы","would_refute":"что опровергло бы"},
     "kill_log":[{"rule_id":"F-ABS-001","note":"чем убита версия"}]}
  ]
}

kind=interpretation — только для символических догадок, тогда speculative=true
и confidence не выше 0.4.

УЛИКИ:
{findings}

СЦЕНА (кратко): {scene}

Верни JSON."""


class ReasoningError(RuntimeError):
    pass


def _has_term(text, terms):
    lowered = (text or "").lower()
    return [term for term in terms if term in lowered]


def sanitize_claims(claims, findings):
    """Оставить только утверждения, выдерживающие протокол.

    Возвращает (чистые утверждения, {код отбрасывания: количество}).
    """
    findings_by_id = {f["finding_id"]: f for f in findings}
    kept = []
    dropped = {}

    def drop(code):
        dropped[code] = dropped.get(code, 0) + 1

    for claim in claims or []:
        claim_id = claim.get("claim_id")
        support = claim.get("support") or []
        if not support:
            drop("unsupported_claim")
            continue
        known = [s for s in support if s.get("finding_id") in findings_by_id]
        if not known:
            drop("unknown_finding")
            continue

        ceilings = [findings_by_id[s["finding_id"]]["confidence_ceiling"] for s in known]
        ceiling = min(ceilings)
        try:
            confidence = float(claim.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = min(confidence, ceiling)

        provisional = any(findings_by_id[s["finding_id"]].get("provisional") for s in known)
        if provisional:
            confidence = min(confidence, 0.5)
            claim = {**claim, "provisional": True}

        if claim.get("kind") == "interpretation":
            if not claim.get("speculative"):
                claim = {**claim, "speculative": True}
            confidence = min(confidence, 0.4)
        elif claim.get("kind") == "hypothesis" and not claim.get("falsification"):
            drop("hypothesis_without_falsification")
            continue

        if _has_term(claim.get("text"), ACCUSATORY_TERMS):
            drop("accusatory_framing")
            continue
        if mentions_personality(claim.get("text")):
            if claim.get("kind") != "interpretation" or not claim.get("speculative"):
                drop("personality_inference")
                continue

        step = claim.get("step") or "action"
        claim_step = LADDER_ORDER.get(step, 4)
        broken = False
        for support_item in known:
            finding = findings_by_id[support_item["finding_id"]]
            if ladder_jump(step, finding.get("step") or "action") > (2 if claim_step == LADDER_ORDER["action"] else 1):
                broken = True
                break
        if broken:
            drop("ladder_break")
            continue

        refutation = claim.get("refutation") or {}
        negation = (refutation.get("negation") or "").strip()
        outcome = refutation.get("outcome")
        if negation and outcome in REFUTATION_OUTCOMES:
            if outcome == "refuted":
                drop("refuted_by_negation")
                continue
        else:
            refutation = {}

        kept.append({
            "claim_id": claim_id,
            "kind": claim.get("kind", "inference"),
            "text": claim.get("text", ""),
            "support": [{"finding_id": s["finding_id"]} for s in known],
            "confidence": round(confidence, 3),
            "step": step,
            "confounds": claim.get("confounds") or [],
            "falsification": claim.get("falsification"),
            "provisional": bool(provisional),
            "speculative": bool(claim.get("speculative")),
            "refutation": refutation or None,
        })
    return kept, dropped


def sanitize_hypotheses(hypotheses, claims):
    claim_ids = {c["claim_id"] for c in claims}
    kept = []
    dropped = {}
    for hypothesis in hypotheses or []:
        references = [c for c in (hypothesis.get("claims") or []) if c in claim_ids]
        if not references:
            dropped["hypothesis_without_claims"] = dropped.get("hypothesis_without_claims", 0) + 1
            continue
        if hypothesis.get("status") == "rejected" and not hypothesis.get("kill_log"):
            dropped["rejected_without_kill_log"] = dropped.get("rejected_without_kill_log", 0) + 1
            continue
        discriminator = hypothesis.get("discriminator") or {}
        kept.append({
            "hypothesis_id": hypothesis.get("hypothesis_id"),
            "text": hypothesis.get("text", ""),
            "claims": references,
            "status": hypothesis.get("status", "open"),
            "step": hypothesis.get("step", "action"),
            "discriminator": {
                "question": (discriminator.get("question") or "").strip(),
                "would_confirm": (discriminator.get("would_confirm") or "").strip(),
                "would_refute": (discriminator.get("would_refute") or "").strip(),
            } if (discriminator.get("question") or "").strip() else None,
            "kill_log": hypothesis.get("kill_log") or [],
        })
    return kept, dropped


class MiniMaxReasoner:
    def __init__(self, model="MiniMax-M3", api_key=None, timeout=180, think=True):
        self.client = MiniMaxPerception(model=model, api_key=api_key, timeout=timeout, think=think)

    def reason(self, scene, findings, extra_instruction=None, max_attempts=2):
        if not findings:
            return {"claims": [], "hypotheses": []}, {
                "model": self.client.model,
                "latency_ms": 0,
                "calls": 0,
                "dropped": {},
                "skipped": "нет улик — рассуждать не о чем",
            }

        findings_digest = [
            {
                "finding_id": f["finding_id"],
                "rule_id": f["rule_id"],
                "title": f["title"],
                "inference": f["inference"],
                "confounds": f.get("confounds", []),
                "confidence_ceiling": f["confidence_ceiling"],
                "tags": f.get("tags", []),
                "step": f.get("step", "action"),
                "anchors": f.get("anchors", []),
            }
            for f in findings
        ]
        scene_digest = {
            "objects": [{"id": o.get("id"), "category": o.get("category"), "on": o.get("on")}
                        for o in scene.get("objects", [])][:20],
            "surfaces": [{"id": s.get("id"), "name": s.get("name"), "dust_present": s.get("dust_present")}
                         for s in scene.get("surfaces", [])][:10],
            "regions": [{"id": r.get("id"), "kind": r.get("kind"), "note": r.get("note", "")[:80]}
                        for r in scene.get("regions", [])][:20],
        }
        prompt = REASONING_PROMPT.replace(
            "{findings}", json.dumps(findings_digest, ensure_ascii=False, indent=1))
        prompt = prompt.replace(
            "{scene}", json.dumps(scene_digest, ensure_ascii=False))
        if extra_instruction:
            prompt += f"\n\nДОПОЛНИТЕЛЬНОЕ УСЛОВИЕ ОТ ПОЛЬЗОВАТЕЛЯ: {extra_instruction}"

        last_error = None
        calls = []
        for attempt in range(1, max_attempts + 1):
            try:
                payload, latency = self.client.call_text(prompt, max_tokens=4000)
            except Exception as exc:  # noqa: BLE001 — сеть не должна ронять разбор
                last_error = str(exc)
                continue
            calls.append({"attempt": attempt, "latency_ms": latency})
            text = self.client.text_of(payload)
            try:
                data = self.client.extract_json(text)
            except PerceptionError as exc:
                last_error = str(exc)
                continue

            claims, dropped_claims = sanitize_claims(data.get("claims", []), findings)
            hypotheses, dropped_hypotheses = sanitize_hypotheses(data.get("hypotheses", []), claims)
            dropped = {**dropped_claims, **dropped_hypotheses}
            usage = payload.get("usage") or {}
            return {"claims": claims, "hypotheses": hypotheses}, {
                "model": self.client.model,
                "latency_ms": sum(c["latency_ms"] for c in calls),
                "calls": len(calls),
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "dropped": dropped,
            }
        raise ReasoningError(f"модель не вернула пригодный разбор: {last_error}")
