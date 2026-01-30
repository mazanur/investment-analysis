#!/usr/bin/env python3
"""
Генератор trend.json для компаний.

Читает YAML-метаданные из companies/*/_index.md и создаёт trend.json
с вероятностями роста/падения для внешнего сервиса.

Использование:
    python3 scripts/generate_trend_json.py

Автор: AlmazNurmukhametov
"""

import json
import os
import re
from datetime import date
from typing import Optional


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Ограничивает значение в диапазоне [min_val, max_val]."""
    return max(min_val, min(max_val, value))


def parse_upside(upside_value: str) -> Optional[float]:
    """
    Парсит upside из разных форматов: "64%", "64", "-10%", "+25%".
    Возвращает значение как десятичную дробь (0.64 для 64%).
    """
    if not upside_value:
        return None

    has_percent = '%' in upside_value
    # Убираем %, + и пробелы
    cleaned = upside_value.replace('%', '').replace('+', '').strip()
    try:
        value = float(cleaned)
        # Если есть знак %, всегда делим на 100
        if has_percent:
            return value / 100.0
        # Если число > 1 или < -1, считаем что это проценты
        if abs(value) > 1:
            return value / 100.0
        return value
    except ValueError:
        return None


def parse_yaml_frontmatter(content: str) -> dict:
    """
    Парсит простой YAML frontmatter из markdown-файла.
    Поддерживает только простые key: value пары.
    """
    match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return {}

    yaml_content = match.group(1)
    result = {}

    for line in yaml_content.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        # Ищем key: value
        match = re.match(r'^([a-zA-Z][a-zA-Z0-9_-]*):\s*(.*)$', line)
        if match:
            key = match.group(1)
            value = match.group(2).strip()
            # Убираем кавычки если есть
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            result[key] = value

    return result


def calculate_probabilities(sentiment: str, upside: Optional[float]) -> tuple:
    """
    Рассчитывает вероятности роста и падения на основе sentiment и upside.

    Базовые вероятности по sentiment:
    - bullish: growth=0.65, decline=0.20
    - neutral: growth=0.40, decline=0.40
    - bearish: growth=0.20, decline=0.65

    Корректировка по upside:
    - upside > 50%: growth +0.10
    - upside > 30%: growth +0.05
    - upside < 0%: decline +0.10

    Ограничения: вероятности в диапазоне [0.05, 0.90]
    """
    # Базовые вероятности
    base_probs = {
        'bullish': (0.65, 0.20),
        'neutral': (0.40, 0.40),
        'bearish': (0.20, 0.65),
    }

    growth, decline = base_probs.get(sentiment, (0.40, 0.40))

    # Корректировка по upside
    if upside is not None:
        if upside > 0.50:
            growth += 0.10
        elif upside > 0.30:
            growth += 0.05

        if upside < 0:
            decline += 0.10

    # Ограничиваем в диапазоне [0.05, 0.90]
    growth = clamp(growth, 0.05, 0.90)
    decline = clamp(decline, 0.05, 0.90)

    # Гарантируем, что сумма вероятностей не превышает 1.0
    if growth + decline > 1.0:
        total = growth + decline
        growth = round(growth / total, 2)
        decline = round(decline / total, 2)

    return round(growth, 2), round(decline, 2)


def process_company(company_dir: str, company_name: str) -> Optional[dict]:
    """
    Обрабатывает папку компании и генерирует данные для trend.json.

    Returns:
        dict с данными или None если компания не может быть обработана
    """
    index_file = os.path.join(company_dir, '_index.md')
    if not os.path.exists(index_file):
        return None

    with open(index_file, 'r', encoding='utf-8') as f:
        content = f.read()

    metadata = parse_yaml_frontmatter(content)

    if not metadata:
        print(f"  [SKIP] {company_name}: нет YAML-метаданных")
        return None

    ticker = metadata.get('ticker', company_name)
    sentiment = metadata.get('sentiment')

    # Пропускаем делистингованные компании
    if metadata.get('delisted') == 'true' or metadata.get('status') == 'delisted':
        print(f"  [SKIP] {ticker}: делистингован")
        return None

    if not sentiment or sentiment not in ('bullish', 'neutral', 'bearish'):
        print(f"  [SKIP] {ticker}: нет sentiment или некорректное значение ({sentiment})")
        return None

    upside = parse_upside(metadata.get('upside', ''))
    growth_prob, decline_prob = calculate_probabilities(sentiment, upside)

    return {
        'ticker': ticker,
        'sentiment': sentiment,
        'upside': upside if upside is not None else 0.0,
        'growth_probability': growth_prob,
        'decline_probability': decline_prob,
        'updated': date.today().isoformat(),
    }


def main():
    """Основная функция."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    companies_dir = os.path.join(os.path.dirname(script_dir), 'companies')

    if not os.path.exists(companies_dir):
        print(f"Ошибка: директория {companies_dir} не найдена")
        return 1

    processed = 0
    skipped = 0
    seen_tickers = {}  # ticker -> directory name (dedup)

    print("Генерация trend.json для компаний...")
    print()

    for company_name in sorted(os.listdir(companies_dir)):
        company_dir = os.path.join(companies_dir, company_name)

        if not os.path.isdir(company_dir):
            continue

        # Пропускаем служебные файлы
        if company_name.startswith('_') or company_name.startswith('.'):
            continue

        trend_data = process_company(company_dir, company_name)

        if trend_data:
            ticker = trend_data['ticker']

            # Дедупликация: пропускаем если тикер уже обработан
            if ticker in seen_tickers:
                print(f"  [SKIP] {company_name}: тикер {ticker} "
                      f"уже обработан из {seen_tickers[ticker]}")
                skipped += 1
                continue
            seen_tickers[ticker] = company_name

            output_file = os.path.join(company_dir, 'trend.json')
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(trend_data, f, ensure_ascii=False, indent=2)
                f.write('\n')

            print(f"  [OK] {trend_data['ticker']}: "
                  f"growth={trend_data['growth_probability']}, "
                  f"decline={trend_data['decline_probability']}")
            processed += 1
        else:
            # Удаляем стale trend.json для пропущенных компаний (делистинг и т.д.)
            stale_file = os.path.join(company_dir, 'trend.json')
            if os.path.exists(stale_file):
                os.remove(stale_file)
                print(f"  [CLEANUP] {company_name}: удалён устаревший trend.json")
            skipped += 1

    print()
    print(f"Готово: {processed} файлов создано, {skipped} пропущено")

    return 0


if __name__ == '__main__':
    exit(main())
