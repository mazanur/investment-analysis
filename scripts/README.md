# Скрипты для обновления данных

## Обзор

Скрипты для автоматического сбора и обработки данных из внешних источников.

```
scripts/
├── download_smartlab.py  # Загрузка финансовых CSV со smart-lab
├── telegram_scraper.py   # Скачивание постов из Telegram
├── filter_russia.py      # Фильтрация постов о России
├── generate_opinions.py  # Генерация opinions.md для компаний
├── generate_trend_json.py # Генерация trend.json
├── check_updates.py      # Проверка просроченных документов
├── validate_index.py     # Валидация _index.md
├── top_upside.py         # Топ компаний по upside
├── export_data.py        # Экспорт в JSON
├── generate_dashboard.py # GitHub Pages дашборд
└── README.md             # Эта инструкция
```

## Быстрый старт

```bash
# Полное обновление (все шаги)
cd /путь/к/investment-analysis
make download                      # скачать финансы со smart-lab
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
