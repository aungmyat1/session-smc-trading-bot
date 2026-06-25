# SMC Feature Specification
# scripts/extract_features.py output schema

---

## Overview

Feature extraction runs the ST-A2 signal chain and standalone SMC scanners
on processed OHLCV Parquet, producing event tables stored as Parquet.

---

## Feature Tables

### 1. Session Events — `data/features/sessions/{SYMBOL}.parquet`

One row per detected trading session.

| Column | Type | Values |
|---|---|---|
| session_open | datetime[UTC] | Session open bar timestamp |
| session_close | datetime[UTC] | Session close bar timestamp |
| session | str | `london` / `new_york` |
| session_high | float64 | Session high (pips basis) |
| session_low | float64 | Session low |
| session_mid | float64 | (high + low) / 2 |
| range_pips | float64 | high − low in pips (pair-adjusted) |
| session_type | str | `range` (low ATR) / `trend` (strong BOS + displacement) |

**Session windows (UTC):**
- London: 07:00–10:00 UTC (Asian session used as reference range: 00:00–06:00 UTC)
- New York: 13:00–16:00 UTC

---

### 2. Sweep Events — `data/features/sweeps/{SYMBOL}.parquet`

One row per session sweep detection (high or low broken then closed back inside).

| Column | Type | Values |
|---|---|---|
| timestamp_utc | datetime[UTC] | Bar that completed the sweep |
| session | str | `london` / `new_york` |
| direction | str | `bullish` (low swept) / `bearish` (high swept) |
| sweep_level | float64 | Session H/L that was swept |
| sweep_close | float64 | Close price after sweep |
| session_high | float64 | Full session high |
| session_low | float64 | Full session low |
| htf_bias | str | `bullish` / `bearish` / `neutral` (4H+1H macro bias) |

**Sweep definition (ST-A2):**
- Price breaks session H/L on any bar within killzone window
- Same bar OR next N bars closes back inside session range
- HTF bias filter applied: sweep direction must agree with 4H+1H bias

---

### 3. FVG Events — `data/features/fvg/{SYMBOL}.parquet`

One row per Fair Value Gap (3-candle displacement pattern on M15).

| Column | Type | Values |
|---|---|---|
| timestamp_utc | datetime[UTC] | Bar that created the FVG (middle of 3-bar pattern) |
| direction | str | `bullish` / `bearish` |
| fvg_high | float64 | Top of gap (bar[i-1].high for bearish / bar[i+1].low for bullish) |
| fvg_low | float64 | Bottom of gap |
| fvg_mid | float64 | (fvg_high + fvg_low) / 2 |
| atr_mult | float64 | Displacement candle body size / ATR(14) — 1.2× = displacement threshold |
| filled | bool | True if price has returned to fvg_mid (set in post-processing) |

**FVG definition (ST-A2):**
- Middle bar body ≥ 1.2 × ATR(14) (displacement gate)
- For bullish: gap between bar[i−1].high and bar[i+1].low (no overlap)
- For bearish: gap between bar[i+1].high and bar[i−1].low (no overlap)

---

## Extraction Pipeline

```
data/processed/{SYM}/M15.parquet  ──┐
data/processed/{SYM}/H4.parquet   ──┤── extract_features.py ──► data/features/...
```

The extraction script calls `run_strategy(debug=True)` from
`strategy/session_liquidity/session_strategy.py` to get both signals and
intermediate debug events. When debug records include `event: sweep` and
`event: session`, those are written to feature tables directly.

FVG extraction uses `session_smc/fvg.py` independently (no signal chain dependency).

---

## Usage in Research

```python
import pandas as pd

sweeps  = pd.read_parquet("data/features/sweeps/EURUSD.parquet")
fvgs    = pd.read_parquet("data/features/fvg/EURUSD.parquet")
sessions = pd.read_parquet("data/features/sessions/EURUSD.parquet")

# Count sweeps per session per direction
sweeps.groupby(["session", "direction"]).size()

# FVG fill rate
fvgs["filled"].mean()

# Cross-symbol sweep alignment
eur_sweeps = pd.read_parquet("data/features/sweeps/EURUSD.parquet")
gbp_sweeps = pd.read_parquet("data/features/sweeps/GBPUSD.parquet")
```

---

*SMC_FEATURE_SPEC.md | Written 2026-06-25*
