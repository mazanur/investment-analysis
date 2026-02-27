# Скрипты для обновления данных

## Обзор

Скрипты для автоматического сбора и обработки данных из внешних источников.

```
scripts/
├── download_smartlab.py     # Загрузка финансовых CSV со smart-lab
├── download_moex.py         # Загрузка рыночных данных с MOEX ISS
├── download_moex_events.py  # Загрузка событий и дивидендов с MOEX ISS
├── download_governance.py   # Санкционный скрининг (OpenSanctions API)
├── fill_events.py           # Генерация events.md из скачанных данных
├── fill_governance.py       # Генерация governance.md из скачанных данных
├── telegram_scraper.py      # Скачивание постов из Telegram
├── filter_russia.py         # Фильтрация постов о России
├── generate_opinions.py     # Генерация opinions.md для компаний
├── generate_trend_json.py   # Генерация trend.json
├── generate_catalysts.py    # Генерация catalysts.json (катализаторы)
├── check_updates.py         # Проверка просроченных документов
├── validate_index.py        # Валидация _index.md
├── top_upside.py            # Топ компаний по upside
├── export_data.py           # Экспорт в JSON
├── generate_dashboard.py    # GitHub Pages дашборд
└── README.md                # Эта инструкция
```

## Быстрый старт

```bash
# Полное обновление (все шаги)
cd /путь/к/investment-analysis
make download-all                  # скачать финансы + рыночные + события + санкции
make fill-events                   # сгенерировать events.md
make fill-governance               # сгенерировать governance.md
make opinions                      # обновить мнения из Telegram
make trends                        # сгенерировать trend.json
make dashboard                     # обновить дашборд
```

## Подробное описание

### 0. download_smartlab.py

Загружает финансовые данные (МСФО) со smart-lab.ru в формате CSV.

```bash
python3 scripts/download_smartlab.py              # все компании
python3 scripts/download_smartlab.py SBER LKOH    # конкретные тикеры
python3 scripts/download_smartlab.py --force       # перезаписать (даже если скачано сегодня)
```

**Выходные данные:** `companies/{TICKER}/data/smartlab_yearly.csv`, `companies/{TICKER}/data/smartlab_quarterly.csv`

**Что делает:**
- Скачивает годовые МСФО: `https://smart-lab.ru/q/{TICKER}/f/y/MSFO/download/`
- Скачивает квартальные МСФО: `https://smart-lab.ru/q/{TICKER}/f/q/MSFO/download/`
- Пропускает делистингованные компании и `_TEMPLATE`
- Пропускает если файлы уже скачаны сегодня (без `--force`)
- Пауза 1.5 сек между запросами

**CSV-формат:** разделитель `;`, строки — финансовые показатели, столбцы — годы/кварталы. Содержит: выручку, EBITDA, ЧП, FCF, долг, EPS, ROE, P/E, EV/EBITDA, дивиденды, цену акции, капитализацию и др.

**Makefile:**
```bash
make download                  # все компании
make download TICKER=SBER      # одна компания
make download-force            # принудительно перезаписать
```

### 0.1. download_moex.py

Загружает рыночные данные с MOEX ISS API (публичный, без авторизации).

```bash
python3 scripts/download_moex.py              # все компании
python3 scripts/download_moex.py SBER LKOH    # конкретные тикеры
python3 scripts/download_moex.py --force       # перезаписать
```

**Выходные данные:** `companies/{TICKER}/data/moex_market.json`

**Что содержит JSON:**
- `price` — last, bid, offer, open, high, low, waprice, prev_close
- `volume` — объём торгов за день (штуки, рубли, число сделок)
- `liquidity` — ADV за 30 дней (рубли), bid-ask спред (%)
- `capitalization` — рыночная капитализация, число акций
- `range_52w` — 52-недельный high/low
- `listing` — board, list_level, lot_size

**Makefile:**
```bash
make download-moex             # все компании
make download-moex TICKER=SBER # одна компания
make download-all              # smart-lab + MOEX вместе
```

### 0.2. download_moex_events.py

Загружает события и дивиденды с MOEX ISS API.

