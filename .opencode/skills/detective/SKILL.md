---
name: detective
description: Use when the user asks to analyse a photo or a scene for hidden clues, deduce what happened, compare two images for differences, or answer "who did it" riddles. Runs the ЭЛЕМЕНТАРНО evidence engine (scene graph → cited rules → competing hypotheses → narrated verdict) instead of improvising an answer.
license: MIT
metadata:
  engine: "~/Projects/elementarno"
---

# Детектив: разбор сцены по уликам

Ты не сочиняешь историю о фотографии. Ты прогоняешь сцену через
движок `ЭЛЕМЕНТАРНО` и показываешь **улики со ссылками на правила**.

## Движок

```
~/Projects/elementarno
```

Зависимостей нет (только стандартная библиотека). Для кроп-допроса нужен
Pillow: `cd ~/Projects/elementarno && nix develop --command ...`

Ключ MiniMax: переменная `MINIMAX2_API_KEY` (или `MINIMAX_API_KEY`).
Первый ключ может быть исчерпан по лимиту — тогда используй второй.

## Команды

Один кадр, полный разбор с персоной:

```bash
cd ~/Projects/elementarno && python3 -m tools.elementarno.cli analyze photo.jpg --persona doyle
```

Только сцена-граф (когда нужно посмотреть, что вообще извлечено):

```bash
python3 -m tools.elementarno.cli perceive photo.jpg --out /tmp/scene.json --raw /tmp/raw.json
```

Только улики с цитатами и источниками:

```bash
python3 -m tools.elementarno.cli findings /tmp/scene.json
```

Два кадра: что изменилось

```bash
python3 -m tools.elementarno.cli diff before.jpg-graph.json after.jpg-graph.json --json
```

Загадка по серии кадров (формат: `puzzle.json` со списком `suspects` и `traits`):

```bash
python3 -m tools.elementarno.cli puzzle puzzle.json --persona doyle
```

## Правила, которые нельзя нарушать

1. **Не пересказывай вывод своими словами без цитат.** Каждое утверждение
   должно нести `[RULE-ID]`. Если убрать цитаты — исчезнет главное свойство.
2. **Не выдумывай улики.** Если движок вернул 0 улик — так и скажи:
   «улик недостаточно». Это корректный ответ, а не провал.
3. **Не поднимай уверенность.** Потолок задаёт правило (`confidence_ceiling`);
   черновиковое правило не может обосновать сильный вывод.
4. **Не переходи от улики к персонажу напрямую.** Связь идёт через метки
   (`tags`) правила и `traits` подозреваемого. Нет совпадения меток — нет
   связи.
5. **Оговорки показывай.** У каждой улики есть `confounds` — их нельзя
   опускать: именно они отличают вывод от фантазии.
6. **Про реальных людей.** Формулировка «сценарий, совместимый со сценой».
   Никогда «X сделал Y» по фотографии лица.
7. **Интерпретация — отдельно.** Если правило из слоя `semiotics`, пометь
   вывод как спекулятивный и не выше 0.4.

## Персона

`--persona doyle` — повествование в стиле Конан Дойла, `forensic` —
криминалистический протокол, `plain` — нейтрально. Персона меняет тон, но не
содержание: утверждения, уверенности и цитаты остаются теми же.

## Если что-то сломалось

- `PerceptionError: не удалось получить корректный сцена-граф` — модель дважды
  нарушила схему. Покажи `raw.json`: там видно, что именно она вернула.
- Пусто в `regions` при явных следах — модель не увидела отсутствие. Это
  известное слабое место (affirmation bias); предложи снять кадр с боковым
  светом, а не выдумывай улику.
- Нет `pillow` — кроп-допрос не выполняется, качество падает. Запусти через
  `nix develop`.
