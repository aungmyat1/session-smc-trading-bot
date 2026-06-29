# Vantage Demo — Broker Integration Checklist
# Last updated: 2026-06-29

Scope: Strategy demo stack connecting to Vantage MT5 demo account via MetaAPI Cloud SDK v29.
Account: d6f6eec3-96d5-4001-a802-62b3f4b49817 (cloud-g2, high reliability, full redundancy)

Status key:
  PASS(code)  — implemented and unit-tested; not yet confirmed live
  PASS(live)  — confirmed working against live broker session
  PARTIAL     — works but has a known limitation
  FAIL        — broken or missing
  UNVERIFIED  — code exists; live test not yet run

---

## Connection & Authentication

| # | Check | File | Status | Notes |
|---|-------|------|--------|-------|
| 1 | MetaAPI SDK import | execution/mt5_connector.py:67 | PASS(code) | `metaapi_cloud_sdk>=29` |
| 2 | Token from env (`METAAPI_TOKEN`) | mt5_connector.py:44 | PASS(code) | Fails fast with clear error if unset |
| 3 | Account ID from env (`VANTAGE_DEMO_METAAPI_ID`) | mt5_connector.py:46 | PASS(live) | UUID confirmed: d6f6eec3-… |
| 4 | Account deploy / wait_connected | mt5_connector.py:75–79 | PASS(live) | Deployed and connected 2026-06-24 |
| 5 | RPC connection init | mt5_connector.py:80–82 | PASS(live) | `get_rpc_connection()` + `wait_synchronized(60)` |
| 6 | Graceful disconnect | mt5_connector.py:86–98 | PASS(code) | `connection.close()` + `api.close()` |

## Reconnect Mechanism

| # | Check | File | Status | Notes |
|---|-------|------|--------|-------|
| 7  | Manual reconnect method | mt5_connector.py:100–105 | PASS(code) | `reconnect()` = disconnect + sleep(5) + connect |
| 8  | Auto-reconnect on data fetch failure | run_strategy_demo.py | PASS(code) | Triggers after 3 consecutive fetch fails |
| 9  | Heartbeat with reconnect fallback | mt5_connector.py:109–132 | PASS(code) | `heartbeat()` tries reconnect on failure |
| 10 | WebSocket timeout recovery | — | UNVERIFIED | Timeout occurred 2026-06-24 18:48; auto-reconnect not confirmed to recover |

**Known gap:** The 2026-06-24 runner died on a WebSocket timeout (MetaApi socket client failed to connect). The auto-reconnect was not yet wired in the runner at that time. It is now wired (commit c0706d4). Live confirmation needed.

## Market Data Feed

| # | Check | File | Status | Notes |
|---|-------|------|--------|-------|
| 11 | M15 candles fetch | vantage_demo_executor.py:53–69 | PASS(live) | `_account.get_historical_candles()` confirmed working |
| 12 | H4 candles fetch | vantage_demo_executor.py:53–69 | PASS(live) | Same method, different TF |
| 13 | Timeframe mapping | vantage_demo_executor.py:37–40 | PASS(code) | M5/M15/H1/H4 → SDK strings |
| 14 | EURUSD candle count ≥ 50 | run_strategy_demo.py | PASS(live) | 200-bar requests confirmed |
| 15 | GBPUSD candle count ≥ 50 | run_strategy_demo.py | PASS(live) | Same |
| 16 | XAUUSD candle support | vantage_demo_executor.py | UNVERIFIED | Symbol not yet tested; pip table now updated |
| 17 | Candle field mapping | vantage_demo_executor.py:60–67 | PASS(code) | open/high/low/close/tickVolume mapped |

## Spread Checking

| # | Check | File | Status | Notes |
|---|-------|------|--------|-------|
| 18 | Bid/ask price fetch | vantage_demo_executor.py:71–81 | PASS(live) | `get_symbol_price()` confirmed |
| 19 | Spread-in-pips calculation | vantage_demo_executor.py:76 | PASS(code) | `(ask-bid)/pip_size` |
| 20 | EURUSD max spread gate (1.5 pip) | run_strategy_demo.py | PASS(code) | Skips tick if exceeded |
| 21 | GBPUSD max spread gate (2.0 pip) | run_strategy_demo.py | PASS(code) | Skips tick if exceeded |
| 22 | XAUUSD pip size configured | vantage_demo_executor.py | PASS(code) | 0.1 pip size, $10/pip/lot |

## Order Placement

