# Execution Flow: ST-A2 (Session Liquidity Reversal)

## Overview

The flow has two distinct entry points:
1. Direct call to `run_strategy()` in session_strategy.py (backtest / research scripts).
2. Via `ST2Adapter.generate_signal()` in st_a2_adapter.py (live/portfolio runner).

The adapter wraps run_strategy; all strategy logic lives in run_strategy.

---

## Full Execution Path

```
ST2Adapter.generate_signal(data)
  [st_a2_adapter.py:24]
        |
        |-- Guard: len(m15) < 50? --> return None (early exit)
        |   [st_a2_adapter.py:50]
        |
        |-- import run_strategy, DEFAULT_CONFIG
        |   [ImportError? --> return None silently (early exit)]
        |
        v
run_strategy(candles_m15, candles_4h, symbol, config)
  [session_strategy.py:40]
        |
        |-- Merge config: {**DEFAULT_CONFIG, **(config or {})}
        |
        |-- Guard: candles_m15 empty? --> return [] (early exit)
        |   [session_strategy.py:78]
        |
        |-- Sort candles_m15 by time
        |-- Compute wilder_atr(sorted_m15, period=14) --> atr_map
        |   [displacement_detector.py:wilder_atr():59]
        |   Indices 0..13 --> None (warm-up)
        |   Index 14 --> seed (mean TR[1..14])
        |   Index 15+ --> recursive Wilder
        |
        |-- Pre-group killzone bars by EST date (O(n) pass)
        |   For each bar: classify_session(bar_time) --> 'london'|'new_york'|None
        |   [session_builder.py:classify_session():85]
        |   None bars are excluded from _kz_by_date entirely
        |
        v
  FOR EACH trade_date IN sorted(_kz_by_date.keys()):
        |
        |== PHASE 1: Asian Range Build ==
        |   build_asian_range(sorted_m15, trade_date)
        |   [session_builder.py:build_asian_range():45]
        |   Asian window: (prev_day EST hour >= 18) OR (curr_day EST hour < 2)
        |   Need >= 4 bars in window
        |        |
        |        |-- asian is None? --> SKIP_DAY (log event, continue to next date)
        |
        |== PHASE 4: Minimum Range Filter ==
        |   asian.range_pips < min_range? (EURUSD:15.0 / GBPUSD:20.0)
        |        |
        |        |-- Below threshold? --> SKIP_DAY (continue to next date)
        |
        |-- Initialise: session_traded = set(), pending = None
        |
        v
    FOR EACH (candle, session) IN day_bars [killzone bars for this date]:
        |
        |== PHASE 10: One Trade Per Session ==
        |   session in session_traded?
        |        |-- Yes --> continue (skip this bar)
        |
        |== PENDING SWEEP SESSION GUARD ==
        |   pending is not None AND pending["session"] != session?
        |        |-- Yes --> SWEEP_CANCEL, set pending = None
        |
        |== PHASE 2: HTF Bias ==
        |   htf_bias(candles_4h, bar_time, swing_n=2)
        |   [bias_filter.py:htf_bias():77]
        |   Filter to 4H bars with close_time (open+4h) <= bar_time
        |   Sort 4H bars chronologically
        |   Find swing highs/lows with n=2 bars each side (strict inequality)
        |   Need >= 2 confirmed SHs AND >= 2 confirmed SLs
        |   Classify: bullish (HH+HL) | bearish (LH+LL) | neutral
        |
        |== BRANCH: pending is None? ==
        |
        YES (no pending sweep):
        |        |
        |        |-- bias == 'neutral'? --> NO_TRADE (log, continue)
        |        |
        |        |== PHASE 5: Sweep Detection ==
        |        |   detect_sweep(candle, asian.high, asian.low, bias)
        |        |   [sweep_detector.py:detect_sweep():44]
        |        |   Validate candle (try/except KeyError/TypeError/ValueError)
        |        |   Check strict price breach: low < asian_low OR high > asian_high
        |        |   Match breach to bias direction
        |        |   Check close-back: close > asian_low (long) / close < asian_high (short)
        |        |        |
        |        |        |-- sweep.detected? --> set pending = {sweep, bar_idx, session}
        |        |        |                        log SWEEP event
        |        |        |-- not detected --> log NO_SWEEP, continue
        |
        NO (sweep pending):
                 |
                 |== DISPLACEMENT TIMEOUT CHECK ==
                 |   bars_since = bar_idx - pending["bar_idx"]
                 |   bars_since > timeout (default 4)?
                 |        |-- Yes --> SWEEP_TIMEOUT, set pending = None, continue
                 |
                 |-- atr = atr_map.get(candle["time"])
                 |
                 |== PHASE 6: Displacement Detection ==
                 |   detect_displacement(candle, atr, pending["sweep"].side, mult=1.2)
                 |   [displacement_detector.py:detect_displacement():107]
                 |   Validate candle
                 |   Check ATR availability (None or 0 = reject)
                 |   Check candle_range > 0
                 |   Body gate: abs(close-open) > mult × ATR (strict >)
                 |   Quartile gate:
                 |     long:  close_pos = (close-low)/(high-low) > 0.75
                 |     short: close_pos < 0.25
                 |        |
                 |        |-- disp.detected?
                 |            |
                 |            YES:
                 |            |== PHASES 7-9: Signal Construction ==
                 |            |   build_signal(candle, sweep, disp, asian, session, rr, sl_buf)
                 |            |   [entry_engine.py:build_signal():52]
                 |            |   Gate 1: sweep.detected AND displacement.detected
                 |            |   Gate 2: session in {'london','new_york'}
                 |            |   Gate 3: asian.high > asian.low
                 |            |   Gate 4: rr > 0 AND sl_buffer_pips >= 0
                 |            |   Gate 5: parse candle["close"] as entry
                 |            |   Gate 6: SL geometry: risk > 0
                 |            |   Compute: entry, stop_loss, risk, take_profit, risk_pips
                 |            |   Build Signal dataclass
                 |            |        |
                 |            |        |-- sig is None? --> SIGNAL_REJECTED (log), clear pending
                 |            |        |
                 |            |        |== PHASE ST-A2: Minimum SL Filter ==
                 |            |        |   sig.risk_pips < min_sl_pips (5.0)?
                 |            |        |        |-- Yes --> SIGNAL_REJECTED (log), clear pending
                 |            |        |        |-- No  --> APPEND to signals
                 |            |        |                    session_traded.add(session)
                 |            |                            clear pending
                 |            |
                 |            NO (disp not detected):
                 |                log DISP_REJECT (bars_since/timeout, reason), continue
        |
  END day_bars loop
  END trade_dates loop
        |
        v
  Return signals (list[Signal])
  [if debug=True: return (signals, events)]

        |
        v
  ST2Adapter (if called via adapter):
        |
        |-- signals empty? --> return None
        |
        |-- raw = signals[-1]  (most recent signal only)
        |
        |-- Translate to core.Signal:
        |   action = 'BUY' if raw.side == 'long' else 'SELL'
        |   entry_price = float(raw.entry)
        |   stop_loss   = float(raw.stop_loss)
        |   take_profit = float(raw.take_profit)
        |   risk_percent = 0.25  [hardcoded]
        |   confidence   = 1.0   [hardcoded]
        |   timestamp    = datetime.now(utc)  [NOT raw.timestamp]
        |   metadata = {session, risk_pips, reward_pips, rr, reason}
        |
        v
  Return core.Signal (or None)
```

