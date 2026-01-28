#!/usr/bin/env python3
"""
Скрипт для скачивания всех постов из публичного Telegram канала.
Использует веб-превью t.me/s/channel с пагинацией.
Без внешних зависимостей (только стандартная библиотека).

Использование:
    python3 telegram_scraper.py investopit output.json
"""

import urllib.request
import json
import time
import sys
import ssl
from html.parser import HTMLParser
from html import unescape
from datetime import datetime


class TelegramPostParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.posts = []
        self.current_post = {}
        self.in_message_text = False
        self.current_text = ""
        self.min_post_id = None

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        classes = attrs_dict.get('class', '')

        # Получаем ID поста из data-post
        if 'data-post' in attrs_dict:
            post_ref = attrs_dict['data-post']  # например "investopit/3100"
            if '/' in post_ref:
                post_id = int(post_ref.split('/')[-1])
                self.current_post['id'] = post_id
                if self.min_post_id is None or post_id < self.min_post_id:
                    self.min_post_id = post_id

        if 'tgme_widget_message_text' in classes:
            self.in_message_text = True
            self.current_text = ""
        elif tag == 'time' and 'datetime' in attrs_dict:
            self.current_post['datetime'] = attrs_dict['datetime']

    def handle_endtag(self, tag):
        if tag == 'div' and self.in_message_text:
            self.in_message_text = False
            if self.current_text.strip():
                self.current_post['text'] = unescape(self.current_text.strip())
                if self.current_post.get('id'):
                    self.posts.append(self.current_post.copy())
            self.current_post = {}

    def handle_data(self, data):
        if self.in_message_text:
            self.current_text += data


def fetch_posts(channel: str, before_id: int = None) -> tuple:
    """Загружает посты из канала. Возвращает (посты, min_id для пагинации)."""
    url = f"https://t.me/s/{channel}"
    if before_id:
        url += f"?before={before_id}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    # Создаём SSL context
    ctx = ssl.create_default_context()

    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            html = resp.read().decode('utf-8')
    except Exception as e:
        print(f"Ошибка загрузки: {e}", file=sys.stderr)
        return [], None

    parser = TelegramPostParser()
    parser.feed(html)

    return parser.posts, parser.min_post_id


def scrape_channel(channel: str, start_year: int = 2022, end_year: int = 2026) -> list:
    """Скачивает все посты канала за указанный период."""
    all_posts = {}
    before_id = None
    page = 0
    consecutive_empty = 0

    start_date = datetime(start_year, 1, 1)

    print(f"Скачиваю посты из @{channel} с {start_year} по {end_year}...")

    while True:
        page += 1
        print(f"  Страница {page}, before_id={before_id}...", end=" ", flush=True)

        posts, min_id = fetch_posts(channel, before_id)

        if not posts:
            consecutive_empty += 1
            print("пусто")
            if consecutive_empty >= 3:
                print("  3 пустые страницы подряд, завершаю")
                break
            if min_id and min_id != before_id:
                before_id = min_id
                time.sleep(1)
                continue
            else:
                break

        consecutive_empty = 0
        new_count = 0
        oldest_date = None

        for post in posts:
            post_id = post.get('id')
            if post_id and post_id not in all_posts:
                # Парсим дату
                dt_str = post.get('datetime', '')
                if dt_str:
                    try:
                        # Убираем timezone
                        dt_clean = dt_str.split('+')[0].split('Z')[0]
                        dt = datetime.fromisoformat(dt_clean)
                        post['date'] = dt.strftime('%Y-%m-%d')
                        post['year'] = dt.year

                        if oldest_date is None or dt < oldest_date:
                            oldest_date = dt

                        # Фильтруем по годам
                        if start_year <= dt.year <= end_year:
                            all_posts[post_id] = post
                            new_count += 1
                    except Exception as e:
                        # Если не удалось распарсить дату, всё равно сохраняем
                        all_posts[post_id] = post
                        new_count += 1

        print(f"найдено {len(posts)}, новых {new_count}, всего {len(all_posts)}", end="")
        if oldest_date:
            print(f", старейший: {oldest_date.strftime('%Y-%m-%d')}")
        else:
            print()

        # Проверяем, не вышли ли за пределы нужных дат
        if oldest_date and oldest_date < start_date:
            print(f"  Достигнут {oldest_date.year} год, завершаю")
            break

        # Пагинация
        if min_id and min_id != before_id:
            before_id = min_id
        else:
            print("  Нет больше страниц")
            break

        # Пауза между запросами
        time.sleep(1.5)

    # Сортируем по ID (новые первые)
    sorted_posts = sorted(all_posts.values(), key=lambda x: x.get('id', 0), reverse=True)

    return sorted_posts


def main():
    if len(sys.argv) < 2:
        print("Использование: python3 telegram_scraper.py <channel> [output.json]")
        print("Пример: python3 telegram_scraper.py investopit posts.json")
        sys.exit(1)

    channel = sys.argv[1].lstrip('@')
    output_file = sys.argv[2] if len(sys.argv) > 2 else f"{channel}_posts.json"

    posts = scrape_channel(channel, start_year=2022, end_year=2026)

    print(f"\nВсего собрано {len(posts)} постов")

    # Статистика по годам
    by_year = {}
    for p in posts:
        year = p.get('year', 'unknown')
        by_year[year] = by_year.get(year, 0) + 1

    print("По годам:")
    for year in sorted(by_year.keys(), key=lambda x: str(x)):
        print(f"  {year}: {by_year[year]} постов")

    # Сохраняем
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

    print(f"\nСохранено в {output_file}")


if __name__ == "__main__":
    main()