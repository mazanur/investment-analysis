#!/usr/bin/env python3
"""
Генерирует opinions.md для каждой компании из собранных постов.
Создаёт папки компаний если их нет.

Использование:
    python3 scripts/generate_opinions.py
"""

import json
import os
import re
from collections import defaultdict
from datetime import datetime
from html import unescape

# Базовые пути
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPANIES_DIR = os.path.join(BASE_DIR, 'companies')
POSTS_FILE = os.path.join(BASE_DIR, 'investopit_posts.json')

# Маппинг тикеров на названия компаний
RUSSIAN_TICKERS = {
    # Нефть и газ
    'GAZP': 'Газпром',
    'LKOH': 'Лукойл',
    'ROSN': 'Роснефть',
    'NVTK': 'Новатэк',
    'TATN': 'Татнефть',
    'SNGS': 'Сургутнефтегаз',
    'SIBN': 'Газпром нефть',
    'BANEP': 'Башнефть',

    # Металлы и добыча
    'GMKN': 'Норникель',
    'NLMK': 'НЛМК',
    'CHMF': 'Северсталь',
    'MAGN': 'ММК',
    'ALRS': 'Алроса',
    'PLZL': 'Полюс',
    'POLY': 'Polymetal',
    'RUAL': 'Русал',

    # Банки и финансы
    'SBER': 'Сбер',
    'VTBR': 'ВТБ',
    'TCSG': 'Т-Банк',
    'MOEX': 'Мосбиржа',
    'AFKS': 'АФК Система',

    # Телеком и IT
    'MTSS': 'МТС',
    'YNDX': 'Яндекс',
    'YDEX': 'Яндекс',
    'VKCO': 'VK',
    'OZON': 'Озон',
    'HHRU': 'HeadHunter',
    'CIAN': 'Циан',
    'POSI': 'Positive Technologies',

    # Ритейл
    'MGNT': 'Магнит',
    'FIVE': 'X5',
    'X5': 'X5',
    'FIXP': 'Fix Price',
    'LENT': 'Лента',
    'DSKY': 'Детский мир',

    # Транспорт
    'AFLT': 'Аэрофлот',
    'FLOT': 'Совкомфлот',
    'NMTP': 'НМТП',
    'FESH': 'ДВМП',

    # Энергетика
    'IRAO': 'Интер РАО',
    'HYDR': 'РусГидро',
    'FEES': 'ФСК ЕЭС',
    'UPRO': 'Юнипро',
    'OGKB': 'ОГК-2',
    'MSNG': 'Мосэнерго',

    # Удобрения
    'PHOR': 'ФосАгро',
    'AKRN': 'Акрон',

    # Строительство
    'PIKK': 'ПИК',
    'LSRG': 'Группа ЛСР',
    'SMLT': 'Самолёт',
    'ETLN': 'Эталон',

    # Прочее
    'RTKM': 'Ростелеком',
    'SGZH': 'Сегежа',
    'MVID': 'М.Видео',
    'CBOM': 'МКБ',
    'BSPB': 'Банк СПб',
}

# Обратный маппинг: название → тикер
NAME_TO_TICKER = {}
for ticker, name in RUSSIAN_TICKERS.items():
    NAME_TO_TICKER[name.lower()] = ticker

