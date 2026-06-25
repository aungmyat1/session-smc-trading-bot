# FORWARD_TEST_VALIDATION.md
# DEP-00 — Forward Test Simulator Validation
# Date: 2026-06-21

---

## Verdict

### ✅ PASS — All 6 validation rules confirmed. 43/43 tests passing.

Sequential forward-feed produces signals identical to the batch backtest.
No lookahead dependency found. Timing, pricing, and session rules all correct.

---

## Purpose

Before broker integration (DEP-01), validate that:

1. The strategy has no hidden lookahead bias
2. Signal timestamps match the first moment the strategy could have known
3. Session enforcement (one signal per session) holds in sequential mode
4. Signal prices are identical between backtest and forward feed
5. State persists correctly across candles
6. ST-A2 min_sl_pips filter is enforced in forward mode

---

## Architecture

### `simulator/forward_test.py`

Three public components:

#### `ForwardTestSimulator`

Wraps `run_strategy()` in a sequential driver.

```
history = []

for candle in m15_stream:
    history.append(candle)                          # candle added FIRST
    all_signals = run_strategy(history, h4, symbol) # strategy sees only history
    emit signals not yet seen (dedup by timestamp)
```

**Lookahead guarantee (by construction):**
When `feed(candle_i)` is called, `candle_i` is appended to `self._m15`
*before* `run_strategy` is called. The strategy receives `candles[0..i]`
and cannot see `candles[i+1..]` — they have not been appended yet.

Any lookahead dependency would require the strategy to produce a signal
whose timestamp is in the future relative to the last-fed candle.
The `test_signal_timestamp_not_in_future` test enforces this invariant
on every candle feed.

#### `replay_day(trade_date, symbol, m15, h4, config)`

Runs `run_strategy` in `debug=True` mode and filters the event list to
the specified date. Parses bar-label brackets `[HH:MM UTC]` from each
event's detail field to build a chronological `ReplayEvent` timeline.

#### `compare_with_backtest(symbol, m15, h4, config)`

Runs both the batch backtest (all candles at once) and the sequential
forward test on identical data, then compares signal lists field by field:
`timestamp`, `entry`, `stop_loss`, `side`, `session`.

If both produce identical lists, the strategy cannot have lookahead:
any lookahead dependency would surface as a signal in the backtest that
the forward test cannot replicate before its trigger candle is fed.

---

## Sample Replay — 2024-01-15 EURUSD

The replay below shows the bar-by-bar decision timeline for one day.

```
Sample Replay — 2024-01-15 EURUSD
=================================
Time            Event                 Detail
————————————    ——————————————————    ————————————————————————————————————
—               ASIAN_RANGE           H=1.07500 L=1.07000 range=50.0pip
07:00 UTC       NO_SWEEP              london no_breach bias=bullish
07:15 UTC       SWEEP                 london side=long price=1.06820 bias=bullish
07:30 UTC       SIGNAL                london long entry=1.07900 sl=1.06800 rr=3.0
```

Asian range is built at the start of the killzone (no time bracket — it's
a date-level event, not a specific bar). Each London bar is evaluated in
sequence. The sweep is detected at 07:15 UTC. The displacement candle at
07:30 UTC confirms the signal. Signal timestamp = 07:30 UTC = bar-close of
displacement candle.

**compare_with_backtest result on this dataset:**

```
{'match': True, 'backtest_count': 1, 'forward_count': 1, 'mismatches': []}
```

---

## Validation Rules — Results

| Rule | Check | Method | Status |
|---|---|---|---|
| A | Signal timestamp == first moment strategy could have known | `test_signal_timestamp_equals_displacement_close_time` | ✅ PASS |
| A | Signal timestamp ≤ time of last candle fed when signal appeared | `test_signal_timestamp_not_in_future` | ✅ PASS |
| B | No signal before sweep confirmation | `test_no_signal_after_sweep_only` | ✅ PASS |
| C | No signal before displacement confirmation | `test_no_signal_after_asian_only` | ✅ PASS |
| D | One signal max per session (rule enforced across sequential feeds) | `test_no_duplicate_after_extra_london_bars` | ✅ PASS |
| E | One signal max per day (london + ny tracked separately) | `test_two_days_two_signals` | ✅ PASS |
| F | Signal prices match backtest | `test_compare_with_backtest_reports_match` | ✅ PASS |

---

## Test Results

43 tests across 10 categories, all passing.

| Category | Tests | Description |
|---|---|---|
| 1 Sequential feeding | 4 | Forward count = backtest count; timestamps identical; compare() matches |
| 2 No future access | 4 | No signal after Asian only; no signal after sweep only; signal fires on displacement candle; timestamp ≤ last-fed candle |
| 3 Signal emitted once | 3 | Exactly 1 signal; no duplicate after extra London bars; candle count correct |
| 4 Signal at correct candle | 4 | Timestamp = 07:30 UTC; entry = 1.07900; side = long; session = london |
| 5 Multi-day replay | 4 | Two days → two signals; separate dates; backtest agrees; reset() works |
| 6 Empty dataset | 4 | Zero candles → zero signals; compare() matches empty backtest |
| 7 Missing H4 data | 2 | No H4 → neutral bias → no signals; compare() agrees with backtest |
| 8 Replay output | 9 | Timeline is list of ReplayEvent; has ASIAN_RANGE, SWEEP, SIGNAL; sweep before signal; format_replay produces string |
| 9 ST-A2 filter | 4 | Default 5-pip floor passes 110-pip SL; 200-pip threshold blocks; 0-pip passes; filter consistent with backtest |
| 10 Debug timeline | 5 | ReplayEvent fields; ASIAN_RANGE has time=—; SIGNAL detail has entry=; format contains all event types; empty timeline |

---

## Known Limitations

1. **O(n²) simulation cost.** `feed()` calls `run_strategy` with full history on
   every candle. For a 5-year (121k bar) dataset, this is impractical (~14.6B
   operations). The simulator is designed for validation samples (≤ 30 days)
   and per-day replays, not a live 5-year replay.

2. **H4 candles passed in full.** The simulator passes all H4 history to
   `run_strategy` on each call rather than incrementally filtering. This is safe
   because `htf_bias()` gates H4 bars by `bar_time` internally
   (`bar_open_time ≤ before_dt − 4h` — see bias_filter.py §Lookahead rule).
   Confirmed: bias filter was validated in SA-02 with this explicit time gate.

3. **Synthetic fixture data only.** The compare_with_backtest validation above
   used a 35-bar synthetic dataset. The 5-year production dataset would require
   an incremental (stateful) strategy implementation for O(n) forward testing.
   For DEP-01 demo trade monitoring, the bot runs bar-by-bar in real time —
   that IS the forward test; this simulator validates the signal generation
   code path is correct before connecting to MetaAPI.

4. **No broker-layer validation.** DEP-00 validates the signal generation
   pipeline only. Execution correctness (lot sizing, order placement, SL/TP
   confirmation) is validated in DEP-01 (demo) before DEP-02 (live).

---

## Files Produced

| File | Lines | Purpose |
|---|---|---|
| `simulator/__init__.py` | — | Module marker |
| `simulator/forward_test.py` | 191 | ForwardTestSimulator, replay_day, compare_with_backtest |
| `tests/test_forward_test.py` | 313 | 43 tests across 10 categories |

*DEP-00 | Date: 2026-06-21*
