"""Ценность информации: какой следующий кадр различит конкурирующие версии.

Приложение умеет не только разбирать присланное, но и просить то, что
разведёт версии. Ценность вопроса считается по энтропии гипотез: вопрос
полезен ровно настолько, насколько его ответ различает версии.

Формально (docs/MATH.md §7): EIG(q) = H(Y | Z) − H(Y | Z, a),
где Y — истинная гипотеза, Z — текущие данные, a — ответ на вопрос.
"""

import math

# Каталог вопросов. kinds — следы, которые такой кадр способен показать.
QUESTIONS = [
    {
        "id": "surface-wide",
        "question": "Снимите поверхность целиком, включая края и углы, где обычно скапливается пыль",
        "kinds": ["dust_outline", "unfaded_patch", "stain", "scratch"],
        "why": "края и углы — места, где след удалённого предмета виден лучше всего",
    },
    {
        "id": "side-light",
        "question": "Снимите сцену с боковым светом: фонарик или лампа сбоку, без вспышки",
        "kinds": ["dust_outline", "disturbed_dust", "fingerprint", "unfaded_patch"],
        "why": "при боковом свете рельеф виден, и контур проступает, даже если света мало",
    },
    {
        "id": "floor-grazing",
        "question": "Снимите пол под углом к поверхности, почти скользя",
        "kinds": ["footprint", "mud_footprint", "oil_trace", "wet_trace"],
        "why": "следы на полу видны только в скользящем ракурсе",
    },
    {
        "id": "wall-hooks",
        "question": "Снимите стену с крючками и полками крупным планом",
        "kinds": ["empty_hook", "unfaded_patch", "disturbed_dust"],
        "why": "пустой крючок и «чистое» место под ним — самая говорящая пара улик",
    },
    {
        "id": "window-full",
        "question": "Снимите окно целиком вместе с рамой, подоконником и отливом",
        "kinds": ["water_line", "disturbed_dust", "condensation"],
        "why": "от границы прежнего уровня воды видно, откуда шла вода",
    },
    {
        "id": "closeups",
        "question": "Снимите кропом те места, которые выглядят подозрительно",
        "kinds": ["dust_outline", "fingerprint", "paint_splash", "sawdust", "oil_trace"],
        "why": "кроп даёт модели больше деталей, чем общий план",
    },
    {
        "id": "second-view",
        "question": "Снимите ту же сцену с другого угла и в другое время суток",
        "kinds": ["disturbed_dust", "water_line", "wet_trace"],
        "why": "другой ракурс отделяет след от артефакта съёмки",
    },
    {
        "id": "context-wide",
        "question": "Снимите общий план: вся комната целиком, включая пол и потолок",
        "kinds": ["water_line", "burn", "disturbed_dust", "mud_footprint"],
        "why": "общий план нужен, чтобы понять, где в доме снята сцена",
    },
]

PERSON_QUESTIONS = {
    "shoes": {
        "question": "Если это возможно — снимите обувь участников рядом со входом",
        "kinds": ["footprint", "mud_footprint"],
        "why": "рисунок подошвы сопоставляется со следом в сцене",
    },
    "hand": {
        "question": "Снимите предмет, к которому прикасались, крупным планом",
        "kinds": ["fingerprint", "paint_trace"],
        "why": "следы пальцев на гладкой поверхности видны только вблизи",
    },
    "route": {
        "question": "Снимите путь от входа до места события: пол, пороги, дверные ручки",
        "kinds": ["footprint", "mud_footprint", "wet_trace"],
        "why": "цепочка следов показывает маршрут, а не только точку",
    },
}


def _entropy(weights):
    total = sum(weights)
    if total <= 0:
        return 0.0
    result = 0.0
    for weight in weights:
        p = weight / total
        if p > 0:
            result -= p * math.log(p)
    return result


