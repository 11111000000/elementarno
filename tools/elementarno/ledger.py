"""Evidence ledger: claim validation, hypothesis bookkeeping, refusal policy.

Validation lives here, in code, not in a prompt. A model that checks itself
tends to agree with itself.
"""

import math

from .paths import resolve


class Verdict:
    SUFFICIENT = "sufficient_evidence"
    INSUFFICIENT = "insufficient_evidence"
    CONFLICT = "conflicting_evidence"


# Формулировки, которые приложение не имеет права производить: вывод о вине
# или о свойствах характера не следует из изображения и не является
# абдукцией. Проверка грубая, но она ловит самую частую ошибку — подменить
# наблюдение обвинением.
ACCUSATORY_TERMS = (
    "виновен", "виноват", "винов", "убийц", "преступник", "причастен к убийству",
    "совершил убийство", "совершил преступление", "замешан в",
)

# Свойства личности. Корни лексем + исключения: «характер» само по себе
# может относиться к веществу («характер пыли»), и такое утверждение
# отбрасывать нельзя. Поэтому проверка контекстная.
PERSONALITY_ROOTS = (
    "характер", "психика", "натура", "темперамент", "врождённ", "врожденн",
    "нравственн", "душевн",
)
PERSONALITY_EXCEPTIONS = (
    "характер пыли", "характер следов", "характер следа", "характер поверхности",
    "характер вещества", "характер пятна", "характер почвы", "характер грязи",
    "характер сцены", "характер помещения",
)
PERSONALITY_TERMS = (
    "характер человека", "характер личности", "по характеру", "психика",
    "врождённый", "врожденный", "нравственность", "склонность к",
    "тип человека", "натура человека", "душевные качества", "темперамент",
)


LADDER_ORDER = {"scene": 0, "activity": 1, "presence": 2, "role": 3, "action": 4}

# Исход отрицания: чем кончилась попытка опровергнуть утверждение.
REFUTATION_OUTCOMES = ("survived", "refuted", "undetermined")


def _restates_rule(claim, findings_by_id):
    """Утверждение, которое дословно повторяет вывод своей улики.

    Повтор не добавляет ничего, поэтому отрицать его нечего: работает
    опровержение самого правила (`falsification.physical_test`). Всё, что
    идёт дальше вывода улики, обязано быть атаковано отдельно.
    """
    text = (claim.get("text") or "").strip()
    if not text:
        return False
    for support in claim.get("support") or []:
        finding = findings_by_id.get(support.get("finding_id"))
        if finding and (finding.get("inference") or "").strip() == text:
            return True
    return False


def _refutation_problem(claim, findings_by_id):
    """Что не так с попыткой опровержения. None — претензий нет."""
    refutation = claim.get("refutation")
    if not refutation:
        if _restates_rule(claim, findings_by_id):
            return None
        return "утверждение идёт дальше вывода улики и не подвергнуто отрицанию"
    negation = (refutation.get("negation") or "").strip()
    outcome = refutation.get("outcome")
    if not negation:
        return "в записи об отрицании нет самой гипотезы, которую проверяли"
    if outcome not in REFUTATION_OUTCOMES:
        return f"неизвестный исход отрицания: {outcome!r}"
    return None


def ladder_jump(claim_step, finding_step):
    """На сколько ступеней утверждение опережает свою улику.

    Общее правило — не более одной ступени: утверждение «кто-то был»
    не может опираться на «это кухня». Исключение — ступень `action`:
    вывод о действии («вошёл с улицы») по природе опирается на присутствие,
    и требовать для этого ещё и роль значило бы запрещать нормальный вывод.
    """
    claim = LADDER_ORDER.get(claim_step, 4)
    finding = LADDER_ORDER.get(finding_step, 4)
    if finding > claim:
        return 99
    return claim - finding


def _has_term(text, terms):
    lowered = (text or "").lower()
    return [term for term in terms if term in lowered]


