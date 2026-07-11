# Market Regime Spec

`scripts/generate_market_regimes.py` writes `research/market_regimes/<SYMBOL>.parquet`.

Schema:

- `timestamp`
- `symbol`
- `regime`
- `volatility_score`
- `trend_score`

Labels include `TREND_LOW_VOL`, `TREND_HIGH_VOL`, `RANGE_LOW_VOL`, `RANGE_HIGH_VOL`, `LONDON_OPEN`, and `NEWYORK_OPEN`. `NEWS_WINDOW` is reserved for a future free news-calendar adapter.

