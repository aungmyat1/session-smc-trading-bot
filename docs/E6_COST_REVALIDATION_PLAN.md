# E6_COST_REVALIDATION_PLAN.md
# E6 — Cost Revalidation Plan
# ST-A2 | Session Liquidity Reversal
# Status: PENDING — awaiting Phase 2 collection gate (5 London + 5 NY + 7,000 rows)

---

## Purpose

E6 is a hard gate in the revised demo-trading sequence (`docs/OPS02_REVISED_GATE.md`).
It answers one question: **does ST-A2's Phase-0 PASS hold when backtested against actual
Vantage trading costs instead of the inherited VT Markets placeholder?**

The Phase-0 gate margin is PF_2x = 1.025 — only 0.025 above the minimum. The entire verdict
depends on the cost assumption. E6 replaces the assumption with a measured value before
any live trading begins.

---

## 1 — Current Spread Assumptions (Placeholder)

Source: `config/costs.json → profiles.PLACEHOLDER_vt_markets_assumption`

Active as of 2026-06-24 — all prior backtest results use these numbers.

| Symbol | Standard (pip) | Stress 2× (pip) | Origin |
|---|---|---|---|
| EURUSD | 1.40 | 2.80 | VT Markets Standard account — assumed, not measured |
| GBPUSD | 1.80 | 3.60 | VT Markets Standard account — assumed, not measured |

These numbers were used to produce:
- ST-A2 PASS: PF_std=1.151, PF_2x=1.025 (run 20260621T100458-183aaa)
- All EXP05 variant verdicts

No Vantage-specific measurement was taken before these results were recorded.

---

## 2 — Measured Spread Source

Source: `scripts/capture_spreads.py` running against:
- Account: Vantage Standard STP (VantageMarkets-Demo, MetaAPI ID d6f6eec3-…)
- Symbols: EURUSD, GBPUSD, USDJPY, AUDUSD
- Sessions: London (06:00–09:00 UTC summer) | New York (11:00–14:00 UTC summer)
- Interval: 30 seconds per poll
- Output: `research/spread_samples.csv`

Killzone-hour averages from this file become the `vantage_measured` cost profile.
The cost used in each backtest is the **average spread during the hours the strategy
actually trades** — not the broker's headline or off-hours spread.

---

## 3 — Replacement Methodology

### Step 1 — Confirm gate met

```bash
python3 scripts/check_phase2_completion.py
# Must output: READY_FOR_COST_REVALIDATION
```

If NOT_READY: continue collecting. Do not proceed.

### Step 2 — Compute killzone averages

```bash
python3 -c "
import csv, statistics
from collections import defaultdict
rows = [r for r in csv.DictReader(open('research/spread_samples.csv'))
        if r['session'] in ('london', 'new_york')]
agg = defaultdict(list)
for r in rows:
    agg[r['symbol']].append(float(r['spread_pips']))
for sym in ['EURUSD', 'GBPUSD']:
    vals = agg[sym]
    avg = statistics.mean(vals)
    med = statistics.median(vals)
    p95 = sorted(vals)[int(len(vals)*0.95)]
    print(f'{sym}: avg={avg:.2f}  med={med:.2f}  p95={p95:.2f}  n={len(vals)}')
    print(f'  -> standard={avg:.2f}  stress2x={avg*2:.2f}')
"
```

Use the **average** (not median, not P95) as the standard cost.
2× stress is computed as `standard × 2`.

Rationale for average over median: the backtest applies cost uniformly across all trades.
The average correctly weights high-spread events that would apply to a real trade.
P95 would over-estimate; median would under-estimate in the presence of open-hour spikes.

### Step 3 — Update config/costs.json

Edit `config/costs.json`:
1. Fill `profiles.vantage_measured` with the computed values
2. Set `active_profile = "vantage_measured"`

