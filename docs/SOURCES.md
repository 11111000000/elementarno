# Ведомость источников правил

Дата проверки: **2026-11-03**. Объект: 31 уникальных `sources[].ref` из 56 правил (`rules/*.json`).

Документ отвечает на один вопрос: **существует ли источник, и подтверждает ли он то, что написано в его поле `note`**. Это не переписывание правил и не рецензия правил.

## 0. Честные границы проверки

1. **Я не человек-эксперт.** Проверка — это проверка **существования и содержания** документа, а не рецензия правила. Вердикт `confirmed` означает «документ найден, и в нём есть подтверждение утверждения из `note`»; он не означает, что правило корректно или что его уверенность оправдана.
2. **`partial` означает в том числе «документ есть, но утверждение из `note` в нём не подтверждено».** Ни один `partial` не выдавался за подтверждение.
3. **`not_found` означает «найти или проверить не удалось»**, а не «документа нет».
4. **Вердикт по памяти не выставлялся.** Каждый `confirmed` подкреплён конкретным местом в документе.
5. **`verified: true` ставится только там, где вердикт `confirmed` и `note` точно соответствует прочитанному тексту.** Для остальных — `verified: false`, даже когда документ существует.
6. **Правила в `rules/semiotics.json` не трогались** (владелец ветки): их источники приведены здесь, но ссылки и `note` оставлены как есть.
8. **Одна запись может закрывать несколько строк `ref`.** Правила могут ссылаться на один документ разными строками (например, ANSI/ASB 070-22 и 011-22 отдельно и вместе). Такие варианты объявлены в ведомости строкой «входит в запись» и при сверке приводятся к одной записи.
7. **Одно исключение из правила 5:** в `PRES-004` источник FRE Rule 1002 подтверждён (текст прочитан), но флаг `verified` оставлен `false` — контрактный тест `tests/test_household.py` требует, чтобы у новых черновиков HOME-005 и PRES-004 источники оставались непроверенными. Это ограничение базы, а не оценка документа.

### Что важно про «поднятие потолка»

`tools/elementarno/rules.py:112` — `is_provisional` истинно, если `review_status != "reviewed"` **или** хотя бы один источник не `verified`. Потолок правила равен `min(confidence_ceiling, 0.5)`, пока правило черновик.

Проверка источников снимает **только одно из двух** условий. Чтобы потолок вырос, владелец ветки должен дополнительно проставить `sources[].verified: true` (где это сделано) **и** перевести `review_status` правила в `"reviewed"` — а это экспертная рецензия правила, которой здесь не было.

## 1. Как проверялось

Что сработало:

- **OSAC Registry (NIST)** — полная выгрузка реестра (`https://www.nist.gov/osac/registry-export?_format=csv`, 264 стандарта) с проверкой точных названий подкомитетов и заголовков; отсюда все замены выдуманных подкомитетов.
- **PDF целиком** — WHO Guidelines (2.7 МБ), ENFSI BPM для почерка (5.5 МБ), «The Book of Symbols» (archive.org), страницы FRE 1001 и 1002.
- **Страницы издателей и каталогов** — who.int, nfpa.org, enfsi.eu, taschen.com, law.cornell.edu, nij.ojp.gov, fda.gov, link.springer.com, arxiv.org, openlibrary.org, archive.org, Wikipedia.
- **Wayback Machine** — для страниц, закрытых сейчас (iicrc.org, iicweb.org).

Что не сработало (и повлияло на вердикты):

- **Платные тексты**: Kirk's, Serway, NFPA LiNK (NFPA 921), ANSI/IICRC S500, Sebeok в archive.org, стандарты ASTM/ASB. Для них проверялось существование и библиографическое описание, но не содержание.
- **Блокировки**: pearson.com, iicrc.org (GoDaddy), ANSI webstore, HathiTrust, Google Books API, Semantic Scholar, arXiv API.
- **Поисковые системы** (DuckDuckGo, Bing, Mojeek, Google, Marginalia) — к середине работы начали отдавать CAPTCHA и подменённые выдачи; поздние находки делались только по прямым адресам и каталогам.
- **OpenStax и Physics LibreTexts** — текст разделов о геометрии теней достать не удалось (JS-рендеринг, 403 на PDF-ассеты), поэтому PHY-002/PHY-003 опираются на прочитанную энциклопедическую статью, а не на учебник.
- **Буклет NIJ «Eyewitness Evidence»** — PDF отдаётся как сканы (текстовых слоёв нет), прочитано только описание издателя на странице NIJ.

## 2. Сводная таблица

| # | Источник (`ref`) | Вердикт | Правила |
| --- | --- | --- | --- |
| 3.1 | `Federal Rules of Evidence, Rule 1002 (Requirement of the Original), Cornell Legal Information Institute` | **confirmed** | PRES-004 |
| 3.2 | `The Abduction of Sherlock Holmes: A Dataset for Visual Abductive Reasoning, Hessel, Hwang, Bhagavatula, Choi, ECCV 2022, Springer LNCS 13696 — абдуктивные связки «признак → бытовое объяснение»` | **confirmed** | PUZ-003 |
| 3.3 | `The Abduction of Sherlock Holmes: A Dataset for Visual Abductive Reasoning, Hessel, Hwang, Bhagavatula, Choi, ECCV 2022, Springer LNCS 13696 — формат «улика → вывод» с локализацией улики` | **confirmed** | PUZ-001 |
| 3.4 | `WHO Guidelines for Indoor Air Quality: Dampness and Mould, 2009` | **confirmed** | BIO-002, WAT-002 |
| 3.5 | `Wikipedia, статья «Shadow» (свободная энциклопедия)` | **confirmed** | PHY-002, PHY-003 |
| 3.6 | `Схема сцены-графа ЭЛЕМЕНТАРНО, schemas/scene-graph.schema.json — определения ссылок (observations[].about, objects[].on, regions[].region)` | **confirmed** | PHY-001 |
| 3.7 | `ANSI/IICRC S500, Standard and Reference Guide for Professional Water Damage Restoration, 4th ed. 2015 (IICRC)` | partial | WAT-001, WAT-003 |
| 3.8 | `ENFSI Best Practice Manual for the Forensic Examination of Handwriting, ENFSI-BPM-FHX-01, Ed. 04 (2022)` | partial | SEM-003 |
| 3.9 | `Eyewitness Evidence: A Guide for Law Enforcement, National Institute of Justice (1999)` | partial | PRES-004 |
| 3.10 | `NFPA 921: Guide for Fire and Explosion Investigations, 2024 edition (National Fire Protection Association; в реестре OSAC — подкомитет Fire & Explosion Investigation)` | partial | FIRE-001, FIRE-002 |
| 3.11 | `NL-Eye: Abductive NLI for Images, 2024 (arXiv:2410.02613)` | partial | SEM-001, SEM-002 |
| 3.12 | `OSAC Registry (NIST), подкомитет Crime Scene Investigation & Reconstruction: ANSI/ASB 159-24 (Standard for Scene Investigation and Reconstruction — Foundational Principles), OSAC 2023-N-0002 (Standard for Scene Documentation Procedures), OSAC 2021-N-0018 (Standard for On-Scene Collection and Preservation of Physical Evidence)` | partial | ABS-001, ABS-002, ABS-003, ABS-004, HOME-001, HOME-002, HOME-003, OFF-001, OFF-004, PUZ-002, PUZ-006, TRD-007 |
| 3.13 | `OSAC Registry (NIST), подкомитет Firearms & Toolmarks: ANSI/ASB 162-24 (Standard Method for the Forensic Examination and Documentation of Non-Firearm Tools and Toolmarks)` | partial | MECH-002 |
| 3.14 | `OSAC Registry (NIST), подкомитет Firearms & Toolmarks: OSAC 2024-S-0002 (Standard Test Method for the Examination and Comparison of Toolmarks for Source Attribution)` | partial | MECH-002 |
| 3.15 | `OSAC Registry (NIST), подкомитет Footwear & Tire: OSAC 2023-S-0017 (Standard for the Articulation of Footwear and Tire Interpretations), ANSI/ASB BPR 052-22 (Best Practice Recommendation for the Detection and Collection of Footwear and Tire Impression Evidence)` | partial | GRD-003, HOME-004, MECH-001, PRES-001, PUZ-004 |
| 3.16 | `OSAC Registry (NIST), подкомитет Forensic Document Examination: ANSI/ASB 070-22 (Standard for Examination of Handwritten Items), ANSI/ASB 011-22 (Scope of Expertise in Forensic Document Examination)` | partial | OFF-002, SEM-005, TRD-008 |
| 3.18 | `OSAC Registry (NIST), подкомитет Friction Ridge: OSAC 2023-N-0020 (Standard for the On-Scene Collection and Preservation of Friction Ridge Impressions), OSAC 2022-N-0033 (Standard for Processing Evidence for the Detection of Friction Ridge Impressions), OSAC 2023-S-0026 (Task-Relevant Information in Friction Ridge Examination)` | partial | OFF-003, PRES-002, PRES-003, TRD-010 |
| 3.19 | `OSAC Registry (NIST), подкомитет Trace Materials` | partial | HOME-005 |
| 3.20 | `OSAC Registry (NIST), подкомитет Trace Materials: ANSI/ASTM E1610-18 (Standard Guide for Forensic Paint Analysis and Comparison), ANSI/ASTM E2808-21a (Standard Guide for Microspectrophotometry in Forensic Paint Analysis)` | partial | TRD-001, TRD-010, TRD-011 |
| 3.21 | `OSAC Registry (NIST), подкомитет Trace Materials: ANSI/ASTM E3272-23 (Standard Guide for the Collection of Soils and Other Geological Evidence for Criminal Forensic Applications), OSAC 2025-S-0011 (Standard Guide for Polarized Light Microscopy in the Forensic Examination and Comparison of Soils)` | partial | GRD-001, GRD-004, TRD-002, TRD-003, TRD-006, TRD-011 |
| 3.22 | `OSAC Registry (NIST), подкомитет Trace Materials: ANSI/ASTM E3294-23 (Standard Guide for Forensic Analysis of Geological Materials by Powder X-Ray Diffraction)` | partial | TRD-005 |
| 3.23 | `OSAC Registry (NIST), подкомитет Trace Materials: ANSI/ASTM E3296-22 (Standard Guide for Forensic Examination of Polymers by Pyrolysis Gas Chromatography and Pyrolysis Gas Chromatography-Mass Spectrometry)` | partial | TRD-004 |
| 3.24 | `OSAC Registry (NIST), подкомитет Trace Materials: ANSI/ASTM E3462-25e1 (Standard Guide for Interpretation and Reporting in Forensic Comparisons of Trace Materials), ANSI/ASTM E3457-25 (Standard Guide for Detection and Preservation of Forensic Trace Evidence)` | partial | TRD-009 |
| 3.25 | `OSAC Registry (NIST), подкомитет Trace Materials: ANSI/ASTM E3501-25 (Standard Guide for Forensic Analysis of Geological Materials by Scanning Electron Microscopy and Energy Dispersive X-Ray Spectrometry)` | partial | TRD-005 |
| 3.26 | `OSAC Registry (NIST), подкомитет Wildlife Forensic Biology: ANSI/ASB 028-19 (Wildlife Forensics Morphology Standards)` | partial | BIO-001 |
| 3.27 | `OSAC Registry (NIST), подкомитет Wildlife Forensic Biology: ANSI/ASB 029-19 (Report Writing in Wildlife Forensics: Morphology and Genetics)` | partial | BIO-001 |
| 3.28 | `Ronnberg, A. The Book of Symbols: Reflections on Archetypal Images, TASCHEN, 2010` | partial | SEM-004 |
| 3.29 | `The Abduction of Sherlock Holmes: A Dataset for Visual Abductive Reasoning, Hessel, Hwang, Bhagavatula, Choi, ECCV 2022, Springer LNCS 13696 — изменение обстановки между наблюдениями` | partial | PUZ-005 |
| 3.30 | `The Abduction of Sherlock Holmes: A Dataset for Visual Abductive Reasoning, Hessel, Hwang, Bhagavatula, Choi, ECCV 2022, Springer LNCS 13696 — изменение состава сцены между наблюдениями` | partial | PUZ-007 |
| 3.31 | `Схема сцены-графа ЭЛЕМЕНТАРНО, schemas/scene-graph.schema.json — определение fill_level` | partial | PHY-004 |
| 3.32 | `Hall, J. Dictionary of Subjects and Symbols in Art, J. Murray, 1974; Routledge, 2018` | partial | SEM-004 |

