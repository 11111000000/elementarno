"""Восприятие: изображение → сцена-граф через мультимодальную модель.

Три прохода, и различаются они не промптом, а ВОПРОСОМ:

1. **Инвентаризация** — что есть: объекты, поверхности, свет. Регионов здесь
   нет намеренно: если просить модель классифицировать следы по нашей
   таксономии, она подгоняет видимое под ближайший bucket («брызги краски»
   → «stain», «следы ног» → «disturbed_dust») и выдумывает отсутствие там,
   где его нет.
2. **Чек-лист** — бинарный вопрос по каждому типу следа: «есть ли брызги
   краски? да/нет». Классификацию выполняет не модель, а сама таблица
   вопросов. Ответ «нет» — нормальный результат, а не провал.
3. **Допрос кропа** — проверка спорных находок на малом контексте: «в этом
   кропе действительно видны брызги краски?». Снимает ложные срабатывания.

Сырой ответ модели сохраняется рядом со сценой: он часть цепочки
доказательств и должен быть перечитываем.
"""

import base64
import json
import mimetypes
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from .scene import validate_scene

DEFAULT_ENDPOINT = "https://api.minimaxi.chat/anthropic/v1/messages"
DEFAULT_MODEL = "MiniMax-M3"

INVENTORY_PROMPT = """Ты — эксперт по осмотру сцены. Переведи фотографию в СТРУКТУРИРОВАННУЮ ОПИСАТЕЛЬНУЮ ИНVENTORY-ЗАПИСЬ.

ПРАВИЛА:
1. Ответ — ТОЛЬКО валидный JSON, без пояснений и без markdown-ограждений.
2. Описывай только то, что реально видно. Не додумывай предметы.
3. Следы, пятна и прочие локальные признаки НЕ описывай — их спросят отдельно.
3a. Кратко и компактно: не более 20 объектов, не более 5 наблюдений, поля заполняй только когда видно.
4. size_m — ориентировочный размер объекта в метрах; если не оценивается — не включай поле.
5. on должен ссылаться на id одной из surfaces. Если объекту не на чем стоять — не включай поле.

ФОРМАТ JSON:
{
  "surfaces": [{"id":"s1","name":"table","material":"wood|floor|tile|soil|sand|gravel|concrete|stone|metal|cloth","dust_present":true,"dust_state":"none|even|uneven|patchy","wet":false,"sunlit":false}],
  "objects": [{"id":"o1","category":"vase","material":"ceramic","state":"new|clean|worn|damaged|fresh|stale|unknown","fill_level":0.0,"size_m":0.25,"on":"s1","wet":false,"visible":true,"bbox":[0.1,0.1,0.2,0.2]}],
  "light": [{"id":"l1","kind":"window|lamp|sun|unknown","position":"left|right|above|behind"}],
  "observations": [{"id":"x1","about":"o1","feature":"open|closed|tilted|full|empty|damaged|new|old","value":"что видно"}],
  "anomalies": ["что выглядит необычным"]
}

Верни JSON."""

# (kind, вопрос). kind попадает в сцена-граф только при положительном ответе.
TRACE_CHECKLIST = [
    ("dust_outline", "контур от убранного предмета: светлая или чистая середина и следы пыли по краям"),
    ("empty_hook", "пустой крючок или вешалка со следом крепления"),
    ("unfaded_patch", "участок без пыли среди запылённой поверхности"),
    ("disturbed_dust", "полоса или полосы нарушенного слоя пыли"),
    ("footprint", "следы ног или животных: ступни, подошвы, лапы, копыта, отпечатки обуви"),
    ("mud_footprint", "след грязи или земли на поверхности"),
    ("wet_trace", "мокрый след или лужа"),
    ("water_line", "ровная граница прежнего уровня воды"),
    ("mold_patch", "очаг плесени или грибного поражения"),
    ("burn", "ожог, обугливание, след огня"),
    ("paint_splash", "брызги краски на поверхности"),
    ("paint_trace", "задетые следы краски на предмете или одежде"),
    ("sawdust", "стружка или опилки"),
    ("metal_swarf", "металлическая стружка или абразивная пыль"),
    ("flour_dust", "мука или мучная пыль"),
    ("oil_trace", "пятно масла, смазки или технической жидкости"),
    ("weld_spatter", "следы сварки, брызги металла"),
    ("plaster_dust", "штукатурная или цементная пыль"),
    ("ink_trace", "пятно чернил или тонера"),
    ("cup_ring", "след кружки или стакана на поверхности"),
    ("fingerprint", "отпечаток пальца или ладони"),
    ("tool_mark", "след от инструмента: царапина, выбоина, след зубила"),
    ("tyre_mark", "след шин"),
    ("scratch", "царапины или потёртости на поверхности"),
    ("crack", "трещина"),
]