def _to_probabilities(log_odds):
    if not log_odds:
        return []
    shifted = [value - max(log_odds) for value in log_odds]
    exponentials = [math.exp(value) for value in shifted]
    total = sum(exponentials)
    return [value / total for value in exponentials]


def kind_tags_from_rules(rules):
    """Сопоставление «вид следа → метки правил, которые на нём срабатывают»."""
    mapping = {}
    for rule in rules:
        for anchor in rule.anchors:
            if "kind=" not in anchor:
                continue
            kind = anchor.split("kind=")[1].split("]")[0]
            mapping.setdefault(kind, set()).update(rule.tags)
    return mapping


def hypothesis_tags(hypotheses, findings):
    """Сопоставление «версия ↔ метки улик»."""
    tags_by_finding = {f["finding_id"]: set(f.get("tags", [])) for f in findings}
    index = {}
    for hypothesis in hypotheses:
        tags = set()
        for finding_id in hypothesis.get("support_findings", []):
            tags |= tags_by_finding.get(finding_id, set())
        index[hypothesis.get("hypothesis_id")] = tags
    return index


def information_gain(hypotheses, kind, tags_by_hypothesis, tags_by_kind, base_rate=0.08):
    """EIG вопроса «виден ли след такого-то вида» по набору версий.

    Версия совместима со следом, если её метки пересекаются с метками
    правил, срабатывающих на этом следе. Несовместимые версии и делают
    вопрос полезным: ответ «след есть» резко перекашивает массу в их пользу.
    """
    if len(hypotheses) < 2:
        return 0.0
    prior = _to_probabilities([h.get("log_odds", 0.0) for h in hypotheses])
    if not prior:
        return 0.0
    prior_entropy = _entropy(prior)

    kind_labels = tags_by_kind.get(kind, set())
    yes_likelihoods = []
    for hypothesis in hypotheses:
        compatible = bool(tags_by_hypothesis.get(hypothesis.get("hypothesis_id"), set()) & kind_labels)
        yes_likelihoods.append(0.85 if compatible else base_rate)

    total_yes = sum(prior[i] * yes_likelihoods[i] for i in range(len(prior)))
    total_no = sum(prior[i] * (1 - yes_likelihoods[i]) for i in range(len(prior)))

    expected_entropy = 0.0
    if total_yes > 0:
        posterior = [prior[i] * yes_likelihoods[i] / total_yes for i in range(len(prior))]
        expected_entropy += total_yes * _entropy(posterior)
    if total_no > 0:
        posterior = [prior[i] * (1 - yes_likelihoods[i]) / total_no for i in range(len(prior))]
        expected_entropy += total_no * _entropy(posterior)
    return max(0.0, prior_entropy - expected_entropy)


def rank_questions(hypotheses, tags_by_hypothesis, tags_by_kind, found_kinds=None, limit=3):
    """Ранжированный список вопросов с ценностью информации."""
    found_kinds = found_kinds or set()
    catalogue = list(QUESTIONS) + [
        {"id": key, "question": entry["question"], "why": entry["why"], "kinds": entry["kinds"]}
        for key, entry in PERSON_QUESTIONS.items()
    ]
    candidates = []
    for entry in catalogue:
        kinds = [k for k in entry["kinds"] if k not in found_kinds] or entry["kinds"]
        gain = sum(information_gain(hypotheses, kind, tags_by_hypothesis, tags_by_kind) for kind in kinds)
        candidates.append({
            "id": entry["id"],
            "question": entry["question"],
            "why": entry["why"],
            "kinds": kinds,
            "eig": round(gain, 4),
        })
    candidates.sort(key=lambda c: c["eig"], reverse=True)
    return candidates[:limit]


def prior_spread(hypotheses):
    """Насколько версии сейчас неразличимы."""
    if len(hypotheses) < 2:
        return 0.0
    return _entropy(_to_probabilities([h.get("log_odds", 0.0) for h in hypotheses]))
