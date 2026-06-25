# ST-A2 Real Data Validation — Final Verdict
Generated: 2026-06-25T15:45:00Z

---

## VERDICT: ⚠️ CONDITIONAL PASS

The real-data pipeline is working correctly. The 2024 EURUSD result is weaker than
2025 (PF_std 0.738 vs 1.067) but falls within expected single-year sampling variance
for n=14 trades. The Phase-0 gate (n≥50, PF>1.0 at std+2× stress) requires 5-year
multi-pair data and was already passed — this run does not replace it.

---

## Summary of All Phases

| Phase | Task | Outcome | Report |
|---|---|---|---|
| Phase 1 | Build OHLCV from tick data | ✅ PASS — 6 TFs built, 20.65M ticks processed | TIMEFRAME_BUILD_REPORT.md |
| Phase 2 | Dataset validation | ✅ PASS — 0 errors, warnings are expected FX behavior | FINAL_DATASET_VALIDATION.md |
| Phase 3 | ST-A2 replay (real data) | ✅ EXECUTED — 14 trades simulated, reports written | STA2_BASELINE_REPORT.md |
| Phase 4 | Replay sanity check | ⚠️ BELOW n GATE — 14 trades (consistent with known frequency) | ST_A2_REAL_DATA_SANITY_CHECK.md |
| Phase 5 | Manual audit of 14 trades | ✅ PASS — 14/14 (100%) pass 7/7 checklist items | ST_A2_MANUAL_AUDIT_20_TRADES.md |
| Phase 6 | Final verdict | ⚠️ CONDITIONAL PASS | This document |

---

## Key Metrics — 2024 EURUSD ST-A2 Real Data

| Metric | 2024 Result | 2025 Result | Phase-0 Baseline |
|---|---|---|---|
| n (trades) | 14 | 16 | 169 (EUR+GBP, 5yr) |
| Win Rate | 42.9% | 31.2% | 32.0% |
| Gross PF | 0.883 | 1.202 | — |
| PF (std 1.4pip) | 0.738 | 1.067 | 1.151 |
| PF (2× stress) | 0.621 | 0.948 | 1.025 |
| Max DD | 3.95R | 6.89R | 18.72R |
| Expectancy | −0.166R/trade | +0.048R/trade | — |
| Data source | Real Dukascopy ticks | CSV historical | MT5 CSV (5yr) |

---

## Phase-0 Gate Checklist

| Gate | Threshold | 2024 Result | Status | Authoritative? |
|---|---|---|---|---|
| n ≥ 50 | 50 | 14 | ❌ BELOW | Single pair + single year cannot clear this gate |
| PF > 1.0 (std) | 1.000 | 0.738 | ❌ BELOW | Not authoritative at n=14 |
| PF > 1.0 (2×) | 1.000 | 0.621 | ❌ BELOW | Not authoritative at n=14 |

**The Phase-0 gate is not in scope for this run.** It was already passed by the 5-year
EUR+GBP multi-pair baseline (VERDICT_LOG, row ST-A2, n=169, PF_2x=1.025). This
supplementary run validates the REAL DATA PIPELINE, not the strategy edge itself.

---

## What This Run Proved

### ✅ Confirmed

1. **Real data pipeline works end-to-end:**
   Dukascopy tick → bi5 decode → Parquet → OHLCV resample → ST-A2 signal chain →
   trade simulation → metrics report. No data format errors, no import failures,
   no schema mismatches.

2. **ST-A2 signal chain is executing correctly on real institutional data:**
   14/14 trades (100%) pass the 7-point manual audit. Sessions, bias, SL math,
   RR, and exit logic are all correct.

3. **Trade frequency is consistent with established production data:**
   14 trades/year (2024) vs 16 trades/year (2025). Both match the Phase-0 rate
   of ~14/year for EURUSD alone (169 / 5yr / 2 pairs ≈ 17/pair/year).

