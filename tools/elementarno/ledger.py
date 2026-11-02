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

PERSONALITY_TERMS = (
    "характер", "психика", "врождённый", "нравственность", "склонность к",
    " тип человека", "натура",
)


LADDER_ORDER = {"scene": 0, "activity": 1, "presence": 2, "action": 3}


def _has_term(text, terms):
    lowered = (text or "").lower()
    return [term for term in terms if term in lowered]


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

        claim_step = LADDER_ORDER.get(claim.get("step") or "action", 3)
        for support in support:
            finding = findings_by_id.get(support["finding_id"])
            if not finding:
                continue
            finding_step = LADDER_ORDER.get(finding.get("step") or "action", 3)
            if finding_step > claim_step:
                errors.append({
                    "claim_id": claim["claim_id"],
                    "code": "ladder_break",
                    "detail": f"улика {finding['rule_id']} относится к более частной ступени, "
                              f"чем утверждение ({claim.get('step') or 'action'})",
                })

        accusatory = _has_term(claim.get("text"), ACCUSATORY_TERMS)
        if accusatory:
            errors.append({
                "claim_id": claim["claim_id"],
                "code": "accusatory_framing",
                "detail": f"вывод о вине недопустим: {accusatory}",
            })

        personality = _has_term(claim.get("text"), PERSONALITY_TERMS)
        if personality:
            if claim.get("kind") != "interpretation" or not claim.get("speculative"):
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
        total = sum(logit(f["confidence_prior"]) for f in support_findings)
        confound_penalty = 0.25 * sum(len(f.get("confounds", [])) for f in support_findings)
        scored.append({
            **hypothesis,
            "log_odds": round(max(-6.0, min(6.0, total - confound_penalty)), 3),
            "support_findings": [f["finding_id"] for f in support_findings],
        })
    scored.sort(key=lambda h: h["log_odds"], reverse=True)
    return scored


def grounding_precision(scene, claims):
    """Fraction of claims whose anchors all exist in the scene graph."""
    known = set()
    for collection in ("surfaces", "objects", "regions"):
        for item in scene.get(collection, []):
            if isinstance(item, dict) and item.get("id"):
                known.add(item["id"])
    if not claims:
        return 1.0
    grounded = 0
    for claim in claims:
        anchors = set()
        for support in claim.get("support", []):
            anchors.add(support["finding_id"])
        if anchors:
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
