#!/usr/bin/env python3
"""
Форматтер stream-json вывода Claude Code в читаемый лог.

Использование:
    claude --output-format stream-json -p "..." | python3 scripts/claude_log.py

Автор: AlmazNurmukhametov
"""

import json
import os
import sys
import textwrap

# Отключаем буферизацию stdout
os.environ["PYTHONUNBUFFERED"] = "1"
sys.stdout.reconfigure(line_buffering=True)

# ANSI-цвета
CYAN = "\033[0;36m"
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
DIM = "\033[2m"
BOLD = "\033[1m"
NC = "\033[0m"

TOOL_RESULT_MAX = 200  # макс. символов для tool_result


def format_tool_input(name: str, inp: dict) -> str:
    """Краткое описание вызова инструмента."""
    if name == "Task":
        desc = inp.get("description", "")
        agent = inp.get("subagent_type", "")
        return f"{agent}: {desc}" if agent else desc
    if name == "Read":
        path = inp.get("file_path", "")
        # показываем только относительный путь
        short = path.split("investment-analysis/")[-1] if "investment-analysis/" in path else path
        return short
    if name == "Write":
        path = inp.get("file_path", "")
        short = path.split("investment-analysis/")[-1] if "investment-analysis/" in path else path
        return short
    if name == "Edit":
        path = inp.get("file_path", "")
        short = path.split("investment-analysis/")[-1] if "investment-analysis/" in path else path
        old = inp.get("old_string", "")[:60]
        return f"{short} ({old}...)" if old else short
    if name == "Bash":
        cmd = inp.get("command", "")
        return cmd[:120]
    if name == "Glob":
        return inp.get("pattern", "")
    if name == "Grep":
        pattern = inp.get("pattern", "")
        path = inp.get("path", "")
        return f"/{pattern}/ in {path}" if path else f"/{pattern}/"
    if name == "WebSearch":
        return inp.get("query", "")
    if name == "WebFetch":
        return inp.get("url", "")[:100]
    # fallback: первые 100 символов JSON
    return json.dumps(inp, ensure_ascii=False)[:100]


def truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def process_line(line: str):
    """Обрабатывает одну JSON-строку stream-json."""
    line = line.strip()
    if not line:
        return

    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return

    event_type = event.get("type")
    message = event.get("message", {})
    content_list = message.get("content", [])

    if event_type == "assistant":
        for block in content_list:
            block_type = block.get("type")

            if block_type == "text":
                text = block.get("text", "").strip()
                if text:
                    wrapped = textwrap.fill(text, width=100, initial_indent="  ", subsequent_indent="  ")
                    print(f"{GREEN}{BOLD}Claude:{NC} {wrapped}")

            elif block_type == "tool_use":
                name = block.get("name", "?")
                inp = block.get("input", {})
                desc = format_tool_input(name, inp)
                print(f"{CYAN}  -> {name}:{NC} {desc}")

    elif event_type == "user":
        for block in content_list:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                content = block.get("content", "")
                is_error = block.get("is_error", False)
                if is_error:
                    short = truncate(str(content), TOOL_RESULT_MAX)
                    print(f"{YELLOW}  <- ERROR: {short}{NC}")
                # успешные результаты не выводим (слишком длинные)

    elif event_type == "result":
        # финальный результат сессии
        result_text = event.get("result", "")
        if result_text:
            print()
            print(f"{GREEN}{BOLD}=== Результат ==={NC}")
            print(result_text)

    elif event_type == "system":
        msg = event.get("message", "")
        subtype = event.get("subtype", "")
        if subtype == "init":
            session_id = event.get("session_id", "")
            print(f"{DIM}session: {session_id}{NC}")
        elif msg:
            print(f"{DIM}[system] {truncate(str(msg), 120)}{NC}")


def main():
    try:
        for line in sys.stdin:
            process_line(line)
    except KeyboardInterrupt:
        print(f"\n{DIM}[прервано]{NC}")
        sys.exit(0)


if __name__ == "__main__":
    main()
