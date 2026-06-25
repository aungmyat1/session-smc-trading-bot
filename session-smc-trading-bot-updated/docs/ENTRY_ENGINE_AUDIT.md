# ENTRY_ENGINE_AUDIT.md
# SA-06 — Entry Engine Worked Examples
# v1.0 | generated from entry_engine.py logic

---

## Configuration

| Parameter | Value |
|---|---|
| SL buffer | 2 pips (0.0002) |
| RR variants | 2, 3, 4, 5 |
| Pip size | 0.0001 (5-decimal pairs) |
| Session gate | london \| new_york only |

---

## Example 1 — Bullish (Long) Signal

**Setup:** EURUSD London killzone, 2024-01-15

### Inputs

| Component | Value |
|---|---|
| Asian High | 1.08000 |
| Asian Low | 1.07000 |
| Asian Range | 100.0 pips |
| HTF Bias | bullish |
| Sweep candle low | **1.06820** (pierced below Asian Low 1.07000) |
| Sweep candle close | 1.07050 (closed back inside range) |
| `SweepResult.sweep_price` | 1.06820 |
| Displacement candle O | 1.07150 |
| Displacement candle H | 1.07550 |
| Displacement candle L | 1.07100 |
| Displacement candle C | **1.07500** (entry) |
| ATR(14) | 0.00100 (10 pips) |
| Body | 0.00350 > 1.2×0.00100=0.00120 ✅ |
| Close position | (1.07500−1.07100)/(1.07550−1.07100) = 88.9% > 75% ✅ |
| Session | london |
| RR | 3.0 |
| SL buffer | 2 pips |

### Computation

```
entry     = candle.close             = 1.07500
stop_loss = sweep_price − buffer     = 1.06820 − 0.0002 = 1.06800
risk      = entry − stop_loss        = 1.07500 − 1.06800 = 0.00700  (70.0 pips)
take_profit = entry + risk × RR      = 1.07500 + 0.00700 × 3 = 1.09600
risk_pips   = 0.00700 / 0.0001       = 70.0 pips
reward_pips = 70.0 × 3               = 210.0 pips
```

### Signal Output

| Field | Value |
|---|---|
| `side` | `long` |
| `entry` | `1.07500` |
| `stop_loss` | `1.06800` |
| `take_profit` | `1.09600` |
| `risk_pips` | `70.0` |
| `reward_pips` | `210.0` |
| `rr` | `3.0` |
| `session` | `london` |
| `reason` | `long sweep @ 1.06820 → displacement @ 1.07500 \| SL 1.06800 \| RR 3.0` |

### Multi-RR Table

| RR | TP Price | Reward (pips) |
|---|---|---|
| 2 | `1.09100` | 160.0 pip |
| 3 | `1.09600` | 210.0 pip |
| 4 | `1.10100` | 280.0 pip |
| 5 | `1.10600` | 350.0 pip |

---

## Example 2 — Bearish (Short) Signal

**Setup:** GBPUSD New York killzone, 2024-01-15

### Inputs

| Component | Value |
|---|---|
| Asian High | 1.27500 |
| Asian Low | 1.26500 |
| Asian Range | 100.0 pips |
| HTF Bias | bearish |
| Sweep candle high | **1.27680** (pierced above Asian High 1.27500) |
| Sweep candle close | 1.27440 (closed back inside range) |
| `SweepResult.sweep_price` | 1.27680 |
| Displacement candle O | 1.27300 |
| Displacement candle H | 1.27350 |
| Displacement candle L | 1.26950 |
| Displacement candle C | **1.27000** (entry) |
| ATR(14) | 0.00110 (11 pips) |
| Body | 0.00300 > 1.2×0.00110=0.00132 ✅ |
| Close position | (1.27000−1.26950)/(1.27350−1.26950) = 12.5% < 25% ✅ |
| Session | new_york |
| RR | 3.0 |
| SL buffer | 2 pips |

### Computation

```
entry     = candle.close             = 1.27000
stop_loss = sweep_price + buffer     = 1.27680 + 0.0002 = 1.27700
risk      = stop_loss − entry        = 1.27700 − 1.27000 = 0.00700  (70.0 pips)
take_profit = entry − risk × RR      = 1.27000 − 0.00700 × 3 = 1.24900
risk_pips   = 0.00700 / 0.0001       = 70.0 pips
reward_pips = 70.0 × 3               = 210.0 pips
```

### Signal Output

| Field | Value |
|---|---|
| `side` | `short` |
| `entry` | `1.27000` |
| `stop_loss` | `1.27700` |
| `take_profit` | `1.24900` |
| `risk_pips` | `70.0` |
| `reward_pips` | `210.0` |
| `rr` | `3.0` |
| `session` | `new_york` |

---

## Example 3 — Rejected Signals

### 3A — Sweep not detected

```
SweepResult(detected=False, reason="no_breach")
→ build_signal() returns None immediately at Gate 1
```

### 3B — Displacement not detected

```
SweepResult(detected=True, side="long", sweep_price=1.06820)
DisplacementResult(detected=False, reason="body(0.00050) ≤ 1.2×ATR(0.00100)")
→ build_signal() returns None at Gate 1 (displacement check)
```

### 3C — Invalid session

```
session = "asian"   # not in {'london', 'new_york'}
→ build_signal() returns None at Gate 2
```

### 3D — Degenerate geometry (risk ≤ 0)

```
sweep_price = 1.07000   (wick low)
buffer      = 2 pips
stop_loss   = 1.07000 − 0.0002 = 1.06980
entry       = 1.06975   (candle closed BELOW the sweep wick — pathological data)
risk        = 1.06975 − 1.06980 = −0.00005  (negative)
→ build_signal() returns None at Gate 6 (risk ≤ 0 check)
```

### 3E — Invalid asian range

```
asian_range = AsianRange(high=1.0750, low=1.0750)  # high == low
→ build_signal() returns None at Gate 3 (asian_range.high <= asian_range.low)
```

### 3F — RR ≤ 0

```
rr = 0.0
→ build_signal() returns None at Gate 4
```

---

## Gate Evaluation Order

```
Gate 1: sweep.detected AND displacement.detected
Gate 2: session in {'london', 'new_york'}
Gate 3: asian_range is not None AND asian_range.high > asian_range.low
Gate 4: rr > 0 AND sl_buffer_pips >= 0
Gate 5: candle['close'] is numeric
Gate 6: sweep.sweep_price is not None
Gate 7: risk > 0  (sl_distance strictly positive)
→ Compute TP, risk_pips, reward_pips, reason, timestamp
→ Return Signal
```

All gates fail fast (early return None). Signal is constructed only when all gates pass.

---

## Execution Contract

The execution layer reads exactly these fields (EXECUTION_SPEC.md):

```python
signal.side          # 'long' | 'short'
signal.entry         # entry price
signal.stop_loss     # stop loss price
signal.take_profit   # take profit price
signal.reason        # log string
signal.session       # 'london' | 'new_york'
signal.timestamp     # UTC datetime
```

`risk_pips`, `reward_pips`, and `rr` are for the backtest only.
The execution layer must not depend on them.
