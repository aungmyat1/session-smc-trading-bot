# Strategy: London Breakout

## Version / Status

- Version: Adaptive Session Engine v1
- Portfolio tier: Tier 2 (demo execution phase)
- Execution mode: `demo` (config/strategy_portfolio.yaml, line 30)
- Live trading: BLOCKED — `CONFIRM-LIVE-ON` required (CLAUDE.md §6)
- Backtest status: NOT validated against Phase-0 gate (no entry in docs/VERDICT_LOG.md referencing this strategy)

## Description

Asian session range breakout strategy for forex. Builds a range from M15 OHLCV bars
covering 00:00–06:00 UTC (Asian session), validates the range width in pips, then
monitors London session (06:00–09:00 UTC) for a breakout close beyond the range
boundary. A signal fires only after a subsequent retest candle pulls back into a
defined retest zone around the broken level. One signal maximum per session.

## Trading Philosophy

Price consolidates during the Asian session forming a tight range. Institutional
order flow at the London open tends to sweep liquidity above or below that range.
The breakout-then-retest pattern filters out false breaks: entry waits for price to
return to the broken level (confirming it as support/resistance) before triggering.
This avoids chasing the initial breakout candle.

## Market / Timeframe / Session / Direction

| Attribute    | Value                                              |
|--------------|----------------------------------------------------|
| Instruments  | EURUSD, GBPUSD, USDJPY (config: adaptive_engine.yaml line 6-9; strategy_portfolio.yaml line 32) |
| Timeframe    | M15 only                                           |
| Session      | London: 06:00–09:00 UTC (breakout + retest window) |
| Range source | Asian: 00:00–06:00 UTC (exclusive end)             |
| Direction    | LONG or SHORT (bidirectional; first qualifying breakout wins) |

## Signal Chain (phase-by-phase, in execution order)

**Phase 1 — Asian Range Build**
Collect all M15 bars where `00 <= utc_hour < 06`. Compute `asian_high = max(bar.high)`,
`asian_low = min(bar.low)`. If no bars fall in the Asian window, return empty (no signal).

**Phase 2 — Range Validation**
Compute range in pips: `(asian_high - asian_low) / pip_size`. Gate: `15.0 <= range_pips <= 50.0`.
If outside bounds, return empty.

**Phase 3 — London Breakout Detection**
Scan London bars (`06 <= utc_hour <= 09`) in chronological order. On each bar:
- If no breakout yet: check if `close > asian_high` (LONG) or `close < asian_low` (SHORT).
  Record breakout direction and bar, then advance to next candle.
- At most one breakout direction is tracked at a time.

**Phase 4 — Retest Confirmation**
On bars after the breakout bar:
- LONG: low of bar must satisfy `(asian_high - 2*pip) <= low <= (asian_high + 0.3*pip)`.
- SHORT: high of bar must satisfy `(asian_low - 0.3*pip) <= high <= (asian_low + 2*pip)`.
- When retest condition is met, compute entry/SL/TP and emit signal.

**Phase 5 — Signal Emission**
Emit one `AdaptiveSignal`. Reset `breakout_direction = None` (one signal per session
enforced by state reset on emit).

## Entry Rules

- Entry price: `candle["close"]` of the retest bar (not the breakout bar).
- Order type: MARKET (set in LondonBreakoutAdapter, line 57).
- No pending/limit order logic exists; entry is at close of retest candle.

## Confirmation Rules

There is no separate confirmation layer beyond the retest zone check. The strategy
sets `metadata["structure_confirmed"] = True` and `metadata["liquidity_swept"] = False`
unconditionally on every emitted signal (london_breakout_strategy.py, lines 147-149
and 177-179). These flags are consumed by the signal scorer:

- `structure_confirmed = True` always awards 2 points (signal_scorer.py line 115-116).
- `liquidity_swept = False` never awards the 2-point liquidity bonus.

Maximum achievable score for a London Breakout signal is therefore 8/10
(structure:2 + active_session:1 + spread:1 + volatility:1 + news:1 = 6, plus
htf_bias if aligned:2). Minimum pass threshold is 7/10.

## Exit Rules (TP / SL / BE / Trailing / Partial)

| Rule       | Detail                                                                 |
|------------|------------------------------------------------------------------------|
| Stop Loss  | LONG: `asian_low - 1 pip`; SHORT: `asian_high + 1 pip`                |
| Take Profit | Fixed R-multiple: `risk * TP_RR` where `TP_RR = 1.5` (hardcoded line 39, also in adaptive_engine.yaml line 41) |
| Breakeven  | Not implemented in strategy layer                                      |
| Trailing   | Not implemented in strategy layer                                      |
| Partial TP | Not implemented in strategy layer                                      |
| Session close | No forced session-end close logic in this strategy                  |