---

## Modules Touched (in call order)

| Order | Module | Function | Role |
|---|---|---|---|
| 1 | st_a2_adapter.py | ST2Adapter.generate_signal() | Entry point; validates inputs; translates output |
| 2 | session_strategy.py | run_strategy() | Orchestrator; day/bar loop |
| 3 | displacement_detector.py | wilder_atr() | Pre-compute ATR for all bars |
| 4 | session_builder.py | classify_session() | Pre-group bars by date/session |
| 5 | session_builder.py | build_asian_range() | Per-day Asian range |
| 6 | bias_filter.py | htf_bias() | Per-bar 4H bias evaluation |
| 7 | sweep_detector.py | detect_sweep() | Per-bar sweep detection |
| 8 | displacement_detector.py | detect_displacement() | Per-bar displacement detection |
| 9 | entry_engine.py | build_signal() | Signal construction |
| 10 | core/signal.py | Signal (dataclass) | Canonical output contract |

---

## Decision Gates (early-exit conditions)

| Gate | Location | Condition | Action |
|---|---|---|---|
| Empty M15 input | session_strategy.py:78 | candles_m15 is empty | Return [] |
| Adapter M15 minimum | st_a2_adapter.py:50 | len(m15) < 50 | Return None |
| Import failure | st_a2_adapter.py:42 | ImportError on session_strategy | Return None silently |
| Asian range missing | session_strategy.py:101 | build_asian_range returns None | Skip day |
| Range too narrow | session_strategy.py:106 | range_pips < min_range | Skip day |
| Session already traded | session_strategy.py:125 | session in session_traded | Skip bar |
| Neutral bias | session_strategy.py:139 | htf_bias returns 'neutral' | Skip bar (no sweep scan) |
| Sweep not detected | session_strategy.py:148 | sweep.detected is False | No pending; log NO_SWEEP |
| Session changed with pending | session_strategy.py:129 | pending["session"] != session | Cancel pending |
| Displacement timeout | session_strategy.py:158 | bars_since > timeout | Cancel pending |
| Displacement not detected | session_strategy.py:190 | disp.detected is False | Log DISP_REJECT |
| Signal construction failed | session_strategy.py:175 | build_signal returns None | Log SIGNAL_REJECTED |
| Min SL not met | session_strategy.py:178 | risk_pips < 5.0 | Log SIGNAL_REJECTED |
| No signals from run_strategy | st_a2_adapter.py:54 | raw_signals is empty | Return None |
# ST-A2 Flow

1. Sort M15 candles chronologically.
1. Compute Wilder ATR across the full series.
1. Group killzone bars by UTC date.
1. Build the Asian range for the trade date.
1. Reject the day if the range is missing or too small.
1. Scan London and New York killzones.
1. Check H4 bias before looking for a sweep.
1. Record a pending sweep when price strictly breaches the Asian range and closes back inside.
1. Wait up to `sweep_timeout_bars` for a displacement candle.
1. Build the final signal from the sweep plus displacement pair.
1. Enforce one completed signal per session per day.
