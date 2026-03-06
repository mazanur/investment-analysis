---
ticker: SBER
updated: 2026-02-01
---

# Рыночные данные: Сбербанк (SBER)

**Основные данные загружаются автоматически** в Investment API с MOEX ISS:

```bash
curl -X POST "$API_URL/jobs/fetch-moex?tickers=SBER" -H "X-API-Key: $API_KEY"
```

Данные доступны через `GET /companies/SBER` и содержат:
- Текущая цена (current_price)
- ADV за 30 дней (adv_rub_mln)
- Капитализация (market_cap) и число акций (shares_out)
- Free-float

## Данные, которых нет на MOEX (заполнять вручную)

```yaml
# Структура капитала (не доступно через API)
shares_preferred_mln: 1000     # млн шт, привилегированные (SBERP торгуется отдельно)

# Индексы
moex_index_weight: 14.5        # %, вес в индексе МосБиржи (крупнейший компонент)
```

Казначейские акции — см. [governance.md](governance.md) (секция «Структура акционеров»).

### Где найти

- Привилегированные акции: moex.com (если есть TICKERP)
- Вес в индексе: https://www.moex.com/ru/index/IMOEX/constituents/
