# Plan: Дозаполнить непокрытые компании из IMOEX

Заполнить исследования для 10 непокрытых компаний из индекса IMOEX, следуя стандартному процессу исследования (Фазы 0-8 из RESEARCH_CHECKLIST.md). Компании отсортированы по весу в индексе (от большего к меньшему).

## Context

- Files involved:
  - `companies/RESEARCH_CHECKLIST.md` — шаблон чеклиста (копируется в каждую компанию)
  - `companies/RESEARCH_GUIDE.md` — методология исследования
  - `companies/_TEMPLATE/` — шаблон папки компании
  - `_index.md` — корневая таблица статуса обновлений
  - `scripts/generate_trend_json.py` — генерация trend.json
  - Секторальные файлы: `sectors/oil-gas/`, `sectors/metals-mining/`, `sectors/transport/`, `sectors/finance/`, `sectors/construction/`, `sectors/energy/`, `sectors/it-telecom/`
- Related patterns: существующие заполненные компании (SBER, GAZP, LKOH, GMKN и др.)
- Dependencies: веб-доступ для получения финансовых данных (smart-lab, MOEX)

## Approach

- Каждая компания исследуется по Фазам 0-8 из RESEARCH_CHECKLIST.md
- Для каждой компании: скопировать шаблон, заполнить _index.md, сгенерировать trend.json
- После каждой компании обновить таблицу статуса в корневом `_index.md`
- Закоммитить и запушить после каждой компании
- Порядок: по убыванию веса в IMOEX (наиболее значимые первыми)

## Tasks

### Task 1: TATN — Татнефть (IMOEX 5.20%)

**Сектор:** oil-gas
**Files:**
- Create: `companies/TATN/_index.md`
- Create: `companies/TATN/RESEARCH_CHECKLIST.md` (удалить после завершения)
- Create: `companies/TATN/trend.json` (автогенерация)
- Modify: `_index.md` (обновить статус)

- [x] Фаза 0: создать папку из шаблона `_TEMPLATE`, скопировать чеклист
- [x] Фаза 1: прочитать контекст (sectors/oil-gas, russia/macro, russia/regulations)
- [x] Фаза 2: собрать финансовые данные (МСФО годовые + квартальные)
- [x] Фаза 3: описать бизнес-модель (нефтедобыча, переработка, шинный бизнес)
- [x] Фаза 4: оценить финансовое здоровье (red/green flags, stop-conditions)
- [x] Фаза 5: рассчитать справедливую стоимость (P/E или EV/EBITDA, 3 сценария)
- [x] Фаза 6: определить позицию (buy/watch/hold/sell) и sentiment
- [x] Фаза 7: заполнить _index.md по стандарту, обновить корневой _index.md
- [x] Фаза 8: финальная проверка, удалить RESEARCH_CHECKLIST.md
- [x] Сгенерировать trend.json через `python3 scripts/generate_trend_json.py`
- [x] Закоммитить и запушить

### Task 2: RUAL — РУСАЛ (IMOEX 1.04%)

**Сектор:** metals-mining
**Примечание:** уже существует stub-файл, нужно дозаполнить
**Files:**
- Modify: `companies/RUAL/_index.md` (дозаполнить из заглушки)
- Create: `companies/RUAL/RESEARCH_CHECKLIST.md` (удалить после завершения)
- Modify: `companies/RUAL/trend.json` (обновить)
- Modify: `_index.md` (обновить статус)

- [x] Фаза 0: скопировать чеклист (папка уже существует)
- [x] Фаза 1: прочитать контекст (sectors/metals-mining, russia/macro, russia/regulations — санкции!)
- [x] Фаза 2: собрать финансовые данные
- [x] Фаза 3: описать бизнес-модель (алюминий, глинозём, зависимость от Норникеля)
- [x] Фаза 4: оценить финансовое здоровье (особое внимание: долг, санкции)
- [x] Фаза 5: рассчитать справедливую стоимость
- [x] Фаза 6: определить позицию и sentiment
- [x] Фаза 7: заполнить _index.md, обновить корневой _index.md
- [x] Фаза 8: финальная проверка, удалить RESEARCH_CHECKLIST.md
- [x] Сгенерировать trend.json
- [x] Закоммитить и запушить