Итого: **confirmed — 6, partial — 25, not_found — 0**.

Нумерация записей сквозная: 3.1–3.32, запись 3.17 вышла из употребления вместе со слиянием двух записей Forensic Document Examination (3.16 и 3.17 → 3.16) и не переиспользуется. Номер 3.32 освободился в этой же правке — запись Sebeok снята как неподтверждённая — и отдан новой записи Hall (3.32).

## 3. Реестр источников

### 3.1 `Federal Rules of Evidence, Rule 1002 (Requirement of the Original), Cornell Legal Information Institute`

- **вердикт:** confirmed
- **note в правилах:** «содержание фотографии доказывается оригиналом: Rule 1002 — «An original writing, recording, or photograph is required in order to prove its content u…»
- **правила:** PRES-004
- **что подтверждено:** Текст статьи прочитан: «An original writing, recording, or photograph is required in order to prove its content unless these rules or a federal statute provides otherwise». Примечание Комитета: «The assumption should not be made that the rule will come into operation on every occasion when use is made of a photograph in evidence. On the contrary, the rule will seldom apply to ordinary photographs». Это и есть `note` правила PRES-004.
- **что не подтверждено:** Ничего; важно, что номер статьи теперь верный — раньше стоял Rule 1001 (определения), где самой нормы нет.
- **примечание:** в правиле PRES-004 флаг `verified` оставлен `false`: контрактный тест `tests/test_household.py` требует, чтобы у новых черновиков HOME-005 и PRES-004 источники оставались непроверенными. Подтверждение ниже относится к тексту статьи, а не к статусу правила.
- **url:** https://www.law.cornell.edu/rules/fre/rule_1002
- **дата проверки:** 2026-11-03

### 3.2 `The Abduction of Sherlock Holmes: A Dataset for Visual Abductive Reasoning, Hessel, Hwang, Bhagavatula, Choi, ECCV 2022, Springer LNCS 13696 — абдуктивные связки «признак → бытовое объяснение»`

- **вердикт:** confirmed
- **note в правилах:** «абдуктивные связки «признак → бытовое объяснение»: 363 тысячи пар (clue, inference), где наблюдатель сначала «observe[s] and identif[ies] salient clu…»
- **правила:** PUZ-003
- **что подтверждено:** Аннотация: «We present Sherlock, an annotated corpus of 103K images… we collect 363K (clue, inference) pairs»; пример из работы: «if we see a “20 mph” sign alongside a road, we might assume the street sits in a residential area». Связка «признак → бытовое объяснение» — ровно то, как устроен набор.
- **что не подтверждено:** Ничего по заявленному `note`.
- **url:** https://link.springer.com/chapter/10.1007/978-3-031-20059-5_32
- **дата проверки:** 2026-11-03

### 3.3 `The Abduction of Sherlock Holmes: A Dataset for Visual Abductive Reasoning, Hessel, Hwang, Bhagavatula, Choi, ECCV 2022, Springer LNCS 13696 — формат «улика → вывод» с локализацией улики`

- **вердикт:** confirmed
- **note в правилах:** «формат «улика → вывод» с локализацией улики: участники сначала «observe and identify salient clues within images … and then provide a plausible infer…»
- **правила:** PUZ-001
- **что подтверждено:** Глава существует: Jack Hessel, Jena D. Hwang, Chandra Bhagavatula, Yejin Choi; Computer Vision – ECCV 2022, LNCS 13696, Springer, опубликовано 29 октября 2022, DOI 10.1007/978-3-031-20059-5_32. Аннотация: «participants first observe and identify salient clues within images (e.g., objects, actions) and then provide a plausible inference about the scene, given the clue»; оценка включает «(ii) localize evidence for inferences via bounding boxes».
- **что не подтверждено:** Ничего по заявленному `note`; набор состоит из отдельных изображений, а не из пар кадров «до/после».
- **url:** https://link.springer.com/chapter/10.1007/978-3-031-20059-5_32
- **дата проверки:** 2026-11-03

### 3.4 `WHO Guidelines for Indoor Air Quality: Dampness and Mould, 2009`

- **вердикт:** confirmed
- **note в правилах:** «признаки плесени и их связь с влажностью»; «связь влаги и роста плесени»
- **правила:** BIO-002, WAT-002
- **что подтверждено:** Документ существует (WHO, 1 января 2009, 248 с., ISBN 9789289041683); полный текст PDF прочитан. «filamentous fungi (mould), growing indoors when sufficient moisture is available»; dampness — «a strong, consistent indicator of risk»; «Dampness was defined on the basis of self-reported indicators, such as water leakage or damage, bubbles or discoloration of floor coverings, and visible mould growth indoors on walls, floors or ceilings»; модель индекса роста плесени M = 0…6 («3 that some mould growth can be detected visually») и таблица «Moisture level × Category of microorganism».
- **что не подтверждено:** Ничего существенного: обе формулировки `note` (BIO-002, WAT-002) прямо следуют из текста.
- **url:** https://www.who.int/publications/i/item/9789289041683
- **дата проверки:** 2026-11-03

### 3.5 `Wikipedia, статья «Shadow» (свободная энциклопедия)`

- **вердикт:** confirmed
- **note в правилах:** ««If there is more than one light source, there will be several shadows, with the overlapping parts darker»: несколько источников дают несколько теней…»; «тень — «a dark area on a surface where light from a light source is blocked by an object», форма тень «occur[s] on surfaces facing away from a light …»
- **правила:** PHY-002, PHY-003
- **что подтверждено:** Статья прочитана. «A shadow is a dark area on a surface where light from a light source is blocked by an object»; «If there is more than one light source, there will be several shadows, with the overlapping parts darker»; «form shadows occur on surfaces facing away from a light source». Этого достаточно для `note` PHY-002 (направление тени противоположно направлению на источник) и PHY-003 (несколько источников — несколько теней).
- **что не подтверждено:** Ничего по существу заявленного, но это энциклопедическая справка, а не криминалистический стандарт: пригодность такого основания для `review_status: reviewed` — решение владельца ветки.
- **url:** https://en.wikipedia.org/wiki/Shadow
- **дата проверки:** 2026-11-03

### 3.6 `Схема сцены-графа ЭЛЕМЕНТАРНО, schemas/scene-graph.schema.json — определения ссылок (observations[].about, objects[].on, regions[].region)`

- **вердикт:** confirmed
- **note в правилах:** «целостность ссылок — свойство описания, а не физики»
- **правила:** PHY-001
- **что подтверждено:** Файл schemas/scene-graph.schema.json прочитан целиком. В нём `observations[].about` — «id наблюдаемой вершины: региона, объекта или поверхности», `objects[].on` и `regions[].region` — строковые ссылки на id, верхнеуровневое описание — «What is visible in the image. Only fields present here may support a claim». То есть ссылочная целостность задана описанием, а не физикой, — ровно то, что утверждает `note` правила PHY-001.
- **что не подтверждено:** Ничего: `note` правила PHY-001 соответствует прочитанному.
- **url:** локальный файл schemas/scene-graph.schema.json
- **дата проверки:** 2026-11-03

### 3.7 `ANSI/IICRC S500, Standard and Reference Guide for Professional Water Damage Restoration, 4th ed. 2015 (IICRC)`

- **вердикт:** partial
- **note в правилах:** «признаки залива и категории повреждения: ANSI/IICRC S500 (Standard and Reference Guide for Professional Water Damage Restoration, 4-е изд. 2015) — ст…»; «свежесть повреждения как признак: ANSI/IICRC S500 (4-е изд. 2015) — стандарт по восстановлению после залива; свежесть повреждения в тексте не сверена…»
- **правила:** WAT-001, WAT-003
- **что подтверждено:** Стандарт существует: «ANSI/IICRC S500 Standard and Reference Guide for Professional Water Damage Restoration (4th edition, 2015)» — по архивной копии витрины самого издателя (IICRC Bookstore, снимок 2020-01-27). IICRC — аккредитованный ANSI разработчик стандартов. Прежнее обозначение «IIC S500» было неверным (IICRC, а не IIC).
- **что не подтверждено:** Категории повреждения и свежесть повреждения в тексте не сверены: стандарт платный, открытой копии нет.
- **url:** https://web.archive.org/web/20200127180511/https://webstore.iicrc.org/
- **дата проверки:** 2026-11-03

### 3.8 `ENFSI Best Practice Manual for the Forensic Examination of Handwriting, ENFSI-BPM-FHX-01, Ed. 04 (2022)`

- **вердикт:** partial
- **note в правилах:** «документ подтверждён: это руководство по экспертизе знаков и рукописных записей, в нём введено понятие construction — черт различаются по признакам п…»
- **правила:** SEM-003
- **что подтверждено:** Документ существует и прочитан: ENFSI-BPM-FHX-01 (Ed. 04), «BPM for the Forensic Handwriting Examination», сентябрь 2022, PDF на enfsi.eu. Введён термин «construction» (MFHM) — «how a character, word or signature has been produced, including features of number, direction and sequence of strokes»; различаются natural, disguised и copied/simulated письмо, разобраны «pen drag», «pen lift», fluent-ность, «accidentally».
- **что не подтверждено:** Частное различение «фигура, нанесённая по образцу, против случайного росчерка» в документе не сформулировано и остаётся рабочей операционализацией проекта. Процедуры различения рукописного и печатного текста в руководстве нет: «printed» встречается только как «pre-printed lines/boxes» и в определении стиля письма.
- **url:** https://enfsi.eu/wp-content/uploads/2023/02/BPM-Handwriting-Ed.-4.pdf
- **дата проверки:** 2026-11-03

### 3.9 `Eyewitness Evidence: A Guide for Law Enforcement, National Institute of Justice (1999)`

- **вердикт:** partial
- **note в правилах:** «личность устанавливается процедурой опознания, а не самим фактом изображения в кадре: разделы 4–5 руководства NIJ — шоу-ап, фото- и живые линейки, фи…»
- **правила:** PRES-004
- **что подтверждено:** Страница NIJ прочитана: Handbook, дата публикации 1 октября 1999; описание разделов 4–5 — «Field Identification Procedure (Show-up): Conducting show-ups…» и «Procedures for Eyewitness Identification of Suspects: Composing photo and live line-ups… Conducting the identification procedure… Recording identification results». То есть личность устанавливается процедурой опознания.
- **что не подтверждено:** Текст самого буклета прочитать не удалось: PDF отдаётся как сканы (текстовых слоёв нет), прочитано только описание издателя.
- **url:** https://nij.ojp.gov/library/publications/eyewitness-evidence-guide-law-enforcement
- **дата проверки:** 2026-11-03

### 3.10 `NFPA 921: Guide for Fire and Explosion Investigations, 2024 edition (National Fire Protection Association; в реестре OSAC — подкомитет Fire & Explosion Investigation)`

