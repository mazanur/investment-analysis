#!/usr/bin/env python3
"""
Показывает топ-10 компаний по upside.

Использование:
    python3 scripts/top_upside.py

Автор: AlmazNurmukhametov
"""

import os
import re

# Цвета
GREEN = '\033[0;32m'
YELLOW = '\033[0;33m'
RED = '\033[0;31m'
CYAN = '\033[0;36m'
NC = '\033[0m'


def parse_yaml_value(content: str, key: str) -> str:
    """Извлекает значение из YAML frontmatter."""
    match = re.search(rf'^{key}:\s*(.+)$', content, re.MULTILINE)
    return match.group(1).strip() if match else ''


def parse_upside(value: str) -> float:
    """Парсит upside в число."""
    if not value:
        return 0.0
    cleaned = value.replace('%', '').strip()
    try:
        num = float(cleaned)
        # Если > 1, это проценты
        if abs(num) > 1:
            return num
        return num * 100
    except ValueError:
        return 0.0


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    companies_dir = os.path.join(os.path.dirname(script_dir), 'companies')

    companies = []

    for company in os.listdir(companies_dir):
        company_path = os.path.join(companies_dir, company)
        if not os.path.isdir(company_path):
            continue
        if company.startswith('_') or company.startswith('.'):
            continue

        index_file = os.path.join(company_path, '_index.md')
        if not os.path.exists(index_file):
            continue

        with open(index_file, 'r', encoding='utf-8') as f:
            content = f.read()

        ticker = parse_yaml_value(content, 'ticker') or company
        sentiment = parse_yaml_value(content, 'sentiment')
        position = parse_yaml_value(content, 'position')
        upside_str = parse_yaml_value(content, 'upside')
        current_price = parse_yaml_value(content, 'current_price')
        fair_value = parse_yaml_value(content, 'my_fair_value')

        if not sentiment:
            continue

        upside = parse_upside(upside_str)

        companies.append({
            'ticker': ticker,
            'sentiment': sentiment,
            'position': position,
            'upside': upside,
            'current_price': current_price,
            'fair_value': fair_value
        })

    # Сортируем по upside
    companies.sort(key=lambda x: x['upside'], reverse=True)

    # Выводим топ-10
    print(f"  {'Тикер':<8} {'Sentiment':<10} {'Position':<8} {'Upside':<10} {'Цена':<10} {'Цель':<10}")
    print(f"  {'-'*8} {'-'*10} {'-'*8} {'-'*10} {'-'*10} {'-'*10}")

    for c in companies[:10]:
        # Цвет по sentiment
        if c['sentiment'] == 'bullish':
            color = GREEN
        elif c['sentiment'] == 'bearish':
            color = RED
        else:
            color = YELLOW

        upside_str = f"{c['upside']:.0f}%"
        print(f"  {color}{c['ticker']:<8}{NC} {c['sentiment']:<10} {c['position']:<8} {upside_str:<10} {c['current_price']:<10} {c['fair_value']:<10}")


if __name__ == '__main__':
    main()
