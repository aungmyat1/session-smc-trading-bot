# EXPERIMENT_RESULTS.md
# Strategy A — Phase-1 Research Experiments
# Base run: 20260621T060745-f6ac57  |  Date: 2026-06-21T09:50:19Z
# Filters applied post-hoc. No production strategy modified.

---

## Baseline (ST-A, RR=5, combined)

| Trades | Net PF (std) | Net PF (2×) | Gap to gate |
|---|---|---|---|
| 181 | 1.126 | 0.965 | +0.035 needed |

---

## Executive Summary
(Best RR per variant, ranked by Net PF 2×)

| # | Exp | Variant | RR | Trades | Win% | Gross PF | Net PF (std) | Net PF (2×) | Δ vs baseline | Max DD | Gate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | EXP-03 | NY only | RR5 | 53 | 39.6% | 1.803 | 1.571 | 1.381 | +0.416 | 11.09R | ❌ FAIL |
| 2 | EXP-04 | Ex GBP/LON | RR5 | 137 | 32.1% | 1.435 | 1.226 | 1.059 | +0.094 | 21.49R | ✅ PASS |
| 3 | EXP-01 | ≥ 5 pip | RR5 | 169 | 32.0% | 1.299 | 1.151 | 1.025 | +0.060 | 18.72R | ✅ PASS |
| 4 | EXP-01 | ≥ 7 pip | RR4 | 166 | 32.5% | 1.286 | 1.142 | 1.020 | +0.055 | 15.50R | ✅ PASS |
| 5 | EXP-02 | ≥ 10 pip | RR5 | 181 | 31.5% | 1.327 | 1.126 | 0.965 | -0.000 | 28.14R | ❌ FAIL |
| 6 | EXP-02 | ≥ 15 pip | RR5 | 181 | 31.5% | 1.327 | 1.126 | 0.965 | -0.000 | 28.14R | ❌ FAIL |
| 7 | EXP-01 | ≥ 10 pip | RR5 | 152 | 31.6% | 1.166 | 1.046 | 0.943 | -0.022 | 26.10R | ❌ FAIL |
| 8 | EXP-02 | ≥ 20 pip | RR5 | 142 | 30.3% | 1.256 | 1.068 | 0.919 | -0.046 | 30.36R | ❌ FAIL |

**3 variant(s) pass Phase-0 gate.** See detailed sections below.

---

## EXP-01 — Minimum SL Floor

*Hypothesis:* Narrow-SL setups have spread_cost_R ≥ 1.08R — removing them improves net PF.

### ≥ 5 pip

| RR | Trades | Win% | Gross PF | Net PF (std) | Net PF (2×) | Δ 2× vs baseline | Max DD | Avg Dur | Gate |
|---|---|---|---|---|---|---|---|---|---|
| RR2 | 169 | 38.5% | 1.152 | 1.003 | 0.877 | -0.088 | 11.57R | 410min | ❌ |
| RR3 | 169 | 34.3% | 1.225 | 1.078 | 0.954 | -0.011 | 11.18R | 531min | ❌ |
| RR4 | 169 | 32.5% | 1.299 | 1.149 | 1.022 | +0.057 | 16.72R | 588min | ✅ |
| RR5 | 169 | 32.0% | 1.299 | 1.151 | 1.025 | +0.060 | 18.72R | 632min | ✅ |

### ≥ 7 pip

| RR | Trades | Win% | Gross PF | Net PF (std) | Net PF (2×) | Δ 2× vs baseline | Max DD | Avg Dur | Gate |
|---|---|---|---|---|---|---|---|---|---|
| RR2 | 166 | 38.0% | 1.124 | 0.983 | 0.864 | -0.101 | 11.57R | 415min | ❌ |
| RR3 | 166 | 33.7% | 1.180 | 1.043 | 0.926 | -0.039 | 13.32R | 538min | ❌ |
| RR4 | 166 | 32.5% | 1.286 | 1.142 | 1.020 | +0.055 | 15.50R | 596min | ✅ |
| RR5 | 166 | 31.9% | 1.277 | 1.135 | 1.015 | +0.050 | 17.50R | 640min | ✅ |

### ≥ 10 pip

| RR | Trades | Win% | Gross PF | Net PF (std) | Net PF (2×) | Δ 2× vs baseline | Max DD | Avg Dur | Gate |
|---|---|---|---|---|---|---|---|---|---|
| RR2 | 152 | 36.2% | 1.025 | 0.908 | 0.808 | -0.157 | 17.06R | 445min | ❌ |
| RR3 | 152 | 32.9% | 1.093 | 0.976 | 0.876 | -0.089 | 23.72R | 573min | ❌ |
| RR4 | 152 | 31.6% | 1.149 | 1.030 | 0.928 | -0.037 | 30.10R | 627min | ❌ |
| RR5 | 152 | 31.6% | 1.166 | 1.046 | 0.943 | -0.022 | 26.10R | 670min | ❌ |

**Trades retained at best variant (≥ 5 pip, RR5):** 169 / 181 (12 removed)

## EXP-02 — Minimum Asian Range

*Hypothesis:* Wider ranges produce larger sweeps and reduce spread_cost_R on SL.

### ≥ 10 pip

