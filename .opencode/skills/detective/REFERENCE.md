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
     "note": "светлый прямоугольный контур на столе, ближе к правому краю"},
    {"id": "r2", "kind": "symbol", "shape": "triangle",
     "archetype": "all_seeing_eye", "medium": "карандаш",
     "construction": "by_model",
     "readings": ["детский рисунок с лучами", "заимствованный образец «глаз в треугольнике»"],
     "note": "треугольник с глазом и лучами, нанесён на стене"}
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

Поля знака (`symbol`, `inscription`):

| поле | что означает |
| --- | --- |
| `archetype` | узнанный образец: `all_seeing_eye`, `pentagram`… Пусто, если не опознан |
| `medium` | чем нанесено: карандаш, краска, уголь, процарапано, выжжено |
| `construction` | `by_model` (по образцу) · `freehand` (на глаз) · `unknown` |
| `readings` | несколько прочтений, каждое своими словами. Их должно быть ≥ 2 |

## Виды следов (каталог для след-прохода)

`dust_outline` · `empty_hook` · `unfaded_patch` · `disturbed_dust` ·
`footprint` · `mud_footprint` · `wet_trace` · `water_line` · `mold_patch` ·
`burn` · `paint_splash` · `paint_trace` · `sawdust` · `metal_swarf` ·
`flour_dust` · `oil_trace` · `weld_spatter` · `plaster_dust` · `ink_trace` ·
`cup_ring` · `fingerprint` · `tool_mark` · `tyre_mark` · `scratch` · `crack` ·
`symbol` · `inscription`

Полные описания и правила — в `rules/*.json`.

## Как читать знак

Знак отвечает на два разных вопроса, и путать их — источник половины
ошибок.

**«Что это за знак?»** — прочтение, трактовка. Она может быть неверной,
она помечается как спекулятивная (`kind: interpretation`, потолок 0.4) и
никогда не подпирает проверяемый вывод. Ответ — не один, а несколько:
«детский рисунок» и «заимствованный образец» сосуществуют.

**«Намеренно ли он?»** — проверяемый факт. `construction: by_model` против
`freehand`: симметрия, правильные пропорции, характерные детали образца.
Правило `SEM-003` утверждает только это; `SEM-004` — прочтение, и оно
отдельно помечено как спекулятивное.

Детский рисунок и символ на фотографии неразличимы, пока не спросишь. Поэтому
и спроси.

## Леджер (`ledger.json`)

```json
{
  "claims": [
    {"claim_id": "C-1", "kind": "inference",
     "text": "Предмет убрали недавно: на столе остался пылевой контур",
     "support": [{"finding_id": "F-ABS-001"}],
     "confidence": 0.5, "step": "activity",
     "confounds": ["влажная уборка могла размазать контур"],
     "falsification": "Посветить боковым светом: вогнутый контур — след предмета",
     "refutation": {
       "negation": "контура на столе не было, его придумали",
       "outcome": "survived",
       "note": "боковой свет показал вогнутый край, как у предмета"}}
  ],
  "hypotheses": [
    {"hypothesis_id": "H-1", "text": "Присутствовал в сцене: садовник",
     "claims": ["C-1"], "status": "open", "step": "presence",
     "discriminator": {
       "question": "есть ли следы садового инвентаря у стены?",
       "would_confirm": "инвентарь найден рядом с контуром",
       "would_refute": "инвентаря нет, контур оставлен другим"},
     "kill_log": [{"rule_id": "F-PUZ-004", "note": "совпал рисунок подошвы"}]}
  ]
}
```

`kind`: `observation` · `inference` · `hypothesis` · `interpretation`.
`step`: `scene` · `activity` · `presence` · `role` · `action`.

`refutation` обязателен для утверждений, которые идют дальше вывода улики.
`outcome`: `survived` · `refuted` · `undetermined`. Утверждение с
`outcome: refuted` в ответе быть не должно — убери его.

`discriminator` — вопрос, который разведёт версию с конкурирующими. Без него
версии с одинаковым весом остаются неразличимыми, и движок не сможет
предложить следующий кадр.

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
| `missing_refutation` | утверждение не атаковано, либо в записи об отрицании нет самой проверяемой гипотезы | добавь `refutation` или убери утверждение |
| `refuted_claim_present` | утверждение опровергнуто собственной проверкой | убери утверждение: отрицание победило |

## Ступени лестницы

`scene` → `activity` → `presence` → `role` → `action`

Утверждение опирается на улику своей ступени или соседней снизу. Для
`action` допускается опора на `presence`. Прыжок через ступень — ошибка.

## Оговорки

У каждой улики есть `confounds` — альтернативные объяснения. Переноси их в
`confounds` утверждения и **показывай пользователю**. Именно они отличают
вывод от фантазии. В ответе печатаются обе строки: оговорки улики и оговорки
вывода, — потому что это разные вещи: первое относится к основанию, второе
к тому, что ты из него вывел.

## Профили

`--profile detective|audit|household|mystery` (файл `config/profiles.json`).
Профиль задаёт набор доменных паков, режим, персону и пороги.
