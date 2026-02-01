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

.PHONY: help status check next research speculative trends opinions dashboard update-macro sector clean portfolio top export validate download download-moex download-all fill-governance fill-events fill-consensus fill-all

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
	@echo "$(GREEN)Данные:$(NC)"
	@echo "  make download-all  — скачать всё (smart-lab + MOEX)"
	@echo "  make download      — скачать финансы со smart-lab"
	@echo "  make download-moex — скачать рыночные данные с MOEX"
	@echo ""
	@echo "$(GREEN)Исследование доп. файлов (Claude):$(NC)"
	@echo "  make fill-governance TICKER=SBER — корп. управление"
	@echo "  make fill-events TICKER=SBER    — события и катализаторы"
	@echo "  make fill-consensus TICKER=SBER — консенсус аналитиков"
	@echo "  make fill-all TICKER=SBER       — всё вместе"
	@echo ""
	@echo "$(GREEN)Генерация (скрипты):$(NC)"
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
# ИССЛЕДОВАНИЕ ДОП. ФАЙЛОВ (Claude)
# ============================================================================

define CHECK_TICKER
ifndef TICKER
	@echo "$(RED)Ошибка: укажи тикер$(NC)"
	@echo "Использование: make $@ TICKER=SBER"
	@exit 1
endif
endef

fill-governance:
ifndef TICKER
	@echo "$(RED)Ошибка: укажи тикер. Использование: make fill-governance TICKER=SBER$(NC)"
	@exit 1
endif
	@echo "$(CYAN)Исследование корп. управления $(TICKER)...$(NC)"
	@claude $(CLAUDE_FLAGS) -p "Исследуй корпоративное управление компании $(TICKER) и заполни companies/$(TICKER)/governance.md по шаблону companies/_TEMPLATE/governance.md. \
	\
	Задача: найти и структурировать данные для расчёта GOD-дисконта. \
	\
	Порядок поиска: \
	1. Прочитай текущий companies/$(TICKER)/governance.md (если есть) — не потеряй существующие данные. \
	2. Прочитай companies/$(TICKER)/_index.md — возьми название компании, сектор. \
	3. Веб-поиск: '$(TICKER) структура акционеров крупнейшие акционеры 2025 2026'. Ищи долю государства (прямую и косвенную — через РФПИ, ВЭБ, Росимущество, госкорпорации). \
	4. Веб-поиск: '$(TICKER) дивидендная политика устав payout'. Найди текст дивидендной политики (% от ЧП МСФО/РСБУ), периодичность, стабильность выплат. \
	5. Веб-поиск: '$(TICKER) buyback обратный выкуп акций 2025 2026'. Есть ли программа, объём, сколько выкуплено. \
	6. Веб-поиск: '$(TICKER) казначейские акции квазиказначейские'. Доля на балансе компании, планы по гашению. \
	7. Веб-поиск: '$(TICKER) генеральный директор CEO CFO совет директоров 2025'. Ключевые лица, стаж. \
	8. Веб-поиск: '$(TICKER) допэмиссия сделки аффилированные лица корпоративные конфликты'. Красные флаги. \
	\
	Заполни все секции governance.md. Рассчитай GOD-дисконт в последней таблице. \
	Если данных нет — пиши 'не найдено', не выдумывай." | $(CLAUDE_LOG)

fill-events:
ifndef TICKER
	@echo "$(RED)Ошибка: укажи тикер. Использование: make fill-events TICKER=SBER$(NC)"
	@exit 1