# Алиасы для поиска в тексте
COMPANY_ALIASES = {
    'GAZP': ['газпром', 'gazprom', '#gazp'],
    'LKOH': ['лукойл', 'lukoil', '#lkoh'],
    'SBER': ['сбер', 'сбербанк', 'sber', 'sberbank', '#sber'],
    'GMKN': ['норникель', 'норильский никель', 'norilsk', '#gmkn'],
    'YNDX': ['яндекс', 'yandex', '#yndx', '#ydex'],
    'YDEX': ['яндекс', 'yandex', '#yndx', '#ydex'],
    'ROSN': ['роснефть', 'rosneft', '#rosn'],
    'NVTK': ['новатэк', 'novatek', '#nvtk'],
    'TATN': ['татнефть', 'tatneft', '#tatn'],
    'CHMF': ['северсталь', 'severstal', '#chmf'],
    'NLMK': ['нлмк', '#nlmk'],
    'MAGN': ['ммк', 'магнитогорский', '#magn'],
    'ALRS': ['алроса', 'alrosa', '#alrs'],
    'PLZL': ['полюс', 'polyus', '#plzl'],
    'POLY': ['polymetal', 'полиметалл', '#poly'],
    'RUAL': ['русал', 'rusal', '#rual'],
    'VTBR': ['втб', 'vtb', '#vtbr'],
    'TCSG': ['тинькофф', 'т-банк', 'tinkoff', 't-bank', 'т-брокер', '#tcsg'],
    'MOEX': ['мосбиржа', 'московская биржа', '#moex'],
    'MTSS': ['мтс', '#mtss'],
    'VKCO': ['vk', 'вконтакте', '#vkco'],
    'OZON': ['озон', '#ozon'],
    'MGNT': ['магнит', '#mgnt'],
    'FIVE': ['x5', 'пятёрочка', 'пятерочка', 'перекрёсток', '#five'],
    'X5': ['x5', 'пятёрочка', 'пятерочка', 'перекрёсток', '#five'],
    'AFLT': ['аэрофлот', 'aeroflot', '#aflt'],
    'IRAO': ['интер рао', 'inter rao', '#irao'],
    'HYDR': ['русгидро', 'rushydro', '#hydr'],
    'PHOR': ['фосагро', 'phosagro', '#phor'],
    'AKRN': ['акрон', '#akrn'],
    'PIKK': ['пик', '#pikk'],
    'SMLT': ['самолёт', 'самолет', '#smlt'],
    'RTKM': ['ростелеком', 'rostelecom', '#rtkm'],
    'MVID': ['м.видео', 'мвидео', '#mvid'],
    'AFKS': ['афк система', 'sistema', '#afks'],
    'SNGS': ['сургутнефтегаз', 'сургут', '#sngs'],
    'SIBN': ['газпром нефть', 'газпромнефть', '#sibn'],
    'HHRU': ['headhunter', 'hh.ru', '#hhru'],
    'POSI': ['позитив', 'positive', '#posi'],
    'FIXP': ['fix price', 'фикс прайс', '#fixp'],
    'FLOT': ['совкомфлот', '#flot'],
    'SGZH': ['сегежа', 'segezha', '#sgzh'],
    'LENT': ['лента', '#lent'],
}


def find_tickers_in_text(text: str) -> set:
    """Находит тикеры российских компаний в тексте."""
    text_lower = text.lower()
    found = set()

    # Поиск по тикерам (в формате #TICKER)
    for ticker in RUSSIAN_TICKERS.keys():
        pattern = rf'#?{ticker}\b'
        if re.search(pattern, text, re.IGNORECASE):
            found.add(ticker)

    # Поиск по алиасам
    for ticker, aliases in COMPANY_ALIASES.items():
        for alias in aliases:
            if alias in text_lower:
                found.add(ticker)
                break

    return found


def extract_price_targets(text: str) -> list:
    """Извлекает целевые цены из текста."""
    targets = []

    # Паттерны для целевых цен
    patterns = [
        r'оценка справедливой стоимости[:\s\-–]+(\d+[\d\s]*)\s*(дол|руб|\$|₽)?',
        r'справедливая стоимость[:\s\-–]+(\d+[\d\s]*)\s*(дол|руб|\$|₽)?',
        r'оценка[:\s\-–]+(\d+[\d\s]*)\s*(дол|руб|\$|₽)?',
        r'целевая цена[:\s\-–]+(\d+[\d\s]*)\s*(дол|руб|\$|₽)?',
    ]

    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            price = match.group(1).replace(' ', '')
            currency = match.group(2) if match.lastindex >= 2 else None
            if currency:
                currency = 'USD' if currency in ['дол', '$'] else 'RUB'
            targets.append({'price': price, 'currency': currency})

    return targets


