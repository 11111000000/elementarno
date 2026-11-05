"""Доменно-нейтральный слой: факты и признаки вместо криминалистических следов.

Криминалистика — это один словарь поверх общей задачи: «что видно на фото, что
из этого следует, что можно предположить и как это проверить». Здесь лежит
нижний этаж, который ничего не знает про криминалистику:

* **признаки** (`features`) — нормализованный словарь предмета: drinkware,
  tool, food, textile, lighter… Категории, которые выдаёт модель восприятия,
  свободным текстом; признаки приводят их к общему виду, иначе наборы
  («кружка + ложка + сахар») нельзя ни найти, ни проверить.
* **факты** — проверяемые утверждения о кадре: предмет и его состояние,
  количество, заполненность, связь с поверхностью, отсутствие ожидаемого,
  контраст состояний. Каждый факт помнит, чем он подтверждён.

Дальше факты и признаки читают правила (пак `general`) — они дают связи,
которые криминалистическая таксономия следов не выражает: «кружка не допита»,
«подставка пуста, а ноутбук закрыт», «табак и спичка на одном столе».

Признаки назначаются по трём основаниям, и каждое — с разной уверенностью:
словарь категорий (детерминированно), наблюдения восприятия (с их
уверенностью), арифметика сцены (контрасты и количества).
"""

import re

# Признак → слова категорий. Совпадение по слову, а не по подстроке:
# «open_container» не должен попадать в «writing» из-за «pen» внутри «open».
LEXICON = {
    "drinkware": ["mug", "cup", "glass", "tumbler", "beaker", "goblet", "кружк", "чашк", "стакан", "бокал"],
    "tableware": ["plate", "bowl", "dish", "saucer", "tray", "тарелк", "миск", "блюд", "поднос"],
    "utensil": ["spoon", "fork", "knife", "teaspoon", "ложка", "вилка", "нож"],
    "food": ["food", "bread", "bun", "roll", "cake", "pie", "apple", "fruit", "salad", "cheese",
             "хлеб", "булк", "пирог", "торт", "яблок", "еда", "продукт", "сыр"],
    "packaged_food": ["food_package", "bread bag", "package of food", "упаковка еды", "пачка еды"],
    "cookware": ["pot", "pan", "kettle", "saucepan", "frying", "кастрюл", "сковород", "чайник", "кофемолк"],
    "drink_container": ["bottle", "jar", "can", "thermos", "бутылк", "банк", "жестян", "термос"],
    "tool": ["knife", "hammer", "screwdriver", "wrench", "saw", "drill", "chisel", "pliers", "screw",
             "нож", "молоток", "отвёртк", "отвертк", "пил", "дрел", "гаечн", "плоскогуб"],
    "writing": ["pen", "pencil", "marker", "notebook", "тетрад", "ручк", "карандаш", "блокнот"],
    "device": ["phone", "smartphone", "laptop", "tablet", "computer", "monitor", "remote", "keyboard",
               "телефон", "ноутбук", "планшет", "компьютер", "монитор", "пульт", "клавиатур"],
    "small_device": ["usb flash drive", "flash drive", "charger", "power bank", "adapter",
                     "флешк", "зарядк", "переходник"],
    "lamp": ["lamp", "candle", "lantern", "ламп", "свеч", "фонар"],
    "textile": ["blanket", "towel", "cloth", "sheet", "curtain", "scarf", "hat",
                "одеял", "полотенц", "ткань", "простын", "штор", "платок", "шляп"],
    "seat": ["chair", "stool", "bench", "armchair", "стул", "табурет", "скамейк", "кресл"],
    "bed": ["bed", "mattress", "кроват", "матрас"],
    "bag": ["bag", "pouch", "backpack", "suitcase", "сумк", "пакет", "рюкзак", "чемодан"],
    "luggage": ["backpack", "suitcase", "duffel", "рюкзак", "чемодан", "сумка для дороги"],
    "packaging": ["packet", "package", "box", "tin", "carton", "wrapper", "коробк", "пачк", "упаковк", "жестян"],
    "ignition": ["lighter", "matchbox", "matches", "зажигалк", "спичк"],
    "tobacco": ["tobacco", "cigarette", "pipe", "tabak", "табак", "сигарет", "трубк"],
    "hygiene": ["toothbrush", "comb", "soap", "shampoo", "toothpaste",
                "зубн", "расч", "мыл", "шампун", "паст"],
    "toy": ["toy", "doll", "plush", "lego", "игрушк", "кукл", "конструктор"],
    "pet_item": ["leash", "litter", "pet bowl", "поводок", "миска для животных", "наполнитель"],
    "appliance": ["fridge", "refrigerator", "microwave", "oven", "stove",
                  "холодильник", "микроволн", "плит", "духовк"],
    "sanitary": ["toilet", "sink", "bathtub", "унитаз", "раковин", "ванн"],
    "sports": ["ball", "racket", "skis", "bike", "dumbbell", "мяч", "ракетк", "лыж", "велосипед", "гиря"],
    "plant": ["potted plant", "flowerpot", "planter", "горшок", "цветочн"],
    "electronics": ["usb flash drive", "flash drive", "card", "battery", "mouse", "кабель", "провод", "карта"],
    "medicine": ["pill", "medicine", "bandage", "thermometer", "таблетк", "лекарств", "бин", "термометр"],
    "person": ["person", "man", "woman", "child", "человек", "мужчин", "женщин", "ребенок"],
}