endif
	@echo "$(CYAN)Исследование событий и катализаторов $(TICKER)...$(NC)"
	@claude $(CLAUDE_FLAGS) -p "Исследуй корпоративные события компании $(TICKER) и заполни companies/$(TICKER)/events.md по шаблону companies/_TEMPLATE/events.md. \
	\
	Задача: собрать последние события (6 мес.), предстоящие катализаторы, guidance менеджмента и санкционный статус. \
	\
	Порядок поиска: \
	1. Прочитай текущий companies/$(TICKER)/events.md (если есть) — не потеряй существующие данные. \
	2. Прочитай companies/$(TICKER)/_index.md — возьми название, сектор, текущий sentiment. \
	3. Веб-поиск: '$(TICKER) отчётность МСФО результаты 2025 2026'. Найди даты последних и предстоящих публикаций отчётности. \
	4. Веб-поиск: '$(TICKER) дивиденды 2025 2026 отсечка ГОСА'. Даты объявления дивидендов, размер, дата закрытия реестра. \
	5. Веб-поиск: '$(TICKER) новости корпоративные события 2025 2026'. Последние 6 месяцев: M&A, реструктуризация, смена менеджмента, IPO дочек, изменение стратегии. \
	6. Веб-поиск: '$(TICKER) прогноз менеджмента guidance стратегия'. Что менеджмент обещает по выручке, марже, CAPEX, долгу на 2026 год. \
	7. Веб-поиск: '$(TICKER) санкции SDN OFAC ЕС'. Санкционный статус: SDN-лист, секторальные санкции, влияние на бизнес. \
	8. Прочитай russia/macro.md — возьми даты ближайших заседаний ЦБ как потенциальные катализаторы для сектора. \
	\
	Для каждого события укажи влияние: позитив/негатив/нейтрально. \
	Для катализаторов укажи ожидаемую дату. \
	Если данных нет — пиши 'не найдено', не выдумывай." | $(CLAUDE_LOG)

fill-consensus:
ifndef TICKER
	@echo "$(RED)Ошибка: укажи тикер. Использование: make fill-consensus TICKER=SBER$(NC)"
	@exit 1
endif
	@echo "$(CYAN)Исследование консенсуса аналитиков $(TICKER)...$(NC)"
	@claude $(CLAUDE_FLAGS) -p "Исследуй консенсус-прогнозы аналитиков по компании $(TICKER) и заполни companies/$(TICKER)/consensus.md по шаблону companies/_TEMPLATE/consensus.md. \
	\
	Задача: собрать таргеты брокеров, forward-прогнозы прибыли и прогнозы дивидендов из открытых источников. Часть данных за пейволлом — бери то, что удаётся найти публично. \
	\
	Порядок поиска: \
	1. Прочитай текущий companies/$(TICKER)/consensus.md (если есть) — не потеряй существующие данные. \
	2. Прочитай companies/$(TICKER)/_index.md — возьми название, текущую цену, EPS. \
	3. Веб-поиск: '$(TICKER) целевая цена таргет аналитики 2025 2026'. Ищи таргеты от BCS, SberCIB, T-Investments, Финам, Альфа, ВТБ Капитал. \
	4. Веб-поиск: '$(TICKER) прогноз прибыли выручки 2026 consensus'. Ищи forward-оценки выручки, EBITDA, чистой прибыли. \
	5. Веб-поиск: '$(TICKER) прогноз дивидендов 2025 2026 DPS'. \
	6. Загрузи https://www.dohod.ru/ik/analytics/share/$(TICKER) — там бывают консенсус-данные. \
	7. Веб-поиск: '$(TICKER) analyst target price 2026' (англоязычные источники, если есть ADR/GDR). \
	8. Веб-поиск: 'site:bcs-express.ru $(TICKER) прогноз' — BCS публикует часть аналитики открыто. \
	9. Веб-поиск: 'site:finam.ru $(TICKER) прогноз консенсус'. \
	\
	Заполни таблицы. Рассчитай Forward P/E = текущая цена / консенсус EPS. \
	Укажи дату каждого прогноза — устаревшие (>3 мес.) пометь. \
	Если данные не найдены — оставь ячейку пустой, напиши 'данные за пейволлом' в примечаниях." | $(CLAUDE_LOG)

fill-all:
ifndef TICKER
	@echo "$(RED)Ошибка: укажи тикер. Использование: make fill-all TICKER=SBER$(NC)"
	@exit 1
endif
	@echo "$(CYAN)Полное исследование доп. файлов для $(TICKER)...$(NC)"
	@echo ""
	@$(MAKE) fill-governance TICKER=$(TICKER)
	@echo ""
	@$(MAKE) fill-events TICKER=$(TICKER)
	@echo ""
	@$(MAKE) fill-consensus TICKER=$(TICKER)

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

download-all:
	@echo "$(CYAN)Загрузка всех данных (smart-lab + MOEX)...$(NC)"
	@echo ""
ifdef TICKER
	@python3 scripts/download_smartlab.py $(TICKER)
	@echo ""
	@python3 scripts/download_moex.py $(TICKER)
else
	@python3 scripts/download_smartlab.py
	@echo ""
	@python3 scripts/download_moex.py
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
