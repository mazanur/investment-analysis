# Шаблон папки компании

Эта папка — эталон структуры для анализа компании. Скопируй её при создании новой компании.

## Быстрый старт

```bash
# Скопировать шаблон для новой компании
cp -r companies/_TEMPLATE companies/TICKER
# Заменить TICKER на реальный тикер во всех файлах

# Загрузить данные в API
curl -X POST "$API_URL/jobs/fetch-smartlab/TICKER" -H "X-API-Key: $API_KEY"
curl -X POST "$API_URL/jobs/fetch-moex?tickers=TICKER" -H "X-API-Key: $API_KEY"
curl -X POST "$API_URL/jobs/fetch-prices?tickers=TICKER" -H "X-API-Key: $API_KEY"
curl -X POST "$API_URL/jobs/fetch-events/TICKER" -H "X-API-Key: $API_KEY"
curl -X POST "$API_URL/jobs/fetch-ir-calendar" -H "X-API-Key: $API_KEY"
```

## Структура файлов

```
companies/{TICKER}/
├── _index.md          # Основной анализ (заполняет Claude)
├── financials.md      # Пометки о разовых статьях, корректировки
├── market_snapshot.md # Казначейские акции, привилегированные (заполняет ПОЛЬЗОВАТЕЛЬ)
├── consensus.md       # Прогнозы аналитиков (заполняет ПОЛЬЗОВАТЕЛЬ)
├── governance.md      # Корпоративное управление (СКРИПТ + ПОЛЬЗОВАТЕЛЬ)
├── events.md          # События и катализаторы (СКРИПТ + ПОЛЬЗОВАТЕЛЬ)
├── opinions.md        # Внешние мнения (автогенерация скриптом)
└── trend.json         # Вероятности для API (автогенерация скриптом)
```

> **Данные компании** (финансы, цены, новости, дивиденды, торговые сигналы) хранятся в **Investment API**, а не в локальных файлах. Доступ через `GET /companies/{TICKER}/...` endpoints.

## Кто что заполняет

| Файл / Данные | Кто | Источник |
|----------------|-----|----------|
| **Investment API** (финансы) | **Job** (`POST /jobs/fetch-smartlab/{TICKER}`) | smart-lab.ru |
| **Investment API** (рыночные данные) | **Job** (`POST /jobs/fetch-moex`) | MOEX ISS API |
| **Investment API** (дивиденды) | **Job** (`POST /jobs/fetch-events/{TICKER}`) | MOEX ISS API |
| **Investment API** (IR-календарь) | **Job** (`POST /jobs/fetch-ir-calendar`) | MOEX ISS API |
| **Investment API** (цены) | **Job** (`POST /jobs/fetch-prices`) | MOEX ISS API |
| **RSS Feeder** (новости, сигналы) | **Автопайплайн** | `http://feeder.zagirnur.dev/api/impact/articles?company={id}` |
| `consensus.md` | Пользователь | Прогнозы брокеров (за пейволлом) |
| `governance.md` | **Скрипт** + Пользователь (`make fill-governance`) | Авто: дивидендная история, санкции. Вручную: акционеры, менеджмент, buyback |
| `events.md` | **Скрипт** + Пользователь (`make events && make fill-events`) | Авто: IR-календарь из API. Вручную: guidance, IR-презентации |
| `market_snapshot.md` | Пользователь (опц.) | Только казначейские/преф. акции |
| `financials.md` | Пользователь (опц.) | Только пометки о разовых статьях |
| `_index.md` | **Claude** | Анализ на основе всех данных выше |
| `opinions.md` | **Скрипт** | Генерируется из Telegram-каналов |
| `trend.json` | **Скрипт** | Генерируется из _index.md |

## Что хранит API

### Финансовые отчёты (`GET /companies/{TICKER}/reports`)
- Выручка, EBITDA, ЧП, FCF, OCF, CAPEX
- Долг, чистый долг, Net Debt/EBITDA
- EPS, ROE, ROA, P/E, EV/EBITDA, P/BV
- Дивиденды на акцию, payout ratio
- Цена акции, капитализация, free-float, число акций
- Отраслевые метрики (добыча, число магазинов и т.д.)
- Источник: smart-lab.ru. Загрузка: `POST /jobs/fetch-smartlab/{TICKER}`

### Рыночные данные (`GET /companies/{TICKER}`)
- Текущая цена (current_price)
- Объём торгов (ADV за 30 дней — adv_rub_mln)
- Капитализация (market_cap) и число акций (shares_out)
- Free-float
- Источник: MOEX ISS API. Загрузка: `POST /jobs/fetch-moex`