4. **Weekend and holiday bars in Dukascopy tick data do not contaminate the signal chain:**
   The EST killzone filter correctly excludes non-trading hours.

5. **No lookahead or parameter drift detected:**
   Signal chain matches the ST-A2 canonical spec (DEFAULT_CONFIG, min_sl_pips=5.0).

### ⚠️ Flagged (not blocking)

1. **2024 PF is weaker than 2025:**
   PF_std 0.738 vs 1.067. With n=14, a difference of 3–4 trade outcomes explains
   the entire gap. November 2024 (3 trades, 2 losses including a 44.6-pip wide-SL
   loss post-election) accounts for −1.49R.

2. **H4 context limited to 2024 only:**
   The Phase-0 baseline used 5+ years of H4 data. Starting 2024 with no prior-year
   H4 context means the bias filter may have been slower to establish directional
   structure in January 2024 (no January trades were generated).

3. **Session_end exits dominate profitable trades:**
   Of 6 winning trades, only 1 hit the full 3R TP (T04). The other 5 winners exited
   at session end with 0.075–1.697R. This is structurally correct behavior but
   reduces the realized RR vs the theoretical 3.0.

---

## Signal Chain Funnel (2024)

| Stage | Count | Interpretation |
|---|---|---|
| Trading days | ~261 | Full FX year |
| Days with valid Asian range | 154 (59%) | Many low-vol days below 15-pip minimum |
| Sweeps detected | 83 | ~1 sweep per 2 range-eligible days |
| Signals generated | 14 | 16.9% sweep→signal conversion (displacement gate) |
| Signals rejected (SL < 5pip) | 2 | min_sl_pips gate working |

Primary funnel bottlenecks:
1. Asian range too small (41% of days skipped)
2. H4 bias = neutral (40% of killzone bar evaluations)
3. Displacement < 1.2× ATR (73.6% of sweeps rejected)

---

## Recommendations

1. **Do not redesign ST-A2 based on 2024 alone.** n=14 has too much sampling noise.
   The 5-year Phase-0 baseline (n=169) is the authoritative data source.

2. **Expand Dukascopy dataset to 2021–2023** to run a full 5-year real-data replay
   for ST-A2. This would provide n≈70–80 EURUSD trades and a definitive real-data
   validation with Phase-0 statistical power.

3. **Continue demo trading** per §3 Phase Plan — Phase-0 gate was passed, no evidence
   of structural strategy deterioration. 2024 underperformance is within variance.

4. **Do not add filters to compensate for 2024 weakness.** That path leads to
   overfitting (the ag-auto-trade graveyard pattern). Any new filter = new trial ID.

---

## Data Lineage

```
Dukascopy bi5 tick feed (institutional)
  → scripts/download_dukascopy.py (LZMA decode, 2 workers max)
  → data/raw/dukascopy/EURUSD/2024/{01-12}/ticks.parquet (20.65M ticks, 199.6 MB)
  → scripts/build_timeframes.py (mid-price resample)
  → data/processed/EURUSD/{M1,M5,M15,H1,H4,D1}.parquet
  → scripts/replay_db.py --symbol EURUSD --start 2024-01-01 --end 2024-12-31 --dry-run
  → strategy/session_liquidity/session_strategy.py (ST-A2 canonical, no modifications)
  → 14 trades, reports/STA2_BASELINE_REPORT.md
```

**No synthetic data. No parameter modifications. No lookahead.**

---

## Final Statement

The Dukascopy EURUSD 2024 real-data validation run is COMPLETE.
The pipeline is production-ready. The strategy executes correctly on real tick data.
The 2024 PF result (0.738 std) is below the Phase-0 gate threshold but is not
authoritative at n=14 — it represents one of the weaker possible 14-trade samples
from a strategy whose 5-year edge (PF_2x=1.025) has been independently validated.

**Next step: Expand tick data download to 2021–2023 for a 5-year real-data run.**
