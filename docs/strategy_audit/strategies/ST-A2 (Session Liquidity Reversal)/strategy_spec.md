# Strategy: ST-A2 (Session Liquidity Reversal)

## Version / Status

| Field | Value |
|---|---|
| Trial ID | ST-A2 |
| Date registered | 2026-06-21 |
| Phase-0 run ID | 20260621T100458-183aaa |
| Phase-0 verdict | PASS |
| Current phase | Phase-1 (paper trade) |
| Net PF (std, RR5) | 1.151 |
| Net PF (2x, RR5) | 1.025 |
| Trade count (5yr backtest) | 169 |
| Win rate | 32.0% |
| Max drawdown | 18.72R |
| Operating RR | 5 (max PF_2x in backtest) |

ST-A2 is the Phase-0-validated evolution of ST-A. The single change from ST-A: a minimum
SL floor of 5.0 pips. This removed 12 trades with sweep wicks shorter than 5 pips; those
trades had gross wins fully consumed by spread at 2x stress, making them net-negative. ST-A
failed Phase-0 (PF_2x=0.965); ST-A2 passes (PF_2x=1.025).

## Description

ST-A2 (Session Liquidity Reversal) is a mean-reversion strategy that targets institutional
liquidity grabs at the edges of the Asian session range. It requires three sequential
confirmations before entry: (1) a 4H structural bias, (2) a wick sweep of the Asian range
that closes back inside, and (3) a single displacement candle with a large body and a close
in the top/bottom quartile of its range. Entry is taken at the close of the displacement
candle. The min_sl_pips=5.0 filter is the only ST-A2-specific addition over ST-A.

## Trading Philosophy

Wait for smart money to sweep Asian session liquidity and confirm the reversal with a single
strong displacement candle. Do not predict — react. Never enter on the sweep candle itself.
The displacement candle is the confirmation that price is moving away from the swept level
with institutional conviction.

Distinguish from ST-1 (prior failure): ST-1 entered at the CHoCH close, which is too far
past the inflection point. ST-A2 enters at the displacement close within 1–4 bars of the
sweep, capturing the initial impulse move.

Use only: Time, Price, Liquidity. No oscillators, no moving average crossovers, no trendlines.

## Market / Timeframe / Session / Direction

| Dimension | Value |
|---|---|
| Instruments | EURUSD, GBPUSD |
| Broker | VT Markets (Standard account) |
| Primary TF (signal) | M15 |
| HTF bias TF | 4H |
| Sessions | London killzone: 02:00–04:59 EST / 07:00–09:59 UTC (winter) |
| | New York killzone: 07:00–09:59 EST / 12:00–14:59 UTC (winter) |
| Direction | Both long and short; direction determined by 4H bias |
| DST | Handled via zoneinfo America/New_York (EDT shifts windows 1h earlier in UTC) |

Session windows as implemented in session_builder.py classify_session():
- London: EST hour in [2, 3, 4]
- New York: EST hour in [7, 8, 9]

## Signal Chain (phase-by-phase, in execution order)

All phases are AND-gated. Any phase failure causes immediate skip for that bar/day.

### Phase 1 — Asian Range Build (daily, SA-01)

Build the Asian session high and low for the current trade date (EST calendar date).
Asian window: 18:00–23:59 EST on trade_date-1 AND 00:00–01:59 EST on trade_date.
The 02:00 EST bar is the London open and is excluded.
Minimum: 4 Asian bars required. Fewer bars = skip day (holiday or data gap).
Output: AsianRange(trade_date, high, low)

### Phase 2 — Minimum Range Filter (daily, SA-07)

Asian range in pips = (high - low) / 0.0001.
EURUSD: minimum 15.0 pips. GBPUSD: minimum 20.0 pips.
If below threshold: skip day (dead market; fee cost consumes edge).

### Phase 3 — Killzone Filter (per-bar, SA-01)

Only process M15 bars that fall within the London or New York killzone.
classify_session() returns 'london', 'new_york', or None.
Bars outside killzones are ignored entirely.

### Phase 4 — One Trade Per Session Gate (per-bar, SA-07)

Track session_traded set per calendar day. If a signal has already been generated
for the current session (london or new_york), skip all remaining bars in that session.

### Phase 5 — Session Change / Pending Sweep Cancel (per-bar, SA-07)

If a sweep is pending from a prior session and the current bar is in a different session,
cancel the pending sweep. No carryover of sweep state across session boundaries.