### История цен (`GET /companies/{TICKER}/prices`)
- OHLCV дневные данные
- Источник: MOEX ISS API. Загрузка: `POST /jobs/fetch-prices`

### Дивиденды (`GET /companies/{TICKER}/dividends`)
- Дивидендная история и ближайшие выплаты
- Источник: MOEX ISS API. Загрузка: `POST /jobs/fetch-events/{TICKER}`

### IR-календарь (`GET /companies/{TICKER}/catalysts?type=event`)
- Публикации отчётности (РПБУ, МСФО), конференц-звонки, ГОСА, IR-события
- Источник: MOEX ISS API. Загрузка: `POST /jobs/fetch-ir-calendar`

## Новости и торговые реакции

Новости и impact-анализ доступны через RSS Feeder (`http://feeder.zagirnur.dev/`):
1. Найди company_id: `GET /api/companies` → по полю `ticker` (ID в feeder ≠ ID в investment API!)
2. Новости: `GET /api/impact/articles?company={feeder_id}`
3. Сигналы: `GET /api/signals/items?company={feeder_id}`

Реакции на новости записывай в `events.md` по инструкции из `NEWS_REACTION_GUIDE.md`.

**Как читать сигнал:**

| Поле | Что значит |
|------|-----------|
| `signal` | `buy` — есть спекулятивная возможность, `skip` — не торгуем |
| `direction` | `long-positive` — покупка на позитиве (рынок не отреагировал), `long-oversold` — покупка на панике |
| `confidence` | `high` → позиция до 5% портфеля, `medium` → до 3% |
| `entry.condition` | Условие входа: «По рынку» или «Лимитка на X ₽» |
| `entry.price` | Цена входа |
| `exit.take_profit` | Цена фиксации прибыли |
| `exit.stop_loss` | Цена стоп-лосса (обязателен!) |
| `exit.time_limit_days` | Максимальный срок удержания (торговых дней). По истечении — выход по рынку |
| `exit.exit_trigger` | Событие для выхода помимо цены (напр. «Публикация отчёта») |
| `risk_reward_ratio` | Соотношение доход/риск. Минимум 2.0 для buy-сигнала |
| `expected_return_pct` | Ожидаемая доходность (%) |
| `reasoning` | Обоснование решения |

**Что делать с сигналом:**

1. **buy** → проверь условия входа (`entry`), выставь стоп-лосс (`exit.stop_loss`) и тейк-профит (`exit.take_profit`). Следи за `exit_trigger` и `time_limit_days`
2. **skip** → не торгуем. В `reasoning` написано почему — используй для понимания ситуации

**Схема API:** `api/trade-signals-schema.yaml`

## Порядок работы

1. Пользователь копирует `_TEMPLATE` → `companies/TICKER`
2. Загрузить данные в API через job endpoints (см. «Быстрый старт»)
3. `make events TICKER=TICKER && make fill-events TICKER=TICKER` — загрузить события в API и сгенерировать events.md
4. `make fill-governance TICKER=TICKER` — сгенерировать governance.md (авто-секции)
5. По возможности заполняет ручные секции: `consensus.md`, `governance.md`, `events.md`
6. Просит Claude провести анализ
7. Claude читает данные из API и заполняет `_index.md`
8. `make sync TICKER=TICKER` — синхронизировать анализ в API
9. Скрипты генерируют `opinions.md` и `trend.json`

## Приоритет файлов для пользователя

| Приоритет | Файл | Без него |
|-----------|------|----------|
| **1 (желателен)** | `consensus.md` | Нет forward-оценки, только trailing |
| **2 (желателен)** | `governance.md` | Авто-часть через `make fill-governance`. Для точного GOD нужно заполнить акционеров и менеджмент вручную |
| **3 (желателен)** | `events.md` | Авто-часть через `make events && make fill-events`. Для катализаторов нужен guidance вручную |
| — | API данные | Загружаются через job endpoints |
| — | `market_snapshot.md` | Основные рыночные данные уже в API |
| — | `financials.md` | Только для пометок о разовых статьях |

## Минимальный набор для анализа

**Без заполнения пользователем** (только загрузка данных в API через job endpoints): Claude может провести полный trailing-анализ — финансы, мультипликаторы, ликвидность, текущая цена, upside. Не хватает forward-прогнозов, деталей корпоративного управления и катализаторов.

**С полным заполнением:** точная forward-оценка, корректный GOD-дисконт, понятные катализаторы, обоснованный position (buy vs watch).
