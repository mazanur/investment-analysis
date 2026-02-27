# Шаблон папки компании

Эта папка — эталон структуры для анализа компании. Скопируй её при создании новой компании.

## Быстрый старт

```bash
# Скопировать шаблон для новой компании
cp -r companies/_TEMPLATE companies/TICKER
# Заменить TICKER на реальный тикер во всех файлах

# Скачать все данные (smart-lab финансы + MOEX рыночные)
make download-all TICKER=TICKER
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
├── data/              # Автоматически скачиваемые данные
│   ├── smartlab_yearly.csv     # Годовые МСФО (smart-lab)
│   ├── smartlab_quarterly.csv  # Квартальные МСФО (smart-lab)
│   ├── moex_market.json        # Цена, объём, ADV, спред (MOEX ISS)
│   ├── moex_events.json        # Дивиденды, IR-календарь (MOEX ISS)
│   └── sanctions.json          # Санкционный скрининг (OpenSanctions)
├── opinions.md        # Внешние мнения (автогенерация скриптом)
└── trend.json         # Вероятности для API (автогенерация скриптом)
```

## Кто что заполняет

| Файл | Кто | Источник |
|------|-----|----------|
| `data/smartlab_*.csv` | **Скрипт** (`make download`) | smart-lab.ru CSV |
| `data/moex_market.json` | **Скрипт** (`make download-moex`) | MOEX ISS API |
| `data/moex_events.json` | **Скрипт** (`make download-events`) | MOEX ISS API |
| `data/sanctions.json` | **Скрипт** (`make download-governance`) | OpenSanctions API |
| `consensus.md` | Пользователь | Прогнозы брокеров (за пейволлом) |
| `governance.md` | **Скрипт** + Пользователь (`make fill-governance`) | Авто: дивидендная история, санкции. Вручную: акционеры, менеджмент, buyback |
| `events.md` | **Скрипт** + Пользователь (`make fill-events`) | Авто: события MOEX. Вручную: guidance, IR-презентации |
| `market_snapshot.md` | Пользователь (опц.) | Только казначейские/преф. акции |
| `financials.md` | Пользователь (опц.) | Только пометки о разовых статьях |
| `_index.md` | **Claude** | Анализ на основе всех данных выше |
| `opinions.md` | **Скрипт** | Генерируется из Telegram-каналов |
| `trend.json` | **Скрипт** | Генерируется из _index.md |

## Что скачивается автоматически

### Smart-lab CSV (`make download`)
- Выручка, EBITDA, ЧП, FCF, OCF, CAPEX
- Долг, чистый долг, Net Debt/EBITDA
- EPS, ROE, ROA, P/E, EV/EBITDA, P/BV
- Дивиденды на акцию, payout ratio
- Цена акции, капитализация, free-float, число акций
- Отраслевые метрики (добыча, число магазинов и т.д.)

### MOEX ISS API (`make download-moex`)
- Текущая цена (last, bid, offer)
- Объём торгов (сегодня + ADV за 30 дней)
- Bid-ask спред (%)
- Капитализация и число акций
- 52-недельный диапазон (high/low)
- Уровень листинга

## Порядок работы

1. Пользователь копирует `_TEMPLATE` → `companies/TICKER`
2. `make download-all TICKER=TICKER` — скачать финансы + рыночные данные + санкции
3. `make fill-events TICKER=TICKER` — сгенерировать events.md (авто-секции)
4. `make fill-governance TICKER=TICKER` — сгенерировать governance.md (авто-секции)
5. По возможности заполняет ручные секции: `consensus.md`, `governance.md`, `events.md`
6. Просит Claude провести анализ
7. Claude читает данные из `data/` и заполняет `_index.md`
8. Скрипты генерируют `opinions.md` и `trend.json`

## Приоритет файлов для пользователя

| Приоритет | Файл | Без него |
|-----------|------|----------|
| **1 (желателен)** | `consensus.md` | Нет forward-оценки, только trailing |
| **2 (желателен)** | `governance.md` | Авто-часть через `make fill-governance`. Для точного GOD нужно заполнить акционеров и менеджмент вручную |
| **3 (желателен)** | `events.md` | Авто-часть через `make fill-events`. Для катализаторов нужен guidance вручную |
| — | `data/` | Скачивается через `make download-all` |
| — | `market_snapshot.md` | Основное уже в moex_market.json |
| — | `financials.md` | Только для пометок о разовых статьях |

## Минимальный набор для анализа

**Без заполнения пользователем** (только `make download-all`): Claude может провести полный trailing-анализ — финансы, мультипликаторы, ликвидность, текущая цена, upside. Не хватает forward-прогнозов, деталей корпоративного управления и катализаторов.

**С полным заполнением:** точная forward-оценка, корректный GOD-дисконт, понятные катализаторы, обоснованный position (buy vs watch).
