---
ticker: TICKER
updated: 2026-01-01
---

# Рыночные данные: Название (TIтCKER)

**Основные данные загружаются автоматически** в Investment API с MOEX ISS:

```bash
curl -X POST "$API_URL/jobs/fetch-moex?tickers=TICKER" -H "X-API-Key: $API_KEY"
```

Данные доступны через `GET /companies/TICKER` и содержат:
- Текущая цена (current_price)
- ADV за 30 дней (adv_rub_mln)
- Капитализация (market_cap) и число акций (shares_out)
- Free-float

## Данные, которых нет на MOEX (заполнять вручную)

```yaml
# Структура капитала (не доступно через API)
shares_preferred_mln: 0       # млн шт, привилегированные (0 если нет)

# Индексы (опционально)
moex_index_weight: 0           # %, вес в индексе МосБиржи (0 если не входит)
```

Казначейские акции — см. [governance.md](governance.md) (секция «Структура акционеров»).

### Где найти

- Привилегированные акции: moex.com (если есть TICKERP)
- Вес в индексе: https://www.moex.com/ru/index/IMOEX/constituents/