Exit management is delegated to the downstream execution/trade_manager layer.
The strategy only sets entry, SL, and TP levels.

## Filters (Spread / Volatility / Session / News)

Filters are applied by the signal scoring layer (`adaptive/engine/signal_scorer.py`),
not within the strategy itself. The adapter layer adds a minimum bar count check.

| Filter              | Threshold                       | Location                                 | Notes                                  |
|---------------------|---------------------------------|------------------------------------------|----------------------------------------|
| Min M15 bars        | 30 bars                         | london_breakout_adapter.py line 36       | Guards against insufficient history   |
| Asian range min     | 15 pips                         | london_breakout_strategy.py line 36      | Hardcoded; also in adaptive_engine.yaml line 40 |
| Asian range max     | 50 pips                         | london_breakout_strategy.py line 37      | Hardcoded; also in adaptive_engine.yaml line 41 |
| Max spread EURUSD   | 1.5 pips                        | signal_scorer.py line 19; adaptive_engine.yaml line 20 | Applied at score stage |
| Max spread GBPUSD   | 2.0 pips                        | signal_scorer.py line 20                 |                                        |
| Max spread USDJPY   | 2.0 pips                        | signal_scorer.py line 21                 |                                        |
| Max spread (regime) | 3.0 pips → UNSAFE               | regime_detector.py line 22               | Causes REGIME_BLOCKED before scoring  |
| Max ATR%            | 0.8% of price                   | signal_scorer.py line 25; adaptive_engine.yaml line 25 |                        |
| Min ATR%            | 0.1% of price                   | signal_scorer.py line 26; adaptive_engine.yaml line 26 |                        |
| Allowed regimes     | BREAKOUT, RANGING               | trade_router.py line 37                  | TRENDING or UNSAFE → REGIME_MISMATCH  |
| Active session gate | London 06-09 UTC                | signal_scorer.py line 29-30              | Scoring only; not a hard block        |
| News filter         | `news_event` context flag       | signal_scorer.py line 127-128            | Stub always returns safe (news_filter.py line 43) |
| Min signal score    | 7/10                            | signal_scorer.py line 15                 | Hard rejection threshold              |
| Min confidence      | 0.60                            | strategy_portfolio.yaml line 33          | Checked by PortfolioManager           |

Portfolio-level filters (run_portfolio.py):

| Filter            | Value                  | Location                          |
|-------------------|------------------------|-----------------------------------|
| Max spread (run)  | EURUSD:1.5, GBPUSD:2.0, USDJPY:1.5 | run_portfolio.py line 125 |
| Min M15 bars (run)| 50                     | run_portfolio.py line 195         |

## Kill Switch / Safety

| Control                  | Value      | Location                                | Notes |
|--------------------------|------------|-----------------------------------------|-------|
| DRY_RUN default          | True       | demo_executor.py line 23; trade_router.py line 82 | Live execution raises NotImplementedError |
| LIVE mode block          | Hard exit  | run_portfolio.py lines 387-393          | `sys.exit(1)` if mode=live |
| Daily loss halt          | 1.5%       | risk_manager.py DEFAULT_CONFIG line 27  | Halts entire adaptive engine risk state |
| Max trades/day (adaptive)| 6          | risk_manager.py DEFAULT_CONFIG line 28; adaptive_engine.yaml line 14 | |
| Max consecutive losses   | 3          | risk_manager.py DEFAULT_CONFIG line 29  | Triggers halt |
| Correlation guard        | EURUSD+GBPUSD same direction blocked | risk_manager.py lines 51-62 | LONG+LONG only |
| CircuitBreaker signals/hr| 3 (LondonBreakout) | circuit_breaker.py config example line 13 | Default if unconfigured: 6 |
| CircuitBreaker trades/day| 3 (LondonBreakout) | circuit_breaker.py config example line 14 | Default if unconfigured: 4 |
| CircuitBreaker cooldown  | 4 hours    | circuit_breaker.py line 31             | After max_losses hit |
| Portfolio max open       | 3 positions| strategy_portfolio.yaml line 8          |       |
| Portfolio daily loss     | 2.0%       | strategy_portfolio.yaml line 9          |       |
| Portfolio weekly loss    | 5.0%       | strategy_portfolio.yaml line 10         |       |
| Portfolio monthly loss   | 8.0%       | strategy_portfolio.yaml line 11         |       |

## Known Limitations

