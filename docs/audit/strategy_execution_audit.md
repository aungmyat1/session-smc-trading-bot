# Strategy Execution Audit

## Current Architecture

The active demo path is:

`scripts/run_strategy_demo.py` -> `scripts/run_st_a2_demo.py` -> `MT5Connector` -> `VantageDemoExecutor` -> `ST2Adapter` -> `TradeManager` -> `DemoTradeJournal` -> dashboard state in `logs/strategy_demo_state.json`

The ST-A2 strategy layer itself is:

`strategy/session_liquidity/session_strategy.py`

It orchestrates:

- HTF bias: `strategy/session_liquidity/bias_filter.py`
- Asian range / session filter: `strategy/session_liquidity/session_builder.py`
- Liquidity sweep detection: `strategy/session_liquidity/sweep_detector.py`
- Displacement / confirmation: `strategy/session_liquidity/displacement_detector.py`
- Signal build: `strategy/session_liquidity/entry_engine.py`

## Audit Findings

### Broken Components

1. Market-data access was not consistently abstracted.
   The repo already had a safe broker wrapper in `execution/metaapi_client.py`, but the active demo runner and some legacy data paths still fetched candles through direct MetaAPI account/connection calls.

2. Candle API compatibility was brittle.
   The observed failure `'RpcMetaApiConnectionInstance' object has no attribute 'get_candles'` is consistent with older fallback logic that assumed the RPC connection exposed `get_candles()`. The stable SDK surface in this repo is the account-level `get_historical_candles()` call.

3. Strategy config loading was incomplete.
   `strategies/adapters/st_a2_adapter.py` defaulted to the in-module `DEFAULT_CONFIG` and did not load the checked-in ST-A2 YAML plus portfolio overrides, so runtime behavior could drift from repo configuration.

4. Demo runner health state was too thin.
   The runner wrote `status` and `last_signal`, but not explicit `broker_status`, `strategy_status`, or `execution_status`, which made dashboard diagnostics weaker and blocked a simple `/health/demo` contract.

### Verified Healthy Components

1. ST-A2 signal generation logic is internally coherent and well tested.
   Existing tests already cover HTF bias, sweep detection, displacement confirmation, session gating, duplicate signal prevention, and minimum-SL filtering.

2. Execution and journal utilities are present and test-covered.
   `TradeManager`, `DemoTradeJournal`, `execution/order_manager.py`, and the risk modules already have strong local unit coverage.

3. Dashboard services were structurally healthy.
   The dashboard and live dashboard code were already able to present broker, order, and journal data once the runner state and candle path were repaired.

## Missing / Weak Dependencies

- `pytest` in this environment must be run with `-o addopts=''` because `pytest.ini` requires coverage plugins that are not installed here.
- The live demo path still depends on real MetaAPI credentials in `.env` for end-to-end broker validation.

## Repairs Implemented

1. Added a dedicated market-data abstraction in `execution/market_data.py`:
   - `MarketDataProvider`
   - `MetaApiMarketDataProvider`
   - `MockMarketDataProvider`
   - `ReplayMarketDataProvider`

2. Moved demo candle reads onto the provider abstraction through `execution/vantage_demo_executor.py`.

3. Hardened legacy candle retrieval in `data/forex_data.py` to prefer account-level `get_historical_candles()` before any connection fallback.

4. Updated `strategies/adapters/st_a2_adapter.py` to load:
   - `strategy/session_liquidity/config.yaml`
   - `config/config.json` session strategy overrides
   - `config/strategy_portfolio.yaml` ST-A2 parameter overrides

5. Extended runner state and dashboard health reporting with explicit:
   - `broker_status`
   - `strategy_status`
   - `execution_status`
   - `/health/demo`

## Recommended Follow-Ups

1. Move `scripts/run_portfolio.py` onto the same market-data provider abstraction for full consistency across demo runners.
2. Add a live credential smoke test job that only verifies broker connect + candle fetch, without placing orders.
3. Decide whether H1 should be a first-class ST-A2 input or remain validation-only; the current strategy logic still uses M15 + H4.