### Phase 6 — 4H HTF Bias (per-bar, SA-02)

Call htf_bias(candles_4h, bar_time, swing_n=2).
Only 4H bars whose close time <= bar_time are used (close time = open time + 4h).
Swing detection: strict inequality, n=2 bars each side required.
Bullish = latest swing high > prior AND latest swing low > prior (HH+HL).
Bearish = latest swing high < prior AND latest swing low < prior (LH+LL).
Neutral = mixed or insufficient confirmed swings (< 2 swing highs and 2 swing lows).
If neutral: skip bar — no trade without committed bias.

### Phase 7 — Liquidity Sweep Detection (per-bar, SA-04)

Only evaluated when no sweep is pending.
Bullish sweep: candle.low < asian_low AND candle.close > asian_low AND bias == 'bullish'.
Bearish sweep: candle.high > asian_high AND candle.close < asian_high AND bias == 'bearish'.
Strict inequality on both the breach and the close-back.
Touch only (low == asian_low) is NOT a sweep.
On detection: record sweep as pending with current bar_idx.

### Phase 8 — Displacement Detection (per-bar, SA-05)

Only evaluated when a sweep is pending.
Timeout check: if bars_since_sweep > sweep_timeout_bars (default 4), cancel pending sweep.
ATR: Wilder ATR(14) pre-computed across full M15 history. Undefined for bars 0..13.
Bullish displacement: body > displacement_mult × ATR(14) AND close_position > 0.75.
Bearish displacement: body > displacement_mult × ATR(14) AND close_position < 0.25.
body = abs(close - open). close_position = (close - low) / (high - low).
Both gates use strict inequality. ATR=None or ATR=0 = reject.

### Phase 9 — Signal Construction (SA-06)

Only reached when displacement.detected is True.
build_signal() computes:
- Entry = displacement candle close.
- SL = sweep_price - sl_buffer_pips * 0.0001 (long) or sweep_price + buffer (short).
- risk = entry - stop_loss (long) or stop_loss - entry (short).
- If risk <= 0: reject (degenerate geometry).
- TP = entry + risk * rr (long) or entry - risk * rr (short).
- risk_pips = risk / 0.0001.

### Phase 10 — Minimum SL Filter (SA-07)

After build_signal() returns, check: signal.risk_pips >= min_sl_pips (default 5.0).
This is the ST-A2-specific gate. Signals with sweep wicks shorter than 5 pips are rejected.

## Entry Rules

1. Entry is taken at market on close of the displacement candle.
2. Order type: MARKET (as translated by ST2Adapter).
3. Entry price = float(displacement_candle["close"]).
4. Session must be 'london' or 'new_york' at time of entry.
5. Maximum one entry per session per calendar day.
6. Entry is only triggered after all 10 phases of the signal chain pass.

## Confirmation Rules

The displacement candle must satisfy all of the following (strict inequalities throughout):
- body (abs(close - open)) > displacement_mult (1.2) × ATR(14).
- For long: close_position = (close - low) / (high - low) > 0.75.
- For short: close_position < 0.25.
- ATR must be defined (bar index >= atr_period = 14).
- Candle range (high - low) > 0 (zero-range candle rejected).
- Displacement must appear within sweep_timeout_bars (4) M15 killzone bars of the sweep.

## Exit Rules (TP / SL / BE / Trailing / Partial)

As specified in entry_engine.py build_signal() and the adapter:

| Exit type | Rule |
|---|---|
| Stop Loss | sweep_price - sl_buffer_pips × 0.0001 (long) / sweep_price + buffer (short) |
| Take Profit | entry +/- risk × rr (single TP level) |
| Partial / BE | NOT implemented in signal chain or adapter. Signal is single TP only. |
| Trailing | NOT implemented. |
| Session close | Specified in RISK_SPEC.md and EXECUTION_SPEC.md but NOT in session_strategy.py. |

Note: SIGNAL_SPEC.md and RISK_SPEC.md describe a two-part exit (TP1 4R close 75%, SL to BE,
TP2 5R+ runner) and a session-end close rule. These are NOT implemented in the current
session_strategy.py signal chain or ST2Adapter. The signal emits a single TP level only.
The backtest (Phase-0 run) used a single fixed-RR exit, not a partial/BE/runner model.

## Filters (Spread / Volatility / Session / News)

