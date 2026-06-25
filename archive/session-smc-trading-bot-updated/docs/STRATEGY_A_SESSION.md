# STRATEGY_A_SESSION.md
# Strategy A — Session Liquidity Reversal
# v1.0 | lock before backtest

---

## Concept

Capture institutional reversals after liquidity sweeps of the Asian session range.
Trade only during London and New York Killzones.

**Use only: Time · Price · Liquidity**
No RSI. No EMA entries. No MACD. No trendlines.

---

## Phase 1 — Asian Session Build

**Session window:** 18:00 EST → 02:00 EST (next calendar day)

Track:
- `asian_high` = max of all M15 highs in window
- `asian_low`  = min of all M15 lows in window

Rules:
- Use **completed candles only** (the 02:00 EST bar is excluded — it belongs to London)
- Reset at start of each new trading day (EST calendar date)
- If fewer than 4 Asian bars exist → skip day (holiday / data gap)
- Store as `AsianRange(trade_date, high, low)`

UTC equivalent (DST-aware via `zoneinfo("America/New_York")`):
- EST (winter): 23:00 UTC prev day → 07:00 UTC
- EDT (summer): 22:00 UTC prev day → 06:00 UTC

---

## Phase 2 — 4H Bias Filter

**Do not trade against HTF structure.**

| Pattern | Bias |
|---|---|
| HH + HL on 4H | Bullish → long only |
| LL + LH on 4H | Bearish → short only |
| Mixed | Neutral → no trade |

Implementation:
- Use `swing_n=2` (2 bars each side for swing confirmation)
- Only include 4H bars whose close time ≤ current M15 bar time (lookahead prevention)
- A 4H bar at time T closes at T+4h, so cutoff = `current_time - 4h`
- Need ≥ 2 confirmed swing highs AND ≥ 2 confirmed swing lows
- Bias = last 2 SHs are HH AND last 2 SLs are HL → bullish
- Bias = last 2 SHs are LH AND last 2 SLs are LL → bearish
- Otherwise → neutral

---

## Phase 3 — Killzone Filter

Only scan for setups during:

| Session | EST | UTC (EST winter) | UTC (EDT summer) |
|---|---|---|---|
| London | 02:00–05:00 | 07:00–10:00 | 06:00–09:00 |
| New York | 07:00–10:00 | 12:00–15:00 | 11:00–14:00 |

Outside these windows: no action.

---

## Phase 4 — Asian Range Filter

Calculate: `asian_range_pips = (asian_high - asian_low) / 0.0001`

Minimum thresholds (configurable):
- EURUSD: 15 pips
- GBPUSD: 20 pips

If below threshold → skip day (dead/ranging market, spread kills edge).

---

## Phase 5 — Liquidity Sweep Detection

**Bullish sweep (long setup):**
1. `candle.low < asian_low` — wick pierces below
2. `candle.close > asian_low` — closes back inside range
3. `4H bias == bullish`

**Bearish sweep (short setup):**
1. `candle.high > asian_high` — wick pierces above
2. `candle.close < asian_high` — closes back inside range
3. `4H bias == bearish`

On detection: store `Sweep(direction, bar_idx, sweep_low, sweep_high, bar_time)`.
**Do not enter on the sweep candle.** Wait for displacement.

---

## Phase 6 — Displacement Confirmation

The candle AFTER the sweep must show strong institutional rejection.

**Bullish displacement:**
- `abs(close - open) > 1.2 × ATR(14)`
- `close > low + 0.75 × (high - low)` (close in upper 25% of range)

**Bearish displacement:**
- `abs(close - open) > 1.2 × ATR(14)`
- `close < high - 0.75 × (high - low)` (close in lower 25% of range)

ATR(14): Wilder's method on M15 bars.
- Seed at index 14: `mean(TR[1..14])`
- Recursive: `ATR[i] = (ATR[i-1] × 13 + TR[i]) / 14`
- NaN for bars 0..13 → skip

Timeout: if displacement does not appear within 4 bars of sweep → cancel setup.

---

## Phase 7 — Entry

Entry = **close of displacement candle** (bar-close execution).

- Long: after bullish sweep + bullish displacement
- Short: after bearish sweep + bearish displacement

---

## Phase 8 — Stop Loss

| Direction | Stop Loss |
|---|---|
| Long | `sweep_low - buffer` |
| Short | `sweep_high + buffer` |

Buffer: configurable, default **2 pips** (`2 × 0.0001`).

If `sl_distance ≤ 0` → reject signal (degenerate geometry).

---

## Phase 9 — Take Profit (Configurable RR)

`TP = entry ± RR × sl_distance`

Backtest all four variants:
- RR 2, RR 3, RR 4, RR 5

Do not hardcode. Pass `rr` as config parameter.

---

## Phase 10 — Risk & Session Gate

- Risk per trade: **1% of account**
- **One active trade per session per day**
  - Max 1 London trade per calendar day
  - Max 1 NY trade per calendar day
- After a signal fires in a session, no further scanning for that session that day

---

## File Layout

```
strategy/session_liquidity/
  __init__.py              re-exports Signal, run_strategy
  session_builder.py       AsianRange, build_asian_range()
  bias_filter.py           htf_bias()
  sweep_detector.py        Sweep, detect_sweep()
  displacement_detector.py Displacement, wilder_atr(), detect_displacement()
  entry_engine.py          Signal, build_signal()
  session_strategy.py      run_strategy(), DEFAULT_CONFIG
```

---

## Signal Output Contract

```python
Signal(
    side: str,           # 'long' | 'short'
    entry: float,
    stop_loss: float,
    take_profit: float,
    reason: str,
    session: str,        # 'london' | 'new_york'
    timestamp: datetime,
    sl_pips: float,
    rr: float,
)
```

The execution layer reads only `side`, `entry`, `stop_loss`, `take_profit`, `reason`, `session`, `timestamp`.

---

## Known Prior Failures (do not re-propose without LTF confirmation)

| Trial | Strategy | Result |
|---|---|---|
| T27 | EURUSD session sweep alone | PF=0.58 FAIL |
| T28 | GBPUSD session sweep alone | PF=0.95 FAIL (2× stress) |

**Strategy A adds the displacement confirmation gate** — this is the differentiating element vs T27/T28.
