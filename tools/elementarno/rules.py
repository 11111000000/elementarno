"""Rule packs: loading, dependency ordering, evaluation, findings.

A rule is a citable artifact. Loading enforces that: a rule without sources or
without confounds is rejected at load time, not quietly tolerated.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from .paths import resolve, values_equal

REQUIRED_FIELDS = (
    "id",
    "version",
    "pack",
    "title",
    "domain",
    "predicate",
    "inference",
    "confounds",
    "exceptions",
    "falsification",
    "sources",
    "review_status",
)


class RuleError(ValueError):
    pass


@dataclass(frozen=True)
class Rule:
    raw: dict

    @property
    def id(self):
        return self.raw["id"]

    @property
    def version(self):
        return self.raw["version"]

    @property
    def pack(self):
        return self.raw["pack"]

    @property
    def title(self):
        return self.raw["title"]

    @property
    def domain(self):
        return self.raw["domain"]

    @property
    def review_status(self):
        return self.raw["review_status"]

    @property
    def requires(self):
        return self.raw.get("requires", [])

    @property
    def depends_on(self):
        return self.raw.get("depends_on", [])

    @property
    def predicate(self):
        return self.raw["predicate"]

    @property
    def inference(self):
        return self.raw["inference"]

    @property
    def anchors(self):
        return self.raw.get("anchors", [])

    @property
    def confounds(self):
        return self.raw["confounds"]

    @property
    def exceptions(self):
        return self.raw["exceptions"]

    @property
    def falsification(self):
        return self.raw["falsification"]

    @property
    def sources(self):
        return self.raw["sources"]

    @property
    def tags(self):
        return self.inference.get("tags", [])

    @property
    def layer(self):
        return self.raw.get("layer", "epistemic")

    @property
    def is_provisional(self):
        return self.review_status != "reviewed" or not all(s.get("verified") for s in self.sources)

    @property
    def ceiling(self):
        ceiling = float(self.inference["confidence_ceiling"])
        if self.is_provisional:
            return min(ceiling, 0.5)
        return ceiling


def load_packs(rules_dir):
    rules = []
    for path in sorted(Path(rules_dir).glob("*.json")):
        if path.name in ("registry.json",):
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for raw in payload.get("rules", []):
            _validate(raw, path)
            rules.append(Rule(raw))
    seen = {}
    for rule in rules:
        if rule.id in seen:
            raise RuleError(f"duplicate rule id {rule.id} in {rule.pack}")
        seen[rule.id] = rule
    return rules


def _validate(raw, path):
    missing = [f for f in REQUIRED_FIELDS if f not in raw]
    if missing:
        raise RuleError(f"{path.name}: rule {raw.get('id', '?')} missing {missing}")
    if not raw["confounds"]:
        raise RuleError(f"{path.name}: rule {raw['id']} has no confounds")
    if not raw["exceptions"]:
        raise RuleError(f"{path.name}: rule {raw['id']} has no exceptions")
    if not raw["sources"]:
        raise RuleError(f"{path.name}: rule {raw['id']} has no sources")
    if raw["review_status"] not in ("draft", "reviewed"):
        raise RuleError(f"{path.name}: rule {raw['id']} has unknown review_status")


def order_rules(rules):
    by_id = {rule.id: rule for rule in rules}
    ordered = []
    state = {}

    def visit(rule):
        mark = state.get(rule.id)
        if mark == "done":
            return
        if mark == "active":
            raise RuleError(f"dependency cycle at {rule.id}")
        state[rule.id] = "active"
        for dep in rule.depends_on:
            if dep not in by_id:
                raise RuleError(f"rule {rule.id} depends on unknown rule {dep}")
            visit(by_id[dep])
        state[rule.id] = "done"
        ordered.append(rule)

    for rule in rules:
        visit(rule)
    return ordered


def evaluate_predicate(predicate, scene, fired):
    kind = predicate.get("kind")
    if kind == "all":
        return all(evaluate_predicate(c, scene, fired) for c in predicate.get("conditions", []))
    if kind == "any":
        return any(evaluate_predicate(c, scene, fired) for c in predicate.get("conditions", []))
    if kind == "not":
        return not evaluate_predicate(predicate["condition"], scene, fired)
    if kind == "present":
        found = resolve(scene, predicate["path"])
        return any(values_equal(v, predicate["value"]) for v in found)
    if kind == "count":
        n = len(resolve(scene, predicate["path"]))
        if "gte" in predicate and n < predicate["gte"]:
            return False
        if "lte" in predicate and n > predicate["lte"]:
            return False
        return "gte" in predicate or "lte" in predicate
    if kind == "absent":
        return len(resolve(scene, predicate["path"])) == 0
    if kind == "rule":
        return predicate["id"] in fired
    if kind == "dangling":
        known = {item.get("id") for item in scene.get(predicate["collection"], [])}
        return any(ref not in known for ref in resolve(scene, predicate["path"]))
    if kind == "mismatch":
        left = resolve(scene, predicate["left"])
        right = resolve(scene, predicate["right"])
        if not left or not right:
            return False
        return any(not values_equal(l, r) for l in left for r in right)
    if kind == "max":
        values = [v for v in resolve(scene, predicate["path"]) if isinstance(v, (int, float))]
        if not values:
            return False
        if "gt" in predicate and not max(values) > predicate["gt"]:
            return False
        if "gte" in predicate and not max(values) >= predicate["gte"]:
            return False
        if "lt" in predicate and not max(values) < predicate["lt"]:
            return False
        return True
    if kind == "distinct":
        values = [str(v).lower() for v in resolve(scene, predicate["path"])]
        if "gte" in predicate:
            return len(set(values)) >= predicate["gte"]
        if "lte" in predicate:
            return len(set(values)) <= predicate["lte"]
        return False
    raise RuleError(f"unknown predicate kind: {kind!r}")


def _requirements_met(rule, scene):
    for collection in rule.requires:
        value = scene.get(collection)
        if value is None or (isinstance(value, list) and not value):
            return False
    return True


def evaluate(rule, scene, fired):
    if not _requirements_met(rule, scene):
        return None
    if not evaluate_predicate(rule.predicate, scene, fired):
        return None
    anchors = []
    for path in rule.anchors:
        for value in resolve(scene, path):
            if isinstance(value, str):
                anchors.append(value)
    return {
        "finding_id": f"F-{rule.id}",
        "rule_id": rule.id,
        "rule_version": rule.version,
        "pack": rule.pack,
        "title": rule.title,
        "layer": rule.layer,
        "inference": rule.inference["claim"],
        "anchors": anchors,
        "tags": rule.tags,
        "sources": rule.sources,
        "confounds": rule.confounds,
        "exceptions": rule.exceptions,
        "falsification": rule.falsification,
        "confidence_prior": float(rule.inference["confidence_prior"]),
        "confidence_ceiling": rule.ceiling,
        "provisional": rule.is_provisional,
    }


def evaluate_all(rules, scene):
    ordered = order_rules(rules)
    fired = set()
    findings = []
    for rule in ordered:
        finding = evaluate(rule, scene, fired)
        if finding is not None:
            fired.add(rule.id)
            findings.append(finding)
    return findings
