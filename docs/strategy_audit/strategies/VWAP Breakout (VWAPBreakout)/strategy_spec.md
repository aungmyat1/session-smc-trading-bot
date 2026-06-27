# Strategy: VWAP Breakout (VWAPBreakout)

## Version / Status

- **Version:** unversioned (no version field in source)
- **Status:** SHADOW — observe only, no broker orders placed
- **Execution mode (config):** `shadow` (`config/strategy_portfolio.yaml`, strategies.VWAPBreakout.execution_mode)
- **Risk tier:** tier3 (`core/portfolio_manager.py:33`)
- **Phase:** Unvalidated — Phase-0 backtest not yet run

## Description

Session-scoped VWAP (Volume-Weighted Average Price) cross strategy with volume confirmation. Fires a BUY signal when price crosses upward through the session VWAP and a SELL signal on a downward cross, provided the current bar's volume is at least 1.3x the session average. Active only during London (07:00–10:00 UTC) and New York (13:00–16:00 UTC) sessions.

The strategy is self-contained in a single adapter file (`strategies/adapters/vwap_adapter.py`). There is no separate strategy module; all logic — session detection, VWAP calculation, volume check, signal construction — lives in `VWAPBreakoutAdapter.generate_signal()`.

## Trading Philosophy

Price crossing its session VWAP with above-average volume indicates genuine institutional participation rather than noise. The VWAP acts as a dynamic fair-value anchor within each session; a clean cross with volume expansion suggests a directional move is likely to follow.

## Market / Timeframe / Session / Direction

| Attribute | Value |
|---|---|
| Instruments | EURUSD, GBPUSD (from `config/strategy_portfolio.yaml`) |
| Timeframe | 15-minute candles (M15) |
| Sessions | London 07:00–09:59 UTC, New York 13:00–15:59 UTC |
| Direction | Both (BUY on bullish cross, SELL on bearish cross) |
| Order type | MARKET |

## Signal Chain (phase-by-phase, in execution order)

1. **Data guard** — reject if fewer than 20 M15 bars supplied (`_MIN_BARS = 20`)
2. **Session gate** — reject if current UTC hour is outside London (7–9) or NY (13–15) ranges
3. **Session bar extraction** — select only bars whose `time` attribute falls in the current session; fall back to the last 20 bars if fewer than 5 session bars exist with datetime timestamps
4. **Minimum session bar guard** — reject if fewer than 5 session bars after extraction
5. **VWAP calculation** — compute cumulative (typical_price × volume) / cumulative_volume over session bars
6. **Guard: zero VWAP or zero avg_vol** — reject if either is zero
7. **Volume confirmation** — reject if current bar's volume < 1.3× session average volume
8. **Direction determination** — check prev close vs VWAP vs current close for bullish or bearish cross
9. **Signal construction** — build `Signal` with SL, TP, risk_percent, confidence, and metadata

## Entry Rules

| Rule | Detail |
|---|---|
| Bullish cross | `prev_close < vwap < current_close` |
| Bearish cross | `prev_close > vwap > current_close` |
| Entry price | Current bar's `close` (market order) |
| Volume gate | `current_volume >= session_avg_volume * 1.3` |

## Confirmation Rules

The only confirmation is the volume gate (`vol >= avg_vol * 1.3`). There is no HTF bias filter, no spread filter, no structural confirmation (no CHoCH/BOS/FVG), and no ATR/volatility filter within the adapter itself. Spread filtering is applied upstream in `scripts/run_portfolio.py` before `generate_signal` is called.

## Exit Rules (TP / SL / BE / Trailing / Partial)

All exits are defined at signal construction time. There is no trade management, BE move, trailing, or partial close logic inside this adapter.

| Parameter | BUY | SELL |
|---|---|---|
| Stop Loss | `low - 5 pips` (`low - 5 * 0.0001`) | `high + 5 pips` (`high + 5 * 0.0001`) |
| Take Profit | `entry + (entry - SL) * 1.5` (1.5 R) | `entry - (SL - entry) * 1.5` (1.5 R) |
| Risk-Reward | Fixed 1.5 R | Fixed 1.5 R |
| BE / Trailing | None — not implemented in adapter | None |
| Partial close | None — not implemented in adapter | None |

Note: the `pip` constant is hardcoded as `0.0001` (4-decimal pairs only; JPY pairs would require `0.01`).

## Filters (Spread / Volatility / Session / News)

| Filter | Location | Detail |
|---|---|---|
| Spread | `scripts/run_portfolio.py:193` | EURUSD ≤ 1.5 pip, GBPUSD ≤ 2.0 pip — applied before signal generation |
| Session | `vwap_adapter.py:58–60` | Hard-coded London/NY only |
| Volume | `vwap_adapter.py:85` | Current bar ≥ 1.3× session average |
| Minimum bars | `vwap_adapter.py:54` | Total bars ≥ 20; session bars ≥ 5 |
| Volatility | None | No ATR/spread-based volatility filter |
| News | None | No news filter |

