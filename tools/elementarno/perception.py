"""Восприятие: изображение → сцена-граф через мультимодальную модель.

Слой намеренно тонкий. Он не «понимает сцену» — он переводит пиксели в
типизированный граф, потому что дальше работают правила с цитатами. Модель
не имеет права придумывать отсутствующие объекты, поэтому промпт отдельно
требует фиксировать отсутствие.

Сырой ответ модели сохраняется рядом со сценой: он часть цепочки доказательств
и должен быть перечитываем.
"""

import base64
import json
import mimetypes
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from .scene import validate_scene

DEFAULT_ENDPOINT = "https://api.minimaxi.chat/anthropic/v1/messages"
DEFAULT_MODEL = "MiniMax-M3"

PROMPT = """Ты — эксперт по осмотру сцены. Твоя задача — перевести фотографию в СТРУКТУРИРОВАННЫЙ ОПИСАТЕЛЬНЫЙ ГРАФ.

ПРАВИЛА ОТВЕТА:
1. Ответ — ТОЛЬКО валидный JSON, без пояснений, без markdown-ограждений.
2. Описывай только то, что реально видно. Не додумывай предметы.
3. Ключевой навык — ЗАМЕЧАТЬ ОТСУТСТВИЕ. Обязательно ищи: пылевой контур от убранного предмета,
   пустой крючок, невыцветший участок среди запылённой поверхности, нарушенный слой пыли,
   следы ног, разводы воды, посторонние следы (грязь, вода). Отсутствие — главная улика.
4. Координаты bbox — нормализованные [x1,y1,x2,y2], 0..1, начало — левый верхний угол.
4a. Ищи следы ремесла и привычек: брызги краски (paint_splash), задетые следы краски (paint_trace),
   стружка и опилки (sawdust), мучная пыль (flour_dust), следы масла и смазки (oil_trace),
   металлическая стружка (metal_swarf), штукатурная пыль (plaster_dust), следы чернил (ink_trace),
   кружки на поверхности (cup_ring). Это улики о занятии человека: красил, пили, пекал, чинил.
5. size_m — ориентировочный размер объекта в метрах, если оценивается; иначе null.
6. Не выдумывай то, чего нет. Лучше пустой массив, чем правдоподобная деталь.

ФОРМАТ JSON:
{
  "surfaces": [{"id":"s1","name":"table","material":"wood","dust_present":true,"dust_state":"even|uneven|patchy|none","wet":false,"sunlit":false,"region":"rX"}],
  "objects": [{"id":"o1","category":"vase","material":"ceramic","state":"new|clean|worn|damaged|fresh|unknown","fill_level":0.0,"size_m":0.25,"on":"s1","wet":false,"shadow_dir":"west|east|north|south|unknown","visible":true,"region":"rX","bbox":[0.1,0.1,0.2,0.2]}],
  "regions": [{"id":"r1","kind":"dust_outline|empty_hook|unfaded_patch|stain|scratch|crack|dent|burn|water_line|mold_patch|footprint|tyre_mark|tool_mark|puddle|condensation|disturbed_dust|mud_footprint|other","shape":"round|rect|irregular","area_m2":0.04,"contrast":0.12,"freshness":"sharp|soft|erased|unknown","edges":"concave|convex|flat|ragged|unknown","bbox":[0.1,0.1,0.2,0.2],"note":"что видно"}],
  "observations": [{"id":"x1","about":"r1","feature":"v_pattern|dust_path|shadow_edge|other","value":true,"confidence":0.8}],
  "light": [{"id":"l1","kind":"window|lamp|sun|unknown","direction":"west|east|north|south","position":"left|right|above|behind"}],
  "anomalies": ["что выглядит необычно или отсутствует"]
}

Верни JSON."""


class PerceptionError(RuntimeError):
    pass


ABSENCE_SWEEP_PROMPT = """Ты эксперт по следовому анализу. Рассмотри фотографию и найди ТОЛЬКО СЛЕДЫ ОТСУТСТВИЯ и необычные локальные признаки.

Что искать:
- dust_outline — контур от предмета, который убрали (пыль заполнила середину, но не края)
- empty_hook — крючок/вешалка, на которой ничего не висит
- unfaded_patch — участок без пыли среди запылённой поверхности
- disturbed_dust — полоса нарушенного слоя пыли
- footprint / mud_footprint — след ноги, особенно грязный или мокрый
- water_line — граница прежнего уровня воды
- mold_patch — очаг плесени
- stain / scratch / tool_mark — пятно, царапина, след инструмента

ВАЖНО: не пересказывай то, что и так очевидно. Нужны только локальные следы.
Если ничего не нашёл — верни пустой массив. Ложная находка хуже пропуска.

ФОРМАТ JSON (только JSON):
{"candidates":[{"kind":"dust_outline","bbox":[0.1,0.1,0.2,0.2],"shape":"rect","area_m2":0.04,"freshness":"sharp","edges":"concave","contrast":0.12,"confidence":0.6,"why":"почему так"}]}

bbox нормализован [x1,y1,x2,y2], 0..1."""