1. **No liquidity_swept flag**: `metadata["liquidity_swept"]` is hardcoded to `False`,
   so the 2-point liquidity bonus in the signal scorer is never awarded. Maximum
   achievable score is 8/10, not 10/10. This means HTF bias alignment is required
   for the signal to pass (score 7+). Without HTF bias, the highest possible score is
   6/10, which will always be rejected.

2. **One signal per session cap**: once a signal is emitted, `breakout_direction` resets
   to None and no further signals are generated for that session, even if a second
   valid breakout occurs in a different direction later in the London window.

3. **No HTF bias computation in strategy**: `structure_confirmed = True` is hardcoded;
   HTF bias must be supplied externally via the `context` dict or the signal scores ≤ 6.

4. **Retest zone asymmetry**: LONG retest window is `ah - 2*pip` to `ah + 0.3*pip`
   (2.3 pip total width). SHORT retest window is `al - 0.3*pip` to `al + 2*pip` (same
   2.3 pip width). The 2-pip buffer extends downward for LONG (below the broken high)
   and upward for SHORT (above the broken low). This is not documented or explained.

5. **Timestamp from retest candle, not signal time**: `timestamp` in the emitted signal
   is the candle's own timestamp (`ts_str`), not the wall-clock time of detection.
   The adapter overwrites this with `datetime.now(timezone.utc).isoformat()` (adapter
   line 51), causing a discrepancy between signal candle time and adapter emission time.

6. **No Phase-0 backtest**: strategy has not been validated against the n≥50 / net PF>1.0
   gate required by CLAUDE.md §3 before demo execution.

7. **USDJPY pip size used for adapter confidence**: `_PIP` in adapter includes USDJPY=0.01
   but the strategy's `_PIP_SIZE` dict does not include XAUUSD. The adapter's `_PIP` dict
   adds XAUUSD=0.1 (adapter line 14) but the underlying strategy would use the default
   0.0001 fallback for XAUUSD, giving incorrect range calculations for that pair.
   (XAUUSD is not in any active pair list, so this is latent.)

## Dependencies (modules, external)

**Internal modules:**

| Module | Role |
|--------|------|
| `adaptive/strategies/__init__.py` | `AdaptiveSignal` dataclass |
| `adaptive/strategies/london_breakout_strategy.py` | Core signal generation |
| `strategies/adapters/london_breakout_adapter.py` | Bridge to `core.Signal` |
| `core/base_strategy.py` | Abstract base class |
| `core/signal.py` | `Signal` dataclass consumed by execution layer |
| `adaptive/engine/trade_router.py` | Regime + score + risk approval pipeline |
| `adaptive/engine/regime_detector.py` | ADX/ATR market regime classification |
| `adaptive/engine/signal_scorer.py` | 0-10 point scoring |
| `adaptive/engine/risk_manager.py` | Intra-day risk state (adaptive engine path) |
| `adaptive/filters/news_filter.py` | News stub (always safe) |
| `adaptive/execution/demo_executor.py` | Dry-run execution interface |
| `core/circuit_breaker.py` | Per-strategy rate + loss limit (portfolio path) |
| `core/portfolio_manager.py` | Portfolio-level limits + correlation |
| `core/signal_router.py` | TTL, geometry, conflict resolution |

**External dependencies:**

| Dependency | Purpose | Required for |
|------------|---------|--------------|
| Python stdlib: `datetime`, `timezone` | Time parsing | Strategy core |
| `metaapi-cloud-sdk` | Broker connection | Shadow runner / portfolio runner |
| `python-dotenv` | `.env` loading | Runners |
| `pyyaml` | Config loading | Portfolio runner (soft dependency, falls back to hardcoded) |
| No numpy/pandas | Deliberate — pure Python | regime_detector.py docstring explicitly states this |
# London Breakout

## Overview

London Breakout is the session breakout branch in `adaptive/strategies/london_breakout_strategy.py`, wrapped for portfolio execution by `strategies/adapters/london_breakout_adapter.py`.

## Audit Status

- Catalog status: `research`
- Approval: `false`
- Version: `0.3`
- Deployment target: `research`
- Portfolio mode: `demo`

## Runtime Behavior

- Build the Asian range from `00:00-06:00 UTC`.
- Look for a London-session close above the Asian high or below the Asian low.
- Wait for a retest before confirming the signal.
- Emit one `AdaptiveSignal` per confirmed breakout sequence.

## Pair Coverage Note

The source docstring names `EURUSD`, `GBPUSD`, and `USDJPY`, while the portfolio config currently also routes `XAUUSD`. The adapter itself is symbol-agnostic enough to handle the pair map provided by the portfolio layer.