CHECKLIST_PROMPT = """Ты — эксперт по следовому анализу. Перечисли следы, которые ты ВИДИШЬ на фотографии.

ФОРМАТ (только JSON, без markdown):
{"found":[{"kind":"<один из списка ниже>","bbox":[x1,y1,x2,y2],"note":"что именно видно, своими словами"}]}

ПРАВИЛА:
1. Перечисляй ТОЛЬКО то, что действительно видишь. Не выдумывай.
2. kind — строго один из идентификаторов в списке ниже. Своими словами пиши только в note.
3. bbox — область находки в нормализованных координатах 0..1. Если область не уверенная, bbox [0,0,0,0].
4. note — 5–15 слов по-русски: что видно и где.
5. Если следов нет — верни {"found":[]}. Это нормальный и правильный ответ.
6. Один след — одна запись. Один и тот же вид в двух местах — две записи.

СПИСОК ВИДОВ И ЧТО ЭТО ЗНАЧИТ:
{checklist}

Верни JSON."""

VERIFY_PROMPT = """Ты эксперт по следовому анализу. Перед тобой та же фотография, которую уже смотрели.

Наблюдение, которое требует подтверждения:
«{description}»

Подтверди наблюдение по самой фотографии: видно ли именно это?
Ответь ТОЛЬКО JSON: {{"yes":true,"confidence":0.0,"note":""}}
yes=false только если ты уверен, что такого на фотографии НЕТ.
Сомневаешься — true с невысокой уверенностью."""


def normalize_kind(raw, known):
    """Привести название вида к нашему идентификатору.

    Модель пишет почти точные ключи, но иногда с синонимом или опечаткой.
    Несовпадение — это отсутствие улики, а не повод выдумывать вид.

    Перебор упорядочен: порядок множества зависел от хеш-сида процесса,
    и один и тот же ответ модели давал разный вид следа от запуска к
    запуску. При нескольких совпадениях берётся самое специфичное
    (mud_footprint, а не footprint); равные по длине — отбрасываются как
    неоднозначные.
    """
    if not raw:
        return None
    value = str(raw).strip().lower().replace(" ", "_").replace("-", "_")
    if value in known:
        return value
    aliases = {
        "mud_prints": "mud_footprint", "footprints": "footprint", "foot_print": "footprint",
        "paint_spatter": "paint_splash", "paint_splashes": "paint_splash",
        "paint_splatter": "paint_splash", "wood_dust": "sawdust", "shavings": "sawdust",
        "mold": "mold_patch", "mould": "mold_patch", "mildew": "mold_patch",
        "water_stain": "water_line", "waterline": "water_line", "flood_line": "water_line",
        "oil": "oil_trace", "grease": "oil_trace", "grease_trace": "oil_trace",
        "burn_mark": "burn", "burnt": "burn", "char": "burn",
        "dust_mark": "dust_outline", "outline": "dust_outline", "dust_ring": "dust_outline",
        "hook": "empty_hook", "empty_hanger": "empty_hook",
        "unfaded": "unfaded_patch", "clean_patch": "unfaded_patch",
        "wet_floor": "wet_trace", "wet_mark": "wet_trace", "puddle": "wet_trace",
        "fingerprint_mark": "fingerprint", "prints": "fingerprint",
        "flour": "flour_dust", "flour_powder": "flour_dust",
        "plaster": "plaster_dust", "cement_dust": "plaster_dust",
        "metal_shavings": "metal_swarf", "swarf": "metal_swarf", "grinding_dust": "metal_swarf",
        "cup_mark": "cup_ring", "coffee_ring": "cup_ring", "mug_ring": "cup_ring",
        "ink": "ink_trace", "toner": "ink_trace",
    }
    if value in aliases:
        return aliases[value]
    matches = sorted((candidate for candidate in known if candidate in value), key=len, reverse=True)
    if not matches:
        return None
    if len(matches) > 1 and len(matches[0]) == len(matches[1]):
        return None
    return matches[0]


def _build_checklist_prompt():
    lines = [f"- {kind}: {question}" for kind, question in TRACE_CHECKLIST]
    return CHECKLIST_PROMPT.replace("{checklist}", "\n".join(lines))


