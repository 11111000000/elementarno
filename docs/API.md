# HTTP API ЭЛЕМЕНТАРНО

Тонкий HTTP-слой над движком: тот же протокол доказательности, те же правила,
тот же рендеринг — только в JSON и без терминала.

Сервер собран на стандартной библиотеке (`http.server` + `ThreadingHTTPServer`),
внешних зависимостей нет. Логика разбора живёт в чистых функциях
`elementarno.server.handle_*`: они принимают словарь и возвращают словарь,
поэтому проверяются без сервера и без сети.

## Запуск

```sh
cd /home/az/Projects/elementarno
PYTHONPATH=tools python3 -m elementarno.server
```

| Переменная | Значение по умолчанию | Смысл |
| --- | --- | --- |
| `ELEMENTARNO_PORT` | `8733` | порт прослушивания |
| `ELEMENTARNO_HOST` | `127.0.0.1` | адрес прослушивания |
| `ELEMENTARNO_RULES` | `<репозиторий>/rules` | каталог паков правил |
| `ELEMENTARNO_API_QUIET` | — | `1` — не писать журнал запросов в stderr |

Флаги `--host` и `--port` перекрывают переменные окружения.

Сервер по умолчанию слушает только петлю: наружу он не выставлен.

## Общие правила

- Тело запроса — JSON-объект. Пустое тело считается пустым объектом.
- Ответ всегда JSON с `Content-Type: application/json; charset=utf-8`.
- Ошибка никогда не роняет сервер и никогда не приходит HTML:

```json
{
  "error": "scene_not_found",
  "detail": "файл сцены не найден: /tmp/нет-такого.json"
}
```

| Код | Когда |
| --- | --- |
| `400 bad_request` | тело не JSON, нет обязательного поля, недопустимое значение параметра |
| `404 scene_not_found` / `404 image_not_found` | нет файла сцены или изображения |
| `404 not_found` | неизвестный путь |
| `405 method_not_allowed` | путь есть, но метод не тот |
| `500 internal_error` | непредусмотренный сбой (сервер продолжает работать) |
| `502 perception_failed` / `502 reasoning_failed` | модель не дала пригодный результат |
| `503 model_unavailable` | не задан ключ MiniMax |

Общие необязательные поля запроса:

| Поле | Смысл |
| --- | --- |
| `packs` | ограничить правила списком паков (`["core", "absence"]`) |
| `rules_dir` | каталог правил, если он нестандартный |
| `persona` | `plain` (по умолчанию в `/analyze` — `doyle`), `doyle`, `forensic` |
| `mode` | `detective` (по умолчанию), `audit`, `forensic`, `solve`, `nextshot` |
| `min_findings` | сколько улик нужно для вердикта, по умолчанию `1` |
| `model` | модель MiniMax, по умолчанию `MiniMax-M3` |

---

## GET /health

Проверка живости сервера.

```sh
curl -s http://127.0.0.1:8733/health
```

```json
{
  "ok": true,
  "version": "0.2.0"
}
```

---

## POST /perceive

Фотография → сцена-граф. Вызывается мультимодальная модель.

**Тело:** `{"image_path": "…"}`, необязательно `model`, `think`.

```sh
curl -s -X POST http://127.0.0.1:8733/perceive \
  -H 'Content-Type: application/json' \
  -d '{"image_path": "photos/кухня.jpg"}'
```

Ответ — сам сцена-граф плюс метаданные вызова:

```json
{
  "surfaces": [{"id": "s1", "name": "table", "material": "wood", "dust_present": true, "dust_state": "even"}],
  "objects": [],
  "regions": [{"id": "c1", "kind": "dust_outline", "bbox": [0.2, 0.2, 0.4, 0.4], "note": "контур на столе"}],
  "observations": [],
  "light": [],
  "meta": {"perception": {"model": "MiniMax-M3", "latency_ms": 8120, "calls": 3}},
  "perception_meta": {"model": "MiniMax-M3", "latency_ms": 8120, "calls": 3,
                      "input_tokens": 4210, "output_tokens": 640, "regions_found": 1}
}
```

---

## POST /analyze

Сцена-граф → улики → утверждения → версии → текст. Ядро API.

**Тело:** `image_path` (фотография, разбирается моделью) **или** `scene_path`
(готовая сцена-граф на диске — без вызова модели). Необязательно: `persona`,
`mode`, `packs`, `min_findings`.

```sh
curl -s -X POST http://127.0.0.1:8733/analyze \
  -H 'Content-Type: application/json' \
  -d '{"scene_path": "eval/benchmarks/protocol-core/scenes/absence-dust-outline.json", "persona": "plain"}'
```

```json
{
  "findings": [
    {
      "finding_id": "F-ABS-001",
      "rule_id": "ABS-001",
      "rule_version": 1,
      "pack": "absence",
      "title": "Пылевой контур от убранного предмета",
      "layer": "epistemic",
      "step": "activity",
      "inference": "На поверхности сохранился контур предмета, которого больше нет…",
      "anchors": ["r1"],
      "tags": ["removal", "recent_movement"],
      "sources": [{"ref": "Kirk's Fire Investigation, 8th ed., Pearson 2019", "note": "", "verified": false}],
      "confounds": ["Влажная уборка может размазать контур и выдать его за свежий"],
      "exceptions": ["Контур появляется и без предметов: трещина, скол, вмятина в дереве"],
      "falsification": {"refuted_by": ["ABS-004"], "physical_test": "Посветить боковым светом…"},
      "confidence_prior": 0.65,
      "confidence_ceiling": 0.5,
      "provisional": true
    }
  ],
  "claims": [
    {
      "claim_id": "C-ABS-001",
      "kind": "inference",
      "text": "На поверхности сохранился контур предмета, которого больше нет…",
      "support": [{"finding_id": "F-ABS-001"}],
      "confidence": 0.5,
      "provisional": true,
      "confounds": ["Влажная уборка может размазать контур и выдать его за свежий"],
      "falsification": "Посветить боковым светом: вогнутый контур — след предмета…",
      "step": "activity"
    }
  ],
  "hypotheses": [],
  "report": {
    "errors": [],
    "warnings": [],
    "citation_completeness": 1.0,
    "claims": 1,
    "resolvable_claims": 1
  },
  "text": "Что видно на фотографии и что из этого следует.\n\nАктивность:\n…",
  "verdict": "sufficient_evidence",
  "meta": {"source": "scene_path"}
}
```