| # | Check | File | Status | Notes |
|---|-------|------|--------|-------|
| 23 | DEMO_ONLY guard on all writes | vantage_demo_executor.py:112–116 | PASS(code) | Returns simulated result if DEMO_ONLY=true |
| 24 | Market buy order | vantage_demo_executor.py:134–135 | UNVERIFIED | `create_market_buy_order()` — code ready, not live-tested |
| 25 | Market sell order | vantage_demo_executor.py:136–137 | UNVERIFIED | `create_market_sell_order()` — code ready, not live-tested |
| 26 | Magic number stamped (21099) | trade_manager.py | PASS(code) | All strategy demo orders get magic=21099 |
| 27 | Comment field set | vantage_demo_executor.py | PASS(code) | Uses strategy-specific comment text |
| 28 | Simulated order ID on DEMO_ONLY | vantage_demo_executor.py:131 | PASS(code) | `SIM-XXX-XXXXXX` format |

## Order Modification

| # | Check | File | Status | Notes |
|---|-------|------|--------|-------|
| 29 | Modify SL/TP | vantage_demo_executor.py:150–158 | UNVERIFIED | `modify_position()` — code ready, not live-tested |
| 30 | Emergency close single position | trade_manager.py:65–67 | UNVERIFIED | `close_position()` via RPC |
| 31 | Emergency close all strategy demo positions | trade_manager.py | UNVERIFIED | Filters by magic=21099, closes all |

## Stop Loss & Take Profit

| # | Check | File | Status | Notes |
|---|-------|------|--------|-------|
| 32 | SL passed to broker order | vantage_demo_executor.py:128 | PASS(code) | Included in `place_order(sl=sl)` |
| 33 | TP passed to broker order | vantage_demo_executor.py:128 | PASS(code) | Included in `place_order(tp=tp)` |
| 34 | SL/TP geometry validated pre-order | signal_router.py:82–94 | PASS(code) | BUY: sl<entry<tp | SELL: tp<entry<sl |
| 35 | SL tighter-of-two logic in strategy | strategy/session_liquidity/ | PASS(code) | 25% range vs sweep wick + 3pip |

## Position Tracking

| # | Check | File | Status | Notes |
|---|-------|------|--------|-------|
| 36 | Fetch open positions | vantage_demo_executor.py:93–108 | UNVERIFIED | `get_positions()` RPC call; not confirmed with real order |
| 37 | Filter positions by magic (21099) | trade_manager.py:75 | PASS(code) | Only ST-A2 positions returned |
| 38 | Position fields: id, symbol, direction, lots, entry, sl, tp, profit | vantage_demo_executor.py:96–108 | PASS(code) | All mapped |

## Account Information

| # | Check | File | Status | Notes |
|---|-------|------|--------|-------|
| 39 | Balance retrieval | vantage_demo_executor.py:83–90 | PASS(live) | Confirmed during 2026-06-24 session |
| 40 | Equity retrieval | vantage_demo_executor.py:85 | PASS(live) | Confirmed |
| 41 | Free margin retrieval | vantage_demo_executor.py:87 | PASS(live) | Confirmed |

---

## Summary

| Category | PASS(live) | PASS(code) | UNVERIFIED | FAIL | PARTIAL |
|----------|-----------|-----------|-----------|------|---------|
| Connection/Auth | 3 | 3 | 0 | 0 | 0 |
| Reconnect | 0 | 3 | 1 | 0 | 0 |
| Market Data | 4 | 2 | 1 | 0 | 0 |
| Spread Check | 1 | 4 | 0 | 0 | 0 |
| Order Placement | 0 | 5 | 3 | 0 | 0 |
| Order Modification | 0 | 0 | 3 | 0 | 0 |
| SL/TP | 0 | 4 | 0 | 0 | 0 |
| Position Tracking | 0 | 2 | 1 | 0 | 0 |
| Account Info | 3 | 0 | 0 | 0 | 0 |
| **TOTAL** | **11** | **23** | **9** | **0** | **0** |

**No FAIL items. 9 UNVERIFIED items require live order test (first demo trade clears most of them).**

---

## Pre-First-Trade Blockers

None. All code paths are implemented. UNVERIFIED items are cleared by running the first live demo order with `TRADING_MODE=demo` and `DEMO_ONLY=false`.

## Recommended Verification Sequence

1. Run `python3 scripts/health_check.py` — confirms connection, account info, data feed.
2. Start runner with `TRADING_MODE=shadow` for one London session — confirms signal generation.
3. Switch to `TRADING_MODE=demo` — first order clears items 24–31, 36.
4. After first close — confirms position tracking and journal write.
