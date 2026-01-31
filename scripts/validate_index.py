#!/usr/bin/env python3
"""
Проверяет валидность _index.md файлов компаний.

Использование:
    python3 scripts/validate_index.py

Автор: AlmazNurmukhametov
"""

import os
import re

# Цвета
GREEN = '\033[0;32m'
YELLOW = '\033[0;33m'
RED = '\033[0;31m'
NC = '\033[0m'

# Обязательные поля для заполненной карточки
REQUIRED_FIELDS = ['ticker', 'name', 'sector', 'sentiment', 'updated']
RECOMMENDED_FIELDS = ['position', 'current_price', 'my_fair_value', 'upside']


def parse_yaml_frontmatter(content: str) -> dict:
    """Парсит YAML frontmatter."""
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
            result[key] = value

    return result


def validate_company(company_path: str, company_name: str) -> list:
    """Проверяет _index.md компании. Возвращает список ошибок."""
    errors = []
    warnings = []

    index_file = os.path.join(company_path, '_index.md')

    if not os.path.exists(index_file):
        return [f"Нет _index.md"], []

    with open(index_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Проверяем YAML
    meta = parse_yaml_frontmatter(content)

    if not meta:
        return [f"Нет YAML frontmatter"], []

    # Проверяем обязательные поля
    for field in REQUIRED_FIELDS:
        if field not in meta or not meta[field]:
            errors.append(f"Отсутствует {field}")

    # Проверяем рекомендуемые поля (если есть sentiment)
    if meta.get('sentiment') in ('bullish', 'neutral', 'bearish'):
        for field in RECOMMENDED_FIELDS:
            if field not in meta or not meta[field]:
                warnings.append(f"Рекомендуется заполнить {field}")

    # Проверяем валидность sentiment
    sentiment = meta.get('sentiment', '')
    if sentiment and sentiment not in ('bullish', 'neutral', 'bearish'):
        errors.append(f"Некорректный sentiment: {sentiment}")

    # Проверяем валидность position
    position = meta.get('position', '')
    if position and position not in ('buy', 'hold', 'sell', 'watch', 'avoid'):
        errors.append(f"Некорректный position: {position}")

    # Проверяем HTML-комментарии (остатки от шаблона)
    if '<!--' in content:
        warnings.append("Остались HTML-комментарии от шаблона")

    return errors, warnings


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    companies_dir = os.path.join(os.path.dirname(script_dir), 'companies')

    total = 0
    valid = 0
    with_errors = 0
    with_warnings = 0

    print(f"Проверка компаний в {companies_dir}...")
    print()

    for company in sorted(os.listdir(companies_dir)):
        company_path = os.path.join(companies_dir, company)
        if not os.path.isdir(company_path):
            continue
        if company.startswith('_') or company.startswith('.'):
            continue

        total += 1
        errors, warnings = validate_company(company_path, company)

        if errors:
            with_errors += 1
            print(f"{RED}✗{NC} {company}")
            for err in errors:
                print(f"    {RED}•{NC} {err}")
            for warn in warnings:
                print(f"    {YELLOW}•{NC} {warn}")
        elif warnings:
            with_warnings += 1
            print(f"{YELLOW}⚠{NC} {company}")
            for warn in warnings:
                print(f"    {YELLOW}•{NC} {warn}")
        else:
            valid += 1

    print()
    print(f"Итого: {total} компаний")
    print(f"  {GREEN}✓ Валидных: {valid}{NC}")
    if with_warnings:
        print(f"  {YELLOW}⚠ С предупреждениями: {with_warnings}{NC}")
    if with_errors:
        print(f"  {RED}✗ С ошибками: {with_errors}{NC}")

    return 1 if with_errors > 0 else 0


if __name__ == '__main__':
    exit(main())