| RR | Trades | Win% | Gross PF | Net PF (std) | Net PF (2×) | Δ 2× vs baseline | Max DD | Avg Dur | Gate |
|---|---|---|---|---|---|---|---|---|---|
| RR2 | 181 | 39.2% | 1.200 | 0.992 | 0.824 | -0.141 | 11.28R | 384min | ❌ |
| RR3 | 181 | 33.7% | 1.208 | 1.014 | 0.859 | -0.106 | 18.22R | 498min | ❌ |
| RR4 | 181 | 32.0% | 1.301 | 1.102 | 0.942 | -0.023 | 26.14R | 552min | ❌ |
| RR5 | 181 | 31.5% | 1.327 | 1.126 | 0.965 | -0.000 | 28.14R | 593min | ❌ |

### ≥ 15 pip

| RR | Trades | Win% | Gross PF | Net PF (std) | Net PF (2×) | Δ 2× vs baseline | Max DD | Avg Dur | Gate |
|---|---|---|---|---|---|---|---|---|---|
| RR2 | 181 | 39.2% | 1.200 | 0.992 | 0.824 | -0.141 | 11.28R | 384min | ❌ |
| RR3 | 181 | 33.7% | 1.208 | 1.014 | 0.859 | -0.106 | 18.22R | 498min | ❌ |
| RR4 | 181 | 32.0% | 1.301 | 1.102 | 0.942 | -0.023 | 26.14R | 552min | ❌ |
| RR5 | 181 | 31.5% | 1.327 | 1.126 | 0.965 | -0.000 | 28.14R | 593min | ❌ |

### ≥ 20 pip

| RR | Trades | Win% | Gross PF | Net PF (std) | Net PF (2×) | Δ 2× vs baseline | Max DD | Avg Dur | Gate |
|---|---|---|---|---|---|---|---|---|---|
| RR2 | 142 | 39.4% | 1.188 | 0.985 | 0.821 | -0.144 | 11.28R | 381min | ❌ |
| RR3 | 142 | 33.1% | 1.181 | 0.995 | 0.847 | -0.118 | 17.88R | 481min | ❌ |
| RR4 | 142 | 31.0% | 1.230 | 1.043 | 0.895 | -0.070 | 27.36R | 542min | ❌ |
| RR5 | 142 | 30.3% | 1.256 | 1.068 | 0.919 | -0.046 | 30.36R | 587min | ❌ |

**Trades retained at best variant (≥ 10 pip, RR5):** 181 / 181 (0 removed)

## EXP-03 — NY Session Only

*Hypothesis:* NY win rate (39.6%) and PF 2×=1.344 dominate vs London 28.1% / 0.819.

### NY only

| RR | Trades | Win% | Gross PF | Net PF (std) | Net PF (2×) | Δ 2× vs baseline | Max DD | Avg Dur | Gate |
|---|---|---|---|---|---|---|---|---|---|
| RR2 | 53 | 47.2% | 1.484 | 1.265 | 1.081 | +0.116 | 5.27R | 497min | ❌ |
| RR3 | 53 | 41.5% | 1.528 | 1.318 | 1.147 | +0.182 | 7.09R | 586min | ❌ |
| RR4 | 53 | 39.6% | 1.680 | 1.460 | 1.280 | +0.315 | 11.09R | 646min | ❌ |
| RR5 | 53 | 39.6% | 1.803 | 1.571 | 1.381 | +0.416 | 11.09R | 691min | ❌ |

**Trades retained at best variant (NY only, RR5):** 53 / 181 (128 removed)

## EXP-04 — Exclude GBPUSD London

*Hypothesis:* GBPUSD London (PF 2×=0.701) is the single largest drag on combined PF.

### Ex GBP/LON

| RR | Trades | Win% | Gross PF | Net PF (std) | Net PF (2×) | Δ 2× vs baseline | Max DD | Avg Dur | Gate |
|---|---|---|---|---|---|---|---|---|---|
| RR2 | 137 | 40.9% | 1.294 | 1.078 | 0.902 | -0.063 | 9.03R | 391min | ❌ |
| RR3 | 137 | 35.0% | 1.280 | 1.081 | 0.920 | -0.045 | 15.89R | 519min | ❌ |
| RR4 | 137 | 32.8% | 1.398 | 1.192 | 1.026 | +0.061 | 20.71R | 556min | ✅ |
| RR5 | 137 | 32.1% | 1.435 | 1.226 | 1.059 | +0.094 | 21.49R | 597min | ✅ |

**Trades retained at best variant (Ex GBP/LON, RR5):** 137 / 181 (44 removed)

---

## Key Findings

1. **EXP-03 NY only @ RR5** — PF 2×=1.381 (+0.416 vs 0.965 baseline), n=53
2. **EXP-04 Ex GBP/LON @ RR5** — PF 2×=1.059 (+0.094 vs 0.965 baseline), n=137
3. **EXP-01 ≥ 5 pip @ RR5** — PF 2×=1.025 (+0.060 vs 0.965 baseline), n=169

## Minimum Change That Reaches Gate

**EXP-01 — Minimum SL Floor / ≥ 5 pip @ RR5**

- Trades retained: 169 / 181 (12 removed = least invasive passing filter)
- Net PF (std): 1.151
- Net PF (2×): 1.025 ✅
- Max DD: 18.72R

Removes the fewest trades while crossing the gate.
Register as new trial (ST-A2) in VERDICT_LOG.md before implementing.

---

*Base run: 20260621T060745-f6ac57 | Generated: 2026-06-21T09:50:19Z*