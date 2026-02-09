#!/usr/bin/env python3
"""
Генератор статического дашборда для GitHub Pages.

Читает companies/*/_index.md, companies/*/trend.json, sectors/*/_index.md
и генерирует docs/index.html + docs/companies/{TICKER}.html.

Использование:
    python3 scripts/generate_dashboard.py

Автор: AlmazNurmukhametov
"""

import csv
import html as html_module
import json
import os
import re
from datetime import date
from typing import Optional


# ============================================================================
# ANSI-цвета для вывода в терминал
# ============================================================================

GREEN = '\033[0;32m'
YELLOW = '\033[0;33m'
RED = '\033[0;31m'
CYAN = '\033[0;36m'
NC = '\033[0m'


# ============================================================================
# ПАРСЕРЫ
# ============================================================================

def parse_yaml_frontmatter(content: str) -> dict:
    """
    Парсит YAML frontmatter из markdown-файла.
    Поддерживает простые key: value и YAML-списки.
    """
    match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return {}

    yaml_content = match.group(1)
    result = {}
    current_key = None
    current_list = None

    for line in yaml_content.split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        # Элемент списка
        if stripped.startswith('- ') and current_key:
            if current_list is None:
                current_list = []
            current_list.append(stripped[2:].strip())
            continue

        # Если были элементы списка — сохраняем
        if current_list is not None and current_key:
            result[current_key] = current_list
            current_list = None
            current_key = None

        # key: value
        kv = re.match(r'^([a-zA-Z][a-zA-Z0-9_-]*):\s*(.*)$', stripped)
        if kv:
            key = kv.group(1)
            value = kv.group(2).strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]

            if value == '' or value is None:
                # Может быть начало списка
                current_key = key
                current_list = None
            else:
                result[key] = value
                current_key = key
                current_list = None

    # Финальный список
    if current_list is not None and current_key:
        result[current_key] = current_list

    return result


def get_body(content: str) -> str:
    """Возвращает содержимое markdown после YAML frontmatter."""
    match = re.match(r'^---\s*\n.*?\n---\s*\n?', content, re.DOTALL)
    if match:
        return content[match.end():]
    return content


def parse_upside(value: str) -> Optional[float]:
    """Парсит upside из '64%', '64', '-10%', '+25%' → десятичная дробь."""
    if not value:
        return None
    has_percent = '%' in value
    cleaned = value.replace('%', '').replace('+', '').strip()
    try:
        num = float(cleaned)
        if has_percent:
            return num / 100.0
        if abs(num) > 1:
            return num / 100.0
        return num
    except ValueError:
        return None


def parse_number(value: str) -> Optional[float]:
    """Парсит число из строки."""
    if not value:
        return None
    cleaned = value.replace('%', '').replace(',', '.').strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


# ============================================================================
# MARKDOWN → HTML КОНВЕРТЕР
# ============================================================================

def markdown_to_html(md: str) -> str:
    """Regex-конвертер markdown → HTML."""
    lines = md.split('\n')
    html_parts = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Пустая строка
        if not line.strip():
            i += 1
            continue

        # HTML-комментарии — пропускаем
        if line.strip().startswith('<!--'):
            start_i = i
            while i < len(lines) and '-->' not in lines[i]:
                i += 1
            if i >= len(lines):
                # Незакрытый комментарий — выводим предупреждение
                print(f"  {YELLOW}[WARN]{NC} Незакрытый HTML-комментарий (строка {start_i + 1})")
            i += 1
            continue

        # Горизонтальная линия
        if re.match(r'^---+\s*$', line.strip()):
            html_parts.append('<hr>')
            i += 1
            continue

        # Заголовки
        hm = re.match(r'^(#{1,4})\s+(.+)$', line)
        if hm:
            level = len(hm.group(1))
            text = inline_format(hm.group(2))
            html_parts.append(f'<h{level}>{text}</h{level}>')
            i += 1
            continue

        # Блок цитат
        if line.strip().startswith('> '):
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith('> '):
                quote_lines.append(lines[i].strip()[2:])
                i += 1
            html_parts.append(
                '<blockquote>' + inline_format('<br>'.join(quote_lines)) + '</blockquote>'
            )
            continue

        # Таблица
        if '|' in line and i + 1 < len(lines) and re.match(r'^[\s|:-]+$', lines[i + 1]):
            table_html = parse_table(lines, i)
            if table_html:
                html_parts.append(table_html[0])
                i = table_html[1]
                continue

        # Неупорядоченный список
        if re.match(r'^\s*[-*]\s', line):
            list_html, i = parse_unordered_list(lines, i)
            html_parts.append(list_html)
            continue

        # Упорядоченный список
        if re.match(r'^\s*\d+\.\s', line):
            list_html, i = parse_ordered_list(lines, i)
            html_parts.append(list_html)
            continue

        # Параграф
        para_lines = []
        while i < len(lines) and lines[i].strip() and not _is_block_start(lines[i]):
            para_lines.append(lines[i].strip())
            i += 1
        if para_lines:
            html_parts.append('<p>' + inline_format(' '.join(para_lines)) + '</p>')
            continue

        i += 1

    return '\n'.join(html_parts)


def _is_block_start(line: str) -> bool:
    """Проверяет, начинается ли строка с блочного элемента."""
    s = line.strip()
    if re.match(r'^#{1,4}\s', s):
        return True
    if re.match(r'^[-*]\s', s):
        return True
    if re.match(r'^\d+\.\s', s):
        return True
    if s.startswith('> '):
        return True
    if s.startswith('|') and '|' in s[1:]:
        return True
    if re.match(r'^---+\s*$', s):
        return True
    return False


def _safe_link(match) -> str:
    """Создаёт ссылку, блокируя javascript: и data: URI.

    Вызывается из inline_format(), где текст уже прошёл через escape_html(),
    поэтому URL и label здесь повторно НЕ экранируются.
    """
    label = match.group(1)
    url = match.group(2)
    # Декодируем HTML-сущности для проверки схемы, т.к. текст уже экранирован
    url_decoded = url.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
    url_lower = url_decoded.strip().lower()
    if url_lower.startswith(('javascript:', 'data:', 'vbscript:')):
        return label
    return f'<a href="{url}" target="_blank">{label}</a>'


def inline_format(text: str) -> str:
    """Форматирует inline-элементы: bold, italic, code, links, checkboxes.

    Сначала экранирует HTML, затем применяет markdown-разметку.
    """
    # Экранируем HTML-спецсимволы в исходном тексте
    text = escape_html(text)
    # Код inline
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    # Ссылки (с проверкой URL-схемы)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', _safe_link, text)
    # Bold
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    # Italic
    text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)
    # Чекбоксы
    text = re.sub(r'\[x\]', '<input type="checkbox" checked disabled>', text)
    text = re.sub(r'\[ \]', '<input type="checkbox" disabled>', text)
    return text