def generate_opinions_md(ticker: str, posts: list) -> str:
    """Генерирует содержимое opinions.md для компании."""
    company_name = RUSSIAN_TICKERS.get(ticker, ticker)

    lines = [
        "---",
        f"ticker: {ticker}",
        f"company: {company_name}",
        f"generated: {datetime.now().strftime('%Y-%m-%d')}",
        "source: '@investopit'",
        "---",
        "",
        f"# Внешние мнения: {company_name} ({ticker})",
        "",
        f"Агрегированные мнения из Telegram-канала [@investopit](https://t.me/investopit).",
        "",
        f"**Всего упоминаний:** {len(posts)}",
        "",
        "---",
        "",
    ]

    # Сортируем посты по дате (новые первые)
    sorted_posts = sorted(posts, key=lambda x: x.get('date', ''), reverse=True)

    for post in sorted_posts:
        date = post.get('date', 'N/A')
        text = post.get('text', '').strip()
        post_id = post.get('id', '')

        # Извлекаем целевые цены
        targets = extract_price_targets(text)

        lines.append(f"## {date}")
        if post_id:
            lines.append(f"[Источник](https://t.me/investopit/{post_id})")
        lines.append("")

        # Если есть целевые цены, выделяем их
        if targets:
            for t in targets:
                currency = t.get('currency', '')
                lines.append(f"**Целевая цена:** {t['price']} {currency}")
            lines.append("")

        lines.append(f"> {text}")
        lines.append("")
        lines.append("---")
        lines.append("")

    return '\n'.join(lines)


def main():
    # Читаем посты
    if not os.path.exists(POSTS_FILE):
        print(f"Файл {POSTS_FILE} не найден. Сначала запусти telegram_scraper.py")
        return

    with open(POSTS_FILE, 'r', encoding='utf-8') as f:
        posts = json.load(f)

    print(f"Загружено {len(posts)} постов")

    # Группируем посты по тикерам
    by_ticker = defaultdict(list)

    for post in posts:
        text = post.get('text', '')
        if not text:
            continue

        tickers = find_tickers_in_text(text)
        for ticker in tickers:
            by_ticker[ticker].append(post)

    print(f"Найдено {len(by_ticker)} компаний с упоминаниями")

    # Генерируем opinions.md для каждой компании
    generated = 0
    for ticker, ticker_posts in by_ticker.items():
        # Создаём папку если нет
        company_dir = os.path.join(COMPANIES_DIR, ticker)
        os.makedirs(company_dir, exist_ok=True)

        # Генерируем opinions.md
        content = generate_opinions_md(ticker, ticker_posts)
        opinions_file = os.path.join(company_dir, 'opinions.md')

        with open(opinions_file, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"  {ticker}: {len(ticker_posts)} постов → {opinions_file}")
        generated += 1

    print(f"\nСгенерировано {generated} файлов opinions.md")

    # Создаём заглушки _index.md для новых компаний
    created_stubs = 0
    for ticker in by_ticker.keys():
        index_file = os.path.join(COMPANIES_DIR, ticker, '_index.md')
        if not os.path.exists(index_file):
            company_name = RUSSIAN_TICKERS.get(ticker, ticker)
            stub = f"""---
ticker: {ticker}
company: {company_name}
sector:
sentiment:
position: watch
updated: {datetime.now().strftime('%Y-%m-%d')}
---

# {company_name} ({ticker})

> Заглушка. Требуется исследование.

## Бизнес-модель

<!-- Описание бизнеса -->

## Финансовые показатели

| Показатель | Значение |
|------------|----------|
| Капитализация | |
| P/E | |
| EV/EBITDA | |
| Див. доходность | |

## Инвестиционный тезис

<!-- Почему интересна / не интересна -->

## Риски

-

## Источники

- [Smart-lab](https://smart-lab.ru/q/{ticker}/)
- [Внешние мнения](opinions.md)
"""
            with open(index_file, 'w', encoding='utf-8') as f:
                f.write(stub)
            created_stubs += 1
            print(f"  Создана заглушка: {ticker}/_index.md")

    if created_stubs:
        print(f"\nСоздано {created_stubs} заглушек _index.md")


if __name__ == "__main__":
    main()
