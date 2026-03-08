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

.PHONY: help status check next research speculative trends opinions dashboard update-macro sector clean portfolio top export validate download download-moex events fill-events download-all daily update-prices check-reports catalysts news-reaction sync sync-all deploy deploy-build deploy-logs deploy-restart deploy-ssh deploy-migrate

# Цвета для вывода
GREEN  := \033[0;32m
YELLOW := \033[0;33m
RED    := \033[0;31m
CYAN   := \033[0;36m
NC     := \033[0m

TODAY := $(shell date +%Y-%m-%d)

# Общие флаги для Claude в автоматическом режиме
CLAUDE_FLAGS := --verbose --allowedTools "Read Write Glob Grep Bash" --output-format stream-json
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
	@echo "  make news-reaction TICKER=EUTR — реакция на новость (trade signal)"
	@echo "  make update-macro  — обновить macro.md после заседания ЦБ"
	@echo ""
	@echo "$(GREEN)Данные и генерация (скрипты):$(NC)"
	@echo "  make download-all  — скачать финансы + рыночные данные (smart-lab + MOEX)"
	@echo "  make download      — скачать финансы со smart-lab"
	@echo "  make download-moex — скачать рыночные данные с MOEX"
	@echo "  make download TICKER=SBER — скачать для конкретной компании"
	@echo "  make events        — загрузить IR-календарь MOEX в API"
	@echo "  make fill-events   — сгенерировать events.md из API"
	@echo "  make trends        — сгенерировать trend.json для всех компаний"
	@echo "  make catalysts     — сгенерировать catalysts.json для всех компаний"
	@echo "  make opinions      — сгенерировать opinions.md из Telegram"
	@echo "  make dashboard     — сгенерировать GitHub Pages дашборд"
	@echo "  make sync TICKER=SBER — синхронизировать компанию в Investment API"
	@echo "  make sync-all      — синхронизировать все компании в API"
	@echo ""
	@echo "$(GREEN)Аналитика:$(NC)"
	@echo "  make portfolio     — показать компании с position=buy"
	@echo "  make top           — топ-10 компаний по upside"
	@echo "  make export        — экспортировать данные в JSON"
	@echo ""
	@echo "$(GREEN)Ежедневное обновление:$(NC)"
	@echo "  make daily         — обновить цены + trends + дашборд + коммит + пуш"
	@echo "  make update-prices — обновить цены с MOEX"
	@echo "  make check-reports — проверить новые отчёты + скачать + запустить анализ"
	@echo ""
	@echo "$(GREEN)Деплой (investment-api → сервер):$(NC)"
	@echo "  make deploy        — залить код и пересобрать на сервере"
	@echo "  make deploy-build  — пересобрать образ без заливки"
	@echo "  make deploy-restart— перезапустить контейнеры"
	@echo "  make deploy-logs   — показать логи приложения"
	@echo "  make deploy-migrate— применить миграции"
	@echo "  make deploy-ssh    — подключиться к серверу"
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

news-reaction:
ifndef TICKER
	@echo "$(RED)Ошибка: укажи тикер$(NC)"
	@echo "Использование: make news-reaction TICKER=EUTR"
	@echo "  С новостью: make news-reaction TICKER=EUTR NEWS_JSON='{...}'"
	@exit 1
endif
	@echo "$(CYAN)Обновление цены $(TICKER) через API...$(NC)"
	@curl -s -X POST "$(API_URL)/jobs/fetch-moex?tickers=$(TICKER)" -H "X-API-Key: $(API_KEY_VAL)" > /dev/null
	@curl -s -X POST "$(API_URL)/jobs/fetch-prices?tickers=$(TICKER)" -H "X-API-Key: $(API_KEY_VAL)" > /dev/null
	@echo ""
	@PROMPT=$$(FEEDER_URL=$(FEEDER_URL) API_URL=$(API_URL) python3 scripts/prepare_news_context.py $(TICKER) $(CURDIR) \
		$(if $(NEWS_JSON),--news-json '$(NEWS_JSON)',)); \
	if [ "$$PROMPT" = "SKIP" ]; then \
		echo "$(YELLOW)Skipped $(TICKER) (pre-filter)$(NC)"; \
	else \
		echo "$(CYAN)Запуск Claude (sonnet) для анализа $(TICKER)...$(NC)"; \
		cd /tmp && claude --model sonnet $(CLAUDE_FLAGS) -p "$$PROMPT"; \
	fi


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

download-moex:
ifdef TICKER
	@echo "$(CYAN)Загрузка рыночных данных с MOEX для $(TICKER)...$(NC)"
	@python3 scripts/download_moex.py $(TICKER)
else
	@echo "$(CYAN)Загрузка рыночных данных с MOEX для всех компаний...$(NC)"
	@python3 scripts/download_moex.py
endif

API_URL ?= https://investment-api.zagirnur.dev
FEEDER_URL ?= https://feeder.zagirnur.dev
API_KEY_VAL := $(shell grep '^API_KEY=' .env | head -1 | cut -d= -f2-)

events:
	@echo "$(CYAN)Загрузка IR-календаря MOEX в API...$(NC)"
ifdef TICKER
	@curl -s -X POST "$(API_URL)/jobs/fetch-events/$(TICKER)" -H "X-API-Key: $(API_KEY_VAL)" | python3 -m json.tool 2>/dev/null || true
endif
	@curl -s -X POST "$(API_URL)/jobs/fetch-ir-calendar" -H "X-API-Key: $(API_KEY_VAL)" | python3 -m json.tool 2>/dev/null || true

fill-events:
ifdef TICKER
	@python3 scripts/fill_events.py $(TICKER)
else
	@python3 scripts/fill_events.py
endif

download-all:
	@echo "$(CYAN)Загрузка данных (smart-lab + MOEX + цены)...$(NC)"
	@echo ""
ifdef TICKER
	@python3 scripts/download_smartlab.py $(TICKER)
	@echo ""
	@python3 scripts/download_moex.py $(TICKER)
	@echo ""
	@python3 scripts/check_reports.py $(TICKER)
else
	@python3 scripts/download_smartlab.py
	@echo ""
	@python3 scripts/download_moex.py
endif

trends:
	@echo "$(CYAN)Генерация trend.json...$(NC)"
	@python3 scripts/generate_trend_json.py

catalysts:
	@echo "$(CYAN)Генерация catalysts.json...$(NC)"
ifdef TICKER
	@python3 scripts/generate_catalysts.py $(TICKER)
else
	@python3 scripts/generate_catalysts.py
endif

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
# API SYNC
# ============================================================================

sync:
ifndef TICKER
	@echo "$(RED)Ошибка: укажи тикер$(NC)"
	@echo "Использование: make sync TICKER=SBER"
	@exit 1
endif
	@echo "$(CYAN)Синхронизация $(TICKER) в Investment API...$(NC)"
	@python3 scripts/sync_analysis.py $(TICKER)

sync-all:
	@echo "$(CYAN)Синхронизация всех компаний в Investment API...$(NC)"
	@python3 scripts/sync_analysis.py --all

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
# ЕЖЕДНЕВНОЕ ОБНОВЛЕНИЕ
# ============================================================================

update-prices:
	@echo "$(CYAN)Обновление цен через API...$(NC)"
	@curl -s -X POST "$(API_URL)/jobs/fetch-moex" -H "X-API-Key: $(API_KEY_VAL)" | python3 -m json.tool
	@curl -s -X POST "$(API_URL)/jobs/fetch-prices" -H "X-API-Key: $(API_KEY_VAL)" | python3 -m json.tool

daily:
	@echo "$(CYAN)═══════════════════════════════════════════════════════════════$(NC)"
	@echo "$(CYAN)  Ежедневное обновление ($(TODAY))$(NC)"
	@echo "$(CYAN)═══════════════════════════════════════════════════════════════$(NC)"
	@echo ""
	@echo "$(CYAN)[1/5] Обновление цен через API...$(NC)"
	@curl -s -X POST "$(API_URL)/jobs/fetch-moex" -H "X-API-Key: $(API_KEY_VAL)" | python3 -m json.tool
	@curl -s -X POST "$(API_URL)/jobs/fetch-prices" -H "X-API-Key: $(API_KEY_VAL)" | python3 -m json.tool
	@curl -s -X POST "$(API_URL)/jobs/fetch-prices?tickers=IMOEX" -H "X-API-Key: $(API_KEY_VAL)" | python3 -m json.tool
	@echo ""
	@echo "$(CYAN)[2/5] Генерация trend.json...$(NC)"
	@python3 scripts/generate_trend_json.py
	@echo ""
	@echo "$(CYAN)[3/5] Генерация catalysts.json...$(NC)"
	@python3 scripts/generate_catalysts.py
	@echo ""
	@echo "$(CYAN)[4/5] Генерация дашборда...$(NC)"
	@python3 scripts/generate_dashboard.py
	@echo ""
	@echo "$(CYAN)[5/5] Коммит и пуш...$(NC)"
	@git add companies/*/_index.md companies/*/trend.json companies/*/data/catalysts.json docs/
	@git commit -m "daily: update prices and dashboard ($(TODAY))" || echo "$(YELLOW)Нет изменений для коммита$(NC)"
	@git push || echo "$(RED)Пуш не удался$(NC)"
	@echo ""
	@echo "$(GREEN)Готово!$(NC)"

check-reports:
	@echo "$(CYAN)═══════════════════════════════════════════════════════════════$(NC)"
	@echo "$(CYAN)  Проверка новых отчётов ($(TODAY))$(NC)"
	@echo "$(CYAN)═══════════════════════════════════════════════════════════════$(NC)"
	@echo ""
	@python3 scripts/check_reports.py --download
	@echo ""
	@if [ -s reports_new_tickers.txt ]; then \
		echo "$(CYAN)Запуск анализа для компаний с новыми отчётами...$(NC)"; \
		echo ""; \
		while IFS= read -r ticker; do \
			[ -z "$$ticker" ] && continue; \
			echo "$(CYAN)═══ Анализ $$ticker ═══$(NC)"; \
		claude $(CLAUDE_FLAGS) -p "Для компании $$ticker вышел новый финансовый отчёт. Обнови анализ компании следуя методологии из companies/RESEARCH_GUIDE.md (фазы 0-8). После обновления запусти make trends && make dashboard." < /dev/null | $(CLAUDE_LOG); \
			echo ""; \
		done < reports_new_tickers.txt; \
	else \
		echo "$(GREEN)Новых отчётов нет, анализ не требуется.$(NC)"; \
	fi

# ============================================================================
# ДЕПЛОЙ (investment-api → сервер)
# ============================================================================

# Настройки сервера (из .env)
SSH_HOST := $(shell grep '^SSH_HOST=' .env | head -1 | cut -d= -f2-)
SSH_USER := $(shell grep '^SSH_USER=' .env | head -1 | cut -d= -f2-)
SSH_PASS := $(shell grep '^SSH_PASSWORD=' .env | head -1 | cut -d= -f2-)
REMOTE_DIR := /opt/investment-api
SSH_CMD := SSHPASS='$(SSH_PASS)' sshpass -e ssh -o StrictHostKeyChecking=accept-new $(SSH_USER)@$(SSH_HOST)
SCP_CMD := SSHPASS='$(SSH_PASS)' sshpass -e scp -o StrictHostKeyChecking=accept-new

deploy:
	@echo "$(CYAN)Заливка investment-api на сервер...$(NC)"
	@echo ""
	@echo "$(CYAN)[1/3] Копирование файлов...$(NC)"
	@$(SCP_CMD) -r investment-api/app investment-api/alembic investment-api/alembic.ini investment-api/pyproject.toml investment-api/Dockerfile investment-api/entrypoint.sh investment-api/docker-compose.yml $(SSH_USER)@$(SSH_HOST):$(REMOTE_DIR)/
	@echo "$(GREEN)Файлы скопированы$(NC)"
	@echo ""
	@echo "$(CYAN)[2/3] Пересборка образа...$(NC)"
	@$(SSH_CMD) 'cd $(REMOTE_DIR) && docker compose build app'
	@echo ""
	@echo "$(CYAN)[3/3] Перезапуск...$(NC)"
	@$(SSH_CMD) 'cd $(REMOTE_DIR) && docker compose up -d app'
	@echo ""
	@echo "$(GREEN)Деплой завершён!$(NC)"
	@$(SSH_CMD) 'docker ps --filter name=investment-api --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"'

deploy-build:
	@echo "$(CYAN)Пересборка образа на сервере...$(NC)"
	@$(SSH_CMD) 'cd $(REMOTE_DIR) && docker compose build app && docker compose up -d app'

deploy-restart:
	@echo "$(CYAN)Перезапуск контейнеров...$(NC)"
	@$(SSH_CMD) 'cd $(REMOTE_DIR) && docker compose restart'

deploy-logs:
	@$(SSH_CMD) 'docker logs investment-api-app-1 --tail 50'

deploy-migrate:
	@echo "$(CYAN)Применение миграций...$(NC)"
	@$(SSH_CMD) 'docker exec investment-api-app-1 alembic upgrade head'

deploy-ssh:
	@SSHPASS='$(SSH_PASS)' sshpass -e ssh -o StrictHostKeyChecking=accept-new $(SSH_USER)@$(SSH_HOST)

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
