# E6_PAIR_ANALYSIS.md
# ST-A2 — Pair-Level Analysis at Measured Costs
# Status: TEMPLATE — populate after E6 backtest completes
# Purpose: Determine whether each pair remains viable individually under measured spread

---

## Why Pair-Level Analysis Matters

At placeholder costs (PRE_E6_BASELINE):
- **EURUSD alone: PF_2x = 0.945** — already fails 2× stress
- **GBPUSD alone: PF_2x = 1.168** — carries the combined pass

EURUSD's viability under measured costs is the critical question.
If measured EURUSD spread > placeholder (1.4 pip), combined PF_2x degrades further.
If measured GBPUSD spread < placeholder (1.8 pip) — preliminary data shows 1.55 pip avg —
GBPUSD improves and may offset any EURUSD deterioration.

---

## Baseline Reference (PRE_E6_BASELINE, placeholder costs, RR 5)

| Metric | EURUSD | GBPUSD | Combined |
|---|---|---|---|
| Trades | 105 | 64 | 169 |
| Win rate | 29.5% | 35.9% | 32.0% |
| Gross PF | 1.196 | 1.484 | 1.299 |
| Net PF (std) | 1.059 | 1.314 | 1.151 |
| **Net PF (2×)** | **0.945** | **1.168** | **1.025** |
| Max DD | 14.00 R | 9.70 R | 18.72 R |
| Total net R | 4.61 R | 13.67 R | 18.28 R |
| Spread (std) | 1.4 pip (placeholder) | 1.8 pip (placeholder) | — |

---

## EURUSD — E6 Results

*Populate after `bash scripts/run_e6_revalidation.sh` and reading `docs/BACKTEST_RESULTS.md`.*

| Metric | Baseline (placeholder) | E6 (measured) | Delta | Direction |
|---|---|---|---|---|
| Trades | 105 | | | |
| Win rate | 29.5% | | | |
| Gross PF | 1.196 | | | |
| Net PF (std) | 1.059 | | | |
| **Net PF (2×)** | **0.945** | | | |
| Max DD | 14.00 R | | | |
| Total net R | 4.61 R | | | |
| Spread applied (std) | 1.4 pip | *from cost_model.json* | | |

### EURUSD Viability Assessment

| Condition | Threshold | E6 Result | Status |
|---|---|---|---|
| Net PF (std) > 1.0 | 1.0 | *pending* | *pending* |
| Net PF (2×) > 1.0 | 1.0 | *pending* | *pending* |
| Measured spread ≤ placeholder | ≤ 1.4 pip | *pending* | *pending* |

**Guidance:** EURUSD already fails 2× stress at placeholder costs. For E6 to improve
EURUSD's standing, the measured killzone spread must be materially below 1.4 pip.
Preliminary data (1 session): 1.35 pip avg — which would slightly improve PF_2x but
is unlikely to bring it above 1.0 at 2× stress. EURUSD's contribution to the
combined pass depends primarily on its gross R, which is independent of spread cost.

---

## GBPUSD — E6 Results

*Populate after E6 backtest.*

| Metric | Baseline (placeholder) | E6 (measured) | Delta | Direction |
|---|---|---|---|---|
| Trades | 64 | | | |
| Win rate | 35.9% | | | |
| Gross PF | 1.484 | | | |
| Net PF (std) | 1.314 | | | |
| **Net PF (2×)** | **1.168** | | | |
| Max DD | 9.70 R | | | |
| Total net R | 13.67 R | | | |
| Spread applied (std) | 1.8 pip (placeholder) | *from cost_model.json* | | |

### GBPUSD Viability Assessment

| Condition | Threshold | E6 Result | Status |
|---|---|---|---|
| Net PF (std) > 1.0 | 1.0 | *pending* | *pending* |
| Net PF (2×) > 1.0 | 1.0 | *pending* | *pending* |
| Measured spread ≤ placeholder | ≤ 1.8 pip | *pending* | *pending* |

**Guidance:** GBPUSD passes 2× stress at placeholder (PF_2x = 1.168) with comfortable
margin. Preliminary data shows ~1.55 pip avg vs 1.80 pip placeholder — a −0.25 pip
improvement. This would materially improve GBPUSD's PF_2x. GBPUSD is the key driver
of the combined pass; any improvement here strengthens the case for E1–E4 gate.

---

## Portfolio Contribution (E6)

*Populate after E6 backtest.*

| Pair | E6 PF_2x | Contribution to pass | Action |
|---|---|---|---|
| EURUSD | *pending* | *pending* | *pending* |
| GBPUSD | *pending* | *pending* | *pending* |
| Combined | *pending* | *pending* | *pending* |

### Contribution Guidance Table

| EURUSD PF_2x | GBPUSD PF_2x | Combined expectation | Action |
|---|---|---|---|
| ≥ 1.00 | ≥ 1.00 | Solid — both pairs viable | Trade both pairs |
| < 1.00 | ≥ 1.10 | GBPUSD carries combined | Trade both; monitor EUR |
| < 1.00 | 1.00–1.10 | Marginal — combined near gate | Restrict to GBPUSD only; re-evaluate EUR |
| < 1.00 | < 1.00 | REJECT | Stop — write ST_A3_RECOVERY_OPTIONS.md |

---

## Pair Exclusion Trigger

If E6 shows EURUSD PF_2x < 0.90 AND GBPUSD PF_2x ≥ 1.10:
→ Consider registering a GBPUSD-only variant as ST-A3 (new trial, not an optimization of ST-A2)
→ Do NOT modify ST-A2 strategy code — register a new trial

This is NOT authorized in this document. It requires a new VERDICT_LOG.md entry.

---

*E6_PAIR_ANALYSIS.md | Template | Populate after E6 ~2026-06-30*