## Kill Switch / Safety

The adapter itself contains no kill switch. Safety is enforced by the surrounding portfolio infrastructure:

| Layer | Mechanism | Reference |
|---|---|---|
| Execution mode | `shadow` — no broker orders placed | `config/strategy_portfolio.yaml:54` |
| Shadow tracker | All signals written to `logs/shadow_trades.jsonl`, `executed: false` | `strategies/shadow_tracker.py` |
| Portfolio loss limits | Daily 2%, weekly 5%, monthly 8% — tick skipped on breach | `core/portfolio_manager.py:117–129` |
| Circuit breaker | Max 6 signals/hr, max 4 trades/day, max 4 consecutive losses → 4h cooldown | `core/circuit_breaker.py` |
| Signal router | TTL expiry (300s), geometry validation, BUY+SELL conflict rejection | `core/signal_router.py` |
| Live mode block | `--mode live` exits with code 1; `LIVE_TRADING=False` enforced by `CLAUDE.md §0` | `scripts/run_portfolio.py:387–393` |

## Known Limitations

1. **No HTF bias filter.** Signals fire regardless of 4H/1H trend direction. Other strategies (ST-A2, AdaptiveSMC) consume H4 data; VWAPBreakout does not.
2. **Pip value hardcoded to 0.0001.** Only valid for 4-decimal pairs (EURUSD, GBPUSD). Would silently produce wrong SL/TP for JPY pairs even though the portfolio config lists EURUSD/GBPUSD only.
3. **No spread filter inside adapter.** The adapter accepts whatever data it is given; spread rejection is entirely in the runner. If called directly (e.g., in backtest), spread is not applied.
4. **VWAP uses volume=1 fallback.** `c.get("volume", 1)` — if volume data is absent, VWAP degrades to a simple arithmetic mean of typical price. The volume confirmation check (step 7) then compares `vol=0` against `avg_vol` derived from those fallback values, and will reject the signal since `0 < avg_vol * 1.3`. This may silently suppress valid signals when broker volume is unavailable.
5. **Session bar fallback is lossy.** If fewer than 5 bars have a datetime `time` field, the code falls back to `m15[-20:]`, which may span multiple sessions or even days.
6. **One signal per tick, no "one per session" enforcement.** The strategy generates at most one signal per `generate_signal()` call, but there is no state maintained between calls. If called on every 60-second tick, it can fire on consecutive ticks as long as the cross condition persists.
7. **Confidence can be 0.0.** `confidence = min(1.0, vol/avg_vol - 1.0)`: when `vol/avg_vol` is exactly 1.3 (the minimum), confidence = 0.3. But if `avg_vol` is very large and `vol` barely exceeds 1.3×, confidence approaches 0.3 — still valid. However if somehow `vol == avg_vol * 1.3` exactly, `vol/avg_vol - 1.0 = 0.3`, so minimum real-world confidence is ~0.3, which is below the portfolio's `min_confidence: 0.70` for VWAPBreakout. Signals with `confidence < 0.70` will be filtered out by PortfolioManager.
8. **Not backtest-validated.** Phase-0 gate has not been run. The strategy is in shadow mode pending validation.

## Dependencies (modules, external)

| Dependency | Type | Used for |
|---|---|---|
| `core.base_strategy.BaseStrategy` | Internal | Abstract interface; adapter inherits from it |
| `core.signal.Signal` | Internal | Return type of `generate_signal` |
| `datetime`, `timezone` | stdlib | Current time, session detection, bar timestamp parsing |
| `typing.Optional` | stdlib | Return type annotation |
| `scripts/run_portfolio.py` | Internal (caller) | Invokes `generate_signal`, provides M15 data and spread |
| `core/signal_router.py` | Internal (downstream) | Validates signal geometry and TTL |
| `core/circuit_breaker.py` | Internal (downstream) | Rate-limits signals |
| `core/portfolio_manager.py` | Internal (downstream) | Applies min_confidence (0.70), correlation filter, trade caps |
| `strategies/shadow_tracker.py` | Internal (downstream) | Logs signals without execution |
| `config/strategy_portfolio.yaml` | Config | Pairs, execution_mode, min_confidence, enabled flag |
| No external pip packages | — | Strategy is pure Python |
# VWAP Breakout

## Overview

`VWAPBreakout` is a compatibility alias for `VWAPMeanReversion`. The adapter class keeps the older name for import stability, but the emitted signal identity remains `VWAPMeanReversion`.

## Audit Status

- Catalog status: `shadow`
- Approval: `false`
- Version: `0.3`
- Deployment target: `shadow`

## Runtime Behavior

- The alias uses the same underlying code path as `VWAPMeanReversion`.
- The alias exists for backward compatibility only.
- No separate trading logic is defined here.