CHECKLIST_READY = _build_checklist_prompt()


class PerceptionError(RuntimeError):
    pass


def resolve_api_key(explicit=None):
    if explicit:
        return explicit
    for name in ("MINIMAX2_API_KEY", "MINIMAX_API_KEY", "MINIMAX_API_KEY_2"):
        value = os.environ.get(name)
        if value:
            return value
    raise PerceptionError("нет ключа MiniMax: задайте MINIMAX2_API_KEY")


def normalize_scene(scene):
    """Мягкая нормализация типовых огрехов модели.

    Ничего не выдумывается: неизвестные значения переводятся в «unknown»,
    невалидные ссылки снимаются, а факт снятия записывается в anomalies.
    Лучше граф без одной детали, чем выдуманная поверхность, на которой
    «стоял» предмет.
    """
    notes = []
    surfaces = scene.get("surfaces") or []
    objects = scene.get("objects") or []
    regions = scene.get("regions") or []

    surface_names = {(s.get("name") or "").lower() for s in surfaces if s.get("name")}
    surface_ids = {s.get("id") for s in surfaces}
    region_ids = {r.get("id") for r in regions}

    kept = []
    for obj in objects:
        category = (obj.get("category") or "").lower()
        if category and category in surface_names:
            notes.append(f"объект «{obj.get('id')}» ({category}) — дубль поверхности, перенесён в surfaces")
            continue
        kept.append(obj)
    objects = kept

    for obj in objects:
        on = obj.get("on")
        if on is None:
            obj.pop("on", None)
        elif on not in surface_ids:
            notes.append(f"объект «{obj.get('id')}» ссылался на несуществующую поверхность «{on}» — ссылка снята")
            obj.pop("on")
        region = obj.get("region")
        if region and region not in region_ids:
            obj.pop("region", None)
        for field in ("fill_level", "size_m"):
            if obj.get(field) is None:
                obj.pop(field, None)
        if obj.get("state") not in VALID_OBJECT_STATES:
            if obj.get("state"):
                notes.append(f"объект «{obj.get('id')}»: состояние «{obj['state']}» неизвестно — заменено на unknown")
            obj["state"] = "unknown"
        if not obj.get("shadow_dir"):
            obj["shadow_dir"] = "unknown"

    for surface in surfaces:
        region = surface.get("region")
        if region and region not in region_ids:
            surface.pop("region", None)
        if surface.get("dust_state") not in VALID_DUST_STATES:
            surface["dust_state"] = "none"
        if surface.get("dust_present") is None:
            surface["dust_present"] = False

    for region in regions:
        if region.get("kind") not in VALID_REGION_KINDS:
            region["kind"] = "other"
        for field in ("freshness", "edges"):
            if region.get(field) not in VALID_REGION_FIELDS.get(field, set()):
                region[field] = "unknown"
        for field in ("area_m2", "contrast"):
            if region.get(field) is None:
                region.pop(field, None)

    scene["surfaces"] = surfaces
    scene["objects"] = objects
    scene["regions"] = regions
    return scene, notes


VALID_OBJECT_STATES = {"new", "clean", "worn", "damaged", "fresh", "stale", "unknown"}
VALID_DUST_STATES = {"none", "even", "uneven", "patchy"}
VALID_REGION_FIELDS = {
    "freshness": {"sharp", "soft", "erased", "unknown"},
    "edges": {"concave", "convex", "flat", "ragged", "unknown"},
}
VALID_REGION_KINDS = {
    "dust_outline", "empty_hook", "unfaded_patch", "stain", "scratch", "crack",
    "dent", "burn", "water_line", "mold_patch", "footprint", "tyre_mark",
    "tool_mark", "puddle", "condensation", "disturbed_dust", "mud_footprint",
    "fingerprint", "paint_splash", "paint_trace", "sawdust", "flour_dust",
    "oil_trace", "weld_spatter", "plaster_dust", "ink_trace", "cup_ring",
    "metal_swarf", "other",
}


