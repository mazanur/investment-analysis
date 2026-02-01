# Investment Analysis Makefile
# Автоматизация задач с Claude Code
#
# Использование:
#   make help          — показать все команды
#   make status        — статистика базы знаний
#   make check         — проверить просроченные документы
#   make next          — заполнить следующую компанию-заглушку
#   make research TICKER=SBER  — исследовать компанию
#   make speculative   — найти спекулятивные идеи
#
# Автор: AlmazNurmukhametov

.PHONY: help status check next research speculative trends opinions dashboard update-macro sector clean portfolio top export validate download

# Цвета для вывода
GREEN  := \033[0;32m
YELLOW := \033[0;33m
RED    := \033[0;31m
CYAN   := \033[0;36m
NC     := \033[0m

TODAY := $(shell date +%Y-%m-%d)

# Общие флаги для Claude в автоматическом режиме
CLAUDE_FLAGS := --verbose --dangerously-skip-permissions --output-format stream-json
CLAUDE_LOG := python3 scripts/claude_log.py

help:
	@echo "$(CYAN)Investment Analysis — команды$(NC)"
	@echo ""
	@echo "$(GREEN)Информация:$(NC)"
	@echo "  make status        — статистика базы знаний (заполнено/заглушки)"
	@echo "  make check         — показать просроченные документы"
	@echo ""
	@echo "$(GREEN)Исследование (запускает Claude):$(NC)"
	@echo "  make next          — заполнить следующую компанию-заглушку"
	@echo "  make research TICKER=SBER  — исследовать конкретную компанию"
	@echo "  make sector SECTOR=finance — исследовать сектор"
	@echo "  make speculative   — найти спекулятивные идеи"
	@echo "  make update-macro  — обновить macro.md после заседания ЦБ"
	@echo ""
	@echo "$(GREEN)Данные и генерация (скрипты):$(NC)"
	@echo "  make download      — скачать финансы со smart-lab (все компании)"
	@echo "  make download TICKER=SBER — скачать для конкретной компании"
	@echo "  make trends        — сгенерировать trend.json для всех компаний"
	@echo "  make opinions      — сгенерировать opinions.md из Telegram"
	@echo "  make dashboard     — сгенерировать GitHub Pages дашборд"
	@echo ""
	@echo "$(GREEN)Аналитика:$(NC)"
	@echo "  make portfolio     — показать компании с position=buy"
	@echo "  make top           — топ-10 компаний по upside"
	@echo "  make export        — экспортировать данные в JSON"
	@echo ""
	@echo "$(GREEN)Прочее:$(NC)"
	@echo "  make validate      — проверить валидность _index.md"
	@echo "  make clean         — удалить временные файлы"

# ============================================================================
# ИНФОРМАЦИЯ
# ============================================================================

status:
	@echo "$(CYAN)═══════════════════════════════════════════════════════════════$(NC)"
	@echo "$(CYAN)  Статус базы знаний ($(TODAY))$(NC)"
	@echo "$(CYAN)═══════════════════════════════════════════════════════════════$(NC)"
	@echo ""
	@echo "$(GREEN)Компании:$(NC)"
	@total=$$(ls -d companies/*/ 2>/dev/null | wc -l | tr -d ' '); \
	filled=$$(grep -l "^sentiment:" companies/*/_index.md 2>/dev/null | wc -l | tr -d ' '); \
	stubs=$$((total - filled)); \
	echo "  Всего папок:    $$total"; \
	echo "  Заполнено:      $(GREEN)$$filled$(NC)"; \
	echo "  Заглушек:       $(YELLOW)$$stubs$(NC)"
	@echo ""
	@echo "$(GREEN)Секторы:$(NC)"
	@total=$$(ls -d sectors/*/ 2>/dev/null | wc -l | tr -d ' '); \
	filled=$$(grep -l "^sentiment:" sectors/*/_index.md 2>/dev/null | wc -l | tr -d ' '); \
	echo "  Всего:          $$total"; \
	echo "  Заполнено:      $(GREEN)$$filled$(NC)"
	@echo ""
	@echo "$(GREEN)trend.json:$(NC)"
	@trends=$$(ls companies/*/trend.json 2>/dev/null | wc -l | tr -d ' '); \
	echo "  Сгенерировано:  $$trends"
	@echo ""

check:
	@echo "$(CYAN)═══════════════════════════════════════════════════════════════$(NC)"
	@echo "$(CYAN)  Проверка обновлений ($(TODAY))$(NC)"
	@echo "$(CYAN)═══════════════════════════════════════════════════════════════$(NC)"
	@echo ""
	@python3 scripts/check_updates.py

# ============================================================================
# ИССЛЕДОВАНИЕ (Claude)
# ============================================================================

next:
	@echo "$(CYAN)Запуск Claude для заполнения следующей компании-заглушки...$(NC)"
	@claude $(CLAUDE_FLAGS) -p "Прочитай companies/RESEARCH_GUIDE.md и _index.md. Найди первую компанию-заглушку (без sentiment в _index.md) и заполни её по инструкции. После заполнения запусти make trends." | $(CLAUDE_LOG)

next1:
	@echo "$(CYAN)Запуск Claude для заполнения следующей компании-заглушки...$(NC)"
	@claude $(CLAUDE_FLAGS) -p "как меня можно назвать?  " | $(CLAUDE_LOG)

research:
ifndef TICKER
	@echo "$(RED)Ошибка: укажи тикер$(NC)"
	@echo "Использование: make research TICKER=SBER"
	@exit 1
endif
	@echo "$(CYAN)Запуск Claude для исследования $(TICKER)...$(NC)"
	@claude $(CLAUDE_FLAGS) -p "Прочитай companies/RESEARCH_GUIDE.md. Исследуй компанию $(TICKER) и заполни companies/$(TICKER)/_index.md по инструкции. После заполнения запусти make trends." | $(CLAUDE_LOG)

sector:
ifndef SECTOR
	@echo "$(RED)Ошибка: укажи сектор$(NC)"
	@echo "Использование: make sector SECTOR=finance"
	@echo "Доступные секторы: oil-gas, finance, it-telecom, retail, metals-mining, energy, construction, transport, agro, healthcare, manufacturing"
	@exit 1
endif
	@echo "$(CYAN)Запуск Claude для исследования сектора $(SECTOR)...$(NC)"
	@claude $(CLAUDE_FLAGS) -p "Прочитай sectors/RESEARCH_GUIDE.md. Исследуй сектор $(SECTOR) и обнови sectors/$(SECTOR)/_index.md по инструкции." | $(CLAUDE_LOG)

speculative:
	@echo "$(CYAN)Запуск Claude для поиска спекулятивных идей...$(NC)"
	@claude $(CLAUDE_FLAGS) -p "Прочитай companies/SPECULATIVE_GUIDE.md. Найди топ-3 спекулятивные идеи среди заполненных компаний (sentiment: bullish, position: buy/watch). Рассчитай Speculative Score и покажи результаты." | $(CLAUDE_LOG)

update-macro:
	@echo "$(CYAN)Запуск Claude для обновления macro.md...$(NC)"
	@claude $(CLAUDE_FLAGS) -p "Обнови russia/macro.md после последнего заседания ЦБ. Найди актуальную информацию о ставке, инфляции, прогнозах. Обнови таблицу заседаний и обнови _index.md." | $(CLAUDE_LOG)

# ============================================================================
# ДАННЫЕ И ГЕНЕРАЦИЯ (скрипты)
# ============================================================================

download:
ifdef TICKER
	@echo "$(CYAN)Загрузка данных со smart-lab для $(TICKER)...$(NC)"
	@python3 scripts/download_smartlab.py $(TICKER)
else
	@echo "$(CYAN)Загрузка данных со smart-lab для всех компаний...$(NC)"
	@python3 scripts/download_smartlab.py
endif

download-force:
ifdef TICKER
	@echo "$(CYAN)Загрузка данных со smart-lab для $(TICKER) (принудительно)...$(NC)"
	@python3 scripts/download_smartlab.py --force $(TICKER)
else
	@echo "$(CYAN)Загрузка данных со smart-lab (принудительно)...$(NC)"
	@python3 scripts/download_smartlab.py --force
endif

trends:
	@echo "$(CYAN)Генерация trend.json...$(NC)"
	@python3 scripts/generate_trend_json.py

opinions:
	@echo "$(CYAN)Генерация opinions.md...$(NC)"
	@echo "$(YELLOW)Для полной генерации сначала скачай посты:$(NC)"
	@echo "  python3 scripts/telegram_scraper.py investopit investopit_posts.json"
	@echo "  python3 scripts/filter_russia.py"
	@python3 scripts/generate_opinions.py

dashboard:
	@echo "$(CYAN)Генерация дашборда в docs/...$(NC)"
	@python3 scripts/generate_dashboard.py
	@echo "$(GREEN)Готово: открой docs/index.html в браузере$(NC)"

# ============================================================================
# АНАЛИТИКА
# ============================================================================

portfolio:
	@echo "$(CYAN)═══════════════════════════════════════════════════════════════$(NC)"
	@echo "$(CYAN)  Портфель (position: buy)$(NC)"
	@echo "$(CYAN)═══════════════════════════════════════════════════════════════$(NC)"
	@echo ""
	@for f in companies/*/_index.md; do \
		if grep -q "^position: buy" "$$f" 2>/dev/null; then \
			ticker=$$(grep "^ticker:" "$$f" | cut -d: -f2 | tr -d ' '); \
			sentiment=$$(grep "^sentiment:" "$$f" | cut -d: -f2 | tr -d ' '); \
			upside=$$(grep "^upside:" "$$f" | cut -d: -f2 | tr -d ' '); \
			price=$$(grep "^current_price:" "$$f" | cut -d: -f2 | tr -d ' '); \
			target=$$(grep "^my_fair_value:" "$$f" | cut -d: -f2 | tr -d ' '); \
			echo "  $(GREEN)$$ticker$(NC) — $$sentiment, upside: $$upside, цена: $$price → $$target"; \
		fi \
	done
	@echo ""

top:
	@echo "$(CYAN)═══════════════════════════════════════════════════════════════$(NC)"
	@echo "$(CYAN)  Топ-10 по upside$(NC)"
	@echo "$(CYAN)═══════════════════════════════════════════════════════════════$(NC)"
	@echo ""
	@python3 scripts/top_upside.py
	@echo ""

export:
	@echo "$(CYAN)Экспорт данных в data/export.json...$(NC)"
	@mkdir -p data
	@python3 scripts/export_data.py
	@echo "$(GREEN)Готово: data/export.json$(NC)"

# ============================================================================
# ПРОЧЕЕ
# ============================================================================

validate:
	@echo "$(CYAN)Проверка валидности _index.md...$(NC)"
	@python3 scripts/validate_index.py

clean:
	@echo "$(CYAN)Очистка временных файлов...$(NC)"
	@find . -name "*.pyc" -delete
	@find . -name "__pycache__" -delete
	@echo "$(GREEN)Готово$(NC)"