def mentions_personality(text):
    """Упоминание свойств личности человека.

    Контекстная проверка: «изменился характер пыли» — утверждение о
    веществе и должно проходить; «по фото виден характер» — вывод о
    человеке, и проходить не должен.
    """
    lowered = (text or "").lower()
    hits = _has_term(lowered, PERSONALITY_TERMS)
    if hits:
        return hits
    roots = _has_term(lowered, PERSONALITY_ROOTS)
    if not roots:
        return []
    exceptions = _has_term(lowered, PERSONALITY_EXCEPTIONS)
    if exceptions:
        return []
    return roots


def validate(findings, ledger):
    findings_by_id = {f["finding_id"]: f for f in findings}
    errors = []
    warnings = []
    claims = ledger.get("claims", [])
    claim_ids = {c["claim_id"] for c in claims}

    resolvable = 0
    for claim in claims:
        support = claim.get("support") or []
        if not support:
            errors.append({
                "claim_id": claim["claim_id"],
                "code": "unsupported_claim",
                "detail": "claim has no finding to point at",
            })
            continue
        unknown = [s["finding_id"] for s in support if s["finding_id"] not in findings_by_id]
        if unknown:
            errors.append({
                "claim_id": claim["claim_id"],
                "code": "unresolved_citation",
                "detail": f"no such finding: {unknown}",
            })
            continue
        resolvable += 1

        caps = [findings_by_id[s["finding_id"]]["confidence_ceiling"] for s in support]
        ceiling = min(caps)
        if claim["confidence"] > ceiling + 1e-9:
            errors.append({
                "claim_id": claim["claim_id"],
                "code": "overconfidence",
                "detail": f"confidence {claim['confidence']} exceeds ceiling {ceiling}",
            })

        if any(findings_by_id[s["finding_id"]]["provisional"] for s in support):
            if claim["confidence"] > 0.5 + 1e-9:
                errors.append({
                    "claim_id": claim["claim_id"],
                    "code": "draft_backs_strong_claim",
                    "detail": "a draft rule cannot back a claim above 0.5",
                })
            if not claim.get("provisional"):
                errors.append({
                    "claim_id": claim["claim_id"],
                    "code": "missing_provisional_flag",
                    "detail": "claim rests on a draft rule and must be marked provisional",
                })

        if claim.get("kind") == "hypothesis" and not claim.get("falsification"):
            errors.append({
                "claim_id": claim["claim_id"],
                "code": "hypothesis_without_falsification",
                "detail": "a hypothesis must say what would refute it",
            })
        if claim.get("kind") == "interpretation":
            if not claim.get("speculative"):
                errors.append({
                    "claim_id": claim["claim_id"],
                    "code": "interpretation_not_marked",
                    "detail": "interpretation must be marked speculative",
                })
            if claim["confidence"] > 0.4 + 1e-9:
                errors.append({
                    "claim_id": claim["claim_id"],
                    "code": "interpretation_too_confident",
                    "detail": "interpretation confidence must be <= 0.4",
                })

        claim_step = LADDER_ORDER.get(claim.get("step") or "action", 4)
        for support in support:
            finding = findings_by_id.get(support["finding_id"])
            if not finding:
                continue
            finding_step = LADDER_ORDER.get(finding.get("step") or "action", 4)
            if finding_step > claim_step:
                errors.append({
                    "claim_id": claim["claim_id"],
                    "code": "ladder_break",
                    "detail": f"улика {finding['rule_id']} относится к более частной ступени, "
                              f"чем утверждение ({claim.get('step') or 'action'})",
                })

        problem = _refutation_problem(claim, findings_by_id)
        if problem:
            errors.append({
                "claim_id": claim["claim_id"],
                "code": "missing_refutation",
                "detail": problem,
            })
        elif (claim.get("refutation") or {}).get("outcome") == "refuted":
            errors.append({
                "claim_id": claim["claim_id"],
                "code": "refuted_claim_present",
                "detail": "утверждение опровергнуто собственной проверкой — его нужно убрать, "
                          "а не отвечать им",
            })

        accusatory = _has_term(claim.get("text"), ACCUSATORY_TERMS)
        if accusatory:
            errors.append({
                "claim_id": claim["claim_id"],
                "code": "accusatory_framing",
                "detail": f"вывод о вине недопустим: {accusatory}",
            })

        personality = mentions_personality(claim.get("text"))
        if personality:
            errors.append({
                "claim_id": claim["claim_id"],
                "code": "personality_inference",
                "detail": f"свойства личности не выводятся из изображения: {personality}",
            })

    for hypothesis in ledger.get("hypotheses", []):
        for claim_id in hypothesis.get("claims", []):
            if claim_id not in claim_ids:
                errors.append({
                    "hypothesis_id": hypothesis["hypothesis_id"],
                    "code": "unknown_claim",
                    "detail": f"hypothesis points at missing claim {claim_id}",
                })
        if hypothesis.get("status") == "rejected" and not hypothesis.get("kill_log"):
            errors.append({
                "hypothesis_id": hypothesis["hypothesis_id"],
                "code": "rejected_without_kill_log",
                "detail": "a rejected hypothesis must record what killed it",
            })

    total = len(claims)
    if total == 0:
        return {
            "errors": errors,
            "warnings": warnings,
            "citation_completeness": 1.0,
            "claims": 0,
            "resolvable_claims": 0,
        }
    return {
        "errors": errors,
        "warnings": warnings,
        "citation_completeness": resolvable / total,
        "claims": total,
        "resolvable_claims": resolvable,
    }


