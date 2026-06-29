# VALIDATION_01_SINGLE_DAY.md
# SA-07 — Strategy A End-to-End Validation
# Date: 2023-03-14 | Audit mode only. No trades executed.

---

## Purpose

Verify that `run_strategy()` wiring produces the same decisions as the manual
signal chain audit in `docs/DRY_RUN_2023_03_14.md`. This is the first end-to-end
run of all SA-01 through SA-06 modules working together.

---

## Run Parameters

| Parameter | Value |
|---|---|
| Date | 2023-03-14 |
| Symbols | EURUSD, GBPUSD |
| Data source | Dukascopy M15 + H4 (via `data/historical/`) |
| RR tested | 2, 3, 4, 5 (single RR=3 shown below) |
| ATR period | 14 (Wilder's, M15) |
| Displacement mult | 1.2× ATR |
| SL buffer | 2 pips |
| Sweep timeout | 4 bars |
| DST | 2023-03-14 is post-spring-forward → EDT (UTC−4) |

---

## EURUSD — 2023-03-14

### Phase 1 — Asian Session Range

EST 18:00 (2023-03-13) → EST 02:00 (2023-03-14)
EDT offset → UTC window: **2023-03-13T22:00Z → 2023-03-14T06:00Z**

| | Value |
|---|---|
| Asian High | `1.07309` |
| Asian Low  | `1.06970` |
| Range      | 33.9 pips ✅ (≥ 15 pip min) |

### Phase 2 — HTF Bias

4H swing analysis as of first London bar (06:00 UTC):
- HTF Bias: **bullish** (HH+HL confirmed on H4)
- Long setups only for this day

### Phase 3 — Killzone Windows (EDT)

| Session | EDT | UTC |
|---|---|---|
| London | 02:00–05:00 | **06:00–09:00** |
| New York | 07:00–10:00 | **11:00–14:00** |

### Intraday Timeline

| Time (UTC) | Event | Detail |
|---|---|---|
| pre-London | Asian Range built | H=1.07309 L=1.06970 range=33.9pip |
| 06:00 | No sweep | H=1.07126 L=1.07049 — no breach of Asian Low |
| **06:15** | **SWEEP 1 DETECTED** | low=1.06942 < asian_low=1.06970 ✓; close=1.07006 > asian_low ✓; bias=bullish ✓ |
| 06:30 | Disp pending [1/4] | body=0.00037 ≤ 1.2×ATR(0.00084) — body too small |
| 06:45 | Disp pending [2/4] | body=0.00001 ≤ 1.2×ATR(0.00084) — doji |
| 07:00 | Disp pending [3/4] | body=0.00034 ≤ 1.2×ATR(0.00084) — body too small |
| 07:15 | Disp pending [4/4] | body passes but close_pos=6.09% ≤ 75% — bearish bar |
| 07:30 | **SWEEP 1 TIMEOUT** | 4 bars elapsed, no valid displacement |
| 07:45 | No sweep | close_outside_range — low pierced but close also below asian_low |
| **08:00** | **SWEEP 2 DETECTED** | low=1.06878 < asian_low=1.06970 ✓; close=1.06924 > asian_low ✓ |
| 08:15 | Disp pending [1/4] | body=0.00004 ≤ 1.2×ATR(0.00102) |
| 08:30 | Disp pending [2/4] | body=0.00054 ≤ 1.2×ATR(0.00108) |
| **08:45** | **DISPLACEMENT CONFIRMED** | body=0.00131 > 1.2×ATR(0.00096)=0.00115 ✓; close_pos=95.6% > 75% ✓ |
| 11:00–13:45 | No sweep (NY session) | Price above Asian range — no bearish breach; bias still bullish |

### Displacement Candle (08:45 UTC)

| Field | Value |
|---|---|
| Open | 1.06933 |
| High | 1.07072 |
| Low  | 1.06892 |
| Close | 1.07064 |
| Body | 0.00131 (13.1 pip) |
| ATR(14) | ~0.00096 (9.6 pip) |
| Threshold | 1.2 × 0.00096 = 0.00115 |
| Body > threshold? | **YES** ✅ |
| Close position | (1.07064 − 1.06892) / (1.07072 − 1.06892) = **95.6%** |
| > 75%? | **YES** ✅ |

### Signal — EURUSD LONG

| Field | Value |
|---|---|
| Side | **long** |
| Session | london |
| Entry | **1.07064** (close of displacement bar) |
| Stop Loss | **1.06858** (sweep_price 1.06878 − 2 pip) |
| Risk | 20.6 pips |
| TP (RR 2) | 1.07476 (41.2 pip) |
| TP (RR 3) | 1.07682 (61.8 pip) |
| TP (RR 4) | 1.07888 (82.4 pip) |
| TP (RR 5) | 1.08094 (103.0 pip) |

### Decision Tree

```
[ASIAN RANGE] 33.9 pip ≥ 15 pip min ✅
  → [HTF BIAS] bullish ✅
    → [LONDON 06:00] No sweep (no_breach) ✗
    → [LONDON 06:15] SWEEP 1: bullish_sweep ✅
      → [06:30] body too small ✗
      → [06:45] doji ✗
      → [07:00] body too small ✗
      → [07:15] wrong quartile ✗ → TIMEOUT
    → [LONDON 07:45] No sweep (close_outside_range) ✗
    → [LONDON 08:00] SWEEP 2: bullish_sweep ✅
      → [08:15] body too small ✗
      → [08:30] body too small ✗
      → [08:45] DISPLACEMENT ✅ → SIGNAL: LONG @ 1.07064
    → [NY session] session_traded → SKIP
```

---

## GBPUSD — 2023-03-14

### Phase 1 — Asian Range

| | Value |
|---|---|
| Asian High | `1.21886` |
| Asian Low  | `1.21450` |
| Range      | 43.6 pips ✅ (≥ 20 pip min) |

### Phase 2 — Bias

HTF Bias: **bullish** (4H HH+HL)

### Timeline

| Time (UTC) | Event | Detail |
|---|---|---|
| 06:00–07:45 | No sweep | London bars inside Asian range |
| **08:00** | **SWEEP DETECTED** | low=1.21442 < asian_low=1.21450 ✓; close=1.21548 > asian_low ✓ |
| 08:15 | Disp pending [1/4] | body=0.00072 ≤ 1.2×ATR(0.00139) |
| 08:30 | Disp pending [2/4] | body=0.00057 ≤ 1.2×ATR(0.00140) |
| **08:45** | **DISPLACEMENT CONFIRMED** | body passes; close_pos > 75% ✅ |
| 12:30 | Sweep attempt | low < asian_low ✓ — but session_traded=london → skipped |

### Signal — GBPUSD LONG

| Field | Value |
|---|---|
| Side | **long** |
| Session | london |
| Entry | **1.21663** |
| Stop Loss | **1.21422** (sweep 1.21442 − 2 pip) |
| Risk | 24.1 pips |
| TP (RR 3) | 1.22386 (72.3 pip) |

---

## Cross-Check: run_strategy() vs dry_run.py

| Check | dry_run.py | run_strategy() | Match |
|---|---|---|---|
| EURUSD Asian H | 1.07309 | 1.07309 | ✅ |
| EURUSD Asian L | 1.06970 | 1.06970 | ✅ |
| EURUSD bias | bullish | bullish | ✅ |
| EURUSD sweep 1 | 06:15 UTC | 06:15 UTC | ✅ |
| EURUSD sweep 2 | 08:00 UTC | 08:00 UTC | ✅ |
| EURUSD entry | 1.07064 | 1.07064 | ✅ |
| EURUSD SL | 1.06858 | 1.06858 | ✅ |
| GBPUSD Asian H | 1.21886 | 1.21886 | ✅ |
| GBPUSD entry | 1.21663 | 1.21663 | ✅ |

All gates agree. `run_strategy()` is wired correctly.

---

## Key Observations

1. **Sweep timeout is critical:** Sweep 1 at 06:15 had 4 bars of small-body consolidation. The timeout correctly cancelled it; Sweep 2 at 08:00 produced the actual institutional move.

2. **ATR warm-up:** ATR at the displacement bar is ~9.6 pip. This is computed from the full M15 history (not just the current day), so warmup is always satisfied for mid-day bars.

3. **DST verified:** London session at 06:00 UTC (not 07:00) confirms EDT is applied correctly via `zoneinfo`.

4. **Session gate works:** After the London signal, the 12:30 UTC sweep on GBPUSD was skipped because `"london" ∈ session_traded`. NY session remained open but no sweep occurred there.

---

*Generated by: manual audit + `scripts/dry_run.py` + `run_strategy()` on 2023-03-14 data.*
*Cross-reference: `docs/DRY_RUN_2023_03_14.md`*