`claims` — только те, что прошли валидатор протокола; отклонённые перечислены
в `report.errors` с кодом и пояснением. Пустой `findings` и вердикт
`insufficient_evidence` — корректный ответ, а не сбой.

---

## POST /reason

Сцена-граф → рассуждение модели → связные утверждения и версии.

**Тело:** `scene_path` (обязательно), необязательно `persona`, `mode`,
`instruction`, `no_think`, `min_findings`.

```sh
curl -s -X POST http://127.0.0.1:8733/reason \
  -H 'Content-Type: application/json' \
  -d '{"scene_path": "eval/benchmarks/protocol-core/scenes/absence-dust-outline.json", "persona": "doyle"}'
```

```json
{
  "claims": [{"claim_id": "C-1", "kind": "inference", "text": "…", "support": [{"finding_id": "F-ABS-001"}], "confidence": 0.4, "step": "activity"}],
  "hypotheses": [{"hypothesis_id": "H-1", "text": "…", "claims": ["C-1"], "status": "open", "log_odds": 1.204, "support_findings": ["F-ABS-001"]}],
  "report": {"errors": [], "warnings": [], "citation_completeness": 1.0, "claims": 1, "resolvable_claims": 1},
  "text": "Позвольте представить вам, мой дорогой Уотсон, наши улики…",
  "meta": {"model": "MiniMax-M3", "latency_ms": 4210, "calls": 1, "dropped": {}}
}
```

Ответ модели пропускается через санитайзер: утверждение без ссылки на улику,
с уверенностью выше потолка, обвинительной формулировкой или разрывом
лестницы обобщения в ответ не попадает — количество отброшенного видно в
`meta.dropped`.

---

## POST /nextshot

Какой следующий кадр различит конкурирующие версии. Ценность вопроса —
`eig` в битах.

**Тело:** `scene_path` (обязательно), необязательно `limit` (по умолчанию `3`).

```sh
curl -s -X POST http://127.0.0.1:8733/nextshot \
  -H 'Content-Type: application/json' \
  -d '{"scene_path": "eval/benchmarks/protocol-core/scenes/absence-dust-outline.json"}'
```

```json
{
  "questions": [
    {
      "id": "surface-wide",
      "question": "Снимите поверхность целиком, включая края и углы, где обычно скапливается пыль",
      "why": "края и углы — места, где след удалённого предмета виден лучше всего",
      "kinds": ["dust_outline", "unfaded_patch", "stain", "scratch"],
      "eig": 0.0
    }
  ],
  "count": 3,
  "hypotheses": 0,
  "found_kinds": ["dust_outline"]
}
```

---

## POST /session

Серия фотографий: состояние дела, накопленные улики и следующий вопрос.

**Тело:** `state_path` (файл состояния; создаётся, если его нет),
`image_path` (новый кадр) или `scene_path` (готовая сцена-граф).

```sh
curl -s -X POST http://127.0.0.1:8733/session \
  -H 'Content-Type: application/json' \
  -d '{"state_path": "/tmp/case-1.json", "image_path": "photos/кухня-2.jpg"}'
```

```json
{
  "state": {"rounds": [{"source": "photos/кухня-2.jpg", "regions": 1, "objects": 4}],
            "questions": [], "participants": [], "scene": {"surfaces": [], "objects": [], "regions": []}},
  "rounds": 1,
  "findings": [{"finding_id": "F-ABS-001", "rule_id": "ABS-001", "…": "…"}],
  "claims": [{"claim_id": "C-ABS-001", "…": "…"}],
  "hypotheses": [],
  "participants": [],
  "questions": [{"id": "side-light", "question": "Снимите сцену с боковым светом…", "eig": 0.0}],
  "verdict": "sufficient_evidence",
  "meta": {"source": "image_path", "model": "MiniMax-M3", "latency_ms": 8120}
}
```

Повторный вызов с тем же `state_path` продолжает ту же сессию: кадры
накапливаются, улики пересчитываются, вопросы добавляются.

---

## Проверка без сети

Обработчики — обычные функции: словарь на входе, словарь на выходе. Модель
при этом не вызывается, если вместо `image_path` передан `scene_path`.

```python
import sys
sys.path.insert(0, "tools")
from elementarno import server

result = server.handle_analyze({
    "scene_path": "eval/benchmarks/protocol-core/scenes/absence-dust-outline.json",
})
print(result["verdict"], [f["rule_id"] for f in result["findings"]])
```

Тесты живут в `tests/test_server.py`: сервер поднимается на порту `0`
(выбор свободного порта ядром), проверяются `/health`, разбор готовой сцены
через HTTP, ответ `404` с JSON на неизвестный путь и коды ошибок.