CROP_QUESTION_PROMPT = """Ты эксперт по следовому анализу. Перед тобой КРОП одной области исходной фотографии.

Найди ТОЛЬКО следы ОТСУТСТВИЯ в этом кропе:
- dust_outline — контур от убранного предмета: видна граница, внутри заметно чище, по краям осталась пыль
- unfaded_patch — участок чище окружающей запылённой поверхности
- disturbed_dust — полоса, где слой пыли нарушен
- empty_hook — пустой крючок
- footprint / mud_footprint — след ноги, грязный или мокрый
- water_line — ровная граница прежнего уровня воды
- mold_patch — очаг плесени

Если в кропе ничего из этого нет — верни пустой массив. Ложная находка хуже пропуска.

ФОРМАТ JSON (только JSON):
{"candidates":[{"kind":"dust_outline","confidence":0.0-1.0,"why":"что видно","edges":"concave|convex|flat","freshness":"sharp|soft|erased"}]}"""


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

    Ничего не выдумывается: невалидные ссылки снимаются, факт снятия
    записывается в anomalies. Лучше граф без одной ссылки, чем выдуманная
    поверхность, на которой «стоял» предмет.
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
            obj.pop("region")
        if obj.get("fill_level") is None:
            obj.pop("fill_level", None)
        if obj.get("size_m") is None:
            obj.pop("size_m", None)
        if not obj.get("shadow_dir"):
            obj["shadow_dir"] = "unknown"

    for surface in surfaces:
        region = surface.get("region")
        if region and region not in region_ids:
            surface.pop("region")

    for region in regions:
        for field in ("area_m2", "contrast"):
            if region.get(field) is None:
                region.pop(field, None)

    scene["surfaces"] = surfaces
    scene["objects"] = objects
    scene["regions"] = regions
    return scene, notes