```bash
python3 scripts/download_moex_events.py              # все компании
python3 scripts/download_moex_events.py SBER LKOH    # конкретные тикеры
python3 scripts/download_moex_events.py --force       # перезаписать
```

**Выходные данные:** `companies/{TICKER}/data/moex_events.json`

**Что содержит JSON:**
- `dividends` — история дивидендов (дата закрытия реестра, сумма, валюта)
- `ir_events` — IR-календарь (отчётность, конференц-звонки, ГОСА)

**Makefile:**
```bash
make download-events               # все компании
make download-events TICKER=SBER   # одна компания
```

### 0.3. download_governance.py

Загружает данные о санкциях из OpenSanctions API (бесплатно для некоммерческого использования).

```bash
python3 scripts/download_governance.py              # все компании
python3 scripts/download_governance.py SBER LKOH    # конкретные тикеры
python3 scripts/download_governance.py --force       # перезаписать
```

**Выходные данные:** `companies/{TICKER}/data/sanctions.json`

**Что содержит JSON:**
- `query` — запрос (имя компании)
- `results` — найденные совпадения (id, caption, schema, datasets, score)
- `relevant_matches` — число совпадений со score > 0.7
- `total` — общее число проверенных записей

**Что делает:**
- Берёт имя компании из `_index.md` (поле `name:`) или `moex_market.json`
- Ищет в OpenSanctions: `GET /search/default?q={name}&limit=10`
- Пропускает если уже обновлено сегодня (без `--force`)
- Пауза 1 сек между запросами

**Makefile:**
```bash
make download-governance               # все компании
make download-governance TICKER=SBER   # одна компания
make download-all                      # включает санкции
```

### 0.4. fill_events.py

Генерирует `events.md` из скачанных данных MOEX ISS.

```bash
python3 scripts/fill_events.py              # все компании
python3 scripts/fill_events.py SBER LKOH    # конкретные тикеры
```

**Входные данные:** `companies/{TICKER}/data/moex_events.json`
**Выходные данные:** `companies/{TICKER}/events.md`

**Что делает:**
- Формирует таблицу последних событий (6 месяцев) и предстоящих катализаторов
- Добавляет заседания ЦБ из `russia/macro.md`
- Сохраняет ручные секции (Guidance, IR-презентации, Санкционный статус)

**Makefile:**
```bash
make fill-events               # все компании
make fill-events TICKER=SBER   # одна компания
```

### 0.5. fill_governance.py

Генерирует `governance.md` из нескольких источников данных.

```bash
python3 scripts/fill_governance.py              # все компании
python3 scripts/fill_governance.py SBER LKOH    # конкретные тикеры
```

**Входные данные:**
- `companies/{TICKER}/data/moex_events.json` — дивиденды MOEX ISS
- `companies/{TICKER}/data/smartlab_yearly.csv` — payout ratio (опционально)
- `companies/{TICKER}/data/sanctions.json` — санкционный скрининг (опционально)

**Выходные данные:** `companies/{TICKER}/governance.md`

**Что делает:**
- Анализирует историю дивидендов: периодичность, стабильность, суммы по годам
- Читает payout ratio из smart-lab CSV (если скачан)
- Читает результаты санкционного скрининга (если скачан)
- Генерирует авто-секции: «Дивидендная история», «Санкционный скрининг»
- Сохраняет ручные секции: «Структура акционеров», «Дивидендная политика», «Buyback», «Менеджмент», «Риски», «GOD-дисконт»

**Makefile:**
```bash
make fill-governance               # все компании
make fill-governance TICKER=SBER   # одна компания
```

### 0.6. generate_catalysts.py

Генерирует `catalysts.json` с позитивными и негативными катализаторами.

```bash
python3 scripts/generate_catalysts.py              # все компании
python3 scripts/generate_catalysts.py SBER LKOH    # конкретные тикеры
```

**Входные данные:**
- `companies/{TICKER}/_index.md` — `key_risks` (негативные), `key_opportunities` (позитивные)
- `russia/macro.md` — даты заседаний ЦБ (макро-катализаторы для всех компаний)

**Выходные данные:** `companies/{TICKER}/data/catalysts.json`