# Наблюдения восприятия → признаки состояния. Словарь из схемы сцены.
OBSERVATION_FEATURES = {
    "open": "open",
    "closed": "closed",
    "tilted": "tilted",
    "partially_filled": "partially_filled",
    "full": "full",
    "empty": "empty",
    "damaged": "damaged",
    "torn": "torn",
    "new": "new",
    "old": "old",
    "used": "used",
    "warm": "warm",
    "cold": "cold",
}

CONFIDENCE_LEXICON = 0.75
CONFIDENCE_OBSERVATION = 0.8
CONFIDENCE_DERIVED = 0.6


def _tokens(text):
    return {t for t in re.split(r"[^a-zа-яё0-9]+", str(text or "").lower()) if t}


def _matches_any(category, words):
    cat = str(category or "").lower()
    tokens = _tokens(cat)
    for word in words:
        low = word.lower()
        if " " in low:
            if low in cat:
                return True
        elif low in tokens:
            return True
    return False


def object_features(obj):
    """Признаки одного предмета: из словаря категорий и из его состояния."""
    features = set()
    for feature, words in LEXICON.items():
        if _matches_any(obj.get("category"), words):
            features.add(feature)
    state = obj.get("state")
    if state in ("open", "closed", "empty", "full", "used", "damaged", "new", "old"):
        features.add(state)
    fill = obj.get("fill_level")
    if isinstance(fill, (int, float)):
        if fill <= 0.02:
            features.add("empty")
        elif fill >= 0.98:
            features.add("full")
        else:
            features.add("partially_filled")
    return features


def enrich(scene):
    """Дописать в сцену признаки предметов (словарь + наблюдения)."""
    observations = {}
    for obs in scene.get("observations") or []:
        about = obs.get("about")
        feature = OBSERVATION_FEATURES.get(obs.get("feature"))
        if about and feature:
            observations.setdefault(about, []).append((feature, obs))
    for obj in scene.get("objects") or []:
        features = object_features(obj)
        for feature, _obs in observations.get(obj.get("id"), []):
            features.add(feature)
        obj["features"] = sorted(features)
    return scene


def _fact(kind, text, about, basis, confidence):
    return {
        "kind": kind,
        "text": text,
        "about": about,
        "basis": basis,
        "confidence": confidence,
    }