### Task 3: AFLT — Аэрофлот (IMOEX 0.63%)

**Сектор:** transport
**Files:**
- Create: `companies/AFLT/_index.md`
- Create: `companies/AFLT/RESEARCH_CHECKLIST.md` (удалить после завершения)
- Create: `companies/AFLT/trend.json` (автогенерация)
- Modify: `_index.md` (обновить статус)

- [ ] Фаза 0: создать папку из шаблона, скопировать чеклист
- [ ] Фазы 1-6: полное исследование (авиаперевозки, санкции на авиапарк, лизинг, гос.поддержка)
- [ ] Фаза 7: заполнить _index.md, обновить корневой _index.md
- [ ] Фаза 8: финальная проверка, удалить RESEARCH_CHECKLIST.md
- [ ] Сгенерировать trend.json
- [ ] Закоммитить и запушить

### Task 4: DOMRF — ДОМ.РФ (IMOEX 0.52%)

**Сектор:** finance (или construction — уточнить)
**Files:**
- Create: `companies/DOMRF/_index.md`
- Create: `companies/DOMRF/RESEARCH_CHECKLIST.md` (удалить после завершения)
- Create: `companies/DOMRF/trend.json` (автогенерация)
- Modify: `_index.md` (обновить статус)

- [ ] Фаза 0: создать папку из шаблона, скопировать чеклист
- [ ] Фазы 1-6: полное исследование (ипотечное кредитование, гос.институт развития, облигации)
- [ ] Фаза 7: заполнить _index.md, обновить корневой _index.md
- [ ] Фаза 8: финальная проверка, удалить RESEARCH_CHECKLIST.md
- [ ] Сгенерировать trend.json
- [ ] Закоммитить и запушить

### Task 5: TRNFP — Транснефть прив. (IMOEX 0.45%)

**Сектор:** oil-gas (транспортировка нефти)
**Files:**
- Create: `companies/TRNFP/_index.md`
- Create: `companies/TRNFP/RESEARCH_CHECKLIST.md` (удалить после завершения)
- Create: `companies/TRNFP/trend.json` (автогенерация)
- Modify: `_index.md` (обновить статус)

- [ ] Фаза 0: создать папку из шаблона, скопировать чеклист
- [ ] Фазы 1-6: полное исследование (монополия на нефтепроводы, тарифное регулирование, дивиденды прив.)
- [ ] Фаза 7: заполнить _index.md, обновить корневой _index.md
- [ ] Фаза 8: финальная проверка, удалить RESEARCH_CHECKLIST.md
- [ ] Сгенерировать trend.json
- [ ] Закоммитить и запушить

### Task 6: CBOM — МКБ (IMOEX 0.43%)

**Сектор:** finance (banking)
**Files:**
- Create: `companies/CBOM/_index.md`
- Create: `companies/CBOM/RESEARCH_CHECKLIST.md` (удалить после завершения)
- Create: `companies/CBOM/trend.json` (автогенерация)
- Modify: `_index.md` (обновить статус)

- [ ] Фаза 0: создать папку из шаблона, скопировать чеклист
- [ ] Фазы 1-6: полное исследование (универсальный банк, корпоративное кредитование, NIM, ROE)
- [ ] Фаза 7: заполнить _index.md, обновить корневой _index.md
- [ ] Фаза 8: финальная проверка, удалить RESEARCH_CHECKLIST.md
- [ ] Сгенерировать trend.json
- [ ] Закоммитить и запушить

### Task 7: ENPG — ЭН+ Групп (IMOEX 0.37%)