| Filter | Status | Details |
|---|---|---|
| Session filter | IMPLEMENTED | Only London (02-04 EST) and NY (07-09 EST) killzones |
| Minimum range | IMPLEMENTED | EURUSD 15pip, GBPUSD 20pip minimum Asian range |
| Minimum SL | IMPLEMENTED (ST-A2 specific) | risk_pips >= 5.0 before signal appended |
| HTF bias | IMPLEMENTED | 4H swing structure neutral = no trade |
| Spread filter | NOT IMPLEMENTED in signal chain | Cost modeled only in backtest |
| News filter | NOT IMPLEMENTED | No news or economic calendar check |
| Volatility filter | NOT IMPLEMENTED as explicit gate | min_range_pips is a proxy |
| Max SL | NOT IMPLEMENTED in signal chain | RISK_SPEC.md specifies 50pip max but no code enforces it |

## Kill Switch / Safety

Specified in RISK_SPEC.md and EXECUTION_SPEC.md but NOT implemented in the session_strategy.py
signal chain itself. The signal chain is a pure signal generator with no position state.
Safety controls are in the (unbuilt / separate) execution layer:

| Control | Spec | Code |
|---|---|---|
| Daily loss limit | 3R/day (RISK_SPEC.md) | Not in strategy module |
| Max drawdown kill switch | 10% from peak (RISK_SPEC.md) | Not in strategy module |
| Consecutive losses | 5 (RISK_SPEC.md) | Not in strategy module |
| Weekly loss limit | 6R/week (RISK_SPEC.md) | Not in strategy module |
| LIVE_TRADING flag | False by default (CLAUDE.md) | Not enforced in strategy module |
| One position per session | 1 signal per session/day (session_strategy.py) | IMPLEMENTED |

## Known Limitations

1. EURUSD 2x stress PF = 0.945 (fails gate individually). Strategy passes only on the
   combined EUR+GBP portfolio. EURUSD-only deployment has not passed Phase-0.

2. London session is the structural weak link: London WR=28.0%, Net PF (std)=0.949 at RR5.
   NY session drives the edge: NY WR=41.2%, Net PF (std)=1.731.

3. 3 of 6 backtest years are negative (2021, 2023, 2025). Regime sensitive.
   Low frequency: ~34 trades/year, ~3/month. Paper trade at 30 days captures 3-5 trades only.

4. Single TP exit only. The SIGNAL_SPEC.md partial/BE/runner model is not implemented.
   Backtest PF was computed with fixed RR5 single exit, not the two-part model.

5. No spread filter in live operation. Entries will fire regardless of live spread width.

6. Displacement timeout of 4 bars is counted in killzone bars, not calendar time. A 4-bar
   gap within a 3-hour killzone window is meaningful; the timeout resets if the session
   changes.

7. Adaptation extensions (D2 gates, D1 gates) all failed Phase-0 or produced n < 10 in
   short-window tests. ST-A2 is the final validated form; further filtering is not supported.

## Dependencies (modules, external)

### Internal modules (strategy/session_liquidity/)

| Module | Role | Public API |
|---|---|---|
| session_builder.py (SA-01) | Asian range build + session classification | AsianRange, build_asian_range(), classify_session() |
| bias_filter.py (SA-02) | 4H HTF bias detection | htf_bias() |
| sweep_detector.py (SA-04) | Single-candle sweep detection | SweepResult, detect_sweep() |
| displacement_detector.py (SA-05) | ATR computation + displacement gate | DisplacementResult, wilder_atr(), detect_displacement() |
| entry_engine.py (SA-06) | Signal construction from sweep+displacement | Signal, build_signal() |
| session_strategy.py (SA-07) | Orchestrator; full pipeline loop | run_strategy(), DEFAULT_CONFIG |
| config.yaml | Configuration file (subset of DEFAULT_CONFIG) | rr, sl_buffer_pips, displacement_mult, atr_period, sweep_timeout_bars, min_sl_pips, min_range_pips |

### Adapter (strategies/adapters/)

| Module | Role |
|---|---|
| st_a2_adapter.py | Translates session_liquidity.Signal to core.Signal; implements BaseStrategy |

### Core modules (core/)

| Module | Role |
|---|---|
| base_strategy.py | Abstract base class BaseStrategy |
| signal.py | Canonical Signal dataclass consumed by execution layer |

### External

| Dependency | Version | Purpose |
|---|---|---|
| Python standard library only | — | dataclasses, datetime, zoneinfo, typing |
| No third-party packages | — | Strategy module has zero external imports |
| MetaAPI Cloud SDK | >= 29 | Execution layer (not in strategy module) |