**Что содержит JSON:**
- `catalysts[]` — массив катализаторов, каждый с полями:
  - `type`: `opportunity` | `risk` | `cb_meeting`
  - `impact`: `positive` | `negative` | `mixed`
  - `magnitude`: `high` | `medium` (эвристика по ключевым словам)
  - `date`: ISO-дата или `null`
  - `description`: текст катализатора
  - `source`: `index` | `macro`
- `summary` — статистика: total, positive, negative, mixed

**Makefile:**
```bash
make catalysts               # все компании
make catalysts TICKER=SBER   # одна компания
```

### 1. telegram_scraper.py

Скачивает все посты из публичного Telegram-канала через веб-превью.

```bash
python3 scripts/telegram_scraper.py <channel> [output.json]
```

**Параметры:**
- `channel` — имя канала без @ (например: `investopit`)
- `output.json` — файл для сохранения (по умолчанию: `{channel}_posts.json`)

**Пример:**
```bash
python3 scripts/telegram_scraper.py investopit investopit_posts.json
```

**Что делает:**
- Скачивает посты с 2022 по 2026 год
- Использует пагинацию для получения всей истории
- Сохраняет в JSON с полями: `id`, `date`, `datetime`, `text`, `year`

**Ограничения:**
- Работает только с публичными каналами
- Пауза 1.5 сек между запросами (защита от блокировки)
- Не требует авторизации

### 2. filter_russia.py

Фильтрует посты, относящиеся к российскому рынку.

```bash
python3 scripts/filter_russia.py
```

**Входные данные:** `investopit_posts.json`
**Выходные данные:** `sources/investopit_russia.md`

**Что делает:**
- Ищет упоминания российских компаний (тикеры + названия)
- Ищет ключевые слова: ЦБ, рубль, санкции, Мосбиржа и т.д.
- Группирует по компаниям
- Генерирует markdown с содержанием

### 3. generate_opinions.py

Генерирует `opinions.md` для каждой компании.

```bash
python3 scripts/generate_opinions.py
```

**Входные данные:** `investopit_posts.json`
**Выходные данные:** `companies/{TICKER}/opinions.md`

**Что делает:**
- Находит упоминания компаний в постах
- Создаёт папку `companies/{TICKER}/` если нет
- Генерирует `opinions.md` с постами
- Создаёт заглушки `_index.md` для новых компаний
- Извлекает целевые цены из текста

## Рекомендуемый график обновлений

| Частота | Когда | Действия |
|---------|-------|----------|
| Еженедельно | Воскресенье | Полное обновление (все 3 скрипта) |
| По событию | После важных новостей | telegram_scraper + generate_opinions |
| Ежеквартально | После отчётов | Полное обновление + ревью компаний |

## Добавление нового канала

1. Скачай посты:
```bash
python3 scripts/telegram_scraper.py новый_канал новый_канал_posts.json
```

2. Добавь обработку в `filter_russia.py` (опционально)

3. Добавь источник в `generate_opinions.py`:
   - Обнови маппинг тикеров
   - Добавь алиасы компаний

## Troubleshooting

### "Connection refused" или таймаут
- Telegram может блокировать частые запросы
- Увеличь паузу между запросами в `telegram_scraper.py` (параметр `time.sleep`)

### Не находит компании
- Проверь алиасы в `COMPANY_ALIASES` в `generate_opinions.py`
- Добавь новые варианты написания

### Дубликаты постов
- Скрипт использует `post_id` для дедупликации
- При повторном запуске перезаписывает файлы

## Структура данных

### investopit_posts.json
```json
[
  {
    "id": 3100,
    "datetime": "2026-01-28T10:00:00+00:00",
    "date": "2026-01-28",
    "year": 2026,
    "text": "Текст поста..."
  }
]
```

### opinions.md
```markdown
---
ticker: SBER
company: Сбер
generated: 2026-01-28
source: '@investopit'
---

# Внешние мнения: Сбер (SBER)

## 2026-01-28
[Источник](https://t.me/investopit/3100)

**Целевая цена:** 300 RUB

> Текст поста...
```

## Зависимости

Только стандартная библиотека Python 3.x:
- `urllib.request`
- `json`
- `re`
- `html.parser`

Внешние зависимости не требуются.
