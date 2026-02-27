#!/usr/bin/env python3
"""
Проверяет _index.md и находит просроченные документы.

Использование:
    python3 scripts/check_updates.py

Автор: AlmazNurmukhametov
"""

import os
import re
from datetime import datetime, date

# Цвета для терминала
RED = '\033[0;31m'
YELLOW = '\033[0;33m'
GREEN = '\033[0;32m'
CYAN = '\033[0;36m'
NC = '\033[0m'  # No Color


def parse_index_table(content: str) -> list:
    """
    Парсит таблицу статуса из _index.md.
    Возвращает список словарей с полями: document, status, updated, next_update
    """
    results = []

    # Ищем строки таблицы после "Статус обновлений"
    in_table = False
    for line in content.split('\n'):
        if 'Статус обновлений' in line:
            in_table = True
            continue

        if not in_table:
            continue

        # Пропускаем заголовок и разделитель
        if line.startswith('| Документ') or line.startswith('|---'):
            continue

        # Пропускаем секции (жирный текст без данных)
        if '| **' in line and line.count('|') <= 3:
            continue

        # Парсим строку таблицы
        if line.startswith('|'):
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 5:
                doc = parts[1].strip()
                status = parts[2].strip()
                updated = parts[3].strip()
                next_update = parts[4].strip()

                if doc and status:
                    results.append({
                        'document': doc,
                        'status': status,
                        'updated': updated,
                        'next_update': next_update
                    })

    return results


def check_overdue(documents: list, today: date) -> dict:
    """
    Проверяет документы на просроченность.
    Возвращает словарь с категориями: overdue, due_soon, stubs, ok
    """
    result = {
        'overdue': [],      # Просрочены
        'due_soon': [],     # В ближайшие 7 дней
        'stubs': [],        # Заглушки без даты
        'ok': []            # Всё хорошо
    }

    for doc in documents:
        next_update = doc['next_update']
        status = doc['status']

        # Заглушки
        if status == 'заглушка' or next_update in ('—', '-', '', 'заполнить'):
            result['stubs'].append(doc)
            continue

        # Парсим дату
        try:
            next_date = datetime.strptime(next_update, '%Y-%m-%d').date()
        except ValueError:
            # Не удалось распарсить дату
            result['stubs'].append(doc)
            continue

        days_until = (next_date - today).days

        if days_until < 0:
            doc['days_overdue'] = abs(days_until)
            result['overdue'].append(doc)
        elif days_until <= 7:
            doc['days_until'] = days_until
            result['due_soon'].append(doc)
        else:
            result['ok'].append(doc)

    return result


def find_stub_companies(companies_dir: str) -> list:
    """
    Находит компании-заглушки (без sentiment в _index.md).
    """
    stubs = []

    for company in sorted(os.listdir(companies_dir)):
        company_path = os.path.join(companies_dir, company)
        if not os.path.isdir(company_path):
            continue
        if company.startswith('_') or company.startswith('.'):
            continue

        index_file = os.path.join(company_path, '_index.md')
        if not os.path.exists(index_file):
            stubs.append(company)
            continue

        with open(index_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Проверяем наличие sentiment в YAML
        if not re.search(r'^sentiment:\s*(bullish|neutral|bearish)', content, re.MULTILINE):
            stubs.append(company)

    return stubs


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)
    index_file = os.path.join(base_dir, '_index.md')
    companies_dir = os.path.join(base_dir, 'companies')

    today = date.today()

    # Читаем _index.md
    if not os.path.exists(index_file):
        print(f"{RED}Ошибка: _index.md не найден{NC}")
        return 1

    with open(index_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Парсим таблицу
    documents = parse_index_table(content)

    if not documents:
        print(f"{YELLOW}Таблица статуса не найдена в _index.md{NC}")
        return 1

    # Проверяем просроченность
    checks = check_overdue(documents, today)

    # Находим компании-заглушки
    stub_companies = find_stub_companies(companies_dir)

    # Выводим результаты

    # 1. Просроченные
    if checks['overdue']:
        print(f"{RED}⚠️  ПРОСРОЧЕНЫ ({len(checks['overdue'])}){NC}")
        print()
        for doc in sorted(checks['overdue'], key=lambda x: x['days_overdue'], reverse=True):
            print(f"  {RED}•{NC} {doc['document']}")
            print(f"    Должен был обновиться: {doc['next_update']} ({doc['days_overdue']} дн. назад)")
        print()

    # 2. Скоро нужно обновить
    if checks['due_soon']:
        print(f"{YELLOW}📅 ОБНОВИТЬ В БЛИЖАЙШИЕ 7 ДНЕЙ ({len(checks['due_soon'])}){NC}")
        print()
        for doc in sorted(checks['due_soon'], key=lambda x: x['days_until']):
            days = doc['days_until']
            when = 'сегодня' if days == 0 else f'через {days} дн.'
            print(f"  {YELLOW}•{NC} {doc['document']}")
            print(f"    След. обновление: {doc['next_update']} ({when})")
        print()

    # 3. Компании-заглушки
    if stub_companies:
        print(f"{CYAN}📝 КОМПАНИИ-ЗАГЛУШКИ ({len(stub_companies)}){NC}")
        print()
        # Показываем первые 10
        for company in stub_companies[:10]:
            print(f"  {CYAN}•{NC} {company}")
        if len(stub_companies) > 10:
            print(f"  ... и ещё {len(stub_companies) - 10}")
        print()
        print(f"  Запусти {GREEN}make next{NC} чтобы заполнить следующую")
        print()

    # 4. Итог
    total_ok = len(checks['ok'])
    total_problems = len(checks['overdue']) + len(checks['due_soon'])

    if total_problems == 0 and not stub_companies:
        print(f"{GREEN}✅ Всё актуально! ({total_ok} документов в порядке){NC}")
    else:
        print(f"Итого: {GREEN}{total_ok} в порядке{NC}, ", end='')
        if checks['overdue']:
            print(f"{RED}{len(checks['overdue'])} просрочено{NC}, ", end='')
        if checks['due_soon']:
            print(f"{YELLOW}{len(checks['due_soon'])} скоро обновить{NC}, ", end='')
        if stub_companies:
            print(f"{CYAN}{len(stub_companies)} заглушек{NC}", end='')
        print()

    return 0


if __name__ == '__main__':
    exit(main())