**Сектор:** energy (или metals-mining — холдинг, владеет долей в RUAL)
**Files:**
- Create: `companies/ENPG/_index.md`
- Create: `companies/ENPG/RESEARCH_CHECKLIST.md` (удалить после завершения)
- Create: `companies/ENPG/trend.json` (автогенерация)
- Modify: `_index.md` (обновить статус)

- [ ] Фаза 0: создать папку из шаблона, скопировать чеклист
- [ ] Фазы 1-6: полное исследование (энергетика + доля в РУСАЛ, ГЭС, санкции Дерипаска)
- [ ] Фаза 7: заполнить _index.md, обновить корневой _index.md
- [ ] Фаза 8: финальная проверка, удалить RESEARCH_CHECKLIST.md
- [ ] Сгенерировать trend.json
- [ ] Закоммитить и запушить

### Task 8: AFKS — АФК Система (IMOEX 0.35%)

**Сектор:** finance (или конгломерат/холдинг)
**Files:**
- Create: `companies/AFKS/_index.md`
- Create: `companies/AFKS/RESEARCH_CHECKLIST.md` (удалить после завершения)
- Create: `companies/AFKS/trend.json` (автогенерация)
- Modify: `_index.md` (обновить статус)

- [ ] Фаза 0: создать папку из шаблона, скопировать чеклист
- [ ] Фазы 1-6: полное исследование (холдинг: МТС, Segezha, Ozon, Медси, Степь; долг, IPO дочек)
- [ ] Фаза 7: заполнить _index.md, обновить корневой _index.md
- [ ] Фаза 8: финальная проверка, удалить RESEARCH_CHECKLIST.md
- [ ] Сгенерировать trend.json
- [ ] Закоммитить и запушить

### Task 9: UGLD — ЮГК (IMOEX 0.25%)

**Сектор:** metals-mining (золотодобыча)
**Files:**
- Create: `companies/UGLD/_index.md`
- Create: `companies/UGLD/RESEARCH_CHECKLIST.md` (удалить после завершения)
- Create: `companies/UGLD/trend.json` (автогенерация)
- Modify: `_index.md` (обновить статус)

- [ ] Фаза 0: создать папку из шаблона, скопировать чеклист
- [ ] Фазы 1-6: полное исследование (золотодобыча, себестоимость, AISC, цены на золото)
- [ ] Фаза 7: заполнить _index.md, обновить корневой _index.md
- [ ] Фаза 8: финальная проверка, удалить RESEARCH_CHECKLIST.md
- [ ] Сгенерировать trend.json
- [ ] Закоммитить и запушить

### Task 10: CNRU — Циан (IMOEX 0.23%)

**Сектор:** it-telecom (классифайд/proptech)
**Files:**
- Create: `companies/CNRU/_index.md`
- Create: `companies/CNRU/RESEARCH_CHECKLIST.md` (удалить после завершения)
- Create: `companies/CNRU/trend.json` (автогенерация)
- Modify: `_index.md` (обновить статус)

- [ ] Фаза 0: создать папку из шаблона, скопировать чеклист
- [ ] Фазы 1-6: полное исследование (онлайн-классифайд, рынок недвижимости, конкуренция с Авито/ДомКлик)
- [ ] Фаза 7: заполнить _index.md, обновить корневой _index.md
- [ ] Фаза 8: финальная проверка, удалить RESEARCH_CHECKLIST.md
- [ ] Сгенерировать trend.json
- [ ] Закоммитить и запушить

## Verification

- [ ] Все 10 компаний имеют заполненные _index.md с 23 полями в YAML и 10+ секциями
- [ ] Все trend.json сгенерированы и валидны
- [ ] Таблица статуса в корневом _index.md обновлена для всех 10 компаний
- [ ] Все RESEARCH_CHECKLIST.md удалены
- [ ] Финальный прогон `python3 scripts/generate_trend_json.py` без ошибок

## Post-completion

- [ ] Все изменения закоммичены и запушены