def logit(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def score_hypotheses(findings, claims, hypotheses):
    findings_by_id = {f["finding_id"]: f for f in findings}
    claims_by_id = {c["claim_id"]: c for c in claims}
    scored = []
    for hypothesis in hypotheses:
        support_findings = []
        for claim_id in hypothesis.get("claims", []):
            claim = claims_by_id.get(claim_id)
            if not claim:
                continue
            for support in claim.get("support", []):
                finding = findings_by_id.get(support["finding_id"])
                if finding and finding not in support_findings:
                    support_findings.append(finding)
        if not support_findings:
            scored.append({
                **hypothesis,
                "log_odds": None,
                "support_findings": [],
                "note": "нет улик: версия не может возглавлять рейтинг",
            })
            continue
        total = sum(logit(f["confidence_prior"]) for f in support_findings)
        confound_penalty = 0.15 * sum(len(f.get("confounds", [])) for f in support_findings)
        scored.append({
            **hypothesis,
            "log_odds": round(max(-6.0, min(6.0, total - confound_penalty)), 3),
            "support_findings": [f["finding_id"] for f in support_findings],
        })
    scored.sort(key=lambda h: (h["log_odds"] is not None, h["log_odds"] or -99.0), reverse=True)
    return scored


def grounding_precision(scene, claims, findings=None):
    """Доля утверждений, якоря которых действительно есть в графе сцены.

    Проверяется не «есть ли ссылка», а разрешается ли якорь в конкретную
    вершину: иначе утверждение о «пылевом контуре» может опираться на
    правило, сработавшее не там.
    """
    known = set()
    for collection in ("surfaces", "objects", "regions"):
        for item in scene.get(collection, []) or []:
            if isinstance(item, dict) and item.get("id"):
                known.add(item["id"])
    if not claims:
        return 1.0
    findings_by_id = {f["finding_id"]: f for f in (findings or [])}
    grounded = 0
    for claim in claims:
        support = claim.get("support") or []
        if not support:
            continue
        anchors = []
        for item in support:
            finding = findings_by_id.get(item.get("finding_id"))
            if finding is not None:
                anchors.extend(finding.get("anchors", []))
        if anchors and all(anchor in known for anchor in anchors):
            grounded += 1
    return grounded / len(claims)


def verdict(findings, claims, min_findings=1, mode="detective"):
    if not findings:
        return Verdict.INSUFFICIENT
    if len(findings) < min_findings:
        return Verdict.INSUFFICIENT
    if mode == "audit":
        if not claims:
            return Verdict.INSUFFICIENT
    return Verdict.SUFFICIENT


def rule_ids_in_scene(scene):
    return {c.get("rule_id") for c in scene.get("claims", []) if c.get("rule_id")}


def resolve_anchor_ids(scene, paths):
    ids = []
    for path in paths:
        for value in resolve(scene, path):
            if isinstance(value, str):
                ids.append(value)
    return ids