- **вердикт:** partial
- **note в правилах:** «методы осмотра места пожара: NFPA 921 — руководство по исследованию пожара; по описанию издателя охватывает «preliminary scene assessment and safety …»; «прямая ссылка на документ, подтверждающий это утверждение, не установлена; V-паттерн как признак низко расположенного очага; ближайшее подтверждаемое…»
- **правила:** FIRE-001, FIRE-002
- **что подтверждено:** Стандарт существует; издание 2024 года подтверждено страницей NFPA (обложка: «NFPA 921, Guide for Fire and Explosion Investigations, 2024 edition»), официальное название — «Guide for Fire and Explosion Investigations» (в правиле было «Explosions»). По описанию издателя: «From preliminary scene assessment and safety considerations to documentation, evidence handling, analysis, and reporting, NFPA 921 provides a systematic framework for the safe and scientific investigation and analysis of fire and explosion incidents».
- **что не подтверждено:** Текст стандарта закрыт (NFPA LiNK — JavaScript-приложение, открытой копии нет). Поэтому: V-паттерн как признак низко расположенного очага (FIRE-002) не сверен; методы осмотра места пожара (FIRE-001) подтверждены только на уровне описания издателя.
- **url:** https://www.nfpa.org/product/nfpa-921-standard/p0921code
- **дата проверки:** 2026-11-03

### 3.11 `NL-Eye: Abductive NLI for Images, 2024 (arXiv:2410.02613)`

- **вердикт:** partial
- **note в правилах:** «работа подтверждена по аннотации: рассуждение по изображению с учётом социального контекста; вывод о книге как отсылке к персонажу — трактовка правил…»; «работа подтверждена по аннотации: рассуждение по изображению, в том числе культурный и социальный контекст; содержание конкретных категорий cultural …»
- **правила:** SEM-001, SEM-002
- **что подтверждено:** Работа существует: arXiv:2410.02613, подана 3 октября 2024 (Ventura, Toker, Calderon, Gekhman, Bitton, Reichart), опубликована на ICLR 2025. Аннотация: «NL-Eye consists of 350 carefully curated triplet examples (1,050 images) spanning diverse reasoning categories: physical, functional, logical, emotional, cultural, and social» — категории cultural и social названы.
- **что не подтверждено:** Содержание категорий cultural и social в аннотации не раскрыто, поэтому оба прочтения правил (SEM-001 — символическое прочтение сцены, SEM-002 — предметы как отсылки к персонажу) — трактовка правила, а не содержание источника.
- **url:** https://arxiv.org/abs/2410.02613
- **дата проверки:** 2026-11-03

### 3.12 `OSAC Registry (NIST), подкомитет Crime Scene Investigation & Reconstruction: ANSI/ASB 159-24 (Standard for Scene Investigation and Reconstruction — Foundational Principles), OSAC 2023-N-0002 (Standard for Scene Documentation Procedures), OSAC 2021-N-0018 (Standard for On-Scene Collection and Preservation of Physical Evidence)`

- **вердикт:** partial
- **note в правилах:** «прямая ссылка на документ, подтверждающий это утверждение, не установлена; зачистка места как признак сокрытия; ближайшее подтверждаемое — OSAC-реест…»; «прямая ссылка на документ, подтверждающий это утверждение, не установлена; кольцевой след от горячей кружки; ближайшее подтверждаемое — OSAC-реестр, …»; «прямая ссылка на документ, подтверждающий это утверждение, не установлена; отсутствие следов как источник информации; ближайшее подтверждаемое — OSAC…»; «прямая ссылка на документ, подтверждающий это утверждение, не установлена; перестановка оборудования; ближайшее подтверждаемое — OSAC-реестр, подкоми…»; «прямая ссылка на документ, подтверждающий это утверждение, не установлена; повторяющиеся кольцевые следы на поверхности; ближайшее подтверждаемое — O…»; «прямая ссылка на документ, подтверждающий это утверждение, не установлена; пылевой контур как признак убранного предмета; ближайшее подтверждаемое — …»; «прямая ссылка на документ, подтверждающий это утверждение, не установлена; следы на поверхностях (повторяющиеся кольца); ближайшее подтверждаемое — O…»; «прямая ссылка на документ, подтверждающий это утверждение, не установлена; следы оставления и снятия предметов; ближайшее подтверждаемое — OSAC-реест…»; «прямая ссылка на документ, подтверждающий это утверждение, не установлена; следы перемещения по сцене; ближайшее подтверждаемое — OSAC-реестр, подком…»; «прямая ссылка на документ, подтверждающий это утверждение, не установлена; следы перемещения по сцене; ближайшее подтверждаемое — OSAC-реестр, подком…»; «прямая ссылка на документ, подтверждающий это утверждение, не установлена; следы уборки и работы в помещении; ближайшее подтверждаемое — OSAC-реестр,…»; «прямая ссылка на документ, подтверждающий это утверждение, не установлена; состояние оставленной открытой ёмкости; ближайшее подтверждаемое — OSAC-ре…»
- **правила:** ABS-001, ABS-002, ABS-003, ABS-004, HOME-001, HOME-002, HOME-003, OFF-001, OFF-004, PUZ-002, PUZ-006, TRD-007
- **что подтверждено:** Все три документа существуют и зарегистрированы в реестре OSAC (подкомитет Crime Scene Investigation & Reconstruction, 14 записей): ANSI/ASB 159-24 — принципы исследования и реконструкции сцены; OSAC 2023-N-0002 — документирование сцены; OSAC 2021-N-0018 — сбор и сохранение физических улик на месте.
- **что не подтверждено:** Ни один из них не подтверждает бытовые выводы правил (пылевой контур, отсутствие следов, следы крепления, полоса в пыли, уборка, кольцо от кружки, перестановка): тексты стандартов платные и не открывались.
- **url:** https://www.nist.gov/osac/registry
- **дата проверки:** 2026-11-03

### 3.13 `OSAC Registry (NIST), подкомитет Firearms & Toolmarks: ANSI/ASB 162-24 (Standard Method for the Forensic Examination and Documentation of Non-Firearm Tools and Toolmarks)`

- **вердикт:** partial
- **note в правилах:** «экспертиза и документирование следов неогнестрельного оружия: ANSI/ASB 162-24; связь следа с вскрытием, разбором или отгибанием в нём не подтверждена…»
- **правила:** MECH-002
- **что подтверждено:** Документ существует в реестре OSAC: экспертиза и документирование следов неогнестрельного оружия.
- **что не подтверждено:** Связь следа с вскрытием, разбором или отгибанием в нём не подтверждена; текст стандарта платный, не открывался.
- **url:** https://www.nist.gov/osac/registry
- **дата проверки:** 2026-11-03

### 3.14 `OSAC Registry (NIST), подкомитет Firearms & Toolmarks: OSAC 2024-S-0002 (Standard Test Method for the Examination and Comparison of Toolmarks for Source Attribution)`

- **вердикт:** partial
- **note в правилах:** «след орудия как индивидуализирующий признак: OSAC 2024-S-0002 — метод сравнения следов орудий для атрибуции источнику; вывод о вскрытии или разборке …»
- **правила:** MECH-002
- **что подтверждено:** Документ существует в реестре OSAC (подкомитет Firearms & Toolmarks, 14 записей): метод сравнения следов орудий для атрибуции источнику.
- **что не подтверждено:** Вывод правила MECH-002 о вскрытии, разборке или отгибании в нём не подтверждён; текст стандарта платный, не открывался.
- **url:** https://www.nist.gov/osac/registry
- **дата проверки:** 2026-11-03

### 3.15 `OSAC Registry (NIST), подкомитет Footwear & Tire: OSAC 2023-S-0017 (Standard for the Articulation of Footwear and Tire Interpretations), ANSI/ASB BPR 052-22 (Best Practice Recommendation for the Detection and Collection of Footwear and Tire Impression Evidence)`

