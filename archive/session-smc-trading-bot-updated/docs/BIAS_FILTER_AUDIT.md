# BIAS_FILTER_AUDIT.md
# SA-02 — H4 Lookahead Audit
# Purpose: prove which candles are visible vs excluded at any given before_dt,
#          and why the final bias is produced.

---

## Shared Setup

- 13 bars at 4-hour intervals starting 2024-01-15T00:00:00Z
- Bars: idx 0–12 (open times T0, T0+4h, T0+8h, …, T0+48h)
- `swing_n = 2`: pivot requires 2 bars strict-greater on each side
- Cutoff rule: `cutoff = before_dt − 4h`; bar included iff `bar_open_time ≤ cutoff`

---

## Example A — BULLISH

### Dataset

```
idx  open_time (UTC)          high    low
0    2024-01-15T00:00:00Z     1.0     0.5
1    2024-01-15T04:00:00Z     2.0     1.0
2    2024-01-15T08:00:00Z     5.0     0.8   ← Swing High #1 (5 > 2,1 left; 5 > 2,1 right)
3    2024-01-15T12:00:00Z     2.0     0.5
4    2024-01-15T16:00:00Z     1.0     0.2   ← Swing Low  #1 (0.2 < 0.5,1 left; 0.2 < 0.8,0.5 right)
5    2024-01-15T20:00:00Z     2.0     0.8
6    2024-01-16T00:00:00Z     3.0     0.5
7    2024-01-16T04:00:00Z     3.0     0.8
8    2024-01-16T08:00:00Z     2.0     0.5
9    2024-01-16T12:00:00Z     1.0     0.3   ← Swing Low  #2 (0.3 < 0.5,0.8 left; 0.3 < 1.5,0.5 right)
10   2024-01-16T16:00:00Z     8.0     1.5   ← Swing High #2 (8 > 1,2 left; 8 > 2,1 right)
11   2024-01-16T20:00:00Z     2.0     0.5
12   2024-01-17T00:00:00Z     1.0     0.2
```

### Visibility at `before_dt = 2024-01-17T04:00:00Z`

```
cutoff = 2024-01-17T04:00:00Z − 4h = 2024-01-17T00:00:00Z

idx 0–12  open_time ≤ 2024-01-17T00:00:00Z  → ALL VISIBLE  ✓
```

**Swing detection on all 13 bars:**
- `_swing_highs`: idx2 (5.0), idx10 (8.0)
- `_swing_lows`:  idx4 (0.2), idx9 (0.3)

**Bias classification:**
```
sh_prev = 5.0,  sh_last = 8.0  →  sh_last > sh_prev  (HH ✓)
sl_prev = 0.2,  sl_last = 0.3  →  sl_last > sl_prev  (HL ✓)
Both conditions met  →  BULLISH
```

### What changes at `before_dt = 2024-01-17T00:00:00Z` (last bar still forming)

```
cutoff = 2024-01-17T00:00:00Z − 4h = 2024-01-16T20:00:00Z

idx 12  open_time = 2024-01-17T00:00:00Z  >  cutoff  →  EXCLUDED ✗
         (bar 12 has not closed yet — reading it would be lookahead)

Visible bars: idx 0–11
```

**Swing detection on 12 bars (idx 0–11):**
- `_swing_highs`: idx2 (5.0), idx10 (8.0) — both still visible ✓
- `_swing_lows`: loop runs over `range(2, 10)` = idx 2–9
  - idx4: 0.2 < 0.5,1.0 left ✓;  0.2 < 0.8,0.5 right ✓  →  SL ✓
  - idx9: 0.3 < 0.5,0.8 left ✓;  0.3 < 1.5 right but needs idx11 (0.5) ✓  →  SL ✓

Both SHs and SLs confirmed → still **BULLISH** here (bar 12 carries no swing).

### Critical boundary — last bar IS the right-side neighbour

To show lookahead matters, consider a dataset where the last bar is the **right-side
confirmation** of the second SH. With bars 0–11 and `swing_n=2`, idx10 would need
idx11 and idx12 as right-side neighbours. Excluding idx12 leaves only idx11 → the
pivot at idx10 cannot be confirmed:

```
Scenario: 11-bar dataset (idx 0–10 only), before_dt = T(idx10_close).
  idx10 cannot be confirmed as SH (needs 2 right bars, but only 0 available).
  Only 1 SH visible → neutral.

Add idx11, idx12 → idx10 gains 2 right bars → 2nd SH confirmed → bullish.
```

This is exactly what `test_bar_excluded_when_open_time_equals_before_dt` tests.

---

## Example B — BEARISH

### Dataset

```
idx  open_time (UTC)          high    low
0    2024-01-15T00:00:00Z     1.0     0.5
1    2024-01-15T04:00:00Z     2.0     1.5
2    2024-01-15T08:00:00Z     8.0     1.0   ← Swing High #1 (8 > 2,1 left; 8 > 2,1 right)
3    2024-01-15T12:00:00Z     2.0     0.5
4    2024-01-15T16:00:00Z     1.0     0.3   ← Swing Low  #1 (0.3 < 1.5,1.0 left; 0.3 < 1.0,0.5 right)
5    2024-01-15T20:00:00Z     2.0     1.0
6    2024-01-16T00:00:00Z     3.0     0.5
7    2024-01-16T04:00:00Z     3.0     0.8
8    2024-01-16T08:00:00Z     2.0     0.5
9    2024-01-16T12:00:00Z     1.0     0.2   ← Swing Low  #2 (0.2 < 0.5,0.8 left; 0.2 < 1.5,0.5 right)
10   2024-01-16T16:00:00Z     5.0     1.5   ← Swing High #2 (5 > 1,2 left; 5 > 2,1 right)
11   2024-01-16T20:00:00Z     2.0     0.5
12   2024-01-17T00:00:00Z     1.0     0.3
```

### Visibility at `before_dt = 2024-01-17T04:00:00Z`

```
cutoff = 2024-01-17T00:00:00Z  →  ALL 13 bars visible  ✓
```

**Swing detection on all 13 bars:**
- `_swing_highs`: idx2 (8.0), idx10 (5.0)
- `_swing_lows`:  idx4 (0.3), idx9 (0.2)

**Bias classification:**
```
sh_prev = 8.0,  sh_last = 5.0  →  sh_last < sh_prev  (LH ✓)
sl_prev = 0.3,  sl_last = 0.2  →  sl_last < sl_prev  (LL ✓)
Both conditions met  →  BEARISH
```

---

## Strict-Inequality Rule (equal highs/lows)

A swing pivot requires **strict** `>` or `<` against all neighbours:

```
# equal high at idx5 and idx6 in a dataset:
highs = [1, 2, 5, 2, 1, 3, 3, 2, 1, 2, 8, 2, 1]
                         ↑   ↑
                     idx5=3, idx6=3 (equal)

idx5: highs[5]=3 > highs[6]=3?  → FALSE  →  idx5 NOT a swing high
idx6: highs[6]=3 > highs[5]=3?  → FALSE  →  idx6 NOT a swing high

Internal equal bars never block a clear peak elsewhere.
idx2=5 and idx10=8 confirmed normally → HH → bullish.
```

If the **two confirmed SHs** are equal (SH1 = SH2):
```
sh_last > sh_prev?   5.0 > 5.0  →  FALSE
sh_last < sh_prev?   5.0 < 5.0  →  FALSE
→ neutral (strict inequality enforced at classification stage too)
```

---

## Summary

| Condition | before_dt | Bars visible | SHs | SLs | Result |
|---|---|---|---|---|---|
| All bars closed | T+52h | 0–12 (13 bars) | idx2, idx10 | idx4, idx9 | bullish/bearish |
| Last bar forming | T+48h | 0–11 (12 bars) | depends on pivot | depends | varies |
| Equal SHs | any | all | idx2=5, idx10=5 | idx4, idx9 | neutral |
| Only 1 SH | any | all | idx2 only | idx4, idx9 | neutral |
| < 5 bars total | any | < 5 | none | none | neutral |

**The cutoff formula `before_dt − 4h` is the single point of lookahead control.**
Using `bar_open_time ≤ before_dt` (naïve) instead would include the currently-forming
bar and allow the model to "see" a candle that hasn't closed — invalidating all results.