class MiniMaxPerception:
    def __init__(self, model=DEFAULT_MODEL, endpoint=DEFAULT_ENDPOINT, api_key=None, timeout=180,
                 think=False, min_confidence=0.5, verify_crops=True, votes=1):
        self.model = model
        self.endpoint = endpoint
        self.api_key = resolve_api_key(api_key)
        self.timeout = timeout
        self.think = think
        self.min_confidence = min_confidence
        self.verify_crops = verify_crops
        self.votes = max(1, votes)

    def _payload(self, image_b64, media_type, prompt, max_tokens=3000):
        content = [
            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
            {"type": "text", "text": prompt},
        ]
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": 0,
            "messages": [{"role": "user", "content": content}],
        }
        if self.think:
            body["thinking"] = {"type": "enabled", "budget_tokens": 2048}
        return body

    def call(self, image_b64, media_type, prompt, max_tokens=3000):
        body = json.dumps(self._payload(image_b64, media_type, prompt, max_tokens)).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={
                "content-type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            raise PerceptionError(f"MiniMax API {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise PerceptionError(f"не удалось обратиться к MiniMax API: {exc.reason}") from exc
        return payload, round((time.monotonic() - started) * 1000)

    def call_text(self, prompt, max_tokens=4000):
        body = json.dumps(self._text_payload(prompt, max_tokens)).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={
                "content-type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            raise PerceptionError(f"MiniMax API {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise PerceptionError(f"не удалось обратиться к MiniMax API: {exc.reason}") from exc
        return payload, round((time.monotonic() - started) * 1000)

    def _text_payload(self, prompt, max_tokens=4000):
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": 0,
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        }
        if self.think:
            payload["thinking"] = {"type": "enabled", "budget_tokens": 2048}
        return payload

    @staticmethod
    def text_of(payload):
        parts = []
        for block in payload.get("content", []):
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts).strip()

    @staticmethod
    def repair_json(text):
        """Починить обрезанный JSON: закрыть скобки и убрать висячую запятую."""
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        stack = []
        in_string = False
        escaped = False
        for char in text:
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char in "{[":
                stack.append(char)
            elif char in "}]":
                if stack:
                    stack.pop()
        if in_string:
            text += '"'
        for opener in reversed(stack):
            text += "}" if opener == "{" else "]"
        text = re.sub(r",\s*([}\]])", r"\1", text)
        return text

    @staticmethod
    def extract_json(text):
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        start = text.find("{")
        end = text.rfind("}")
        if start == -1:
            raise PerceptionError("в ответе модели нет JSON")
        candidate = text[start:end + 1] if end > start else text[start:]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            repaired = MiniMaxPerception.repair_json(candidate)
            try:
                return json.loads(repaired)
            except json.JSONDecodeError as exc:
                raise PerceptionError(f"JSON не разобран даже после починки: {exc}") from exc

    def scene_graph(self, image_path, save_raw=None, max_attempts=3):
        path = Path(image_path)
        media_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        image_b64 = base64.b64encode(path.read_bytes()).decode("ascii")

        raw_calls = []
        prompt = INVENTORY_PROMPT
        last_error = None
        scene = None

        for attempt in range(1, max_attempts + 1):
            payload, latency = self.call(image_b64, media_type, prompt, max_tokens=6000)
            text = self.text_of(payload)
            raw_calls.append({"pass": "inventory", "prompt": prompt, "payload": payload, "latency_ms": latency})
            try:
                candidate = self.extract_json(text)
            except (json.JSONDecodeError, PerceptionError) as exc:
                last_error = f"JSON не разобран: {exc}"
                prompt = INVENTORY_PROMPT + f"\n\nПредыдущий ответ не распознан ({last_error}). Верни ТОЛЬКО корректный JSON."
                continue

            candidate.setdefault("surfaces", [])
            candidate.setdefault("objects", [])
            candidate.setdefault("observations", [])
            candidate["regions"] = []
            candidate, notes = normalize_scene(candidate)
            candidate.setdefault("anomalies", [])
            candidate["anomalies"] = list(candidate["anomalies"]) + notes

            problems = validate_scene(candidate)
            if problems:
                last_error = "; ".join(f"{p['code']}: {p['detail']}" for p in problems[:6])
                prompt = (
                    INVENTORY_PROMPT
                    + "\n\nТвой предыдущий ответ нарушает схему: " + last_error
                    + "\nИсправь и верни ТОЛЬКО корректный JSON."
                )
                continue
            scene = candidate
            break

        if scene is None:
            raise PerceptionError(f"не удалось получить корректный сцена-граф: {last_error}")

        regions, checklist_calls = self._checklist(image_b64, media_type)
        raw_calls.extend(checklist_calls)
        scene["regions"].extend(regions)

        if self.verify_crops:
            verified, verify_calls = self._verify(image_b64, media_type, regions)
            raw_calls.extend(verify_calls)
            if verified is not None:
                scene["regions"] = verified

        usage = (raw_calls[0]["payload"].get("usage") or {}) if raw_calls else {}
        meta = {
            "model": self.model,
            "latency_ms": sum(c["latency_ms"] for c in raw_calls),
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "calls": len(raw_calls),
            "anomalies": scene.get("anomalies", []),
            "regions_found": len(scene.get("regions", [])),
        }
        scene["meta"] = {**scene.get("meta", {}), "perception": meta}
        if save_raw:
            raw_path = Path(save_raw)
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(
                json.dumps({"calls": raw_calls, "scene": scene}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            scene["meta"]["perception"]["raw"] = str(raw_path)
        return scene, meta

    def _checklist(self, image_b64, media_type):
        """Перечисление следов, при необходимости — голосованием.

        Ответы модели различаются от сессии к сессии даже при temperature=0,
        поэтому число голосов сделано параметром: один голос — скорость,
        три голоса — устойчивость. Вид попадает в сцену, если набрал
        большинство голосов.
        """
        raw = []
        votes = []
        for _ in range(self.votes):
            payload, latency = self.call(image_b64, media_type, CHECKLIST_READY, max_tokens=4000)
            raw.append({"pass": "checklist", "prompt": CHECKLIST_READY, "payload": payload,
                        "latency_ms": latency})
            try:
                data = self.extract_json(self.text_of(payload))
            except (json.JSONDecodeError, PerceptionError):
                continue
            votes.append(data.get("found", []) or [])

        if not votes:
            return [], raw

        known = {kind for kind, _ in TRACE_CHECKLIST}
        questions = dict(TRACE_CHECKLIST)
        tally = {}
        for found in votes:
            seen_in_vote = set()
            for item in found:
                kind = normalize_kind(item.get("kind"), known)
                if not kind or kind in seen_in_vote:
                    continue
                seen_in_vote.add(kind)
                entry = tally.setdefault(kind, {"count": 0, "item": item})
                entry["count"] += 1

        needed = (len(votes) // 2) + 1
        regions = []
        for index, (kind, entry) in enumerate(tally.items(), start=1):
            if entry["count"] < needed:
                continue
            item = entry["item"]
            bbox = item.get("bbox") or [0, 0, 0, 0]
            if not isinstance(bbox, list) or len(bbox) != 4:
                bbox = [0, 0, 0, 0]
            try:
                confidence = float(item.get("confidence") or 0.7)
            except (TypeError, ValueError):
                confidence = 0.7
            regions.append({
                "id": f"c{index}",
                "kind": kind,
                "bbox": bbox,
                "note": item.get("note", ""),
                "confidence": min(confidence, 0.95),
                "votes": entry["count"],
                "votes_total": len(votes),
                "question": questions.get(kind, ""),
            })
        return regions, raw

    def _verify(self, image_b64, media_type, regions, max_regions=6):
        """Подтверждение находки по её собственному описанию.

        Кроп-проверка отвергнута намеренно: координаты, которые модель отдаёт
        для bbox, ненадёжны, и кроп по ним сбивается с реальной областью —
        верная находка при этом терялась. Описание же модель формулирует
        своими словами, и его можно проверить на всей фотографии.
        """
        if not regions:
            return None, []

        raw = []
        verified = []
        ranked = sorted(regions, key=lambda r: -(r.get("confidence") or 0.0))
        for region in ranked[:max_regions]:
            description = region.get("note") or region.get("question") or region.get("kind")
            prompt = VERIFY_PROMPT.format(description=description)
            payload, latency = self.call(image_b64, media_type, prompt, max_tokens=600)
            raw.append({"pass": "verify", "prompt": prompt, "payload": payload,
                        "latency_ms": latency, "region": region["id"]})
            try:
                answer = self.extract_json(self.text_of(payload))
            except (json.JSONDecodeError, PerceptionError):
                verified.append(region)
                continue
            confidence = float(answer.get("confidence") or 0.0)
            if answer.get("yes"):
                region = dict(region)
                region["verified"] = True
                region["confidence"] = min(region.get("confidence", 0.0), max(confidence, 0.5))
                region["note"] = answer.get("note") or region.get("note", "")
                verified.append(region)
            elif confidence >= 0.8:
                continue
            else:
                region = dict(region)
                region["verified"] = False
                region["confidence"] = round((region.get("confidence") or 0.0) * 0.6, 3)
                region["note"] = (region.get("note", "") + " | проверка не подтвердила: "
                                  + (answer.get("note") or "")).strip()
                verified.append(region)
        return verified, raw
