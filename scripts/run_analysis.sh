#!/bin/bash
# Запуск анализа для тикеров из reports_new_tickers.txt
# Использование:
#   ./scripts/run_analysis.sh              # все тикеры из файла
#   ./scripts/run_analysis.sh LKOH         # начать с LKOH (пропустить предыдущие)
#   ./scripts/run_analysis.sh SBER LKOH    # только указанные тикеры

CYAN="\033[0;36m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
NC="\033[0m"

CLAUDE_FLAGS="--verbose --dangerously-skip-permissions --output-format stream-json"
CLAUDE_LOG="python3 scripts/claude_log.py"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
TICKERS_FILE="$BASE_DIR/reports_new_tickers.txt"

cd "$BASE_DIR"

if [ ! -s "$TICKERS_FILE" ]; then
    echo "Файл $TICKERS_FILE пуст или не найден."
    exit 1
fi

# Определяем список тикеров
if [ $# -gt 0 ]; then
    if [ $# -eq 1 ]; then
        # Один аргумент — начать с этого тикера
        START="$1"
        SKIP=true
        TICKERS=()
        while IFS= read -r ticker; do
            [ -z "$ticker" ] && continue
            if $SKIP; then
                if [ "$ticker" = "$START" ]; then
                    SKIP=false
                else
                    continue
                fi
            fi
            TICKERS+=("$ticker")
        done < "$TICKERS_FILE"
        if [ ${#TICKERS[@]} -eq 0 ]; then
            echo "Тикер $START не найден в $TICKERS_FILE"
            exit 1
        fi
    else
        # Несколько аргументов — только указанные тикеры
        TICKERS=("$@")
    fi
else
    # Без аргументов — все из файла
    TICKERS=()
    while IFS= read -r ticker; do
        [ -z "$ticker" ] && continue
        TICKERS+=("$ticker")
    done < "$TICKERS_FILE"
fi

TOTAL=${#TICKERS[@]}
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Анализ компаний с новыми отчётами ($TOTAL шт.)${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

for i in "${!TICKERS[@]}"; do
    ticker="${TICKERS[$i]}"
    num=$((i + 1))
    echo -e "${CYAN}═══ [$num/$TOTAL] Анализ $ticker ═══${NC}"
    claude $CLAUDE_FLAGS -p "Для компании $ticker вышел новый финансовый отчёт, Обнови анализ компании следуя методологии из companies/RESEARCH_GUIDE.md (фазы 0-8). После обновления запусти make trends && make dashboard." | $CLAUDE_LOG
    echo ""
done

echo -e "${GREEN}Готово! Обработано $TOTAL компаний.${NC}"
