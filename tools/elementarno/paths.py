"""Path resolution over the scene graph.

Path grammar: collection[filter=value][filter=value].field

    regions[kind=dust_outline]          -> list of matching regions
    surfaces[name=table].dust_present   -> list of field values
    changes[kind=object_removed].id     -> list of ids
    objects[category=mug][fill_level>0][fill_level<0.5] -> кружки с напитком

Фильтры сравнения появились потому, что доменно-нейтральный слой работает с
фактами предметов: «есть кружка, в которой что-то есть, но меньше половины»
нельзя выразить через равенство. Фильтры по-прежнему соединяются через И,
а «любой из» выражается предикатом `any`.

Only flat paths are supported (no nested joins). That is a deliberate limit:
a richer query language would need a real database, and the protocol values
a language that can be read and audited.
"""

import re

_COLLECTION_RE = re.compile(r"^([a-z_]+)((?:\[[^\]]+\])*)(?:\.([a-z_]+))?$")
_FILTER_RE = re.compile(r"\[([a-z_]+)(>=|<=|>|<|!=|=)([^\]]*)\]")


class PathError(ValueError):
    pass


def parse_path(path):
    match = _COLLECTION_RE.match(path)
    if not match:
        raise PathError(f"malformed path: {path!r}")
    collection, raw_filters, field = match.groups()
    filters = [(key, op, value) for key, op, value in _FILTER_RE.findall(raw_filters)]
    if raw_filters and not filters:
        raise PathError(f"malformed filters in path: {path!r}")
    return collection, filters, field


def resolve(scene, path):
    collection, filters, field = parse_path(path)
    items = scene.get(collection)
    if items is None:
        return []
    if not isinstance(items, list):
        items = [items]
    for key, op, value in filters:
        items = [i for i in items if _matches(i.get(key), op, value)]
    if field is None:
        return list(items)
    return [i.get(field) for i in items if isinstance(i, dict) and field in i]


def _matches(actual, op, expected):
    if actual is None:
        return False
    if isinstance(actual, list):
        return any(values_equal(item, expected) for item in actual)
    if op == "=":
        return values_equal(actual, expected)
    if op == "!=":
        return not values_equal(actual, expected)
    if isinstance(actual, bool) or not isinstance(actual, (int, float)):
        return False
    try:
        bound = float(expected)
    except ValueError:
        return False
    if op == ">":
        return float(actual) > bound
    if op == ">=":
        return float(actual) >= bound
    if op == "<":
        return float(actual) < bound
    if op == "<=":
        return float(actual) <= bound
    return False


def values_equal(actual, expected):
    if isinstance(actual, bool) or isinstance(expected, bool):
        return str(actual).lower() == str(expected).lower()
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return abs(float(actual) - float(expected)) < 1e-9
    if isinstance(actual, str) and isinstance(expected, str):
        return actual.lower() == expected.lower()
    return actual == expected
