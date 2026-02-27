---
ticker: SBER
updated: 2026-02-01
---

# Рыночные данные: Сбербанк (SBER)

**Основные данные загружаются автоматически** с MOEX ISS API:

```bash
make download-moex TICKER=SBER       # скачать для одной компании
make download-moex                   # скачать для всех
```

Файл сохраняется в `data/moex_market.json` и содержит:
- Текущая цена (last, bid, offer, open, high, low)
- Объём торгов и ADV за 30 дней (в рублях)
- Bid-ask спред (%)
- Капитализация и число акций
- 52-недельный диапазон (high/low)

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