```json
"vantage_measured": {
  "_note": "Measured YYYY-MM-DD to YYYY-MM-DD — London+NY killzone average",
  "EURUSD": { "standard": <avg>, "stress2x": <avg × 2> },
  "GBPUSD": { "standard": <avg>, "stress2x": <avg × 2> }
},
...
"active_profile": "vantage_measured"
```

Do NOT change any other profile. Do NOT delete the placeholder profile (it preserves
the original PASS record for historical reference).

### Step 4 — Re-run ST-A2 backtest

```bash
python3 scripts/backtest_session_liquidity.py
```

This runs the identical backtest that produced the Phase-0 PASS, with the only change
being the cost profile read from `config/costs.json`. No strategy parameters change.
No signal chain changes.

### Step 5 — Read PF_2x and apply decision table

See §5 below.

---

## 4 — Re-Test Procedure

The backtest script (`scripts/backtest_session_liquidity.py`) reads `config/costs.json`
at startup and applies the active profile. No code changes are required to switch from
placeholder to measured costs. The procedure is:

1. Confirm `active_profile = "vantage_measured"` in `config/costs.json`
2. Run: `python3 scripts/backtest_session_liquidity.py`
3. Record the output: PF_std, PF_2x, n, WR, MaxDD
4. The Run ID is logged automatically to `research/backtest_runs.csv`
5. Populate `docs/BACKTEST_COST_REVALIDATION_REPORT.md` with results

This run is NOT a new trial. It is a revalidation of the existing ST-A2 trial at corrected
costs. Register it in `docs/VERDICT_LOG.md` as a sub-entry under ST-A2 with the measured
cost note, not as a new trial row.

---

## 5 — Acceptance Criteria (E6 Decision Table)

From `docs/OPS02_REVISED_GATE.md`:

| PF_2x result | Status | Action |
|---|---|---|
| ≥ 1.05 | ✅ CONFIRMED — margin comfortable | Proceed to E1–E4 (7-day execution gate) |
| 1.00–1.05 | ✅ CONFIRMED — margin thin | Proceed to E1–E4; monitor GBPUSD closely in demo |
| < 1.00 | ❌ INVALIDATED | Stop. Do not begin demo execution. Prepare ST_A3_RECOVERY_OPTIONS.md |

**The PF_2x < 1.00 case is a hard stop.** The agent does not self-authorise any alternative.
The owner decides next steps from ST_A3_RECOVERY_OPTIONS.md.

---

## 6 — Timeline

| Event | Target date | Status |
|---|---|---|
| Phase 2 collection gate met (5+5 sessions) | ~2026-06-30 | PENDING |
| E6 spread averages computed | 2026-06-30 (same day) | PENDING |
| `config/costs.json` updated | 2026-06-30 | PENDING |
| ST-A2 revalidation backtest run | 2026-06-30 | PENDING |
| E6 verdict applied | 2026-06-30 | PENDING |
| E1–E4 (7-day execution gate) begins | 2026-06-30 (if PF_2x ≥ 1.00) | PENDING |

---

## 7 — What Does NOT Change at E6

E6 changes exactly one thing: the cost profile in `config/costs.json → active_profile`.

| Item | Changes at E6 | Notes |
|---|---|---|
| Strategy logic | ❌ No | `session_strategy.py` unchanged |
| Signal chain | ❌ No | All 11 phases unchanged |
| min_sl_pips | ❌ No | 5.0 pip filter unchanged |
| Risk parameters | ❌ No | 1% risk, 3R daily loss, 10% DD kill switch |
| Backtest script | ❌ No | Same script as Phase-0 run |
| LIVE_TRADING | ❌ No | Remains false until E1–E4 complete |
| VERDICT_LOG.md | ✅ Sub-entry | New row under ST-A2 with measured cost note |
| config/costs.json | ✅ active_profile | vantage_measured, with measured values |

---

*E6_COST_REVALIDATION_PLAN.md | 2026-06-24 | Status: PENDING*