class MiniMaxPerception:
    def __init__(self, model=DEFAULT_MODEL, endpoint=DEFAULT_ENDPOINT, api_key=None, timeout=180,
                 think=False, sweep_absence=True, interrogate_regions=True):
        self.model = model
        self.endpoint = endpoint
        self.api_key = resolve_api_key(api_key)
        self.timeout = timeout
        self.think = think
        self.sweep_absence = sweep_absence
        self.interrogate_regions = interrogate_regions

    def _payload(self, image_b64, media_type, prompt):
        content = [
            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
            {"type": "text", "text": prompt},
        ]
        body = {
            "model": self.model,
            "max_tokens": 4000,
            "messages": [{"role": "user", "content": content}],
        }
        if self.think:
            body["thinking"] = {"type": "enabled", "budget_tokens": 2048}
        return body

    def call(self, image_b64, media_type, prompt):
        body = json.dumps(self._payload(image_b64, media_type, prompt)).encode("utf-8")
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
        latency = round((time.monotonic() - started) * 1000)
        return payload, latency

    @staticmethod
    def text_of(payload):
        parts = []
        for block in payload.get("content", []):
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts).strip()

    @staticmethod
    def extract_json(text):
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise PerceptionError("в ответе модели нет JSON")
        return json.loads(text[start:end + 1])

    def scene_graph(self, image_path, save_raw=None, max_attempts=2):
        path = Path(image_path)
        media_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        image_b64 = base64.b64encode(path.read_bytes()).decode("ascii")

        prompt = PROMPT
        last_error = None
        raw_calls = []
        for attempt in range(1, max_attempts + 1):
            payload, latency = self.call(image_b64, media_type, prompt)
            text = self.text_of(payload)
            raw_calls.append({"prompt": prompt, "payload": payload, "latency_ms": latency})
            try:
                scene = self.extract_json(text)
            except (json.JSONDecodeError, PerceptionError) as exc:
                last_error = f"JSON не разобран: {exc}"
                prompt = PROMPT + f"\n\nПредыдущий ответ не распознан ({last_error}). Верни ТОЛЬКО корректный JSON."
                continue

            scene.setdefault("surfaces", [])
            scene.setdefault("objects", [])
            scene.setdefault("regions", [])
            scene.setdefault("observations", [])
            problems = validate_scene(scene)
            if problems:
                last_error = "; ".join(f"{p['code']}: {p['detail']}" for p in problems[:6])
                prompt = (
                    PROMPT
                    + "\n\nТвой предыдущий граф нарушает схему: "
                    + last_error
                    + "\nИсправь и верни ТОЛЬКО корректный JSON."
                )
                continue

            anomalies = scene.pop("anomalies", [])
            normalized, notes = normalize_scene(scene)
            anomalies.extend(notes)
            scene = normalized

            sweep = None
            if self.sweep_absence:
                sweep_payload, sweep_regions, sweep_latency = self._absence_sweep(image_b64, media_type)
                raw_calls.append({"prompt": ABSENCE_SWEEP_PROMPT, "payload": sweep_payload,
                                  "latency_ms": sweep_latency})
                scene["regions"].extend(sweep_regions)

            interrogation = None
            if self.interrogate_regions:
                interrogation, interrogation_raw = self._interrogate(image_path, scene)
                raw_calls.extend(interrogation_raw)
                known = {(r.get("kind"), tuple(r.get("bbox") or ())) for r in scene["regions"]}
                for region in interrogation:
                    key = (region.get("kind"), tuple(region.get("bbox") or ()))
                    if key not in known:
                        scene["regions"].append(region)
                        known.add(key)

            usage = (raw_calls[0]["payload"].get("usage") or {}) if raw_calls else {}
            meta = {
                "model": self.model,
                "latency_ms": sum(c["latency_ms"] for c in raw_calls),
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "attempts": attempt,
                "anomalies": anomalies,
                "absence_sweep": bool(self.sweep_absence),
                "interrogation": bool(self.interrogate_regions),
                "normalized": bool(notes),
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

        raise PerceptionError(f"не удалось получить корректный сцена-граф: {last_error}")

    def _interrogate(self, image_path, scene, max_crops=4, min_confidence=0.5):
        """Покадровый допрос: кроп + узкий вопрос про следы отсутствия."""
        from .crops import HAS_PIL, crop_normalized

        if not HAS_PIL:
            return [], []

        candidates = []
        for region in scene.get("regions", []):
            bbox = region.get("bbox")
            if not bbox or len(bbox) < 4:
                continue
            area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
            if area < 0.002 or area > 0.6:
                continue
            candidates.append(region)
        candidates.sort(key=lambda r: (r.get("contrast") or 0.0), reverse=True)
        candidates = candidates[:max_crops]

        regions = []
        raw_calls = []
        for index, region in enumerate(candidates, start=1):
            crop_path = Path(f"/tmp/elementarno-crop-{index}.png")
            try:
                cropped = crop_normalized(image_path, crop_path, region["bbox"])
            except Exception:  # noqa: BLE001 — кроп не обязателен
                cropped = None
            if not cropped:
                continue
            with open(cropped, "rb") as handle:
                data = base64.b64encode(handle.read()).decode("ascii")
            payload, latency = self.call(data, "image/png", CROP_QUESTION_PROMPT)
            raw_calls.append({"prompt": CROP_QUESTION_PROMPT, "payload": payload,
                              "latency_ms": latency, "crop_of": region.get("id")})
            try:
                parsed = self.extract_json(self.text_of(payload))
            except (json.JSONDecodeError, PerceptionError):
                continue
            for found in parsed.get("candidates", []) or []:
                confidence = float(found.get("confidence") or 0.0)
                kind = found.get("kind")
                if confidence < min_confidence or not kind:
                    continue
                regions.append({
                    "id": f"i{index}_{len(regions) + 1}",
                    "kind": kind,
                    "shape": region.get("shape", "unknown"),
                    "freshness": found.get("freshness", region.get("freshness", "unknown")),
                    "edges": found.get("edges", region.get("edges", "unknown")),
                    "bbox": region.get("bbox"),
                    "note": found.get("why", ""),
                })
        return regions, raw_calls

    def _absence_sweep(self, image_b64, media_type):
        payload, latency = self.call(image_b64, media_type, ABSENCE_SWEEP_PROMPT)
        text = self.text_of(payload)
        try:
            data = self.extract_json(text)
        except (json.JSONDecodeError, PerceptionError):
            return payload, [], latency
        regions = []
        for index, candidate in enumerate(data.get("candidates", []) or [], start=1):
            kind = candidate.get("kind")
            if not kind:
                continue
            region = {
                "id": f"a{index}",
                "kind": kind,
                "shape": candidate.get("shape", "unknown"),
                "contrast": candidate.get("contrast", 0.1),
                "freshness": candidate.get("freshness", "unknown"),
                "edges": candidate.get("edges", "unknown"),
                "bbox": candidate.get("bbox", [0, 0, 0, 0]),
                "note": candidate.get("why", ""),
            }
            if candidate.get("area_m2") is not None:
                region["area_m2"] = candidate["area_m2"]
            regions.append(region)
        return payload, regions, latency
