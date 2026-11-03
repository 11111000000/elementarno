# Форматы и команды

Справочник для скилла. Формальная версия — `docs/PROTOCOL.md` и
`docs/MATH.md`.

## Сцена-граф (`scene.json`)

```json
{
  "surfaces": [
    {"id": "s1", "name": "table", "material": "wood",
     "dust_present": true, "dust_state": "even", "wet": false}
  ],
  "objects": [
    {"id": "o1", "category": "mug", "material": "ceramic",
     "state": "clean", "size_m": 0.1, "on": "s1", "visible": true,
     "note": "слева от края, ближе к зрителю"}
  ],
  "regions": [
    {"id": "r1", "kind": "dust_outline", "shape": "round",
     "note": "светлый прямоугольный контур на столе, ближе к правому краю"}
  ],
  "observations": [
    {"id": "x1", "about": "o1", "feature": "full", "value": "налита доверху"}
  ]
}
```

`kind` региона — только из перечня `schemas/scene-graph.schema.json`.
`on` ссылается на id поверхности. `about` — id объекта, поверхности или
региона.

**Привязки — словами.** Координаты мультимодальная модель выдаёт
ненадёжно, и кроп по ним уезжает с реальной областью.

## Виды следов (каталог для след-прохода)

`dust_outline` · `empty_hook` · `unfaded_patch` · `disturbed_dust` ·
`footprint` · `mud_footprint` · `wet_trace` · `water_line` · `mold_patch` ·
`burn` · `paint_splash` · `paint_trace` · `sawdust` · `metal_swarf` ·
`flour_dust` · `oil_trace` · `weld_spatter` · `plaster_dust` · `ink_trace` ·
`cup_ring` · `fingerprint` · `tool_mark` · `tyre_mark` · `scratch` · `crack`

Полные описания и правила — в `rules/*.json`.

## Леджер (`ledger.json`)

```json
{
  "claims": [
    {"claim_id": "C-1", "kind": "inference",
     "text": "Предмет убрали недавно: на столе остался пылевой контур",
     "support": [{"finding_id": "F-ABS-001"}],
     "confidence": 0.5, "step": "activity",
     "confounds": ["влажная уборка могла размазать контур"],
     "falsification": "Посветить боковым светом: вогнутый контур — след предмета"}
  ],
  "hypotheses": [
    {"hypothesis_id": "H-1", "text": "Присутствовал в сцене: садовник",
     "claims": ["C-1"], "status": "open", "step": "presence",
     "kill_log": [{"rule_id": "F-PUZ-004", "note": "совпал рисунок подошвы"}]}
  ]
}
```

`kind`: `observation` · `inference` · `hypothesis` · `interpretation`.
`step`: `scene` · `activity` · `presence` · `role` · `action`.

## Команды

```bash
cd ~/Projects/elementarno

# улики по правилам: что сработало, с цитатами и источниками
python3 -m tools.elementarno.cli findings scene.json

# проверка леджера: ссылки, потолки, формулировки, лестница
python3 -m tools.elementarno.cli verify scene.json --ledger ledger.json

# версии, веса, kill-log, вердикт
python3 -m tools.elementarno.cli tell scene.json --ledger ledger.json --persona doyle

# следующий вопрос по ценности информации
python3 -m tools.elementarno.cli nextshot scene.json --hypotheses ledger.json

# различия между кадрами
python3 -m tools.elementarno.cli diff before.json after.json --json

# загадка по серии кадров
python3 -m tools.elementarno.cli puzzle puzzle.json --persona doyle

# сессия: накопление кадров и уточняющие вопросы
python3 -m tools.elementarno.cli session --image a.jpg --image b.jpg --state case.json
```

## Коды ошибок протокола

| Код | Что означает | Что делать |
| --- | --- | --- |
| `unsupported_claim` | нет ни одной ссылки на улику | добавь `support` или убери утверждение |
| `unresolved_citation` | такой `finding_id` не существует | проверь id против вывода `findings` |
| `overconfidence` | уверенность выше потолка улики | снизь до потолка |
| `draft_backs_strong_claim` | черновиковое правило обосновывает сильный вывод | снизь уверенность до 0.5 и пометь `provisional` |
| `missing_provisional_flag` | то же, но не помечено | добавь `provisional: true` |
| `ladder_break` | утверждение опережает свою улику больше чем на ступень | смени ступень или возьми другую улику |
| `accusatory_framing` | обвинение («виновен», «убийца») | переформулируй как присутствие или действие |
| `personality_inference` | вывод о свойствах личности | убери или переформулируй как действие |
| `interpretation_too_confident` | трактовка выше 0.4 без маркировки | `speculative: true` и уверенность ≤ 0.4 |
| `hypothesis_without_falsification` | у версии нет условия опровержения | добавь `falsification` |
| `rejected_without_kill_log` | отброшенная версия без записи, чем убита | заполни `kill_log` |

## Ступени лестницы

`scene` → `activity` → `presence` → `role` → `action`

Утверждение опирается на улику своей ступени или соседней снизу. Для
`action` допускается опора на `presence`. Прыжок через ступень — ошибка.

## Оговорки

У каждой улики есть `confounds` — альтернативные объяснения. Переноси их в
`confounds` утверждения и **показывай пользователю**. Именно они отличают
вывод от фантазии.

## Профили

`--profile detective|audit|household|mystery` (файл `config/profiles.json`).
Профиль задаёт набор доменных паков, режим, персону и пороги.
