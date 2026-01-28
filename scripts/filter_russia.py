#!/usr/bin/env python3
"""
Фильтрует посты о российских компаниях и рынке.
Группирует по компаниям и сохраняет в markdown.
"""

import json
import re
from collections import defaultdict
from datetime import datetime

# Российские тикеры и названия компаний
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
    'TCSG': 'Т-Банк (Тинькофф)',
    'MOEX': 'Мосбиржа',
    'AFKS': 'АФК Система',

    # Телеком и IT
    'MTSS': 'МТС',
    'YNDX': 'Яндекс',
    'VKCO': 'VK',
    'OZON': 'Озон',
    'HHRU': 'HeadHunter',
    'CIAN': 'Циан',
    'POSI': 'Positive Technologies',

    # Ритейл
    'MGNT': 'Магнит',
    'FIVE': 'X5 Group',
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

    # Строительство и девелопмент
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

# Альтернативные названия (для поиска в тексте)
COMPANY_ALIASES = {
    'Газпром': ['газпром', 'gazprom'],
    'Лукойл': ['лукойл', 'lukoil'],
    'Сбер': ['сбер', 'сбербанк', 'sber', 'sberbank'],
    'Норникель': ['норникель', 'норильский никель', 'norilsk', 'gmkn'],
    'Яндекс': ['яндекс', 'yandex'],
    'Роснефть': ['роснефть', 'rosneft'],
    'Новатэк': ['новатэк', 'novatek'],
    'Татнефть': ['татнефть', 'tatneft'],
    'Северсталь': ['северсталь', 'severstal'],
    'НЛМК': ['нлмк', 'nlmk'],
    'ММК': ['ммк', 'mmk', 'магнитогорский'],
    'Алроса': ['алроса', 'alrosa'],
    'Полюс': ['полюс', 'polyus'],
    'Polymetal': ['polymetal', 'полиметалл'],
    'Русал': ['русал', 'rusal'],
    'ВТБ': ['втб', 'vtb'],
    'Т-Банк (Тинькофф)': ['тинькофф', 'т-банк', 'tinkoff', 't-bank', 'т-брокер', 'tcsg'],
    'Мосбиржа': ['мосбиржа', 'московская биржа', 'moex'],
    'МТС': ['мтс', 'mts'],
    'VK': ['вк ', 'vk ', 'вконтакте', 'vkontakte'],
    'Озон': ['озон', 'ozon'],
    'Магнит': ['магнит'],
    'X5 Group': ['x5', 'пятёрочка', 'пятерочка', 'перекрёсток', 'перекресток'],
    'Аэрофлот': ['аэрофлот', 'aeroflot'],
    'Интер РАО': ['интер рао', 'inter rao'],
    'РусГидро': ['русгидро', 'rushydro'],
    'ФосАгро': ['фосагро', 'phosagro'],
    'Акрон': ['акрон', 'akron'],
    'ПИК': ['пик ', 'pik '],
    'Самолёт': ['самолёт', 'самолет'],
    'Ростелеком': ['ростелеком', 'rostelecom'],
    'М.Видео': ['м.видео', 'мвидео', 'mvideo'],
    'АФК Система': ['афк система', 'sistema'],
    'Сургутнефтегаз': ['сургутнефтегаз', 'сургут', 'surgutneftegas'],
    'Газпром нефть': ['газпром нефть', 'газпромнефть'],
    'HeadHunter': ['headhunter', 'hh.ru', 'хедхантер'],
    'Positive Technologies': ['позитив', 'positive', 'posi'],
    'Fix Price': ['fix price', 'фикс прайс'],
    'Совкомфлот': ['совкомфлот', 'sovcomflot'],
    'Сегежа': ['сегежа', 'segezha'],
}

# Ключевые слова для общих постов о рынке РФ
RUSSIA_KEYWORDS = [
    'рынок рф', 'рынке рф', 'российский рынок', 'российском рынке',
    'цб рф', 'центробанк', 'банк россии',
    'ключевая ставка', 'ставка цб',
    'рубль', 'рубля', 'рублей', 'рублю',
    'санкции', 'санкций',
    'мосбиржа', 'московская биржа', 'moex',
    'индекс мосбиржи', 'imoex',
    'россия', 'российск',
]