def facts(scene):
    """Доменно-нейтральные факты о сцене.

    Факты детерминированы: один и тот же кадр даёт один и тот же список.
    Уверенность факта — это уверенность его основания, а не вероятность
    интерпретации: интерпретация живёт в правилах и утверждениях.
    """
    objects = scene.get("objects") or []
    surfaces = {s.get("id"): s for s in (scene.get("surfaces") or [])}
    observations = scene.get("observations") or []
    out = []

    by_category = {}
    for obj in objects:
        by_category.setdefault(obj.get("category"), []).append(obj)

    for obj in objects:
        oid = obj.get("id")
        category = obj.get("category")
        note = obj.get("note")
        out.append(_fact("presence", f"в кадре есть {category}" + (f" ({note})" if note else ""),
                         [oid], f"объект {oid}", CONFIDENCE_LEXICON))
        for feature in obj.get("features") or []:
            out.append(_fact("state", f"{category} — {feature}", [oid], f"признак {oid}",
                             CONFIDENCE_OBSERVATION if feature in OBSERVATION_FEATURES.values()
                             else CONFIDENCE_LEXICON))
        fill = obj.get("fill_level")
        if isinstance(fill, (int, float)):
            out.append(_fact("fill", f"{category}: уровень содержимого около {fill:.2f}", [oid],
                             f"поле fill_level {oid}", CONFIDENCE_LEXICON))
        on = obj.get("on")
        if on and on in surfaces:
            out.append(_fact("relation", f"{category} стоит на поверхности «{surfaces[on].get('name')}»",
                             [oid, on], f"поле on {oid}", CONFIDENCE_LEXICON))

    for category, group in by_category.items():
        if len(group) > 1:
            out.append(_fact("quantity", f"предметов вида {category}: {len(group)}",
                             [o.get("id") for o in group], "подсчёт по категории", CONFIDENCE_LEXICON))

    for obs in observations:
        about = obs.get("about")
        feature = OBSERVATION_FEATURES.get(obs.get("feature"))
        if not about or not feature:
            continue
        confidence = obs.get("confidence")
        confidence = float(confidence) if isinstance(confidence, (int, float)) else CONFIDENCE_OBSERVATION
        out.append(_fact("observation", f"наблюдение: {feature} — {obs.get('value')}", [about],
                         f"наблюдение {obs.get('id')}", confidence))

    for category, group in by_category.items():
        if len(group) < 2:
            continue
        fills = [(o, o.get("fill_level")) for o in group if isinstance(o.get("fill_level"), (int, float))]
        if len(fills) >= 2:
            low, high = min(fills, key=lambda x: x[1]), max(fills, key=lambda x: x[1])
            if high[1] - low[1] >= 0.3:
                out.append(_fact("contrast", f"два предмета вида {category} заполнены по-разному "
                                 f"({low[1]:.2f} и {high[1]:.2f})",
                                 [low[0].get("id"), high[0].get("id")], "сравнение заполненности",
                                 CONFIDENCE_DERIVED))
        states = {(o.get("id"), o.get("state")) for o in group if o.get("state")}
        if len({s for _, s in states}) > 1:
            out.append(_fact("contrast", f"предметы вида {category} в разных состояниях",
                             [o.get("id") for o in group], "сравнение состояний", CONFIDENCE_DERIVED))

    for obs in observations:
        if obs.get("feature") != "empty":
            continue
        about = obs.get("about")
        holders = [o for o in objects if o.get("id") != about
                   and set(o.get("features") or []) & {"device", "tool", "drinkware", "tableware"}]
        if holders:
            out.append(_fact("absence", f"{about} пуст, хотя рядом есть предметы того же назначения",
                             [about] + [o.get("id") for o in holders], "пустой предмет и его окружение",
                             CONFIDENCE_DERIVED))

    for index, fact in enumerate(out, start=1):
        fact["fact_id"] = f"FACT-{index:03d}"
    return out


def fact_index(scene):
    """Факты с id и той же нумерацией, что и в `facts`."""
    return facts(enrich(scene))