def parse_table(lines: list, start: int) -> Optional[tuple]:
    """Парсит markdown-таблицу → HTML <table>."""
    # Заголовок
    header_line = lines[start].strip()
    if not header_line.startswith('|'):
        return None

    headers = [c.strip() for c in header_line.strip('|').split('|')]

    # Разделитель
    sep_idx = start + 1
    if sep_idx >= len(lines):
        return None

    # Ряды данных
    i = sep_idx + 1
    rows = []
    while i < len(lines) and lines[i].strip().startswith('|'):
        cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
        rows.append(cells)
        i += 1

    html = '<div class="table-wrap"><table><thead><tr>'
    for h in headers:
        html += f'<th>{inline_format(h)}</th>'
    html += '</tr></thead><tbody>'
    for row in rows:
        html += '<tr>'
        for j, cell in enumerate(row):
            html += f'<td>{inline_format(cell)}</td>'
        html += '</tr>'
    html += '</tbody></table></div>'

    return html, i


def parse_unordered_list(lines: list, start: int) -> tuple:
    """Парсит неупорядоченный список."""
    items = []
    i = start
    while i < len(lines) and re.match(r'^\s*[-*]\s', lines[i]):
        text = re.sub(r'^\s*[-*]\s+', '', lines[i])
        items.append(f'<li>{inline_format(text.strip())}</li>')
        i += 1
    return '<ul>' + ''.join(items) + '</ul>', i


def parse_ordered_list(lines: list, start: int) -> tuple:
    """Парсит упорядоченный список."""
    items = []
    i = start
    while i < len(lines) and re.match(r'^\s*\d+\.\s', lines[i]):
        text = re.sub(r'^\s*\d+\.\s+', '', lines[i])
        items.append(f'<li>{inline_format(text.strip())}</li>')
        i += 1
    return '<ol>' + ''.join(items) + '</ol>', i


# ============================================================================
# ЧТЕНИЕ ДАННЫХ
# ============================================================================

def read_all_companies(companies_dir: str) -> list:
    """Читает все компании из companies/*/."""
    companies = []
    seen_tickers = set()  # dedup by ticker

    for name in sorted(os.listdir(companies_dir)):
        path = os.path.join(companies_dir, name)
        if not os.path.isdir(path):
            continue
        if name.startswith('_') or name.startswith('.'):
            continue

        index_file = os.path.join(path, '_index.md')
        if not os.path.exists(index_file):
            continue

        with open(index_file, 'r', encoding='utf-8') as f:
            content = f.read()

        meta = parse_yaml_frontmatter(content)
        body = get_body(content)

        # Название: поддержка и name: и company:
        company_name = meta.get('name') or meta.get('company') or name
        ticker = meta.get('ticker', name)
        is_stub = not meta.get('sentiment')

        # Дедупликация: пропускаем если тикер уже встречался
        if ticker in seen_tickers:
            continue
        seen_tickers.add(ticker)

        companies.append({
            'ticker': ticker,
            'name': company_name,
            'sector': meta.get('sector', ''),
            'sentiment': meta.get('sentiment', ''),
            'position': meta.get('position', ''),
            'current_price': meta.get('current_price', ''),
            'my_fair_value': meta.get('my_fair_value', ''),
            'upside': meta.get('upside', ''),
            'p_e': meta.get('p_e', ''),
            'dividend_yield': meta.get('dividend_yield', ''),
            'roe': meta.get('roe', ''),
            'market_cap_rub': meta.get('market_cap_rub', ''),
            'updated': meta.get('updated', ''),
            'is_stub': is_stub,
            'body': body,
            'meta': meta,
        })

    return companies


def read_all_sectors(sectors_dir: str) -> dict:
    """Читает все секторы → {slug: {name, sentiment, ...}}."""
    sectors = {}

    for name in sorted(os.listdir(sectors_dir)):
        path = os.path.join(sectors_dir, name)
        if not os.path.isdir(path):
            continue
        if name.startswith('_') or name.startswith('.'):
            continue

        index_file = os.path.join(path, '_index.md')
        if not os.path.exists(index_file):
            continue

        with open(index_file, 'r', encoding='utf-8') as f:
            content = f.read()

        meta = parse_yaml_frontmatter(content)
        sectors[name] = {
            'name': meta.get('name', name),
            'sentiment': meta.get('sentiment', ''),
        }

    return sectors


