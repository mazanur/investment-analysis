#!/usr/bin/env python3
"""
Экспортирует данные всех компаний в JSON.

Использование:
    python3 scripts/export_data.py

Автор: AlmazNurmukhametov
"""

import json
import os
import re
from datetime import date


def parse_yaml_frontmatter(content: str) -> dict:
    """Парсит YAML frontmatter из markdown."""
    match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return {}

    yaml_content = match.group(1)
    result = {}

    for line in yaml_content.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        match = re.match(r'^([a-z_]+):\s*(.*)$', line)
        if match:
            key = match.group(1)
            value = match.group(2).strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            result[key] = value

    return result


def parse_number(value: str) -> float:
    """Парсит число из строки."""
    if not value:
        return None
    cleaned = value.replace('%', '').replace(',', '.').strip()
    try:
        num = float(cleaned)
        return num
    except ValueError:
        return None


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)
    companies_dir = os.path.join(base_dir, 'companies')
    output_dir = os.path.join(base_dir, 'data')
    output_file = os.path.join(output_dir, 'export.json')

    os.makedirs(output_dir, exist_ok=True)

    companies = []

    for company in sorted(os.listdir(companies_dir)):
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

        meta = parse_yaml_frontmatter(content)

        if not meta.get('sentiment'):
            continue

        # Парсим числовые значения
        upside = parse_number(meta.get('upside', ''))
        if upside and abs(upside) > 1:
            upside = upside / 100  # Конвертируем проценты в дробь

        company_data = {
            'ticker': meta.get('ticker', company),
            'name': meta.get('name', ''),
            'sector': meta.get('sector', ''),
            'sentiment': meta.get('sentiment'),
            'position': meta.get('position', ''),
            'current_price': parse_number(meta.get('current_price', '')),
            'fair_value': parse_number(meta.get('my_fair_value', '')),
            'upside': upside,
            'p_e': parse_number(meta.get('p_e', '')),
            'dividend_yield': meta.get('dividend_yield', ''),
            'roe': meta.get('roe', ''),
            'updated': meta.get('updated', ''),
        }

        companies.append(company_data)

    # Формируем итоговый JSON
    export_data = {
        'generated': date.today().isoformat(),
        'total_companies': len(companies),
        'companies': companies
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)

    print(f"Экспортировано {len(companies)} компаний в {output_file}")


if __name__ == '__main__':
    main()
