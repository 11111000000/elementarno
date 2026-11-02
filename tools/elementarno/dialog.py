"""Сессия разбора: серия фотографий, уточняющие вопросы, накопление улик.

Сессия — это состояние дела: принятые кадры, найденные следы, живые версии,
журнал вопросов и ответов. Раунд работы:

    кадр → восприятие → слияние со сценой сессии → улики → версии →
    следующий вопрос (по ценности информации)

Приложение умеет спросить, чего не хватает, и принять ответ — новый кадр
или текст. Отказ остаётся корректным ответом и в середине сессии.
"""

import json
from pathlib import Path

from .diff import diff_scenes
from .ledger import score_hypotheses, validate
from .nextshot import hypothesis_tags, kind_tags_from_rules, rank_questions
from .puzzle import build_claims, score_participants
from .rules import evaluate_all


def merge_scenes(base, addition):
    """Слияние двух сцен: добавление не теряет то, что было найдено раньше."""
    merged = {
        "meta": {**(base.get("meta") or {}), **(addition.get("meta") or {})},
        "surfaces": list(base.get("surfaces", [])),
        "objects": list(base.get("objects", [])),
        "regions": list(base.get("regions", [])),
        "observations": list(base.get("observations", [])),
        "light": list(base.get("light", [])),
        "changes": list(base.get("changes", [])),
    }
    seen_surfaces = {s.get("id") for s in merged["surfaces"]}
    for surface in addition.get("surfaces", []):
        if surface.get("id") not in seen_surfaces:
            merged["surfaces"].append(surface)
            seen_surfaces.add(surface.get("id"))
    seen_objects = {o.get("id") for o in merged["objects"]}
    for obj in addition.get("objects", []):
        if obj.get("id") not in seen_objects:
            merged["objects"].append(obj)
            seen_objects.add(obj.get("id"))
    seen_regions = {(r.get("kind"), tuple(r.get("bbox") or ())) for r in merged["regions"]}
    for region in addition.get("regions", []):
        key = (region.get("kind"), tuple(region.get("bbox") or ()))
        if key not in seen_regions:
            merged["regions"].append(region)
            seen_regions.add(key)
    seen_observations = {o.get("id") for o in merged["observations"]}
    for observation in addition.get("observations", []):
        if observation.get("id") not in seen_observations:
            merged["observations"].append(observation)
            seen_observations.add(observation.get("id"))
    return merged


class Session:
    def __init__(self, rules, participants=None):
        self.rules = rules
        self.participants = participants or []
        self.scene = None
        self.rounds = []
        self.questions = []

    def to_dict(self):
        return {
            "rounds": self.rounds,
            "questions": self.questions,
            "participants": self.participants,
            "scene": self.scene,
        }

    def save(self, path):
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path, rules):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        session = cls(rules, data.get("participants"))
        session.rounds = data.get("rounds", [])
        session.questions = data.get("questions", [])
        session.scene = data.get("scene")
        return session

    def add_scene(self, scene, source=None):
        """Добавить кадр: сцена сливается с накопленной, различия считаются."""
        if self.scene is None:
            self.scene = scene
        else:
            changes = diff_scenes(self.scene, scene)
            self.scene["changes"] = list(self.scene.get("changes", [])) + changes
            self.scene = merge_scenes(self.scene, scene)
        self.rounds.append({
            "source": source,
            "regions": len(scene.get("regions", [])),
            "objects": len(scene.get("objects", [])),
        })
        return self.scene

    def analyze(self):
        """Пересчёт улик и версий по накопленной сцене."""
        if self.scene is None:
            return {"findings": [], "claims": [], "hypotheses": [], "participants": [],
                    "verdict": "insufficient_evidence", "questions": []}
        findings = evaluate_all(self.rules, self.scene)
        claims = build_claims(findings)
        hypotheses = []
        for participant in self.participants:
            matched = [f for f in findings if set(participant.get("traits", [])) & set(f.get("tags", []))]
            hypotheses.append({
                "hypothesis_id": f"H-{participant['id']}",
                "text": f"Присутствовал в сцене: {participant.get('label', participant['id'])}",
                "claims": [f"C-{f['rule_id']}" for f in matched],
                "status": "open",
                "kill_log": [],
                "step": "presence",
            })
        scored = score_hypotheses(findings, claims, hypotheses)
        report = validate(findings, {"claims": claims, "hypotheses": scored})
        found_kinds = {r.get("kind") for r in self.scene.get("regions", [])}
        questions = rank_questions(
            scored,
            hypothesis_tags(scored, findings),
            kind_tags_from_rules(self.rules),
            found_kinds,
        )
        for question in questions:
            self.questions.append(question)
        return {
            "findings": findings,
            "claims": claims,
            "hypotheses": scored,
            "participants": score_participants(self.participants, findings),
            "report": report,
            "verdict": "sufficient_evidence" if findings else "insufficient_evidence",
            "questions": questions,
        }

    def note_answer(self, question_id, text):
        """Текстовый ответ пользователя: попадает в журнал сессии."""
        self.questions.append({"id": question_id, "answer": text, "kind": "answer"})
        return self.questions[-1]