def read_all_trends(companies_dir: str) -> dict:
    """Читает все trend.json → {ticker: data}."""
    trends = {}

    for name in sorted(os.listdir(companies_dir)):
        path = os.path.join(companies_dir, name)
        if not os.path.isdir(path):
            continue

        trend_file = os.path.join(path, 'trend.json')
        if not os.path.exists(trend_file):
            continue

        try:
            with open(trend_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            trends[data.get('ticker', name)] = data
        except (json.JSONDecodeError, KeyError):
            continue

    return trends


def read_price_history(companies_dir: str, ticker: str) -> list[dict]:
    """Читает price_history.csv для тикера. Возвращает список записей."""
    csv_path = os.path.join(companies_dir, ticker, 'data', 'price_history.csv')
    if not os.path.exists(csv_path):
        return []

    rows = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                rows.append({
                    'date': row['date'],
                    'close': float(row.get('close', 0) or 0),
                    'volume_rub': int(float(row.get('volume_rub', 0) or 0)),
                    'market_cap_bln': float(row.get('market_cap_bln', 0) or 0),
                })
            except (ValueError, KeyError):
                continue

    return rows


def generate_price_chart_html(history: list[dict]) -> str:
    """Генерирует интерактивный блок истории цен с переключением периодов."""
    if not history:
        return ''

    prices = [h['close'] for h in history if h['close'] > 0]
    if not prices:
        return ''

    # Данные для JS — только date, close, volume_rub
    js_data = json.dumps(
        [{'d': h['date'], 'c': h['close'], 'v': h['volume_rub']} for h in history],
        ensure_ascii=False,
    ).replace('</', '<\\/')

    return f"""
<div class="price-history">
<h3>История цен</h3>
<div class="period-btns" id="period-btns">
<button class="period-btn" data-days="21">1М</button>
<button class="period-btn" data-days="63">3М</button>
<button class="period-btn" data-days="126">6М</button>
<button class="period-btn active" data-days="252">1Г</button>
<button class="period-btn" data-days="0">Всё</button>
</div>
<div class="price-chart-wrap">
<svg id="price-svg" viewBox="0 0 700 200" class="price-chart"></svg>
<div id="price-tooltip" class="price-tooltip"></div>
</div>
<div id="cmp-badge" class="cmp-badge" style="display:none"></div>
<div class="table-wrap price-table-wrap"><table class="price-table">
<thead><tr><th>Дата</th><th>Цена</th><th>Изм.</th><th>Объём</th></tr></thead>
<tbody id="price-tbody"></tbody>
</table></div>
</div>

<script>
(function() {{
var DATA = {js_data};
var svg = document.getElementById('price-svg');
var tbody = document.getElementById('price-tbody');
var activeDays = 252;

function render(days) {{
    activeDays = days;
    var src = days > 0 ? DATA.slice(-days) : DATA;
    if (!src.length) return;

    // --- SVG chart ---
    var W = 700, H = 200, PT = 20, PB = 30, PL = 60, PR = 20;
    var CW = W - PL - PR, CH = H - PT - PB;
    var prices = src.map(function(r){{ return r.c; }});
    var minP = Math.min.apply(null, prices), maxP = Math.max.apply(null, prices);
    var range = maxP - minP || maxP * 0.1 || 1;
    minP -= range * 0.05; maxP += range * 0.05; range = maxP - minP;
    var n = prices.length;

    function xP(i) {{ return PL + (i / Math.max(n - 1, 1)) * CW; }}
    function yP(p) {{ return PT + CH - ((p - minP) / range) * CH; }}

    var trendColor = prices[n-1] >= prices[0] ? 'var(--positive)' : 'var(--negative)';
    var pts = []; for (var i = 0; i < n; i++) pts.push(xP(i).toFixed(1)+','+yP(prices[i]).toFixed(1));
    var polyline = pts.join(' ');
    var area = xP(0).toFixed(1)+','+(PT+CH)+' '+polyline+' '+xP(n-1).toFixed(1)+','+(PT+CH);

    // Grid
    var h = '';
    for (var g = 0; g < 5; g++) {{
        var gp = minP + (range * g / 4), gy = yP(gp);
        h += '<line x1="'+PL+'" y1="'+gy.toFixed(1)+'" x2="'+(W-PR)+'" y2="'+gy.toFixed(1)+'" stroke="var(--border)" stroke-width="0.5" stroke-dasharray="4,4"/>';
        var lbl = gp >= 1000 ? Math.round(gp).toLocaleString('ru') : gp >= 1 ? gp.toFixed(1) : gp.toFixed(4);
        h += '<text x="'+(PL-8)+'" y="'+gy.toFixed(1)+'" text-anchor="end" dominant-baseline="middle" fill="var(--text-secondary)" font-size="11">'+lbl+'</text>';
    }}

    // Date labels
    var idxs = n >= 3 ? [0, Math.floor(n/2), n-1] : n === 2 ? [0, 1] : [0];
    for (var di = 0; di < idxs.length; di++) {{
        var dd = src[idxs[di]].d.split('-');
        h += '<text x="'+xP(idxs[di]).toFixed(1)+'" y="'+(H-5)+'" text-anchor="middle" fill="var(--text-secondary)" font-size="11">'+dd[2]+'.'+dd[1]+'</text>';
    }}

    h += '<polygon points="'+area+'" fill="'+trendColor+'" opacity="0.1"/>';
    h += '<polyline points="'+polyline+'" fill="none" stroke="'+trendColor+'" stroke-width="2" stroke-linejoin="round"/>';
    h += '<circle cx="'+xP(n-1).toFixed(1)+'" cy="'+yP(prices[n-1]).toFixed(1)+'" r="4" fill="var(--link)"/>';
    // Hover elements (initially hidden)
    h += '<line id="hv-line" x1="0" y1="'+PT+'" x2="0" y2="'+(PT+CH)+'" stroke="var(--text-secondary)" stroke-width="0.5" stroke-dasharray="3,3" visibility="hidden"/>';
    h += '<circle id="hv-dot" cx="0" cy="0" r="4" fill="var(--link)" visibility="hidden"/>';
    // Transparent overlay to capture mouse events
    h += '<rect x="'+PL+'" y="'+PT+'" width="'+CW+'" height="'+CH+'" fill="transparent" style="cursor:crosshair" id="hv-rect"/>';
    // Compare mode elements
    h += '<circle id="pin1" cx="0" cy="0" r="5" fill="var(--link)" stroke="var(--bg)" stroke-width="2" visibility="hidden"/>';
    h += '<circle id="pin2" cx="0" cy="0" r="5" fill="var(--link)" stroke="var(--bg)" stroke-width="2" visibility="hidden"/>';
    h += '<line id="cmp-line" x1="0" y1="0" x2="0" y2="0" stroke="var(--link)" stroke-width="1.5" stroke-dasharray="5,3" visibility="hidden"/>';
    svg.innerHTML = h;

    // --- Hover & Compare interaction ---
    var tooltip = document.getElementById('price-tooltip');
    var hvLine = document.getElementById('hv-line');
    var hvDot = document.getElementById('hv-dot');
    var hvRect = document.getElementById('hv-rect');
    var pin1El = document.getElementById('pin1');
    var pin2El = document.getElementById('pin2');
    var cmpLine = document.getElementById('cmp-line');
    var chartWrap = svg.closest('.price-chart-wrap');
    var cmpBadge = document.getElementById('cmp-badge');
    cmpBadge.style.display = 'none';
    var cmpState = 0; // 0=none, 1=first pinned, 2=both pinned
    var cmpIdx1 = -1, cmpIdx2 = -1;

    function getIdx(e) {{
        var rect = svg.getBoundingClientRect();
        var scaleX = W / rect.width;
        var mouseX = (e.clientX - rect.left) * scaleX;
        var idx = Math.round((mouseX - PL) / CW * (n - 1));
        if (idx < 0) idx = 0; if (idx >= n) idx = n - 1;
        return idx;
    }}

    function fmtPrice(p) {{
        return p >= 100 ? p.toLocaleString('ru', {{minimumFractionDigits:2, maximumFractionDigits:2}}) : p >= 1 ? p.toFixed(2) : p.toFixed(4);
    }}

    function fmtDate(d) {{
        var dd = d.split('-');
        return dd[2]+'.'+dd[1]+'.'+dd[0];
    }}

    function resetCompare() {{
        cmpState = 0; cmpIdx1 = -1; cmpIdx2 = -1;
        pin1El.setAttribute('visibility', 'hidden');
        pin2El.setAttribute('visibility', 'hidden');
        cmpLine.setAttribute('visibility', 'hidden');
        cmpBadge.style.display = 'none';
    }}

    cmpBadge.onclick = function() {{ resetCompare(); }};

    function showBadge(i1, i2) {{
        var lo = Math.min(i1, i2), hi = Math.max(i1, i2);
        var pct = (src[hi].c - src[lo].c) / src[lo].c * 100;
        var sign = pct > 0 ? '+' : '';
        var cls = pct > 0 ? 'positive' : pct < 0 ? 'negative' : 'muted';
        var days = hi - lo;
        var dayWord = 'дн.';
        cmpBadge.innerHTML = '<span class="'+cls+'" style="font-weight:700;font-size:16px">'+sign+pct.toFixed(1)+'%</span>' +
            '<span style="color:var(--text-secondary);font-size:12px;margin-left:8px">'+fmtDate(src[lo].d)+' → '+fmtDate(src[hi].d)+' ('+days+' '+dayWord+')</span>' +
            '<span style="color:var(--text-secondary);font-size:12px;margin-left:8px">'+fmtPrice(src[lo].c)+' → '+fmtPrice(src[hi].c)+'</span>';
        cmpBadge.style.display = 'flex';
    }}

    hvRect.addEventListener('click', function(e) {{
        var idx = getIdx(e);
        if (cmpState === 0) {{
            cmpState = 1; cmpIdx1 = idx;
            pin1El.setAttribute('cx', xP(idx).toFixed(1));
            pin1El.setAttribute('cy', yP(prices[idx]).toFixed(1));
            pin1El.setAttribute('visibility', 'visible');
            pin2El.setAttribute('visibility', 'hidden');
            cmpLine.setAttribute('visibility', 'hidden');
            cmpBadge.innerHTML = '<span style="color:var(--text-secondary);font-size:12px">Кликните вторую точку для сравнения</span>';
            cmpBadge.style.display = 'flex';
        }} else if (cmpState === 1) {{
            cmpState = 2; cmpIdx2 = idx;
            pin2El.setAttribute('cx', xP(idx).toFixed(1));
            pin2El.setAttribute('cy', yP(prices[idx]).toFixed(1));
            pin2El.setAttribute('visibility', 'visible');
            cmpLine.setAttribute('x1', xP(cmpIdx1).toFixed(1));
            cmpLine.setAttribute('y1', yP(prices[cmpIdx1]).toFixed(1));
            cmpLine.setAttribute('x2', xP(idx).toFixed(1));
            cmpLine.setAttribute('y2', yP(prices[idx]).toFixed(1));
            cmpLine.setAttribute('visibility', 'visible');
            showBadge(cmpIdx1, idx);
        }} else {{
            resetCompare();
        }}
    }});

    hvRect.addEventListener('mousemove', function(e) {{
        var idx = getIdx(e);
        var px = xP(idx), py = yP(prices[idx]);
        hvLine.setAttribute('x1', px.toFixed(1));
        hvLine.setAttribute('x2', px.toFixed(1));
        hvLine.setAttribute('visibility', 'visible');
        hvDot.setAttribute('cx', px.toFixed(1));
        hvDot.setAttribute('cy', py.toFixed(1));
        hvDot.setAttribute('visibility', 'visible');
        // Tooltip content
        var r = src[idx];
        var prStr = fmtPrice(r.c);
        var chgHtml = '';
        if (cmpState === 1) {{
            var pct = (r.c - src[cmpIdx1].c) / src[cmpIdx1].c * 100;
            var sign = pct > 0 ? '+' : '';
            var ccls = pct > 0 ? 'positive' : pct < 0 ? 'negative' : 'muted';
            chgHtml = '<span class="'+ccls+'" style="font-size:12px"> '+sign+pct.toFixed(1)+'%</span>';
        }} else if (idx > 0) {{
            var pct = (r.c - src[0].c) / src[0].c * 100;
            var sign = pct > 0 ? '+' : '';
            var ccls = pct > 0 ? 'positive' : pct < 0 ? 'negative' : 'muted';
            chgHtml = '<span class="'+ccls+'" style="font-size:12px"> '+sign+pct.toFixed(1)+'%</span>';
        }}
        tooltip.innerHTML = '<strong>'+prStr+'</strong> '+chgHtml+'<br><span style="color:var(--text-secondary);font-size:11px">'+fmtDate(r.d)+'</span>';
        tooltip.style.display = 'block';
        // Position tooltip
        var tipX = (e.clientX - chartWrap.getBoundingClientRect().left) + 12;
        var tipY = (e.clientY - chartWrap.getBoundingClientRect().top) - 10;
        if (tipX + 130 > chartWrap.offsetWidth) tipX -= 140;
        tooltip.style.left = tipX + 'px';
        tooltip.style.top = tipY + 'px';
        // Live connecting line while picking second point
        if (cmpState === 1) {{
            cmpLine.setAttribute('x1', xP(cmpIdx1).toFixed(1));
            cmpLine.setAttribute('y1', yP(prices[cmpIdx1]).toFixed(1));
            cmpLine.setAttribute('x2', px.toFixed(1));
            cmpLine.setAttribute('y2', py.toFixed(1));
            cmpLine.setAttribute('visibility', 'visible');
        }}
    }});

    hvRect.addEventListener('mouseleave', function() {{
        hvLine.setAttribute('visibility', 'hidden');
        hvDot.setAttribute('visibility', 'hidden');
        tooltip.style.display = 'none';
        if (cmpState === 1) cmpLine.setAttribute('visibility', 'hidden');
    }});

    // --- Table ---
    var tbl = '';
    var recent = src.slice().reverse().slice(0, 30);
    for (var ti = 0; ti < recent.length; ti++) {{
        var row = recent[ti];
        var chg = '\\u2014';
        if (ti < recent.length - 1) {{
            var prev = recent[ti+1].c;
            if (prev > 0) {{
                var pct = (row.c - prev) / prev * 100;
                var cls = pct > 0 ? 'positive' : pct < 0 ? 'negative' : 'muted';
                var sign = pct > 0 ? '+' : '';
                chg = '<span class="'+cls+'">'+sign+pct.toFixed(1)+'%</span>';
            }}
        }}
        var vm = row.v / 1e6;
        var vs = vm >= 1000 ? Math.round(vm).toLocaleString('ru') : vm >= 1 ? Math.round(vm) : vm.toFixed(1);
        var ps = row.c >= 100 ? row.c.toLocaleString('ru', {{minimumFractionDigits:2, maximumFractionDigits:2}}) : row.c >= 1 ? row.c.toFixed(2) : row.c.toFixed(4);
        tbl += '<tr><td>'+row.d+'</td><td>'+ps+'</td><td>'+chg+'</td><td>'+vs+'M</td></tr>';
    }}
    tbody.innerHTML = tbl;

    // Active button
    document.querySelectorAll('.period-btn').forEach(function(b) {{
        b.classList.toggle('active', parseInt(b.getAttribute('data-days')) === days);
    }});
}}

document.getElementById('period-btns').addEventListener('click', function(e) {{
    var btn = e.target.closest('.period-btn');
    if (btn) render(parseInt(btn.getAttribute('data-days')));
}});

render(activeDays);
}})();
</script>"""


# ============================================================================
# CSS
# ============================================================================

def get_css() -> str:
    """Возвращает CSS с поддержкой тёмной и светлой тем через CSS-переменные."""
    return """
/* Тёмная тема (по умолчанию) */
:root {
    --bg: #0d1117; --bg-card: #161b22; --bg-input: #161b22; --bg-metric: #0d1117;
    --border: #30363d; --border-light: #21262d;
    --text: #e6edf3; --text-secondary: #8b949e; --text-strong: #f0f6fc;
    --link: #388bfd;
    --green: #238636; --yellow: #d29922; --red: #da3633; --blue: #388bfd;
    --positive: #3fb950; --negative: #f85149;
    --badge-watch-bg: #484f58; --badge-watch-text: #e6edf3;
    --badge-stub-bg: #30363d; --badge-stub-text: #8b949e;
    --stub-banner-bg: #2d1b00; --stub-banner-border: #d29922;
    --forecast-flat-bg: #30363d; --forecast-flat-text: #8b949e;
    --stub-row-text: #484f58;
    --code-bg: #0d1117;
}
/* Светлая тема */
[data-theme="light"] {
    --bg: #ffffff; --bg-card: #f6f8fa; --bg-input: #f6f8fa; --bg-metric: #ffffff;
    --border: #d0d7de; --border-light: #e1e4e8;
    --text: #1f2328; --text-secondary: #656d76; --text-strong: #1f2328;
    --link: #0969da;
    --green: #1a7f37; --yellow: #9a6700; --red: #cf222e; --blue: #0969da;
    --positive: #1a7f37; --negative: #cf222e;
    --badge-watch-bg: #d0d7de; --badge-watch-text: #1f2328;
    --badge-stub-bg: #e1e4e8; --badge-stub-text: #656d76;
    --stub-banner-bg: #fff8c5; --stub-banner-border: #d4a72c;
    --forecast-flat-bg: #d0d7de; --forecast-flat-text: #656d76;
    --stub-row-text: #a1a9b1;
    --code-bg: #f6f8fa;
}

* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: system-ui, -apple-system, sans-serif;
    background: var(--bg); color: var(--text);
    line-height: 1.6; transition: background 0.2s, color 0.2s;
}
a { color: var(--link); text-decoration: none; }
a:hover { text-decoration: underline; }
.container { max-width: 1280px; margin: 0 auto; padding: 20px; }

/* Шапка */
header {
    border-bottom: 1px solid var(--border); padding: 20px 0; margin-bottom: 24px;
    display: flex; justify-content: space-between; align-items: flex-start;
}
.header-left h1 { font-size: 24px; font-weight: 600; }
.header-left .updated { color: var(--text-secondary); font-size: 14px; margin-top: 4px; }

/* Кнопка переключения темы */
.theme-toggle {
    background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px;
    padding: 8px 12px; cursor: pointer; color: var(--text); font-size: 18px;
    line-height: 1; transition: background 0.2s;
}
.theme-toggle:hover { border-color: var(--link); }

/* Статистика */
.stats { display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap; }
.stat-card {
    background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px;
    padding: 16px 20px; flex: 1; min-width: 140px;
}
.stat-card .label { color: var(--text-secondary); font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
.stat-card .value { font-size: 24px; font-weight: 600; margin-top: 4px; }
.stat-card .value.green { color: var(--green); }
.stat-card .value.blue { color: var(--blue); }

/* Фильтры */
.filters { display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; align-items: center; }
.filters select, .filters input {
    background: var(--bg-input); color: var(--text); border: 1px solid var(--border);
    border-radius: 6px; padding: 8px 12px; font-size: 14px;
    font-family: inherit;
}
.filters select:focus, .filters input:focus { border-color: var(--link); outline: none; }
.filters input { min-width: 200px; }

/* Таблица */
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th {
    background: var(--bg-card); color: var(--text-secondary); font-weight: 600; text-align: left;
    padding: 10px 12px; border-bottom: 2px solid var(--border);
    cursor: pointer; user-select: none; white-space: nowrap;
}
th:hover { color: var(--text); }
th .sort-arrow { margin-left: 4px; font-size: 10px; }
td { padding: 10px 12px; border-bottom: 1px solid var(--border-light); white-space: nowrap; }
tr:hover { background: var(--bg-card); }
tr.stub td { color: var(--stub-row-text); }

/* Бейджи */
.badge {
    display: inline-block; padding: 2px 8px; border-radius: 12px;
    font-size: 12px; font-weight: 500;
}
.badge-bullish { background: var(--green); color: #fff; }
.badge-neutral { background: var(--yellow); color: #fff; }
.badge-bearish { background: var(--red); color: #fff; }
.badge-buy { background: var(--green); color: #fff; }
.badge-hold { background: var(--blue); color: #fff; }
.badge-sell { background: var(--red); color: #fff; }
.badge-watch { background: var(--badge-watch-bg); color: var(--badge-watch-text); }
.badge-avoid { background: var(--red); color: #fff; }
.badge-stub { background: var(--badge-stub-bg); color: var(--badge-stub-text); }

/* Положительный/отрицательный upside */
.positive { color: var(--positive); }
.negative { color: var(--negative); }
.muted { color: var(--text-secondary); }

/* Навигация */
.back { display: inline-block; margin-bottom: 20px; color: var(--text-secondary); font-size: 14px; }
.back:hover { color: var(--text); }

/* Карточка компании */
.company-header {
    background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px;
    padding: 24px; margin-bottom: 24px;
}
.company-header h1 { font-size: 28px; margin-bottom: 8px; }
.company-header .ticker { color: var(--text-secondary); font-size: 16px; }
.badges { display: flex; gap: 8px; margin: 12px 0; flex-wrap: wrap; }
.metrics-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 12px; margin-top: 16px;
}
.metric {
    background: var(--bg-metric); border: 1px solid var(--border); border-radius: 8px;
    padding: 12px;
}
.metric .label { color: var(--text-secondary); font-size: 11px; text-transform: uppercase; }
.metric .value { font-size: 18px; font-weight: 600; margin-top: 2px; }

/* Прогноз-бар */
.forecast { margin-bottom: 24px; }
.forecast h3 { margin-bottom: 8px; font-size: 16px; }
.forecast-bar {
    display: flex; height: 28px; border-radius: 6px; overflow: hidden;
    font-size: 12px; font-weight: 600;
}
.forecast-bar .growth { background: var(--green); display: flex; align-items: center; justify-content: center; color: #fff; }
.forecast-bar .flat { background: var(--forecast-flat-bg); display: flex; align-items: center; justify-content: center; color: var(--forecast-flat-text); }
.forecast-bar .decline { background: var(--red); display: flex; align-items: center; justify-content: center; color: #fff; }

/* Баннер заглушки */
.stub-banner {
    background: var(--stub-banner-bg); border: 1px solid var(--stub-banner-border); border-radius: 8px;
    padding: 16px; margin-bottom: 24px; color: var(--stub-banner-border);
}

/* Контент анализа */
.analysis { background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 24px; }
.analysis h1, .analysis h2, .analysis h3, .analysis h4 { margin-top: 24px; margin-bottom: 12px; }
.analysis h1 { font-size: 24px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
.analysis h2 { font-size: 20px; border-bottom: 1px solid var(--border-light); padding-bottom: 6px; }
.analysis h3 { font-size: 16px; }
.analysis h4 { font-size: 14px; color: var(--text-secondary); }
.analysis p { margin-bottom: 12px; }
.analysis ul, .analysis ol { margin: 8px 0 12px 24px; }
.analysis li { margin-bottom: 4px; }
.analysis table { margin: 12px 0; }
.analysis blockquote {
    border-left: 3px solid var(--border); padding: 8px 16px;
    color: var(--text-secondary); margin: 12px 0;
}
.analysis code {
    background: var(--code-bg); padding: 2px 6px; border-radius: 4px;
    font-size: 13px; font-family: ui-monospace, monospace;
}
.analysis hr { border: none; border-top: 1px solid var(--border); margin: 20px 0; }
.analysis strong { color: var(--text-strong); }
.analysis input[type="checkbox"] { margin-right: 6px; }

/* История цен */
.price-history {
    background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px;
    padding: 24px; margin-bottom: 24px;
}
.price-history h3 { margin-bottom: 12px; font-size: 16px; }
.period-btns { display: flex; gap: 6px; margin-bottom: 16px; }
.period-btn {
    background: var(--bg-metric); border: 1px solid var(--border); border-radius: 6px;
    padding: 4px 12px; cursor: pointer; color: var(--text-secondary); font-size: 13px;
    font-family: inherit; transition: all 0.15s;
}
.period-btn:hover { border-color: var(--link); color: var(--text); }
.period-btn.active { background: var(--link); color: #fff; border-color: var(--link); }
.price-chart-wrap { margin-bottom: 16px; position: relative; }
.price-chart { width: 100%; height: auto; }
.price-tooltip {
    display: none; position: absolute; pointer-events: none;
    background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px;
    padding: 6px 10px; font-size: 14px; white-space: nowrap; z-index: 10;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}
.cmp-badge {
    display: flex; align-items: center; gap: 4px; flex-wrap: wrap;
    padding: 8px 12px; margin-top: 6px;
    background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px;
    font-size: 13px; cursor: pointer;
}
.cmp-badge:hover { border-color: var(--link); }
.price-table-wrap { max-height: 400px; overflow-y: auto; }
.price-table { font-size: 13px; }
.price-table th { position: sticky; top: 0; background: var(--bg-card); z-index: 1; }

/* Responsive */
@media (max-width: 768px) {
    .container { padding: 12px; }
    .stats { flex-direction: column; }
    .stat-card { min-width: auto; }
    .filters { flex-direction: column; }
    .filters input { min-width: auto; width: 100%; }
    .metrics-grid { grid-template-columns: repeat(2, 1fr); }
}
"""


# ============================================================================
# ГЕНЕРАЦИЯ СТРАНИЦ
# ============================================================================

def badge(value: str) -> str:
    """HTML-бейдж для sentiment или position."""
    if not value:
        return '<span class="badge badge-stub">—</span>'
    safe = escape_html(value)
    return f'<span class="badge badge-{safe}">{safe}</span>'


def format_upside(upside_str: str) -> str:
    """Форматирует upside с цветом."""
    if not upside_str:
        return '<span class="muted">—</span>'
    val = parse_upside(upside_str)
    if val is None:
        return f'<span class="muted">{upside_str}</span>'
    pct = round(val * 100)
    css = 'positive' if val > 0 else 'negative' if val < 0 else 'muted'
    sign = '+' if val > 0 else ''
    return f'<span class="{css}">{sign}{pct}%</span>'


def escape_html(s: str) -> str:
    """Экранирует HTML-спецсимволы."""
    return html_module.escape(s, quote=True)


def generate_index_page(companies: list, sectors: dict, trends: dict, output_dir: str):
    """Генерирует docs/index.html."""
    today = date.today().isoformat()

    # Статистика
    total = len(companies)
    filled = sum(1 for c in companies if not c['is_stub'])
    bullish = sum(1 for c in companies if c['sentiment'] == 'bullish')
    buy_count = sum(1 for c in companies if c['position'] == 'buy')
    upsides = [parse_upside(c['upside']) for c in companies if parse_upside(c['upside']) is not None]
    avg_upside = round(sum(upsides) / len(upsides) * 100) if upsides else 0

    # Уникальные значения для фильтров
    all_sectors = sorted(set(c['sector'] for c in companies if c['sector']))
    all_sentiments = sorted(set(c['sentiment'] for c in companies if c['sentiment']))
    all_positions = sorted(set(c['position'] for c in companies if c['position']))

    # Данные для JS
    js_data = []
    for c in companies:
        sector_name = sectors.get(c['sector'], {}).get('name', c['sector']) if c['sector'] else ''
        upside_val = parse_upside(c['upside'])
        pe_val = parse_number(c['p_e'])
        js_data.append({
            'ticker': c['ticker'],
            'name': c['name'],
            'sector': c['sector'],
            'sectorName': sector_name,
            'sentiment': c['sentiment'],
            'position': c['position'],
            'price': c['current_price'],
            'target': c['my_fair_value'],
            'upside': round(upside_val * 100) if upside_val is not None else None,
            'pe': pe_val,
            'divYield': c['dividend_yield'],
            'updated': c['updated'],
            'isStub': c['is_stub'],
        })

    # Опции фильтров
    sector_options = ''.join(
        f'<option value="{escape_html(s)}">{escape_html(sectors.get(s, {}).get("name", s))}</option>'
        for s in all_sectors
    )
    sentiment_options = ''.join(
        f'<option value="{escape_html(s)}">{escape_html(s)}</option>' for s in all_sentiments
    )
    position_options = ''.join(
        f'<option value="{escape_html(s)}">{escape_html(s)}</option>' for s in all_positions
    )

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Инвестиционный дашборд</title>
<style>{get_css()}</style>
</head>
<body>
<div class="container">

<header>
<div class="header-left">
<h1>Инвестиционный дашборд</h1>
<div class="updated">Обновлено: {today}</div>
</div>
<button class="theme-toggle" id="theme-toggle" title="Переключить тему">&#9790;</button>
</header>

<div class="stats">
<div class="stat-card"><div class="label">Всего компаний</div><div class="value">{total}</div></div>
<div class="stat-card"><div class="label">Заполнено</div><div class="value green">{filled}</div></div>
<div class="stat-card"><div class="label">Bullish</div><div class="value green">{bullish}</div></div>
<div class="stat-card"><div class="label">Buy</div><div class="value blue">{buy_count}</div></div>
<div class="stat-card"><div class="label">Средний upside</div><div class="value {'green' if avg_upside >= 0 else 'negative'}">{'+'if avg_upside >= 0 else ''}{avg_upside}%</div></div>
</div>

<div class="filters">
<select id="f-sector"><option value="">Все секторы</option>{sector_options}</select>
<select id="f-sentiment"><option value="">Все sentiment</option>{sentiment_options}</select>
<select id="f-position"><option value="">Все position</option>{position_options}</select>
<input id="f-search" type="text" placeholder="Поиск по тикеру или названию...">
</div>

<div class="table-wrap">
<table>
<thead><tr>
<th data-col="ticker">Тикер <span class="sort-arrow"></span></th>
<th data-col="name">Компания <span class="sort-arrow"></span></th>
<th data-col="sectorName">Сектор <span class="sort-arrow"></span></th>
<th data-col="sentiment">Sentiment <span class="sort-arrow"></span></th>
<th data-col="position">Position <span class="sort-arrow"></span></th>
<th data-col="price">Цена <span class="sort-arrow"></span></th>
<th data-col="target">Цель <span class="sort-arrow"></span></th>
<th data-col="upside">Upside <span class="sort-arrow"></span></th>
<th data-col="pe">P/E <span class="sort-arrow"></span></th>
<th data-col="divYield">Див. дох. <span class="sort-arrow"></span></th>
<th data-col="updated">Обновлено <span class="sort-arrow"></span></th>
</tr></thead>
<tbody id="tbody"></tbody>
</table>
</div>

</div>

<script>
const DATA = {json.dumps(js_data, ensure_ascii=False).replace('</','<\\/')};

const tbody = document.getElementById('tbody');
const fSector = document.getElementById('f-sector');
const fSentiment = document.getElementById('f-sentiment');
const fPosition = document.getElementById('f-position');
const fSearch = document.getElementById('f-search');

let sortCol = 'ticker';
let sortAsc = true;

function esc(s) {{
    if (s === null || s === undefined) return '';
    var d = document.createElement('div');
    d.textContent = String(s);
    return d.innerHTML;
}}

function badgeHTML(type, value) {{
    if (!value) return '<span class="badge badge-stub">\\u2014</span>';
    return '<span class="badge badge-' + esc(value) + '">' + esc(value) + '</span>';
}}

function upsideHTML(val) {{
    if (val === null || val === undefined) return '<span class="muted">\\u2014</span>';
    const cls = val > 0 ? 'positive' : val < 0 ? 'negative' : 'muted';
    const sign = val > 0 ? '+' : '';
    return '<span class="' + cls + '">' + sign + val + '%</span>';
}}

function render() {{
    const sector = fSector.value;
    const sentiment = fSentiment.value;
    const position = fPosition.value;
    const search = fSearch.value.toLowerCase();

    let filtered = DATA.filter(function(c) {{
        if (sector && c.sector !== sector) return false;
        if (sentiment && c.sentiment !== sentiment) return false;
        if (position && c.position !== position) return false;
        if (search && c.ticker.toLowerCase().indexOf(search) === -1 && c.name.toLowerCase().indexOf(search) === -1) return false;
        return true;
    }});

    filtered.sort(function(a, b) {{
        let va = a[sortCol], vb = b[sortCol];
        if (va === null || va === undefined) va = sortAsc ? Infinity : -Infinity;
        if (vb === null || vb === undefined) vb = sortAsc ? Infinity : -Infinity;
        if (typeof va === 'string') va = va.toLowerCase();
        if (typeof vb === 'string') vb = vb.toLowerCase();
        if (va < vb) return sortAsc ? -1 : 1;
        if (va > vb) return sortAsc ? 1 : -1;
        return 0;
    }});

    let html = '';
    for (let i = 0; i < filtered.length; i++) {{
        const c = filtered[i];
        const cls = c.isStub ? ' class="stub"' : '';
        html += '<tr' + cls + '>';
        html += '<td><a href="companies/' + esc(c.ticker) + '.html">' + esc(c.ticker) + '</a></td>';
        html += '<td>' + esc(c.name) + (c.isStub ? ' <span class="badge badge-stub">Заглушка</span>' : '') + '</td>';
        html += '<td>' + (c.sectorName ? esc(c.sectorName) : '<span class="muted">\\u2014</span>') + '</td>';
        html += '<td>' + badgeHTML('sentiment', c.sentiment) + '</td>';
        html += '<td>' + badgeHTML('position', c.position) + '</td>';
        html += '<td>' + (c.price ? esc(c.price) : '<span class="muted">\\u2014</span>') + '</td>';
        html += '<td>' + (c.target ? esc(c.target) : '<span class="muted">\\u2014</span>') + '</td>';
        html += '<td>' + upsideHTML(c.upside) + '</td>';
        html += '<td>' + (c.pe !== null && c.pe !== undefined ? esc(c.pe) : '<span class="muted">\\u2014</span>') + '</td>';
        html += '<td>' + (c.divYield ? esc(c.divYield) : '<span class="muted">\\u2014</span>') + '</td>';
        html += '<td>' + (c.updated ? esc(c.updated) : '<span class="muted">\\u2014</span>') + '</td>';
        html += '</tr>';
    }}
    tbody.innerHTML = html;
}}

// Сортировка по клику на заголовок
document.querySelectorAll('th[data-col]').forEach(function(th) {{
    th.addEventListener('click', function() {{
        const col = this.getAttribute('data-col');
        if (sortCol === col) {{
            sortAsc = !sortAsc;
        }} else {{
            sortCol = col;
            sortAsc = true;
        }}
        document.querySelectorAll('th .sort-arrow').forEach(function(s) {{ s.textContent = ''; }});
        this.querySelector('.sort-arrow').textContent = sortAsc ? '\\u25B2' : '\\u25BC';
        render();
    }});
}});

fSector.addEventListener('change', render);
fSentiment.addEventListener('change', render);
fPosition.addEventListener('change', render);
fSearch.addEventListener('input', render);

// Тема
(function() {{
    var btn = document.getElementById('theme-toggle');
    var saved = localStorage.getItem('theme') || 'dark';
    if (saved === 'light') document.documentElement.setAttribute('data-theme', 'light');
    btn.textContent = saved === 'light' ? '\\u2600' : '\\u263E';
    btn.addEventListener('click', function() {{
        var current = document.documentElement.getAttribute('data-theme');
        var next = current === 'light' ? 'dark' : 'light';
        if (next === 'light') {{
            document.documentElement.setAttribute('data-theme', 'light');
        }} else {{
            document.documentElement.removeAttribute('data-theme');
        }}
        btn.textContent = next === 'light' ? '\\u2600' : '\\u263E';
        localStorage.setItem('theme', next);
    }});
}})();

render();
</script>
</body>
</html>"""

    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, 'index.html')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    return output_file


def generate_company_page(company: dict, sectors: dict, trends: dict, output_dir: str,
                          companies_dir: str = '') -> str:
    """Генерирует docs/companies/{TICKER}.html."""
    ticker = company['ticker']
    if not re.match(r'^[A-Za-z0-9]+$', ticker):
        print(f"  {YELLOW}[WARN]{NC} Пропуск тикера с недопустимыми символами: {ticker}")
        return ''
    name = company['name']
    sector_slug = company['sector']
    sector_name = sectors.get(sector_slug, {}).get('name', sector_slug) if sector_slug else ''
    trend = trends.get(ticker, {})
    meta = company['meta']

    # Метрики
    metrics = []
    if company['current_price']:
        metrics.append(('Цена', company['current_price']))
    if company['my_fair_value']:
        metrics.append(('Цель', company['my_fair_value']))
    if company['upside']:
        up_val = parse_upside(company['upside'])
        if up_val is not None:
            sign = '+' if up_val > 0 else ''
            metrics.append(('Upside', f'{sign}{round(up_val * 100)}%'))
    if company['p_e']:
        metrics.append(('P/E', company['p_e']))
    if company['dividend_yield']:
        metrics.append(('Див. дох.', company['dividend_yield']))
    if company['roe']:
        metrics.append(('ROE', company['roe']))
    if company['market_cap_rub']:
        metrics.append(('Капитализация', company['market_cap_rub']))

    # Доп. метрики из meta
    for key, label in [('p_bv', 'P/BV'), ('ev_ebitda', 'EV/EBITDA'), ('net_debt_ebitda', 'NetDebt/EBITDA')]:
        if meta.get(key):
            metrics.append((label, meta[key]))

    metrics_html = ''
    for label, value in metrics:
        metrics_html += f'<div class="metric"><div class="label">{label}</div><div class="value">{escape_html(str(value))}</div></div>'

    # Прогноз бар
    forecast_html = ''
    if trend:
        gp = trend.get('growth_probability', 0)
        dp = trend.get('decline_probability', 0)
        fp = round(1 - gp - dp, 2)
        if fp < 0:
            fp = 0
        gp_pct = round(gp * 100)
        dp_pct = round(dp * 100)
        fp_pct = max(0, 100 - gp_pct - dp_pct)
        forecast_html = f"""
<div class="forecast">
<h3>Прогноз</h3>
<div class="forecast-bar">
<div class="growth" style="width:{gp_pct}%">&#x25B2; {gp_pct}%</div>
<div class="flat" style="width:{fp_pct}%">{fp_pct}%</div>
<div class="decline" style="width:{dp_pct}%">&#x25BC; {dp_pct}%</div>
</div>
</div>"""

    # Баннер заглушки
    stub_html = ''
    if company['is_stub']:
        stub_html = '<div class="stub-banner">Анализ не завершён. Данные могут быть неполными.</div>'

    # История цен
    price_history_html = ''
    if companies_dir:
        history = read_price_history(companies_dir, ticker)
        price_history_html = generate_price_chart_html(history)

    # Конвертируем body в HTML
    body_html = markdown_to_html(company['body'])

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape_html(name)} ({ticker}) — Инвестиционный дашборд</title>
<style>{get_css()}</style>
</head>
<body>
<div class="container">

<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
<a href="../index.html" class="back" style="margin-bottom:0">&larr; Назад к дашборду</a>
<button class="theme-toggle" id="theme-toggle" title="Переключить тему">&#9790;</button>
</div>

<div class="company-header">
<h1>{escape_html(name)}</h1>
<div class="ticker">{ticker}{(' &middot; ' + escape_html(sector_name)) if sector_name else ''}</div>
<div class="badges">
{badge(company['sentiment'])}
{badge(company['position'])}
</div>
<div class="metrics-grid">{metrics_html}</div>
</div>

{stub_html}
{forecast_html}
{price_history_html}

<div class="analysis">
{body_html}
</div>

</div>

<script>
(function() {{
    var btn = document.getElementById('theme-toggle');
    var saved = localStorage.getItem('theme') || 'dark';
    if (saved === 'light') document.documentElement.setAttribute('data-theme', 'light');
    btn.textContent = saved === 'light' ? '\\u2600' : '\\u263E';
    btn.addEventListener('click', function() {{
        var current = document.documentElement.getAttribute('data-theme');
        var next = current === 'light' ? 'dark' : 'light';
        if (next === 'light') {{
            document.documentElement.setAttribute('data-theme', 'light');
        }} else {{
            document.documentElement.removeAttribute('data-theme');
        }}
        btn.textContent = next === 'light' ? '\\u2600' : '\\u263E';
        localStorage.setItem('theme', next);
    }});
}})();
</script>
</body>
</html>"""

    companies_out = os.path.join(output_dir, 'companies')
    os.makedirs(companies_out, exist_ok=True)
    output_file = os.path.join(companies_out, f'{ticker}.html')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    return output_file


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Основная функция."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)
    companies_dir = os.path.join(base_dir, 'companies')
    sectors_dir = os.path.join(base_dir, 'sectors')
    output_dir = os.path.join(base_dir, 'docs')

    print(f"{CYAN}Генерация дашборда...{NC}")
    print()

    # Читаем данные
    companies = read_all_companies(companies_dir)
    sectors = read_all_sectors(sectors_dir)
    trends = read_all_trends(companies_dir)

    filled = sum(1 for c in companies if not c['is_stub'])
    print(f"  Компаний: {len(companies)} (заполнено: {GREEN}{filled}{NC})")
    print(f"  Секторов: {len(sectors)}")
    print(f"  trend.json: {len(trends)}")
    print()

    # Генерируем главную страницу
    index_file = generate_index_page(companies, sectors, trends, output_dir)
    print(f"  {GREEN}[OK]{NC} {index_file}")

    # Генерируем страницы компаний
    for c in companies:
        page = generate_company_page(c, sectors, trends, output_dir, companies_dir)
        status = 'STUB' if c['is_stub'] else 'OK'
        color = YELLOW if c['is_stub'] else GREEN
        print(f"  {color}[{status}]{NC} {c['ticker']}")

    print()
    print(f"{GREEN}Готово: {len(companies) + 1} файлов сгенерировано в docs/{NC}")

    return 0


if __name__ == '__main__':
    exit(main())