def find_companies_in_text(text: str) -> list:
    """Находит упоминания российских компаний в тексте."""
    text_lower = text.lower()
    found = set()

    # Поиск по тикерам (в формате #TICKER или просто TICKER)
    for ticker, name in RUSSIAN_TICKERS.items():
        pattern = rf'#?{ticker}\b'
        if re.search(pattern, text, re.IGNORECASE):
            found.add(name)

    # Поиск по алиасам
    for company, aliases in COMPANY_ALIASES.items():
        for alias in aliases:
            if alias in text_lower:
                found.add(company)
                break

    return list(found)


def is_russia_related(text: str) -> bool:
    """Проверяет, относится ли пост к российскому рынку."""
    text_lower = text.lower()

    # Проверяем ключевые слова
    for kw in RUSSIA_KEYWORDS:
        if kw in text_lower:
            return True

    # Проверяем упоминания компаний
    if find_companies_in_text(text):
        return True

    return False


def main():
    # Читаем посты
    with open('investopit_posts.json', 'r', encoding='utf-8') as f:
        posts = json.load(f)

    print(f"Всего постов: {len(posts)}")

    # Фильтруем и группируем
    by_company = defaultdict(list)
    general_russia = []

    for post in posts:
        text = post.get('text', '')
        if not text:
            continue

        companies = find_companies_in_text(text)

        if companies:
            for company in companies:
                by_company[company].append(post)
        elif is_russia_related(text):
            general_russia.append(post)

    # Статистика
    total_russia = sum(len(posts) for posts in by_company.values()) + len(general_russia)
    print(f"Постов о России: {total_russia}")
    print(f"Компаний найдено: {len(by_company)}")

    # Сортируем компании по количеству упоминаний
    sorted_companies = sorted(by_company.items(), key=lambda x: len(x[1]), reverse=True)

    # Генерируем markdown
    md_lines = [
        "---",
        "source: '@investopit'",
        f"generated: {datetime.now().strftime('%Y-%m-%d')}",
        "topic: Посты о российских компаниях",
        "---",
        "",
        "# Telegram @investopit — российские компании (2022-2026)",
        "",
        "## Содержание",
        "",
    ]

    # TOC
    for company, company_posts in sorted_companies:
        count = len(company_posts)
        anchor = company.lower().replace(' ', '-').replace('(', '').replace(')', '')
        md_lines.append(f"- [{company}](#{anchor}) ({count} постов)")

    if general_russia:
        md_lines.append(f"- [Общее о рынке РФ](#общее-о-рынке-рф) ({len(general_russia)} постов)")

    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")

    # Посты по компаниям
    for company, company_posts in sorted_companies:
        md_lines.append(f"## {company}")
        md_lines.append("")

        # Сортируем по дате (новые первые)
        company_posts_sorted = sorted(company_posts, key=lambda x: x.get('date', ''), reverse=True)

        for post in company_posts_sorted:
            date = post.get('date', 'N/A')
            text = post.get('text', '').strip()
            post_id = post.get('id', '')

            md_lines.append(f"### {date}")
            if post_id:
                md_lines.append(f"[Ссылка на пост](https://t.me/investopit/{post_id})")
            md_lines.append("")
            md_lines.append(f"> {text}")
            md_lines.append("")
            md_lines.append("---")
            md_lines.append("")

    # Общие посты о рынке РФ
    if general_russia:
        md_lines.append("## Общее о рынке РФ")
        md_lines.append("")

        general_sorted = sorted(general_russia, key=lambda x: x.get('date', ''), reverse=True)

        for post in general_sorted:
            date = post.get('date', 'N/A')
            text = post.get('text', '').strip()
            post_id = post.get('id', '')

            md_lines.append(f"### {date}")
            if post_id:
                md_lines.append(f"[Ссылка на пост](https://t.me/investopit/{post_id})")
            md_lines.append("")
            md_lines.append(f"> {text}")
            md_lines.append("")
            md_lines.append("---")
            md_lines.append("")

    # Сохраняем
    output_file = 'sources/investopit_russia.md'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_lines))

    print(f"\nСохранено в {output_file}")

    # Выводим топ компаний
    print("\nТоп-20 компаний по упоминаниям:")
    for company, company_posts in sorted_companies[:20]:
        print(f"  {company}: {len(company_posts)} постов")


if __name__ == "__main__":
    main()
