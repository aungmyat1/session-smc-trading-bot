# E6_SESSION_ANALYSIS.md
# ST-A2 — Session-Level Analysis at Measured Costs
# Status: TEMPLATE — populate after E6 backtest completes
# Purpose: Validate whether New York remains the primary edge source after measured costs

---

## Why Session-Level Analysis Matters

At placeholder costs (PRE_E6_BASELINE):
- **London: Net PF (std) = 0.949** — already sub-1.0 at standard spread
- **New York: Net PF (std) = 1.731** — sole source of combined profitability

London is a net drag at placeholder costs. The key E6 question: does London become
marginally viable with measured costs, or does it remain sub-1.0?

This matters for E1 (demo gate): if London is consistently unprofitable, a session
restriction to NY-only could be proposed as ST-A3 — but that would be a new trial,
not an optimization of ST-A2.

---

## Baseline Reference (PRE_E6_BASELINE, placeholder costs, RR 5, combined EUR+GBP)

| Metric | London | New York | Combined |
|---|---|---|---|
| Trades | 118 | 51 | 169 |
| Win rate | 28.0% | 41.2% | 32.0% |
| Net PF (std) | **0.949** | **1.731** | **1.151** |
| Net PF (2×) | *N/A in baseline doc* | *N/A in baseline doc* | 1.025 |
| Spread applied | London: 06–09 UTC avg | NY: 11–14 UTC avg | — |

*Note: Per-session PF_2x is not in the PRE_E6_BASELINE doc. E6 will show this
for the first time with session-specific measured costs.*

---

## London Session — E6 Results

*Populate after `bash scripts/run_e6_revalidation.sh` and reading `docs/BACKTEST_RESULTS.md`.*

London session hours: 06:00–09:00 UTC (summer EDT)
Spread measurement: killzone average from `research/cost_model.json` → `london` bucket

| Metric | Baseline (placeholder) | E6 (measured) | Delta | Direction |
|---|---|---|---|---|
| Trades | 118 | | | |
| Win rate | 28.0% | | | |
| Net PF (std) | **0.949** | | | |
| Net PF (2×) | *not captured* | | | |
| Max DD | *not captured* | | | |
| Total net R | *not captured* | | | |
| London spread (measured) | 1.4/1.8 pip (assumed) | *from cost_model.json* | | |

### London Preliminary Spread Data (1 session, 2026-06-24)

From `research/SPREAD_CAPTURE_INTERIM.md`:

| Symbol | London avg (pip) | Placeholder | Trend |
|---|---|---|---|
| EURUSD | 1.35 | 1.40 | Lower |
| GBPUSD | 1.55 | 1.80 | Lower |

Preliminary signal: measured London spreads are below placeholder. If this holds
across 5 sessions, London PF_std may improve from 0.949 toward 1.0.
Whether it crosses 1.0 will be determined at E6.

### London Viability Assessment

| Condition | E6 Result | Implication |
|---|---|---|
| Net PF (std) ≥ 1.0 | *pending* | London is self-sustaining |
| Net PF (std) 0.90–1.00 | *pending* | Marginal drag — acceptable if NY > 1.5 |
| Net PF (std) < 0.90 | *pending* | Material drag — consider NY-only as ST-A3 |

---

## New York Session — E6 Results

*Populate after E6 backtest.*

New York session hours: 11:00–14:00 UTC (summer EDT)
Spread measurement: killzone average from `research/cost_model.json` → `new_york` bucket

| Metric | Baseline (placeholder) | E6 (measured) | Delta | Direction |
|---|---|---|---|---|
| Trades | 51 | | | |
| Win rate | 41.2% | | | |
| Net PF (std) | **1.731** | | | |
| Net PF (2×) | *not captured* | | | |
| Max DD | *not captured* | | | |
| Total net R | *not captured* | | | |
| NY spread (measured) | 1.4/1.8 pip (assumed) | *from cost_model.json* | | |

### NY Viability Assessment

| Condition | E6 Result | Implication |
|---|---|---|
| Net PF (std) ≥ 1.5 | *pending* | NY is the primary edge — healthy |
| Net PF (std) 1.0–1.5 | *pending* | NY viable but weaker than baseline |
| Net PF (std) < 1.0 | *pending* | Critical failure — combined likely fails |

**NY must stay above 1.0 for the combined strategy to pass at measured costs.**

---

## Session Contribution to Total Return (E6)

*Populate after E6 backtest.*

| Session | Trades | Total net R | % of combined R | Role |
|---|---|---|---|---|
| London | *pending* | *pending* | *pending* | *pending* |
| New York | *pending* | *pending* | *pending* | *pending* |
| Combined | 169 | *pending* | 100% | — |

**Baseline:** London contributed ~4.61R / (4.61+13.67) = 25.2% of total net R.
NY contributed 74.8% at placeholder costs.

---

## Session Restriction Trigger

If E6 shows London Net PF (std) < 0.90 consistently across all 5 sessions,
and NY Net PF (std) ≥ 1.50:

→ Document finding in `docs/VERDICT_LOG.md` as a sub-observation under ST-A2
→ Flag for ST-A3 trial: NY-only variant (new trial, not optimization)
→ Do NOT restrict ST-A2 to NY-only — that changes the strategy spec and requires new registration

This is a post-E6 decision only. No action during collection.

---

## Session Timing Risk

New York spread data collection started 2026-06-24 (same day as London).
Only 1 NY session captured so far (24 rows per symbol). Sample size is small.
Preliminary NY finding: EURUSD 1.35, GBPUSD 1.56 — consistent with London.

This may not hold. NY session opens (13:00–14:00 UTC) can have wider spreads at
certain market conditions. 5 NY sessions (≥120 rows per symbol) is the minimum
for a stable average.

---

*E6_SESSION_ANALYSIS.md | Template | Populate after E6 ~2026-06-30*
