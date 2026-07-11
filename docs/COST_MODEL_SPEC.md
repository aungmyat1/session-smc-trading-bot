# Cost Model Spec

`scripts/build_cost_models.py` derives cost profiles from `data/tick`.

Forex outputs live in `research/cost_models/<SYMBOL>.json` and include `spread_p50`, `spread_p90`, `spread_p99`, `asian_profile`, `london_profile`, and `newyork_profile`.

BTC outputs are `commission_model.yaml` and `slippage_model.yaml`. Public candle data cannot infer true venue-specific slippage, so the generated BTC slippage file is an explicit placeholder until aggregate trades are loaded.

Backtests consuming this dataset must report `gross_pnl`, `commission`, `spread_cost`, `slippage_cost`, and `net_pnl`.

