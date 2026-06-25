# SWEEP_DETECTOR_AUDIT.md
# SA-04 — Liquidity Sweep Detector Decision Audit
# Purpose: document exactly which candle values produce each outcome.

---

## Setup

```
asian_high = 1.0920
asian_low  = 1.0880
```

---

## Valid Bullish Sweep

### Candle

```
high  = 1.0915
low   = 1.0875   ← 0.0005 below asian_low (breach confirmed)
close = 1.0895   ← 0.0015 above asian_low (snapback confirmed)
```

### Decision trace

```
Step 1  Validate candle                   PASS (all keys present, float-coercible)
Step 2  bullish_breach = 1.0875 < 1.0880  TRUE
        bearish_breach = 1.0915 > 1.0920  FALSE (high didn't reach level)
Step 3  bias == "bullish"                 → check bullish_breach
        bullish_breach = TRUE             → proceed to close check
        close (1.0895) <= asian_low (1.0880)?  FALSE (1.0895 > 1.0880)
        → all conditions met
```

### Result

```
detected    = True
side        = "long"
sweep_price = 1.0875      (candle.low — the extreme that swept the level)
reason      = "bullish_sweep"
```

### Meaning for downstream

The stop loss will be placed below `sweep_price` (sweep_price − buffer pips).
Entry fires on the **close of the displacement candle**, not this candle.

---

## Valid Bearish Sweep

### Candle

```
high  = 1.0925   ← 0.0005 above asian_high (breach confirmed)
low   = 1.0885
close = 1.0905   ← 0.0015 below asian_high (snapback confirmed)
```

### Decision trace

```
Step 1  Validate candle                   PASS
Step 2  bullish_breach = 1.0885 < 1.0880  FALSE
        bearish_breach = 1.0925 > 1.0920  TRUE
Step 3  bias == "bearish"                 → check bearish_breach
        bearish_breach = TRUE             → proceed to close check
        close (1.0905) >= asian_high (1.0920)?  FALSE (1.0905 < 1.0920)
        → all conditions met
```

### Result

```
detected    = True
side        = "short"
sweep_price = 1.0925      (candle.high — the extreme that swept the level)
reason      = "bearish_sweep"
```

---

## Rejected: No Breach (touch only)

### Candle — bullish attempt, exact touch

```
high  = 1.0915
low   = 1.0880   ← exactly equals asian_low
close = 1.0895
```

### Decision trace

```
Step 2  bullish_breach = 1.0880 < 1.0880  FALSE  ← strict inequality fails
        bearish_breach = 1.0915 > 1.0920  FALSE
        → neither side breached
```

### Result

```
detected = False
reason   = "no_breach"
```

### Why strict inequality

A candle that touches the Asian level without breaching it collects no
liquidity (no stops triggered). The institutional rationale for a sweep
reversal requires that price actually trades through the level, hitting
stop orders below/above. A touch does not do this.

---

## Rejected: Close Outside Range

### Candle — bullish breach, close stays below

```
high  = 1.0915
low   = 1.0875   ← breaches asian_low (TRUE)
close = 1.0878   ← below asian_low = 1.0880
```

### Decision trace

```
Step 2  bullish_breach = 1.0875 < 1.0880  TRUE
Step 3  bias == "bullish" and bullish_breach TRUE → close check
        close (1.0878) <= asian_low (1.0880)?  TRUE  ← rejection
```

### Result

```
detected = False
reason   = "close_outside_range"
```

### Why this matters

If price breaches the Asian low but cannot close back above it, sellers
remain in control. There is no evidence of institutional reversal.
Entering here is entering into the continuation of a failed sweep — the
defining pattern of T27/T28 losses. This gate is mandatory.

### Boundary case: close exactly at asian_low

```
close = 1.0880 == asian_low

close <= asian_low?  1.0880 <= 1.0880 → TRUE → rejected
```

The close must be STRICTLY above asian_low. Pinned at the level is not inside.

---

## Rejected: Bias Mismatch

### Candle — bearish sweep in bullish bias

```
bias  = "bullish"
high  = 1.0925   ← breaches asian_high
low   = 1.0885   ← above asian_low (no bullish breach)
close = 1.0910   ← valid snapback for bearish sweep
```

### Decision trace

```
Step 2  bullish_breach = 1.0885 < 1.0880  FALSE
        bearish_breach = 1.0925 > 1.0920  TRUE
        → at least one breach exists → proceed
Step 3  bias == "bullish" → check bullish_breach
        bullish_breach = FALSE  → directional mismatch
```

### Result

```
detected = False
reason   = "bias_mismatch"
```

### Why bias filtering is mandatory

The 4H structure defines which direction has institutional backing.
A bearish sweep in a bullish 4H trend would require trading against the
higher-timeframe order flow. This is the lesson from T27/T28: sweeps
without structural alignment have no statistical edge (PF < 1.0).

### Neutral bias — also a mismatch

```
bias = "neutral"
```

When the 4H structure is mixed (not clearly HH+HL or LH+LL), no
directional conviction exists. No sweep detection is valid.

```
detected = False
reason   = "bias_mismatch"
```

---

## Decision Matrix

| Bias | Breach | Close | Result | Reason |
|---|---|---|---|---|
| bullish | low < asian_low | close > asian_low | ✅ | bullish_sweep |
| bearish | high > asian_high | close < asian_high | ✅ | bearish_sweep |
| bullish | low < asian_low | close ≤ asian_low | ❌ | close_outside_range |
| bearish | high > asian_high | close ≥ asian_high | ❌ | close_outside_range |
| bullish | high > asian_high only | any | ❌ | bias_mismatch |
| bearish | low < asian_low only | any | ❌ | bias_mismatch |
| neutral | any | any | ❌ | bias_mismatch |
| any | low == asian_low | — | ❌ | no_breach |
| any | high == asian_high | — | ❌ | no_breach |
| any | no breach | — | ❌ | no_breach |
| any | bad data | — | ❌ | invalid_candle |

---

## Scope Boundary

This module evaluates ONE candle, ONE time.

It does NOT:
- Look ahead to the next candle
- Compute ATR or displacement
- Apply session (killzone) gating
- Apply Asian range minimum filter
- Place any trade or signal

Those responsibilities belong to the downstream modules:
- `displacement_detector.py` — Phase 6
- `entry_engine.py`          — Phase 7
- `session_strategy.py`      — orchestration + gating
