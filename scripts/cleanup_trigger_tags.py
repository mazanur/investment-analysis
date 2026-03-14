#!/usr/bin/env python3
"""
Cleanup trigger_tags in _index.md files.

Removes generic/temporal tags that match too many companies
and don't help differentiate which company a news article is about.
"""

import os
import re
import sys

COMPANIES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "companies")

# Tags to ALWAYS remove — too generic or temporal
BLACKLIST = {
    # Reporting (match any company's quarterly report)
    "отчетность", "финансовые результаты", "мсфо", "рсбу", "рпбу",
    "операционные результаты", "финансовая отчетность", "финансовые показатели",
    "годовой отчет", "годовая отчетность", "квартальная отчетность",
    "итоги квартала", "итоги года", "предварительные данные", "итоги",
    "баланс", "прибыль", "результаты",
    # ЦБ/ставка — universal, 33+ companies have this
    "ключевая ставка", "цб", "снижение ставки",
    # Generic business terms
    "финансы", "акции", "показатели", "инвестиции", "перспективы",
    "рост", "стратегия", "выплаты акционерам", "экономика",
    "финансовый рынок", "регулирование",
    # Too generic dividend tags (almost every company has dividends)
    "дивиденды", "дивидендная политика",
    # Generic financial metrics — match too many companies
    "рентабельность", "маржинальность", "себестоимость",
    "капитальные затраты", "капзатраты", "инвестпрограмма",
    "процентные расходы", "долг", "долговая нагрузка",
    "рефинансирование", "денежный поток", "переоценка",
    "убыток", "чистая прибыль", "выручка",
    "облигации", "недооценка", "балансовая стоимость",
    # Sector tags — sector matcher already handles these
    "строительство", "сталь", "электроэнергия", "золото", "ипотека",
    "металлургия", "банковский сектор", "it-сектор", "застройщик",
    "медицина",
    # Generic reporting periods
    "полугодие",
    # Sanctions — too broad (23 companies), sector matching handles this
    "санкции", "sdn", "ofac", "блокирующие санкции",
    # Currency — too broad (8+ companies), sector matching handles FX exposure
    "доллар", "курс валют", "рубль", "девальвация", "юань",
    # Oil — too broad (6 companies), sector matching handles oil price impact
    "нефть", "brent", "urals",
    # EU — too broad (6 companies)
    "ес",
    # Swift — too broad for trigger matching
    "swift",
    # Generic corporate events — match any company doing this
    "допэмиссия", "обратный выкуп", "байбэк", "buyback",
    "размещение акций", "совет директоров", "поглощение", "ipo",
    # Generic banking metrics — match all banks
    "просрочка", "процентная маржа", "достаточность капитала",
    "резервы", "депозиты", "портфель ценных бумаг",
    "ликвидность", "казначейские акции", "free-float",
    # Generic financial terms
    "денежная позиция", "погашение долга", "валютная выручка",
    "проектное финансирование", "модернизация",
    # Taxes/regulation — sector-wide
    "ндпи", "регулирование цен", "заморозка цен",
    # Government programs — sector-wide
    "семейная ипотека", "льготная ипотека", "росимущество",
    "импортозамещение", "госкомпания",
    # Macro/labor terms
    "дефицит кадров", "безработица", "рынок труда",
    "инфляция", "найм", "геополитика",
    # Ambiguous: "система" = generic word "system", false-matches everything;
    # "афк система" is specific enough for AFK Sistema
    "система",
    # Generic trade terms
    "импорт", "экспорт", "квоты",
    # Generic market terms
    "коммод", "lme", "маркетплейс",
    # Substring false positives — match unrelated words/contexts
    "оборот", "пилоты", "европа", "якутия", "энергетика", "туризм",
    "доставка", "запрет", "ограничения", "лицензия", "риски", "2026",
}

# Regex patterns for temporal tags
TEMPORAL_PATTERNS = [
    r"^\d+ месяц",        # "9 месяцев", "3 месяца 2026"
    r"^\d+м \d{4}$",      # "3м 2026", "5м 2026"
    r"^\d{4}$",           # "2026", "2025"
    r"^\d{4} год$",       # "2026 год"
    r"^\d+ квартал$",     # "1 квартал", "3 квартал"
    r"^[iv]+ квартал$",   # "i квартал", "ii квартал"
    r"^(январь|февраль|март|апрель|май|июнь|июль|август|сентябрь|октябрь|ноябрь|декабрь)",
    r"день инвестора",
]


def is_blacklisted(tag: str) -> bool:
    t = tag.lower().strip()
    if t in BLACKLIST:
        return True
    for pattern in TEMPORAL_PATTERNS:
        if re.match(pattern, t):
            return True
    return False


def process_file(filepath: str) -> tuple[int, int]:
    """Process one _index.md file. Returns (removed_tags, remaining_tags)."""
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    removed = 0
    remaining = 0
    i = 0
    while i < len(lines):
        line = lines[i]

        # Check if this is a trigger_tags line
        m = re.match(r'^(\s+)trigger_tags:\s*\[(.+)\]\s*$', line)
        if m:
            indent = m.group(1)
            tags_str = m.group(2)
            # Parse tags
            tags = [t.strip().strip("'\"") for t in tags_str.split(",") if t.strip()]
            clean_tags = [t for t in tags if not is_blacklisted(t)]
            removed += len(tags) - len(clean_tags)
            remaining += len(clean_tags)

            if clean_tags:
                # Rewrite with clean tags
                new_lines.append(f"{indent}trigger_tags: [{', '.join(clean_tags)}]\n")
            else:
                # All tags removed — drop trigger_tags line
                # Check if previous line was "- text: ..." and convert to simple string
                if new_lines and re.match(r'^(\s+)-\s+text:\s+(.+)$', new_lines[-1]):
                    prev_m = re.match(r'^(\s+)-\s+text:\s+(.+)$', new_lines[-1])
                    prev_indent = prev_m.group(1)
                    text_value = prev_m.group(2).strip()
                    new_lines[-1] = f"{prev_indent}- {text_value}\n"
            i += 1
            continue

        new_lines.append(line)
        i += 1

    if removed > 0:
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

    return removed, remaining


def main():
    total_removed = 0
    total_remaining = 0

    tickers = sorted(os.listdir(COMPANIES_DIR))
    for ticker in tickers:
        index_file = os.path.join(COMPANIES_DIR, ticker, "_index.md")
        if not os.path.isfile(index_file):
            continue

        removed, remaining = process_file(index_file)
        if removed > 0:
            print(f"  {ticker}: removed {removed} tags, {remaining} remaining")
            total_removed += removed
        total_remaining += remaining

    print(f"\nTotal: removed {total_removed} tags, {total_remaining} remaining")


if __name__ == "__main__":
    main()