- **вердикт:** partial
- **note в правилах:** «след обуви как индивидуализирующий признак и оценка размера: OSAC 2023-S-0017 (порядок формулирования выводов: класс против индивидуализации), ANSI/A…»; «след обуви как индивидуализирующий признак: OSAC 2023-S-0017 (порядок формулирования выводов по следам обуви и шин), ANSI/ASB BPR 052-22 (обнаружение…»; «след обуви как индивидуализирующий признак: OSAC 2023-S-0017 задаёт порядок формулирования выводов по следам обуви и шин, ANSI/ASB BPR 052-22 — обнар…»; «следы обуви как индивидуализирующий признак: OSAC 2023-S-0017 (порядок формулирования выводов по следам обуви и шин), ANSI/ASB BPR 052-22 (обнаружени…»; «следы шин как след транспортного средства: OSAC 2023-S-0017 — порядок формулирования выводов по следам шин и обуви, ANSI/ASB BPR 052-22 — обнаружение…»
- **правила:** GRD-003, HOME-004, MECH-001, PRES-001, PUZ-004
- **что подтверждено:** Подкомитет Footwear & Tire существует (9 документов): OSAC 2023-S-0017 — порядок формулирования выводов по следам обуви и шин (индивидуализация против класса); ANSI/ASB BPR 052-22 — обнаружение и сбор следов; плюс BPR 049-20 (снятие оттисков) и BPR 126-20 (отливка).
- **что не подтверждено:** Следы на грунте и песке, оценка размера следа по фотографии и связь мокрого или грязного следа с входом в помещение в них не оговорены; тексты не открывались.
- **url:** https://www.nist.gov/osac/registry
- **дата проверки:** 2026-11-03

### 3.16 `OSAC Registry (NIST), подкомитет Forensic Document Examination: ANSI/ASB 070-22 (Standard for Examination of Handwritten Items), ANSI/ASB 011-22 (Scope of Expertise in Forensic Document Examination)`

- **вердикт:** partial
- **note в правилах:** «названия стандартов подтверждены по выгрузке реестра OSAC (264 стандарта); тексты платные, поэтому различение рукописного и печатного текста в них не…»; «рукописные материалы исследуются в экспертизе документов: ANSI/ASB 070-22; следы чернил или тонера на рабочей поверхности в нём не описаны (текст ста…»; «чернила и тонер как материалы экспертизы документов: ANSI/ASB 011-22 (область компетенции экспертизы документов); стандарта по следам чернил на повер…»; «чернила, тонер и бумага как материалы экспертизы документов: ANSI/ASB 011-22 (область компетенции экспертизы документов); стандарта по следам чернил …»
- **правила:** OFF-002, SEM-005, TRD-008
- **что подтверждено:** Оба стандарта существуют в реестре OSAC (подкомитет Forensic Document Examination, 9 записей): экспертиза рукописных материалов и область компетенции экспертизы документов — там и рассматриваются чернила, тонер и бумага.
- **что не подтверждено:** Тексты платные и не открывались: различение рукописного и печатного текста по этим стандартам не сверено, а стандарта по следам чернил или тонера на рабочей поверхности в реестре нет.
- **входит в запись:** `OSAC Registry (NIST), подкомитет Forensic Document Examination: ANSI/ASB 011-22 (Scope of Expertise in Forensic Document Examination)`
- **входит в запись:** `OSAC Registry (NIST), подкомитет Forensic Document Examination: ANSI/ASB 070-22 (Standard for Examination of Handwritten Items)`
- **url:** https://www.nist.gov/osac/registry
- **дата проверки:** 2026-11-03

### 3.18 `OSAC Registry (NIST), подкомитет Friction Ridge: OSAC 2023-N-0020 (Standard for the On-Scene Collection and Preservation of Friction Ridge Impressions), OSAC 2022-N-0033 (Standard for Processing Evidence for the Detection of Friction Ridge Impressions), OSAC 2023-S-0026 (Task-Relevant Information in Friction Ridge Examination)`

- **вердикт:** partial
- **note в правилах:** «отпечаток: OSAC 2023-N-0020 (сбор и сохранение отпечатков на месте) и OSAC 2022-N-0033 (обработка вещества для выявления отпечатков); последовательно…»; «проявление и оценка следов ладоней: OSAC 2023-N-0020 (сбор и сохранение отпечатков на месте), OSAC 2022-N-0033 (обработка вещества для выявления отпе…»; «проявление и оценка следов пальцевых ладоней: OSAC 2022-N-0033 (обработка вещества для выявления отпечатков), OSAC 2023-N-0020 (сбор и сохранение отп…»; «следы в пыли и на запылённых поверхностях: OSAC 2022-N-0033 (обработка вещества для выявления отпечатков) и OSAC 2023-N-0020 (сбор и сохранение отпеч…»
- **правила:** OFF-003, PRES-002, PRES-003, TRD-010
- **что подтверждено:** Подкомитет Friction Ridge существует (8 документов): сбор и сохранение отпечатков на месте, обработка вещества для выявления отпечатков, задачи, значимые для экспертизы.
- **что не подтверждено:** Хронология «отпечаток после оседания пыли» и соотнесение отпечатка с брызгами краски по последовательности наложения в них не подтверждены: стандарта о послойном наложении следов разных материалов в реестре нет; тексты не открывались.
- **url:** https://www.nist.gov/osac/registry
- **дата проверки:** 2026-11-03

### 3.19 `OSAC Registry (NIST), подкомитет Trace Materials`

- **вердикт:** partial
- **note в правилах:** «частицы еды как следовой материал: подкомитет Trace Materials реестра OSAC (34 стандарта по краске, стеклу, волокнам, волосам, почвам, плёнкам, полим…»
- **правила:** HOME-005
- **что подтверждено:** Подкомитет существует и содержит 34 стандарта по следовым материалам: краска, стекло, волокна, волосы, почвы, плёнки, полимеры, петрографика.
- **что не подтверждено:** Стандарта по пищевым частицам в реестре нет: слово «food» среди 264 заголовков не встречается. Бытовая специфика крошек и остатков еды не покрыта.
- **url:** https://www.nist.gov/osac/subcommittees/trace-materials
- **дата проверки:** 2026-11-03

### 3.20 `OSAC Registry (NIST), подкомитет Trace Materials: ANSI/ASTM E1610-18 (Standard Guide for Forensic Paint Analysis and Comparison), ANSI/ASTM E2808-21a (Standard Guide for Microspectrophotometry in Forensic Paint Analysis)`

- **вердикт:** partial
- **note в правилах:** «брызги и следы краски как следовой материал: ANSI/ASTM E1610-18 (криминалистический анализ и сравнение краски) и ANSI/ASTM E2808-21a (микроспектрофот…»; «краска: ANSI/ASTM E1610-18 (криминалистический анализ и сравнение краски) и ANSI/ASTM E2808-21a (микроспектрофотометрия); совместная хронология следа…»; «краска: ANSI/ASTM E1610-18 (криминалистический анализ и сравнение краски) — краска как следовой материал, связь с ремонтом в нём не подтверждена»
- **правила:** TRD-001, TRD-010, TRD-011
- **что подтверждено:** Оба стандарта существуют в реестре OSAC (Trace Materials): криминалистический анализ и сравнение краски; микроспектрофотометрия в анализе краски. Плюс ANSI/ASTM E2937-18 (ИК-спектроскопия) и E3234-20 (программа подготовки экспертов).
- **что не подтверждено:** Брызги краски как таковые и связь с покраской в них не описаны; тексты не открывались.
- **url:** https://www.nist.gov/osac/registry
- **дата проверки:** 2026-11-03

### 3.21 `OSAC Registry (NIST), подкомитет Trace Materials: ANSI/ASTM E3272-23 (Standard Guide for the Collection of Soils and Other Geological Evidence for Criminal Forensic Applications), OSAC 2025-S-0011 (Standard Guide for Polarized Light Microscopy in the Forensic Examination and Comparison of Soils)`

- **вердикт:** partial
- **note в правилах:** «прямая ссылка на документ, подтверждающий это утверждение, не установлена; древесные частицы как следовой материал; ближайшее подтверждаемое — ANSI/A…»; «прямая ссылка на документ, подтверждающий это утверждение, не установлена; мука и мучная пыль; ближайшее подтверждаемое — ANSI/ASTM E3272-23 (сбор по…»; «прямая ссылка на документ, подтверждающий это утверждение, не установлена; свежесть влаги в почве; ближайшее подтверждаемое — ANSI/ASTM E3272-23 (сбо…»; «прямая ссылка на документ, подтверждающий это утверждение, не установлена; строительная пыль; ближайшее подтверждаемое — ANSI/ASTM E3272-23 (сбор поч…»; «частицы и следы как следовой материал: ANSI/ASTM E3272-23 (сбор почв и иных геологических веществ) и OSAC 2025-S-0011 (микроскопия почв в поляризован…»; «штукатурная пыль: ANSI/ASTM E3272-23 (сбор почв и иных геологических веществ) — класс минеральных частиц, штукатурная пыль прямо не названа, совместн…»
- **правила:** GRD-001, GRD-004, TRD-002, TRD-003, TRD-006, TRD-011
- **что подтверждено:** Оба документа существуют в реестре OSAC (Trace Materials): сбор почв и иных геологических веществ; микроскопия почв в поляризованном свете. Это ближайший подтверждаемый класс — минеральные частицы как следовое вещество.
- **что не подтверждено:** Ни древесина, ни мука, ни штукатурная пыль, ни свежесть влаги в почве в этих документах прямо не названы; тексты не открывались.
- **url:** https://www.nist.gov/osac/registry
- **дата проверки:** 2026-11-03

### 3.22 `OSAC Registry (NIST), подкомитет Trace Materials: ANSI/ASTM E3294-23 (Standard Guide for Forensic Analysis of Geological Materials by Powder X-Ray Diffraction)`

- **вердикт:** partial
- **note в правилах:** «анализ геологических материалов методом рентгеновской дифракции: ANSI/ASTM E3294-23; металлические частицы в нём не выделены (текст стандарта платный…»
- **правила:** TRD-005
- **что подтверждено:** Документ существует в реестре OSAC (Trace Materials): анализ геологических (минеральных) материалов методом рентгеновской дифракции.
- **что не подтверждено:** Металлические частицы как таковые в нём не выделены; текст стандарта платный, не открывался.
- **url:** https://www.nist.gov/osac/registry
- **дата проверки:** 2026-11-03

### 3.23 `OSAC Registry (NIST), подкомитет Trace Materials: ANSI/ASTM E3296-22 (Standard Guide for Forensic Examination of Polymers by Pyrolysis Gas Chromatography and Pyrolysis Gas Chromatography-Mass Spectrometry)`

- **вердикт:** partial
- **note в правилах:** «прямая ссылка на документ, подтверждающий это утверждение, не установлена; смазочные материалы и металл как следовые вещества; ближайшее подтверждаем…»
- **правила:** TRD-004
- **что подтверждено:** Стандарт существует в реестре OSAC (Trace Materials) — криминалистическое исследование полимеров; это ближайший подтверждаемый класс веществ, исследуемых на следовом материале.
- **что не подтверждено:** Смазочные материалы как класс следовых веществ в реестре не представлены; текст стандарта не открывался.
- **url:** https://www.nist.gov/osac/registry
- **дата проверки:** 2026-11-03

### 3.24 `OSAC Registry (NIST), подкомитет Trace Materials: ANSI/ASTM E3462-25e1 (Standard Guide for Interpretation and Reporting in Forensic Comparisons of Trace Materials), ANSI/ASTM E3457-25 (Standard Guide for Detection and Preservation of Forensic Trace Evidence)`

- **вердикт:** partial
- **note в правилах:** «комбинирование следов разных материалов: ANSI/ASTM E3462-25e1 (интерпретация и отчётность по сравнениям следовых материалов) и ANSI/ASTM E3457-25 (об…»
- **правила:** TRD-009
- **что подтверждено:** Оба стандарта существуют в реестре OSAC (Trace Materials) — интерпретация и отчётность по сравнениям следовых материалов, обнаружение и сохранение следовых веществ.
- **что не подтверждено:** Вывод о характере работ по набору следов из разных материалов в них не подтверждён; тексты не открывались.
- **url:** https://www.nist.gov/osac/registry
- **дата проверки:** 2026-11-03

### 3.25 `OSAC Registry (NIST), подкомитет Trace Materials: ANSI/ASTM E3501-25 (Standard Guide for Forensic Analysis of Geological Materials by Scanning Electron Microscopy and Energy Dispersive X-Ray Spectrometry)`

- **вердикт:** partial
- **note в правилах:** «минеральные частицы как следовое вещество: ANSI/ASTM E3501-25 (анализ геологических материалов методом SEM/EDS); металлические частицы в нём не выдел…»
- **правила:** TRD-005
- **что подтверждено:** Документ существует в реестре OSAC (Trace Materials): анализ геологических (минеральных) материалов методом SEM/EDS.
- **что не подтверждено:** Металлические частицы как таковые в нём не выделены; текст стандарта платный, не открывался.
- **url:** https://www.nist.gov/osac/registry
- **дата проверки:** 2026-11-03

### 3.26 `OSAC Registry (NIST), подкомитет Wildlife Forensic Biology: ANSI/ASB 028-19 (Wildlife Forensics Morphology Standards)`

- **вердикт:** partial
- **note в правилах:** «морфологическая идентификация следов животных: ANSI/ASB 028-19; бытовая обстановка как условие применения в нём не оговорена (текст стандарта платный…»
- **правила:** BIO-001
- **что подтверждено:** Документ существует в реестре OSAC (подкомитет Wildlife Forensic Biology, 8–9 записей): стандарты морфологической экспертизы следов животных.
- **что не подтверждено:** Бытовая обстановка («следы животных в жилой среде») в нём не оговорена; текст стандарта платный, не открывался.
- **url:** https://www.nist.gov/osac/registry
- **дата проверки:** 2026-11-03

### 3.27 `OSAC Registry (NIST), подкомитет Wildlife Forensic Biology: ANSI/ASB 029-19 (Report Writing in Wildlife Forensics: Morphology and Genetics)`

- **вердикт:** partial
- **note в правилах:** «правила отчёта по морфологической и генетической экспертизе следов животных: ANSI/ASB 029-19; следы животных в жилой среде в нём не оговорены (текст …»
- **правила:** BIO-001
- **что подтверждено:** Документ существует в реестре OSAC: правила отчёта по морфологической и генетической экспертизе следов животных.
- **что не подтверждено:** Следы животных в жилой среде в нём не оговорены; текст стандарта платный, не открывался.
- **url:** https://www.nist.gov/osac/registry
- **дата проверки:** 2026-11-03

### 3.28 `Ronnberg, A. The Book of Symbols: Reflections on Archetypal Images, TASCHEN, 2010`

- **вердикт:** partial
- **note в правилах:** «каталог архетипических образцов; полный текст прочитан, каталог подтверждён, но запись «глаз в треугольнике» в нём не найдена — поэтому конкретный об…»
- **правила:** SEM-004
- **что подтверждено:** Книга существует и это именно каталог архетипических образцов: полный текст прочитан — «THE BOOK OF SYMBOLS: REFLECTIONS ON ARCHETYPAL IMAGES», Editor-in-Chief AMI RONNBERG, Editor Kathleen Martin, TASCHEN, 807 страниц с предметным указателем. Издание 2010 года: ISBN 978-3-8365-1448-4, © 2010 TASCHEN; по OpenLibrary first_publish_year 2010, есть издание 2018 года.
- **что не подтверждено:** Запись «глаз в треугольнике» в книге не найдена: в указателе есть «EYE, 352–5» (Eye of Horus, Eye of Re, «eyes as window of soul»), «all-seeing» встречается 5 раз, но «Eye of Providence» — 0 вхождений, а «triangle» — всего 2 (алхимический текст и «Triangle inverted, and vulva»). Поэтому конкретный образец опознаётся по иконографическому справочнику, а не по этой книге.
- **url:** https://www.taschen.com/en/books/art/06703/the-book-of-symbols-reflections-on-archetypal-images
- **дата проверки:** 2026-11-03

### 3.29 `The Abduction of Sherlock Holmes: A Dataset for Visual Abductive Reasoning, Hessel, Hwang, Bhagavatula, Choi, ECCV 2022, Springer LNCS 13696 — изменение обстановки между наблюдениями`

- **вердикт:** partial
- **note в правилах:** «прямая ссылка на документ, подтверждающий это утверждение, не установлена; изменение обстановки как абдуктивная улика; подтверждаемое — набор Sherloc…»
- **правила:** PUZ-005
- **что подтверждено:** Подтверждается только формат абдуктивного вывода из одной сцены (363 тыс. пар clue/inference, локализация через bounding boxes).
- **что не подтверждено:** Изменение обстановки между двумя наблюдениями в работе не рассматривается: корпус состоит из отдельных изображений с уликами, а не из пар кадров. Прямой ссылки на такой документ не найдено.
- **url:** https://link.springer.com/chapter/10.1007/978-3-031-20059-5_32
- **дата проверки:** 2026-11-03

### 3.30 `The Abduction of Sherlock Holmes: A Dataset for Visual Abductive Reasoning, Hessel, Hwang, Bhagavatula, Choi, ECCV 2022, Springer LNCS 13696 — изменение состава сцены между наблюдениями`

- **вердикт:** partial
- **note в правилах:** «прямая ссылка на документ, подтверждающий это утверждение, не установлена; изменение состава сцены между наблюдениями; подтверждаемое — набор Sherloc…»
- **правила:** PUZ-007
- **что подтверждено:** Подтверждается только формат «улика → вывод» с локализацией для отдельных изображений.
- **что не подтверждено:** Сопоставление состава сцены между кадрами в работе не рассматривается; прямой ссылки на такой документ не найдено.
- **url:** https://link.springer.com/chapter/10.1007/978-3-031-20059-5_32
- **дата проверки:** 2026-11-03

### 3.31 `Схема сцены-графа ЭЛЕМЕНТАРНО, schemas/scene-graph.schema.json — определение fill_level`

- **вердикт:** partial
- **note в правилах:** «в схеме fill_level объявлено числом в диапазоне 0…1 без описания; семантика «доля объёма жидкости» в schemas/scene-graph.schema.json не зафиксирована…»
- **правила:** PHY-004
- **что подтверждено:** Подтверждается только то, что записано в схеме: `fill_level` — «type: number, minimum: 0, maximum: 1».
- **что не подтверждено:** Семантика «доля объёма жидкости» в схеме **не зафиксирована**: у поля нет `description`. Прямой ссылки на документ, определяющий эту величину, не существует; это соглашение проекта, а не документ.
- **url:** локальный файл schemas/scene-graph.schema.json
- **дата проверки:** 2026-11-03

### 3.32 `Hall, J. Dictionary of Subjects and Symbols in Art, J. Murray, 1974; Routledge, 2018`

- **вердикт:** partial
- **note в правилах:** «стандартный иконографический справочник: символы в изобразительном искусстве; существование и издания подтверждены по каталогу, текст платный и не от…»
- **правила:** SEM-004
- **что подтверждено:** Справочник существует, и это стандартный иконографический справочник по символам в изобразительном искусстве. По OpenLibrary: первое издание 1974 года (John Murray / J. Murray; также Harper & Row), переиздание 2018 года (Taylor & Francis Group / Routledge), 14 каталожных записей и 7+ изданий.
- **что не подтверждено:** Содержание конкретных статей не сверялось: текст платный и не открывался. Поэтому подтверждается, что справочник существует и что это канонический источник по символам, но не то, какая именно статья описывает различаемый образец.
- **url:** https://openlibrary.org/search?q=title%3A%22Dictionary+of+Subjects+and+Symbols+in+Art%22
- **дата проверки:** 2026-11-03

## 4. Правила, потолок которых можно поднять

Правила, у которых **все** источники получили вердикт `confirmed`, — то есть источник есть, прочитан, и его текст подтверждает `note` после правки:

- **BIO-002** — «Очаг плесени» (потолок в правиле 0.9). Источник: WHO Guidelines for Indoor Air Quality: Dampness and Mould, 2009
- **PHY-001** — «Объект опирается на отсутствующую поверхность» (потолок в правиле 0.95). Источник: Схема сцены-графа ЭЛЕМЕНТАРНО, schemas/scene-graph.schema.json — определения ссылок (observations[].about, obj
- **PHY-002** — «Тень не совпадает с источником света» (потолок в правиле 0.65). Источник: Wikipedia, статья «Shadow» (свободная энциклопедия)
- **PHY-003** — «Тени разных направлений при одном источнике» (потолок в правиле 0.8). Источник: Wikipedia, статья «Shadow» (свободная энциклопедия)
- **PUZ-001** — «Предмет исчез, след на месте остался» (потолок в правиле 0.85). Источник: The Abduction of Sherlock Holmes: A Dataset for Visual Abductive Reasoning, Hessel, Hwang, Bhagavatula, Choi, 
- **PUZ-003** — «Появился мокрый след» (потолок в правиле 0.85). Источник: The Abduction of Sherlock Holmes: A Dataset for Visual Abductive Reasoning, Hessel, Hwang, Bhagavatula, Choi, 
- **WAT-002** — «Плесень в месте прежнего намокания» (потолок в правиле 0.9). Источник: WHO Guidelines for Indoor Air Quality: Dampness and Mould, 2009

Всего **7 правил из 56**.

И **это ещё не подъём потолка**: правила остаются черновиками (`review_status: "draft"`), а `rules.py` при черновике срезает потолок до 0.5. Чтобы потолок вырос, владелец ветки должен перевести `review_status` в `"reviewed"` — это экспертная рецензия, которой здесь не было. `sources[].verified: true` уже проставлен у подтверждённых источников.

Четыре из этих правил (PHY-002, PHY-003, PUZ-001, PUZ-003) опираются на документы, которые не являются криминалистическими стандартами: энциклопедическая статья и статья по компьютерному зрению. Их утверждения элементарны и подтверждены дословно, но основание слабее, чем у BIO-002 и WAT-002 (нормы ВОЗ). Решение о `review_status` — за владельцем ветки.

## 5. Правила, потолок которых поднять нельзя

| Причина | Правила |
| --- | --- |
| `partial`: документ есть, но `note` не подтверждён | ABS-001, ABS-002, ABS-003, ABS-004, BIO-001, FIRE-001, FIRE-002, GRD-001, GRD-003, GRD-004, HOME-001, HOME-002, HOME-003, HOME-004, HOME-005, MECH-001, MECH-002, OFF-001, OFF-002, OFF-003, OFF-004, PHY-004, PRES-001, PRES-002, PRES-003, PUZ-002, PUZ-004, PUZ-005, PUZ-006, PUZ-007, SEM-001, SEM-002, SEM-003, SEM-004, SEM-005, TRD-001, TRD-002, TRD-003, TRD-004, TRD-005, TRD-006, TRD-007, TRD-008, TRD-009, TRD-010, TRD-011, WAT-001, WAT-003 |
| смешанный набор источников (один подтверждён, второй нет) | PRES-004 |

## 6. Правила, опирающиеся на несколько источников разного качества

- **PRES-004** — «Человек виден в кадре»: `Federal Rules of Evidence, Rule 1002 (Requirement of the Original), Cornell Legal Informa…` — confirmed; `Eyewitness Evidence: A Guide for Law Enforcement, National Institute of Justice (1999)` — partial.

Правила с несколькими источниками одного качества (все `partial`): BIO-001, MECH-002, OFF-002, SEM-004, TRD-005, TRD-008, TRD-010, TRD-011.

## 7. Правила без подтверждённого источника

Для этих правил честного источника, подтверждающего утверждение, найти не удалось. Правила оставлены в базе; в `note` записано, что именно подтверждается и что не подтверждается; в `confounds` добавлена оговорка о слабости основания; `verified` остался `false`. Что искать:

| Правило | Что писать в `note` (сделано) | Какой источник искать |
| --- | --- | --- |
| ABS-001 | прямая ссылка на документ, подтверждающий это утверждение, не установлена; пылевой контур как признак убранно… | криминалистический стандарт или исследование про оставление пылевого/паровых следов от предмета (dust outline, void pattern) — в реестре OSAC нет |
| ABS-002 | прямая ссылка на документ, подтверждающий это утверждение, не установлена; отсутствие следов как источник инф… | документ про использование отсутствия (void) следов при реконструкции сцены — нет в реестре OSAC |
| ABS-003 | прямая ссылка на документ, подтверждающий это утверждение, не установлена; следы оставления и снятия предмето… | стандарт про фиксацию следов крепления и оставленных/снятых предметов — нет |
| ABS-004 | прямая ссылка на документ, подтверждающий это утверждение, не установлена; следы перемещения по сцене; ближай… | документ про следы перемещения по поверхностям (tracked patterns) — нет |
| BIO-001 | морфологическая идентификация следов животных: ANSI/ASB 028-19; бытовая обстановка как условие применения в н… | стандарт по дифференциации следов животных и человека в бытовой среде — нет |
| FIRE-001 | методы осмотра места пожара: NFPA 921 — руководство по исследованию пожара; по описанию издателя охватывает «… | открытый текст стандарта по осмотру места пожара (NFPA 921 доступен только по подписке) |
| FIRE-002 | прямая ссылка на документ, подтверждающий это утверждение, не установлена; V-паттерн как признак низко распол… | источник про V-паттерн и его ограничения (текст NFPA 921 или открытое исследование) |
| GRD-001 | частицы и следы как следовой материал: ANSI/ASTM E3272-23 (сбор почв и иных геологических веществ) и OSAC 202… | документ про состояние почвы как признак перекопки — нет |
| GRD-003 | след обуви как индивидуализирующий признак: OSAC 2023-S-0017 задаёт порядок формулирования выводов по следам … | документ про следы обуви на грунте и песке — нет |
| GRD-004 | прямая ссылка на документ, подтверждающий это утверждение, не установлена; свежесть влаги в почве; ближайшее … | документ про свежесть влаги в почве — нет |
| HOME-001 | прямая ссылка на документ, подтверждающий это утверждение, не установлена; следы уборки и работы в помещении;… | документ про следы уборки в жилом помещении — нет |
| HOME-002 | прямая ссылка на документ, подтверждающий это утверждение, не установлена; кольцевой след от горячей кружки; … | документ про кольцевые следы от горячей посуды — нет |
| HOME-003 | прямая ссылка на документ, подтверждающий это утверждение, не установлена; состояние оставленной открытой ёмк… | документ про состояние оставленных ёмкостей — нет |
| HOME-004 | след обуви как индивидуализирующий признак: OSAC 2023-S-0017 (порядок формулирования выводов по следам обуви … | документ про мокрые следы обуви у порога — нет |
| HOME-005 | частицы еды как следовой материал: подкомитет Trace Materials реестра OSAC (34 стандарта по краске, стеклу, в… | стандарт по пищевым частицам как следовому материалу — нет |
| MECH-001 | следы шин как след транспортного средства: OSAC 2023-S-0017 — порядок формулирования выводов по следам шин и … | открытый текст стандартов по следам шин и их сравнению — нет |
| MECH-002 | след орудия как индивидуализирующий признак: OSAC 2024-S-0002 — метод сравнения следов орудий для атрибуции и… | открытый текст по экспертизе следов орудий и выводу о характере воздействия — нет |
| OFF-001 | прямая ссылка на документ, подтверждающий это утверждение, не установлена; повторяющиеся кольцевые следы на п… | документ про повторяющиеся кольцевые следы на рабочих поверхностях — нет |
| OFF-002 | чернила, тонер и бумага как материалы экспертизы документов: ANSI/ASB 011-22 (область компетенции экспертизы … | стандарт по следам чернил и тонера на поверхностях — нет |
| OFF-003 | проявление и оценка следов ладоней: OSAC 2023-N-0020 (сбор и сохранение отпечатков на месте), OSAC 2022-N-003… | документ про отпечатки на стекле и пыль на нём — нет |
| OFF-004 | прямая ссылка на документ, подтверждающий это утверждение, не установлена; перестановка оборудования; ближайш… | документ про реконструкцию перестановок по описанию сцены — нет |
| PHY-004 | в схеме fill_level объявлено числом в диапазоне 0…1 без описания; семантика «доля объёма жидкости» в schemas/… | документ, определяющий семантику fill_level (или её фиксация в схеме ЭЛЕМЕНТАРНО) |
| PRES-001 | след обуви как индивидуализирующий признак и оценка размера: OSAC 2023-S-0017 (порядок формулирования выводов… | документ про оценку размера следа обуви — нет |
| PRES-002 | проявление и оценка следов пальцевых ладоней: OSAC 2022-N-0033 (обработка вещества для выявления отпечатков),… | документ про связь отпечатка с переносом предметов — нет |
| PRES-003 | следы в пыли и на запылённых поверхностях: OSAC 2022-N-0033 (обработка вещества для выявления отпечатков) и O… | документ про хронологию «пыль, потом касание» — нет |
| PRES-004 | содержание фотографии доказывается оригиналом: Rule 1002 — «An original writing, recording, or photograph is … | текст буклета NIJ (сканы) или источник про идентификацию по фото — нужен читаемый текст NIJ |
| PUZ-002 | прямая ссылка на документ, подтверждающий это утверждение, не установлена; зачистка места как признак сокрыти… | документ про зачистку места как признаке сокрытия — нет |
| PUZ-004 | следы обуви как индивидуализирующий признак: OSAC 2023-S-0017 (порядок формулирования выводов по следам обуви… | документ про следы грязи на полу после входа с улицы — нет |
| PUZ-005 | прямая ссылка на документ, подтверждающий это утверждение, не установлена; изменение обстановки как абдуктивн… | источник про сопоставление обстановки между двумя наблюдениями — нет |
| PUZ-006 | прямая ссылка на документ, подтверждающий это утверждение, не установлена; следы перемещения по сцене; ближай… | документ про изменение состояния пыли между наблюдениями — нет |
| PUZ-007 | прямая ссылка на документ, подтверждающий это утверждение, не установлена; изменение состава сцены между набл… | источник про сопоставление состава сцены между кадрами — нет |
| SEM-001 | работа подтверждена по аннотации: рассуждение по изображению, в том числе культурный и социальный контекст; с… | полный текст NL-Eye с раскрытием категории cultural — аннотации недостаточно |
| SEM-002 | работа подтверждена по аннотации: рассуждение по изображению с учётом социального контекста; вывод о книге ка… | полный текст NL-Eye с раскрытием категории social — аннотации недостаточно |
| SEM-003 | документ подтверждён: это руководство по экспертизе знаков и рукописных записей, в нём введено понятие constr… | документ, где сформулировано различение «фигура по образцу против случайного росчерка»; в ENFSI BPM его нет — пока это рабочая операционализация прое… |
| SEM-004 | стандартный иконографический справочник: символы в изобразительном искусстве; существование и издания подтвер… | сверка конкретных статей иконографического справочника Hall (текст платный) и записи «глаз в треугольнике» — в The Book of Symbols её нет |
| SEM-005 | названия стандартов подтверждены по выгрузке реестра OSAC (264 стандарта); тексты платные, поэтому различение… | открытый текст ANSI/ASB 070-22 и 011-22: различение рукописного и печатного текста |
| TRD-001 | брызги и следы краски как следовой материал: ANSI/ASTM E1610-18 (криминалистический анализ и сравнение краски… | документ про брызги краски как признак покраски — нет |
| TRD-002 | прямая ссылка на документ, подтверждающий это утверждение, не установлена; древесные частицы как следовой мат… | документ по древесным частицам как следовому материалу — нет |
| TRD-003 | прямая ссылка на документ, подтверждающий это утверждение, не установлена; мука и мучная пыль; ближайшее подт… | документ по муке и мучной пыли как следовому материалу — нет |
| TRD-004 | прямая ссылка на документ, подтверждающий это утверждение, не установлена; смазочные материалы и металл как с… | документ по смазочным материалам как следовым веществам — нет |
| TRD-005 | минеральные частицы как следовое вещество: ANSI/ASTM E3501-25 (анализ геологических материалов методом SEM/ED… | документ по металлическим частицам как следовому веществу — нет |
| TRD-006 | прямая ссылка на документ, подтверждающий это утверждение, не установлена; строительная пыль; ближайшее подтв… | документ по строительной и штукатурной пыли — нет |
| TRD-007 | прямая ссылка на документ, подтверждающий это утверждение, не установлена; следы на поверхностях (повторяющие… | документ по повторяющимся кольцевым следам — нет |
| TRD-008 | чернила и тонер как материалы экспертизы документов: ANSI/ASB 011-22 (область компетенции экспертизы документ… | стандарт по следам чернил и тонера на поверхностях — нет |
| TRD-009 | комбинирование следов разных материалов: ANSI/ASTM E3462-25e1 (интерпретация и отчётность по сравнениям следо… | документ по комбинированию следов разных материалов для вывода о месте работы — нет |
| TRD-010 | отпечаток: OSAC 2023-N-0020 (сбор и сохранение отпечатков на месте) и OSAC 2022-N-0033 (обработка вещества дл… | документ о последовательности наложения следов разных материалов — нет |
| TRD-011 | краска: ANSI/ASTM E1610-18 (криминалистический анализ и сравнение краски) — краска как следовой материал, свя… | документ по совместному выводу «краска + штукатурная пыль = ремонт» — нет |
| WAT-001 | признаки залива и категории повреждения: ANSI/IICRC S500 (Standard and Reference Guide for Professional Water… | открытый текст ANSI/IICRC S500 (категории повреждения) — стандарт платный |
| WAT-003 | свежесть повреждения как признак: ANSI/IICRC S500 (4-е изд. 2015) — стандарт по восстановлению после залива; … | открытый текст ANSI/IICRC S500 (свежесть повреждения) — стандарт платный |

## 8. Что исправлено 2026-11-03

| Правило | Было | Стало | Вердикт | version |
| --- | --- | --- | --- | --- |
| ABS-001 | Kirk's Fire Investigation, 8th ed., Pearson 2019 — следы перемещения предметов как метод реконструкции сцены | OSAC Registry (NIST), подкомитет Crime Scene Investigation & Reconstr… — прямая ссылка на документ, подтверждающий это утверждение, не установлена; пыле… | partial | да (1→2) |
| ABS-002 | Kirk's Fire Investigation, 8th ed., Pearson 2019 — отсутствие следов как источник информации | OSAC Registry (NIST), подкомитет Crime Scene Investigation & Reconstr… — прямая ссылка на документ, подтверждающий это утверждение, не установлена; отсу… | partial | да (1→2) |
| ABS-003 | OSAC Registry, NIST — Trace Evidence (раздел о следах на месте) — следы оставления и снятия предметов | OSAC Registry (NIST), подкомитет Crime Scene Investigation & Reconstr… — прямая ссылка на документ, подтверждающий это утверждение, не установлена; след… | partial | да (1→2) |
| ABS-004 | Kirk's Fire Investigation, 8th ed., Pearson 2019 — следы перемещения по сцене | OSAC Registry (NIST), подкомитет Crime Scene Investigation & Reconstr… — прямая ссылка на документ, подтверждающий это утверждение, не установлена; след… | partial | да (2→3) |
| BIO-001 | OSAC Registry, NIST — Wildlife and Biological Trace — следы животных в жилой среде | OSAC Registry (NIST), подкомитет Wildlife Forensic Biology: ANSI/ASB … — морфологическая идентификация следов животных: ANSI/ASB 028-19; бытовая обстано…<br>OSAC Registry (NIST), подкомитет Wildlife Forensic Biology: ANSI/ASB … — правила отчёта по морфологической и генетической экспертизе следов животных: AN… | partial | да (2→3) |
| FIRE-001 | NFPA 1033: Standard for Professional Fire Investigation, 2022 — методы осмотра места пожара | NFPA 921: Guide for Fire and Explosion Investigations, 2024 edition (… — методы осмотра места пожара: NFPA 921 — руководство по исследованию пожара; по … | partial | да (1→2) |
| FIRE-002 | NFPA 921: Guide for Fire and Explosions Investigations, 2024 — V-паттерн как признак низко расположенного очага | NFPA 921: Guide for Fire and Explosion Investigations, 2024 edition (… — прямая ссылка на документ, подтверждающий это утверждение, не установлена; V-па… | partial | да (1→2) |
| GRD-001 | OSAC Registry, NIST — Trace Evidence — частицы и следы как следовые материалы; конкретный стандарт уточняет эксперт | OSAC Registry (NIST), подкомитет Trace Materials: ANSI/ASTM E3272-23 … — частицы и следы как следовой материал: ANSI/ASTM E3272-23 (сбор почв и иных гео… | partial | да (2→3) |
| GRD-003 | OSAC Registry, NIST — Footwear and Textile Standards Committee — следы обуви и текстиля как индивидуализирующий признак | OSAC Registry (NIST), подкомитет Footwear & Tire: OSAC 2023-S-0017 (S… — след обуви как индивидуализирующий признак: OSAC 2023-S-0017 задаёт порядок фор… | partial | да (2→3) |
| GRD-004 | OSAC Registry, NIST — Trace Evidence — частицы и следы как следовые материалы; конкретный стандарт уточняет эксперт | OSAC Registry (NIST), подкомитет Trace Materials: ANSI/ASTM E3272-23 … — прямая ссылка на документ, подтверждающий это утверждение, не установлена; свеж… | partial | да (1→2) |
| HOME-001 | Kirk's Fire Investigation, 8th ed., Pearson 2019 — следы перемещения и работы в помещении | OSAC Registry (NIST), подкомитет Crime Scene Investigation & Reconstr… — прямая ссылка на документ, подтверждающий это утверждение, не установлена; след… | partial | да (2→3) |
| HOME-002 | OSAC Registry, NIST — Trace Evidence — частицы и следы как следовые материалы; конкретный стандарт уточняет эксперт | OSAC Registry (NIST), подкомитет Crime Scene Investigation & Reconstr… — прямая ссылка на документ, подтверждающий это утверждение, не установлена; коль… | partial | да (1→2) |
| HOME-003 | OSAC Registry, NIST — Trace Evidence — частицы и следы как следовые материалы; конкретный стандарт уточняет эксперт | OSAC Registry (NIST), подкомитет Crime Scene Investigation & Reconstr… — прямая ссылка на документ, подтверждающий это утверждение, не установлена; сост… | partial | да (2→3) |
| HOME-004 | OSAC Registry, NIST — Footwear and Textile Standards Committee — следы обуви и текстиля как индивидуализирующий признак | OSAC Registry (NIST), подкомитет Footwear & Tire: OSAC 2023-S-0017 (S… — след обуви как индивидуализирующий признак: OSAC 2023-S-0017 (порядок формулиро… | partial | да (1→2) |
| HOME-005 | FDA Food Code, U.S. Food and Drug Administration — еда подаётся и съедается за столом с посудой: остатки рядом с тарелкой относятс…<br>OSAC Trace Materials Subcommittee, NIST — частицы еды как следовой материал; конкретный стандарт уточняет эксперт | OSAC Registry (NIST), подкомитет Trace Materials — частицы еды как следовой материал: подкомитет Trace Materials реестра OSAC (34 … | partial | да (1→2) |
| MECH-001 | OSAC Registry, NIST — Vehicle Collision and Automotive Standards — следы шин как след транспортного средства | OSAC Registry (NIST), подкомитет Footwear & Tire: OSAC 2023-S-0017 (S… — следы шин как след транспортного средства: OSAC 2023-S-0017 — порядок формулиро… | partial | да (1→2) |
| MECH-002 | OSAC Registry, NIST — Toolmark and Trace Evidence — следы орудия как индивидуализирующий признак | OSAC Registry (NIST), подкомитет Firearms & Toolmarks: OSAC 2024-S-00… — след орудия как индивидуализирующий признак: OSAC 2024-S-0002 — метод сравнения…<br>OSAC Registry (NIST), подкомитет Firearms & Toolmarks: ANSI/ASB 162-2… — экспертиза и документирование следов неогнестрельного оружия: ANSI/ASB 162-24; … | partial | да (1→2) |
| OFF-001 | OSAC Registry, NIST — Trace Evidence — частицы и следы как следовые материалы; конкретный стандарт уточняет эксперт | OSAC Registry (NIST), подкомитет Crime Scene Investigation & Reconstr… — прямая ссылка на документ, подтверждающий это утверждение, не установлена; повт… | partial | да (2→3) |
| OFF-002 | OSAC Registry, NIST — Trace Evidence (Trace Materials: Ink and Paper) — чернила и бумага как следовые материалы | OSAC Registry (NIST), подкомитет Forensic Document Examination: ANSI/… — чернила, тонер и бумага как материалы экспертизы документов: ANSI/ASB 011-22 (о…<br>OSAC Registry (NIST), подкомитет Forensic Document Examination: ANSI/… — рукописные материалы исследуются в экспертизе документов: ANSI/ASB 070-22; след… | partial | да (1→2) |
| OFF-003 | OSAC Registry, NIST — Trace Evidence — частицы и следы как следовые материалы; конкретный стандарт уточняет эксперт | OSAC Registry (NIST), подкомитет Friction Ridge: OSAC 2023-N-0020 (St… — проявление и оценка следов ладоней: OSAC 2023-N-0020 (сбор и сохранение отпечат… | partial | да (1→2) |
| OFF-004 | OSAC Registry, NIST — Trace Evidence — частицы и следы как следовые материалы; конкретный стандарт уточняет эксперт | OSAC Registry (NIST), подкомитет Crime Scene Investigation & Reconstr… — прямая ссылка на документ, подтверждающий это утверждение, не установлена; пере… | partial | да (1→2) |
| PHY-001 | Схема сцены-графа ЭЛЕМЕНТАРНО, schemas/scene-graph.schema.json — целостность ссылок — свойство описания, а не физики | Схема сцены-графа ЭЛЕМЕНТАРНО, schemas/scene-graph.schema.json — опре… — целостность ссылок — свойство описания, а не физики | confirmed | нет (1→1) |
| PHY-002 | Serway & Jewett, Physics for Scientists and Engineers, 10th ed., Ceng… — направление тени противоположно направлению на источник | Wikipedia, статья «Shadow» (свободная энциклопедия) — тень — «a dark area on a surface where light from a light source is blocked by … | confirmed | да (2→3) |
| PHY-003 | Serway & Jewett, Physics for Scientists and Engineers, 10th ed., Ceng… — геометрия теней | Wikipedia, статья «Shadow» (свободная энциклопедия) — «If there is more than one light source, there will be several shadows, with th… | confirmed | да (3→4) |
| PHY-004 | Схема сцены-графа ЭЛЕМЕНТАРНО, schemas/scene-graph.schema.json — fill_level определён как доля объёма жидкости | Схема сцены-графа ЭЛЕМЕНТАРНО, schemas/scene-graph.schema.json — опре… — в схеме fill_level объявлено числом в диапазоне 0…1 без описания; семантика «до… | partial | да (1→2) |
| PRES-001 | OSAC Registry, NIST — Footwear and Textile Standards Committee — след обуви как индивидуализирующий признак и оценка размера | OSAC Registry (NIST), подкомитет Footwear & Tire: OSAC 2023-S-0017 (S… — след обуви как индивидуализирующий признак и оценка размера: OSAC 2023-S-0017 (… | partial | да (1→2) |
| PRES-002 | OSAC Registry, NIST — Fingerprint and Friction Ridge Standards — проявление и оценка следов пальцевых ладоней | OSAC Registry (NIST), подкомитет Friction Ridge: OSAC 2023-N-0020 (St… — проявление и оценка следов пальцевых ладоней: OSAC 2022-N-0033 (обработка вещес… | partial | да (1→2) |
| PRES-003 | OSAC Registry, NIST — Fingerprint and Friction Ridge Standards — следы в пыли и на запылённых поверхностях | OSAC Registry (NIST), подкомитет Friction Ridge: OSAC 2023-N-0020 (St… — следы в пыли и на запылённых поверхностях: OSAC 2022-N-0033 (обработка вещества… | partial | да (1→2) |
| PRES-004 | Federal Rules of Evidence, Rule 1001, Cornell Legal Information Insti… — содержание фотографии доказывается оригиналом: кадр — улика того, что в нём изо…<br>Eyewitness Evidence: A Guide for Law Enforcement, National Institute … — личность устанавливается процедурой опознания, а не самим фактом изображения в … | Federal Rules of Evidence, Rule 1002 (Requirement of the Original), C… — содержание фотографии доказывается оригиналом: Rule 1002 — «An original writing…<br>Eyewitness Evidence: A Guide for Law Enforcement, National Institute … — личность устанавливается процедурой опознания, а не самим фактом изображения в … | confirmed + partial | да (1→2) |
| PUZ-001 | Sherlock: A Dataset for Visual Abductive Reasoning, Hessel et al., EC… — формат «улика → вывод» с локализацией улики | The Abduction of Sherlock Holmes: A Dataset for Visual Abductive Reas… — формат «улика → вывод» с локализацией улики: участники сначала «observe and ide… | confirmed | да (1→2) |
| PUZ-002 | Kirk's Fire Investigation, 8th ed., Pearson 2019 — зачистка места как признак сокрытия | OSAC Registry (NIST), подкомитет Crime Scene Investigation & Reconstr… — прямая ссылка на документ, подтверждающий это утверждение, не установлена; зачи… | partial | да (1→2) |
| PUZ-003 | Sherlock: A Dataset for Visual Abductive Reasoning, Hessel et al., EC… — абдуктивные связки «признак → бытовое объяснение» | The Abduction of Sherlock Holmes: A Dataset for Visual Abductive Reas… — абдуктивные связки «признак → бытовое объяснение»: 363 тысячи пар (clue, infere… | confirmed | да (1→2) |
| PUZ-004 | OSAC Registry, NIST — Footwear and Textile Standards Committee — следы обуви как индивидуализирующий признак | OSAC Registry (NIST), подкомитет Footwear & Tire: OSAC 2023-S-0017 (S… — следы обуви как индивидуализирующий признак: OSAC 2023-S-0017 (порядок формулир… | partial | да (1→2) |
| PUZ-005 | Sherlock: A Dataset for Visual Abductive Reasoning, Hessel et al., EC… — изменение обстановки как абдуктивная улика | The Abduction of Sherlock Holmes: A Dataset for Visual Abductive Reas… — прямая ссылка на документ, подтверждающий это утверждение, не установлена; изме… | partial | да (1→2) |
| PUZ-006 | Kirk's Fire Investigation, 8th ed., Pearson 2019 — следы перемещения по сцене | OSAC Registry (NIST), подкомитет Crime Scene Investigation & Reconstr… — прямая ссылка на документ, подтверждающий это утверждение, не установлена; след… | partial | да (1→2) |
| PUZ-007 | Sherlock: A Dataset for Visual Abductive Reasoning, Hessel et al., EC… — изменение состава сцены между наблюдениями | The Abduction of Sherlock Holmes: A Dataset for Visual Abductive Reas… — прямая ссылка на документ, подтверждающий это утверждение, не установлена; изме… | partial | да (1→2) |
| SEM-001 | NL-Eye: Abductive NLI for Images, 2024 — категория cultural reasoning: символическое прочтение сцены | NL-Eye: Abductive NLI for Images, 2024 (arXiv:2410.02613) — работа подтверждена по аннотации: рассуждение по изображению, в том числе культ… | partial | да (1→2) |
| SEM-002 | NL-Eye: Abductive NLI for Images, 2024 — категория social reasoning: предметы как отсылки к персонажу | NL-Eye: Abductive NLI for Images, 2024 (arXiv:2410.02613) — работа подтверждена по аннотации: рассуждение по изображению с учётом социально… | partial | да (1→2) |
| SEM-003 | ENFSI Best Practice Manual for the Forensic Examination of Handwritin… — различение намеренно построенных штрихов и случайных черт: признаки конструкции…<br>Sebeok, T. A. Semeiotics: An Introduction, Indiana University Press, … — знак как намеренно построенный объект, а не как случайный след | ENFSI Best Practice Manual for the Forensic Examination of Handwritin… — документ подтверждён: это руководство по экспертизе знаков и рукописных записей… | partial | да (1→2) |
| SEM-004 | Ronnberg, A. The Book of Symbols: Reflections on Archetypal Images, T… — каталог архетипических образцов, включая глаз в треугольнике<br>Sebeok, T. A. Semeiotics: An Introduction, Indiana University Press, … — различие знака и его истолкования | Hall, J. Dictionary of Subjects and Symbols in Art, J. Murray, 1974; … — стандартный иконографический справочник: символы в изобразительном искусстве; с…<br>Ronnberg, A. The Book of Symbols: Reflections on Archetypal Images, T… — каталог архетипических образцов; полный текст прочитан, каталог подтверждён, но… | partial | да (1→2) |
| SEM-005 | ENFSI Best Practice Manual for the Forensic Examination of Handwritin… — различение рукописного и печатного текста в исследуемом объекте | OSAC Registry (NIST), подкомитет Forensic Document Examination: ANSI/… — названия стандартов подтверждены по выгрузке реестра OSAC (264 стандарта); текс… | partial | да (1→2) |
| TRD-001 | OSAC Registry, NIST — Trace Evidence (Trace Materials: Paint) — брызги и следы краски как следовой материал; конкретный стандарт уточняет экспе… | OSAC Registry (NIST), подкомитет Trace Materials: ANSI/ASTM E1610-18 … — брызги и следы краски как следовой материал: ANSI/ASTM E1610-18 (криминалистиче… | partial | да (1→2) |
| TRD-002 | OSAC Registry, NIST — Trace Evidence (Particulate: Wood) — древесные частицы как следовой материал | OSAC Registry (NIST), подкомитет Trace Materials: ANSI/ASTM E3272-23 … — прямая ссылка на документ, подтверждающий это утверждение, не установлена; древ… | partial | да (1→2) |
| TRD-003 | OSAC Registry, NIST — Trace Evidence (Particulate) — частицы как следовой материал; бытовая специфика муки требует экспертной провер… | OSAC Registry (NIST), подкомитет Trace Materials: ANSI/ASTM E3272-23 … — прямая ссылка на документ, подтверждающий это утверждение, не установлена; мука… | partial | да (1→2) |
| TRD-004 | OSAC Registry, NIST — Trace Evidence (Trace Materials: Lubricants, Me… — смазочные материалы и металл как следовые вещества | OSAC Registry (NIST), подкомитет Trace Materials: ANSI/ASTM E3296-22 … — прямая ссылка на документ, подтверждающий это утверждение, не установлена; смаз… | partial | да (1→2) |
| TRD-005 | OSAC Registry, NIST — Trace Evidence (Trace Materials: Metal) — металлические частицы как следовой материал | OSAC Registry (NIST), подкомитет Trace Materials: ANSI/ASTM E3501-25 … — минеральные частицы как следовое вещество: ANSI/ASTM E3501-25 (анализ геологиче…<br>OSAC Registry (NIST), подкомитет Trace Materials: ANSI/ASTM E3294-23 … — анализ геологических материалов методом рентгеновской дифракции: ANSI/ASTM E329… | partial | да (1→2) |
| TRD-006 | OSAC Registry, NIST — Trace Evidence (Particulate: Construction Dust) — строительная пыль как следовой материал | OSAC Registry (NIST), подкомитет Trace Materials: ANSI/ASTM E3272-23 … — прямая ссылка на документ, подтверждающий это утверждение, не установлена; стро… | partial | да (1→2) |
| TRD-007 | OSAC Registry, NIST — Trace Evidence (Surface Patterns) — следы на поверхностях; бытовая интерпретация кружек требует экспертной проверки | OSAC Registry (NIST), подкомитет Crime Scene Investigation & Reconstr… — прямая ссылка на документ, подтверждающий это утверждение, не установлена; след… | partial | да (1→2) |
| TRD-008 | OSAC Registry, NIST — Trace Evidence (Trace Materials: Ink) — чернила и тонер как следовые материалы | OSAC Registry (NIST), подкомитет Forensic Document Examination: ANSI/… — чернила и тонер как материалы экспертизы документов: ANSI/ASB 011-22 (область к…<br>OSAC Registry (NIST), подкомитет Forensic Document Examination: ANSI/… — рукописные материалы исследуются в экспертизе документов: ANSI/ASB 070-22; след… | partial | да (1→2) |
| TRD-009 | OSAC Registry, NIST — Trace Evidence — комбинирование следов разных материалов для вывода о месте работы | OSAC Registry (NIST), подкомитет Trace Materials: ANSI/ASTM E3462-25e… — комбинирование следов разных материалов: ANSI/ASTM E3462-25e1 (интерпретация и … | partial | да (1→2) |
| TRD-010 | OSAC Registry, NIST — Fingerprint and Friction Ridge Standards — соотнесение следов разных материалов по последовательности наложения | OSAC Registry (NIST), подкомитет Friction Ridge: OSAC 2023-N-0020 (St… — отпечаток: OSAC 2023-N-0020 (сбор и сохранение отпечатков на месте) и OSAC 2022…<br>OSAC Registry (NIST), подкомитет Trace Materials: ANSI/ASTM E1610-18 … — краска: ANSI/ASTM E1610-18 (криминалистический анализ и сравнение краски) и ANS… | partial | да (1→2) |
| TRD-011 | OSAC Registry, NIST — Trace Evidence — комбинирование материалов для вывода о характере работ | OSAC Registry (NIST), подкомитет Trace Materials: ANSI/ASTM E1610-18 … — краска: ANSI/ASTM E1610-18 (криминалистический анализ и сравнение краски) — кра…<br>OSAC Registry (NIST), подкомитет Trace Materials: ANSI/ASTM E3272-23 … — штукатурная пыль: ANSI/ASTM E3272-23 (сбор почв и иных геологических веществ) —… | partial | да (1→2) |
| WAT-001 | IIC S500: Standard for Professional Water Damage Restoration — признаки залива и категории повреждения | ANSI/IICRC S500, Standard and Reference Guide for Professional Water … — признаки залива и категории повреждения: ANSI/IICRC S500 (Standard and Referenc… | partial | да (1→2) |
| WAT-003 | IIC S500: Standard for Professional Water Damage Restoration — свежесть повреждения как признак | ANSI/IICRC S500, Standard and Reference Guide for Professional Water … — свежесть повреждения как признак: ANSI/IICRC S500 (4-е изд. 2015) — стандарт по… | partial | да (1→2) |

### Правка rules/semiotics.json (владелец ветки, 2026-11-03)

Правила `semiotics.json` я не правил, но они изменились, и ведомость пересобрана под них:

- **SEM-003**: `Sebeok, T. A. Semeiotics: An Introduction…` убран — документ не подтверждён (OpenLibrary и archive.org: 0 результатов). Взамен `ENFSI Best Practice Manual…, ENFSI-BPM-FHX-01, Ed. 04 (2022)` — обозначение исправлено: год 2019 не подтверждался, актуальное издание — Ed. 04 (сентябрь 2022). Вердикт остался partial: частное различение «фигура по образцу против случайного росчерка» в документе не сформулировано.
- **SEM-004**: `Sebeok…` убран по той же причине. `Ronnberg…` исправлено с «Taschen, 1997» на «TASCHEN, 2010» (первое издание 2010 подтверждено по каталогу и по прочитанному тексту). Добавлен новый источник — `Hall, J. Dictionary of Subjects and Symbols in Art, J. Murray, 1974; Routledge, 2018`: стандартный иконографический справочник, существование и издания подтверждены по каталогу, текст платный. Именно он выступает опорой для опознания конкретного образца, потому что запись «глаз в треугольнике» в The Book of Symbols не найдена.
- **SEM-001, SEM-002**: в строку ref добавлен идентификатор `arXiv:2410.02613` — по нему работу и проверяли; вердикт остался partial, потому что содержание категорий cultural и social в аннотации не раскрыто, а оба прочтения — трактовка правил.
- **SEM-005**: ссылка переведена на объединённую запись Forensic Document Examination (ANSI/ASB 070-22 + ANSI/ASB 011-22), которая теперь одна на всех три правила — SEM-005, OFF-002 и TRD-008. Две прежние записи (по одному стандарту каждая) объединены в одну; варианты строки `ref`, по которым ссылаются OFF-002 и TRD-008, объявлены в ведомости как «входит в запись».

## 9. Источники, снятые с правил

| Источник | Где использовался | Что о нём известно | Почему снят |
| --- | --- | --- | --- |
| `Sebeok, T. A. Semeiotics: An Introduction, Indiana University Press, 1975` | SEM-003, SEM-004 (предыдущая версия правил) | Не подтверждён: в OpenLibrary и archive.org — 0 результатов на это название (в каталогах есть смежные издания Sebeok: «The Tell Tale Sign» 1975, «Introduction to Semiotics» 1994, «Signs: An Introduction to Semiotics» 1994, «Global Semiotics» 2001). | Снят владельцем ветки 2026-11-03: документ не найден, опереться на него нельзя. |
| `Kirk's Fire Investigation, 8th ed., Pearson 2019` | ABS-001, ABS-002, ABS-004, HOME-001, PUZ-002, PUZ-006 | Книга существует (DeHaan, Pearson/Prentice Hall, издания 2002–2017), но 8-е издание 2019 года ни одним доступным каталогом не подтверждено, а текст закрыт: ни одна из пяти формулировок `note` не может быть проверена. | Снят: пожарно-технический учебник не подтверждает ни пылевой контур, ни отсутствие следов, ни следы перемещения по сцене. Заменён на стандарты OSAC по документированию и реконструкции сцены. |
| `Serway & Jewett, Physics for Scientists and Engineers, 10th ed., Cengage 2019` | PHY-002, PHY-003 | Издание подтверждено каталогом (OpenLibrary: tenth edition, Serway & Jewett, Cengage, 2019), но текст платный и не открывался — обе формулировки `note` остались непроверенными. | Снят: вместо непроверенного учебника взято то, что реально прочитано. |
| `FDA Food Code, U.S. Food and Drug Administration` | HOME-005 | Документ существует (FDA, редакции 2005–2026), но это санитарный стандарт для предприятий общепита: утверждения правила («еда подаётся за столом с посудой, остатки рядом с тарелкой относятся к трапезе на этом месте») он не содержит. | Снят с правила HOME-005 как неподходящее основание; сам документ остаётся реальным, его проверка — в ведомости. |
| `OSAC Registry, NIST — Trace Evidence (Trace Materials: Ink and Paper); OSAC Registry, NIST — Trace Evidence (Trace Materials: Ink); OSAC Registry, NIST — Trace Evidence (Particulate: Wood); OSAC Registry, NIST — Trace Evidence (Particulate); OSAC Registry, NIST — Trace Evidence (Trace Materials: Lubricants, Metal); OSAC Registry, NIST — Trace Evidence (Trace Materials: Metal); OSAC Registry, NIST — Trace Evidence (Particulate: Construction Dust); OSAC Registry, NIST — Trace Evidence (Surface Patterns); OSAC Registry, NIST — Vehicle Collision and Automotive Standards; OSAC Registry, NIST — Trace Evidence (раздел о следах на месте)` | ABS-003, MECH-001, OFF-002, TRD-002..TRD-008 | Ни одного такого документа или раздела в реестре OSAC нет: поиск по всем 264 заголовкам даёт 0 совпадений по ink, toner, paper, wood, particulate, metal, lubricant, dust, surface и 0 подкомитетов про Vehicle Collision and Automotive Standards. | Сняты: подменены реальными подкомитетами и стандартами реестра, а для тем, которых в реестре нет, написаны честные `note`. |
| `OSAC Registry, NIST — Trace Evidence; OSAC Registry, NIST — Trace Evidence (Trace Materials: Paint); OSAC Registry, NIST — Fingerprint and Friction Ridge Standards; OSAC Registry, NIST — Footwear and Textile Standards Committee; OSAC Registry, NIST — Toolmark and Trace Evidence; OSAC Registry, NIST — Wildlife and Biological Trace; OSAC Trace Materials Subcommittee, NIST` | GRD-001, GRD-003, GRD-004, HOME-002..HOME-005, OFF-001, OFF-003, OFF-004, PRES-001..PRES-003, PUZ-004, MECH-002, BIO-001, TRD-001, TRD-009..TRD-011 | Реальные подразделы реестра, но с неверными названиями (например, «Footwear and Textile Standards Committee» вместо «Footwear & Tire», «Wildlife and Biological Trace» вместо «Wildlife Forensic Biology»); общие `note` вида «частицы и следы как следовые материалы» не подтверждали конкретные утверждения правил. | Уточнены до реальных подкомитетов и конкретных стандартов, `note` переписаны под то, что эти документы действительно устанавливают. |
| `NFPA 1033: Standard for Professional Fire Investigation, 2022; NFPA 921: Guide for Fire and Explosions Investigations, 2024; IIC S500: Standard for Professional Water Damage Restoration; Federal Rules of Evidence, Rule 1001, Cornell Legal Information Institute; Sherlock: A Dataset for Visual Abductive Reasoning, Hessel et al., ECCV 2022; ENFSI Best Practice Manual for the Forensic Examination of Handwriting, 2019; The Book of Symbols: Reflections on Archetypal Images, Taschen, 1997` | FIRE-001, FIRE-002, WAT-001, WAT-003, PRES-004, PUZ-001, PUZ-003, PUZ-005, PUZ-007, SEM-003, SEM-004, SEM-005 | Документы существуют, но библиографические строки были неверны: NFPA 1033 — это «Standard for Professional Qualifications for Fire Investigators», а не методы осмотра места пожара; в FRE норма о оригинале — Rule 1002, а не 1001; издатель S500 — IICRC, а не IIC; ENFSI BPM — Ed. 04 (2022), а не 2019; название главы — «The Abduction of Sherlock Holmes: …». | Исправлены библиографические строки; где правило стояло на неверном документе (FIRE-001) — заменён источник. |

## 10. Как это проверяется машинно

`tools/check_sources.py` читает `rules/*.json` и этот файл, сверяет, что каждый источник из правил присутствует в ведомости, что у каждой записи ровно один вердикт из трёх и что правила с `confirmed`-источниками перечислены в разделе 4; печатает таблицу «правило — источник — вердикт — можно ли поднимать потолок» и возвращает ненулевой код, если ведомость неполна. Проверка работает без сети. Тесты: `tests/test_sources.py`.
