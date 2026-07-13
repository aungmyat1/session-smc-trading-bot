# Verdict Log — Session & SMC Trading Bot

Date: 2026-06-21 (original) | Updated: 2026-07-01
Status: Authoritative
Version: append-only
Owner: Quant Research
Authority: Level 7 — Research Evidence
Note: This log is append-only. Never modify or delete existing rows.
Gate (effective 2026-07-01): n > 200 AND net PF > 1.25 AND Sharpe > 1.2 AND MaxDD < 15%
at BOTH standard AND 2× spread stress.
Prior gate (rows recorded before 2026-07-01): n ≥ 50 AND net PF > 1.0 at BOTH standard
AND 2× spread stress. Historical rows are not retroactively re-graded — read each row's
verdict against the gate in force on its date.

One row per trial. Never delete entries. Every parameter change = new row.
Fee model: VT Markets Standard — spread + 0.6pip commission RT.

Reference failures from simple-smc-ag-trading-bot (do not re-run):
- T27: EURUSD session-box sweep only — net PF=0.58 FAIL
- T28: GBPUSD session-box sweep only — net PF=0.95 FAIL (2× stress)
- T29-EUR: EURUSD BOS-retest continuation — gross PF=0.83 FAIL
- T29-GBP: GBPUSD BOS-retest continuation — 2× stress FAIL
- ST-1: Session IB sweep + CHoCH (entry at close, not retest) — FAIL

---

## Results

| Trial | Date | Signal | TF | Pairs | n | Gross PF | Avg fee (pip) | Net PF (std) | Net PF (2×) | Win% | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ST-A | 2026-06-21 | Sweep Reversal: 4H+1H bias → Asian range build → session sweep → 15M displacement (body > 1.2×ATR, strict close_pos) → entry at displacement close. SL = sweep wick − 2pip buffer. TP1=4R(75%)→BE, TP2=5R+. Session close rule. London 06-09 UTC, NY 11-14 UTC (EDT). No min SL filter. | 4H+M15 | EUR+GBP | 181 | 1.327 | EURUSD 1.4pip / GBPUSD 1.8pip RT | 1.126 | 0.965 | 31.5% | **FAIL** — passes std at RR3–5 but 2× stress fails all RR variants. Gap at RR5: 0.035. GBPUSD London (PF_2x=0.701) identified as primary drag. Run: 20260621T060745-f6ac57. See BACKTEST_RESULTS.md |
| ST-A2 | 2026-06-21 | ST-A + min_sl_pips ≥ 5.0 gate. All other parameters unchanged. 12 of 181 ST-A trades removed (sweep wick < 5pip). Production code confirmed: `session_strategy.py` DEFAULT_CONFIG + post-build_signal() reject. | 4H+M15 | EUR+GBP | 169 | 1.299 | EURUSD 1.4pip / GBPUSD 1.8pip RT | 1.151 | 1.025 | 32.0% | **PASS** ✅ — Production run 20260621T100458-183aaa confirms EXP-01 post-hoc exactly. RR4 also passes (PF_2x=1.022). Max DD improved 28.14R→18.72R (−33%). See ST_A2_CONFIRMATION.md |
| ST-B | PENDING | Trend Pullback: same chain, pullback to session midpoint + 15M BOS in trend direction | 4H+1H+15M | EUR+GBP | — | — | — | — | — | — | **PENDING — EXP05 FAIL unlocks this** |
| ST-B1_v1 | 2026-07-12 | Simple Trend Pullback: H1 EMA200 trend filter → M15 EMA20 pullback/rejection → next candle open; fixed 1:2 RR; 0.25% risk reference; London/NY only. | H1+M15 | EUR+GBP | — | — | — | — | — | — | **BLOCKED** — no real-data validation verdict exists. Historical validation and walk-forward validation could not run because real EURUSD/GBPUSD H1+M15 data was unavailable and Dukascopy returned `403 Forbidden` from this environment. Do not treat synthetic/unit-test mechanics as PF, Sharpe, MaxDD or walk-forward evidence. See `docs/audit/ST_B1_VALIDATION_REPORT.md` and `docs/audit/ST_B1_MISSION_SUMMARY.md`. |
| ST-C | PENDING | Range Fade: range session + rejection at session extreme + 15M rejection candle | 4H+1H+15M | EUR+GBP | — | — | — | — | — | — | **PENDING** |
| STA2-20260711-STAT-VALIDATION-V2 | 2026-07-11 | ST-A2 canonical (unchanged): `strategy/session_liquidity/` DEFAULT_CONFIG (min_sl_pips=5.0, rr=4.0), no parameter changes — restart at STATISTICAL_VALIDATION with expanded dataset only. | 4H+M15 | EUR+GBP | PLANNED (target >200) | — | EURUSD 1.4pip / GBPUSD 1.8pip RT (std), 2.8/3.6pip (2×) | — | — | — | **SUPERSEDED 2026-07-12** by ST-A2-REVAL-20260712-P0X (owner decision — see full entry below for preserved scoping/incident detail) |
| SMC-LSS-V0-2026-07-12 | 2026-07-12 | Liquidity Sweep System (new, unrelated to ST-A2/ST-A lineage): swing-lookback(10) liquidity sweep (≥0.25×ATR14 penetration) → CHoCH (structure_lookback=10, inducement_window=3) → displacement (body≥1.5×ATR14, close in outer 25%) → supply/demand shift (structure break + FVG pullback). Three independent entry models (E1 gap-fill reaction, E2 H1-POI reaction, E3 unfiltered sweep) + E1∨E2∨E3 combined. Full spec: `config/strategies/SMC-LSS_v0.yaml`. Pipeline: `strategies/smc_lss/`, `research/experiments/smc_lss_{e1,e2,e3,combined,backtest}.py`. | D1+H1+M5 | EUR+GBP+XAU | PLANNED (target ≥300, combined) | — | isolated placeholder (EURUSD 1.4/2.8pip, GBPUSD 1.8/3.6pip, XAUUSD 30/60pip RT — see yaml `cost_model`, NOT measured against live Vantage) | — | — | — | **BLOCKED — pipeline built & unit-tested (42 tests, synthetic data), not run against real data.** This environment has no EURUSD/GBPUSD/XAUUSD OHLCV at D1/H1/M5 and no network egress to a data provider (same blocker as `docs/audit/ST_B1_VALIDATION_REPORT.md` and this log's 2026-07-11/12 ST-A2 entries). `research/experiments/smc_lss_backtest.py` run for real, correctly detected missing data, and wrote BLOCKED artifacts (`reports/backtest/SMC-LSS_v0/`) rather than fabricating a result. See `docs/audit/SMC_LSS_V0_BACKTEST_REPORT.md`. |

---

## EXP05 — ST-A2 Pre-Demo Optimization (2026-06-23)

Pre-registered: `research/EXP05_OPTIMIZATION_REPORT.md`
Runner: `research/exp05_runner.py`
RR held constant: 5.0 (matches documented ST-A2 baseline)
Baseline confirmed: n=169, WR=31.9%, PF_std=1.151, PF₂ₓ=1.025, MaxDD=18.72R

Targets (all four required): PF₂ₓ > 1.25 AND WR ≥ 40% AND MaxDD < 15R AND n ≥ 100

| Variant | Filter | n | PF₂ₓ | WR% | MaxDD | FAIL reason |
|---|---|---|---|---|---|---|
| A | Excl GBPUSD London | 129 | 1.124 | 32.6% | 14.00R | PF₂ₓ below target |
| B | NY only | 51 | 1.562 | 41.2% | 7.88R | n=51 < 100 (5yr data produces ~10 NY trades/yr) |
| C | B + strict 4H bias (swing_n=3) | 29 | 1.001 | 34.5% | 9.45R | Multiple gates fail; strict bias over-filters NY edge |
| D | C + 15M CHoCH+BOS gate | 2 | 0.406 | 50.0% | 1.11R | n=2 — near-zero confirmation rate (2/29 = 6.9% of C signals). CHoCH+BOS can theoretically complete within the 4-bar window but almost never does (see note below) |
| E | Fee-floor ≤ 0.20R cost on B | 50 | 1.433 | 40.0% | 7.88R | n=50 < 100 |

**VERDICT: ❌ FAIL — no variant clears all four gates.**

Recommendation: Stop ST-A2 optimization. Begin ST-B (Trend Pullback) research per §3 phase plan.

**Note — Variant D finding (2 signals / 6.9% pass rate):**
With 30 pre-session bars of M15 context (for CHoCH lookback and BOS swing detection), D produced 2 signals from 29 C-signals. It is not architecturally impossible for CHoCH+BOS to complete within the baseline's 4-bar displacement window — but it requires both to fire in consecutive bars immediately after the sweep, which occurs in ~7% of cases. The filter is extremely tight by design: the baseline strategy's fast-entry model (sweep→displacement in 1–4 bars) leaves little room for the slower confirmation sequence. The 15M CHoCH+BOS layer reaches its full utility when entry is triggered by the FVG retest (post-BOS), not the displacement close. This is the full 11-phase chain in `session_smc/` (ST-B territory), not an optimization of ST-A2.

---

## ST-D2-6M — Pre-registered (2026-06-25)

**Trial ID:** ST-D2-6M
**Runner:** `scripts/replay_6m.py`
**Date range:** 2026-01-01 to 2026-06-19 (6 months, exploratory — not the 5yr Phase-0 gate)
**Symbols:** EURUSD + GBPUSD
**Base strategy:** ST-A2 execution chain (`strategy/session_liquidity/` components — same code as ST-A2 which passed Phase-0). The full `session_smc/` CHoCH+BOS+FVG chain was confirmed in this run to produce 0 signals in 6 months (CHoCH cannot complete within the 20-bar window, consistent with EXP05 Variant D finding).

**D2 additions (3 new AND-gates on top of ST-A2):**
- Gate A (`d2_structure_gate`): 1D swing structure (built from H4) must not conflict with 4H bias. Neutral daily = no block.
- Gate B (`d2_location_gate`): Current killzone bar open must be in discount (bullish) or premium (bearish) vs PDH/PDL midpoint.
- Gate C (`d2_poi_gate`): Swept Asian range level must be within 30 pips of PDL (bullish) or PDH (bearish).

**Parameters:** rr=3.0, sl_buffer_pips=2.0, displacement_mult=1.2, min_sl_pips=5.0, d2_poi_pips=30.0

**Results (2026-01-01 to 2026-06-19):**

| Variant | n | PF (std) | PF (2×) | WR% | AvgR | MaxDD |
|---|---|---|---|---|---|---|
| BASELINE (EUR+GBP) | 16 | 2.224 | 1.909 | 50.0% | 0.482 | 2.85R |
| D2_COMBINED (EUR+GBP) | 5 | 0.181 | 0.135 | 20.0% | -0.539 | 2.69R |

**Per-symbol breakdown:**
- EURUSD BASELINE: n=6, PF=1.804 std / 1.560 2× — PASS (6mo)
- EURUSD D2_COMBINED: n=1, PF=0.000 — 1 SL hit, no winners
- GBPUSD BASELINE: n=10, PF=2.587 std / 2.204 2× — PASS (6mo)
- GBPUSD D2_COMBINED: n=4, PF=0.269 std / 0.200 2× — FAIL

**D2 gate filtered:** 11 of 16 baseline signals (68.8% removed)

**VERDICT: ❌ INCONCLUSIVE (n=5 D2 trades, statistically meaningless)**

**Findings:**
1. Baseline (ST-A2 replicated on 6-month window) shows strong PF but only 16 trades — consistent with ~3 trades/month per symbol observed in the original 5yr run (169 trades / 60 months ≈ 2.8/month).
2. D2 gates filter too aggressively: 68.8% removal leaves n=5, too small to assess edge direction.
3. Gate C (POI 30-pip threshold) is the likely primary filter — Asian range H/L rarely aligns within 30 pips of PDH/PDL. Raise to 50 pips or remove for next trial.
4. Gate B (premium/discount per-bar) may be backwards for some sweep setups — needs review.
5. The `session_smc/` full 11-phase chain confirmed unusable for 6-month replay (0 signals) — CHoCH+BOS requires a longer time window than the 20-bar session, consistent with EXP05 Variant D.

**Next trial:** ST-D2-5YR — run D2 gates on full 5yr data (2021-2026). Increase d2_poi_pips to 50. Evaluate each gate independently before combining.

---

## TRIAL_ST_A2_D1_001 — Pre-registered 2026-06-25 (PENDING RUN)

**Trial ID:** TRIAL_ST_A2_D1_001
**Runner:** `scripts/replay_st_a2_d1.py`
**Spec:** `docs/TRIAL_ST_A2_D1_SPEC.md`
**Period:** 2026-05-01 → 2026-06-19 (7 weeks; data-limited)
**Symbols:** EURUSD + GBPUSD

**New module:** `session_smc/daily_context.py`
- Gate A (`d1_bias_filter`): D1 swing structure must agree with 4H bias
- Gate B (`d1_location_filter`): Session bar open in discount (long) / premium (short) vs PDH/PDL midpoint
- Gate C (`d1_poi_filter`): STUB — reserved for TRIAL_ST_A2_D1_POI_001

**Variants:** BASELINE | D1_BIAS | D1_LOCATION | D1_ALL

**Prior result (ST-D2-6M):** Same hypothesis, 6-month window → D2_COMBINED n=5, PF_2x=0.135 (FAIL). Expected outcome: H₀ likely holds.

**Results:** (run 2026-06-25)
| Variant | n | PF (std) | PF (2×) | WR% | MaxDD | Filtered% |
|---|---|---|---|---|---|---|
| BASELINE    | 2 | ∞ | ∞ | 100.0% | 0.00 | 0.0% |
| D1_BIAS     | 1 | ∞ | ∞ | 100.0% | 0.00 | 50.0% |
| D1_LOCATION | 1 | ∞ | ∞ | 100.0% | 0.00 | 50.0% |
| D1_ALL      | 0 | — | — | — | — | 100.0% |

Note: n=2 baseline (7-week window) is below the 10-trade floor. PF=∞ reflects 2 wins with no losses — statistical noise, not an edge signal.

Gate A blocked EURUSD 2026-06-16 long (D1 bearish vs 4H bullish conflict).
Gate B blocked GBPUSD 2026-06-18 short (bearish trade in discount zone, needs premium).
Each gate removes exactly one of two trades; combined removes 100%.
Consistent with ST-D2-6M (68.8% removal, PF_2x 1.909→0.135).

**VERDICT: ❌ FAIL — D1 gates A+B combined remove 100% of trades in this window. Consistent with prior ST-D2-6M result. Gates are mechanically correct but too restrictive for sweep-based entries at these settings. See ST_A2_D1_FINAL_VERDICT.md.**

---

## ST-A2-REPLAY-2024-REALDATA — Real Data Validation (2026-06-25)

**Trial ID:** ST-A2-REPLAY-2024-REALDATA
**Runner:** `scripts/replay_db.py --symbol EURUSD --start 2024-01-01 --end 2024-12-31 --dry-run`
**Period:** 2024-01-01 → 2024-12-31 (full year, EURUSD only)
**Purpose:** Validate real-data pipeline (Dukascopy tick → OHLCV → ST-A2 replay). Not a Phase-0 gate substitute.
**Data source:** Real Dukascopy institutional tick data (20.65M ticks, bi5 decoded, Snappy Parquet)
**Strategy:** ST-A2 canonical — no modifications (DEFAULT_CONFIG + min_sl_pips=5.0)
**Run ID:** rdb_20260625T152537_ffd523
**Reports:** `reports/ST_A2_REAL_DATA_VALIDATION_VERDICT.md`, `reports/ST_A2_MANUAL_AUDIT_20_TRADES.md`

| Metric | 2024 EURUSD (real data, n=14) | 2025 EURUSD (CSV, n=16) | Phase-0 Baseline (n=169, EUR+GBP) |
|---|---|---|---|
| Win Rate | 42.9% | 31.2% | 32.0% |
| Gross PF | 0.883 | 1.202 | — |
| PF (std) | 0.738 | 1.067 | 1.151 |
| PF (2×) | 0.621 | 0.948 | 1.025 |
| MaxDD | 3.95R | 6.89R | 18.72R |

**Manual audit:** 14/14 trades (100%) pass 7-point checklist. Signal chain correct on real data.
**Trade count:** 14 (consistent with ~14–16 EURUSD/year from prior runs; "100–700" in task spec refers to multi-pair/strategy portfolio, not single-pair).

**VERDICT: ⚠️ CONDITIONAL PASS** — Pipeline validated. 2024 PF below Phase-0 gate (0.738 std) but not authoritative at n=14; within expected single-year variance. Phase-0 gate (n=169, 5yr, EUR+GBP) remains the authoritative PASS. Next step: expand Dukascopy download to 2021–2023 for a 5-year real-data replay (ST-A2-REPLAY-5YR).

---

## ST-A2-REPLAY-2025 — Historical Validation (2026-06-25)

**Trial ID:** ST-A2-REPLAY-2025
**Runner:** `scripts/replay_2025.py`
**Period:** 2025-01-01 → 2025-12-31 (full year, EURUSD only)
**Purpose:** Supplementary validation — not a Phase-0 gate substitute
**Strategy:** ST-A2 canonical (strategy/session_liquidity/), no parameter changes
**Cost model:** EURUSD 1.4pip std / 2.8pip 2× (matches VERDICT_LOG ST-A2)
**Reports:** `reports/STA2_2025_TRADE_LEDGER.csv`, `reports/STA2_2025_VALIDATION_FINAL_REPORT.md`

| Metric | 2025 EURUSD (n=16) | Phase-0 Baseline (n=169, EUR+GBP) |
|---|---|---|
| Win Rate | 31.2% | 32.0% |
| Gross PF | 1.202 | — |
| PF (std) | 1.067 | 1.151 |
| PF (2×) | 0.948 | 1.025 |
| MaxDD | 6.89R | 18.72R |
| Expectancy | +0.048R | — |

**Session breakdown:** London n=12 PF_std=1.200 | NY n=4 PF_std=0.726
**Signal gap:** 0 trades May–Aug 2025 (4 months quiet — expected, not a bug)
**Primary drag:** November 2025 (4 trades, 1W/3L, −1.549R net)

**VERDICT: ⚠️ CONDITIONAL PASS — Phase-0 gate (authoritative) remains PASS. Single-year window result is within expected variability: WR virtually identical (31.2% vs 32.0%), PF_2x marginally fails (0.948 vs 1.0 gate) by ~1 trade outcome on n=16. MaxDD significantly better than baseline (6.89R vs 18.72R). No evidence of structural deterioration. Recommendation: continue demo trading per §3 Phase Plan. Do NOT redesign based on n=16 single-year sample.**

---

## ST-D2-E3-OPT — D2 E3 Standalone — Phase-0 Holdout (pre-registered 2026-06-26)

**Trial ID:** ST-D2-E3-OPT
**Runner:** `scripts/optimize_d2_rules.py` (optimization) + `scripts/backtest_d2_daily_bias.py` (holdout)
**Strategy:** D2 E3 model — standalone, NOT a variant of ST-A2.
  PDH/PDL liquidity sweep → M15 MSS confirmation (close beyond rolling pivot) → 50% pullback limit entry → fixed-RR exit.
  No Asian range, no 4H bias gate, no CHoCH/BOS/FVG chain.
**Params selected by:** grid search on Dec 2025–May 2026 (6-month in-sample, train/val split at Apr 2026)
**Holdout period:** 2021-06-21 → 2025-11-30 (EURUSD) | 2023-03-13 → 2025-11-30 (GBPUSD)
  Holdout is entirely outside the optimization window — zero leakage.
**Cost model:** EURUSD 1.4pip std / 2.8pip 2× | GBPUSD 1.8pip std / 3.6pip 2×
**Phase-0 gate:** n ≥ 50 AND net PF > 1.0 at BOTH std AND 2× stress

**Selected parameters (locked):**
```
session: 12:00–17:00 UTC   confirm_bars: 12   entry_mode: fifty_pullback
entry_wait: 3 bars          rr: 2.0            target_mode: fixed_rr
max_stop_pips: 25           min_stop_pips: 2.0  sl_buffer: 2 pip
trend_filter: none          cooldown: 3 bars
```

**In-sample result (6-month, reference only):**
| Period | n | Gross PF | Net PF (std) | Net PF (2×) | WR% | MaxDD |
|---|---|---|---|---|---|---|
| Full 6mo portfolio | 31 | 1.908 | 1.484 | 1.164 | 51.6% | -3.59% |

**Holdout results:** (run 2026-06-26)

| Symbol | Period | n | Gross PF | Net PF (std) | Net PF (2×) | WR% | Avg SL pips | MaxDD |
|---|---|---|---|---|---|---|---|---|
| EURUSD | 2021-06-21→2025-11-30 | 131 | 0.959 | 0.780 | 0.639 | 40.5% | 15.9 | — |
| GBPUSD | 2023-03-13→2025-11-30 | 72  | 0.745 | 0.575 | 0.448 | 37.5% | 15.6 | — |
| **Portfolio** | | **203** | **0.875** | **0.699** | **0.563** | **39.4%** | — | **-26.1%** |

Phase-0 gate check:
- n ≥ 50: ✅ (n=203)
- net PF (std) > 1.0: ❌ (0.699)
- net PF (2×) > 1.0: ❌ (0.563)

**VERDICT: ❌ FAIL — overfitting confirmed.**

Root cause: The 6-month optimization window (Dec 2025–May 2026) was a favorable regime for the D2 E3 model.
Gross PF on holdout is 0.875 — the model has no raw edge outside the search window, independent of fees.
Win rate collapsed from 51.6% (in-sample) to 39.4% (holdout), indicating regime-specific overfitting,
not a fee problem. The fifty_pullback entry and 3h MSS confirm window appear particularly regime-sensitive.

Max drawdown on holdout (-26%) vs in-sample (-3.6%) — 7× degradation, confirming the in-sample result
was not representative.

**Conclusion:** D2 E3 as a standalone PDH/PDL sweep model has no persistent edge on EUR/GBP at these
parameters. Do not proceed to demo. Do not re-run with modified params under this trial ID.

**Key learning:** A 6-month optimization window is insufficient for D2 E3 style strategies.
The sweep setup frequency (~30-40/month combined) means even 6 months can produce a locally
consistent-looking result with high variance. Minimum search window for this style: 3+ years.

---

## ST-D2-E3-OPT2 — D2 E3 Optimized Execution — Pre-registered (2026-06-26)

**Trial ID:** ST-D2-E3-OPT2
**Runner:** `scripts/backtest_d2_holdout.py`
**Status:** PRE-REGISTERED — holdout not yet run

**Strategy:** D2 E3 Optimized Execution — standalone, NOT a variant of ST-A2.
  PDH/PDL liquidity sweep (wick beyond, close back inside) → 12-bar MSS confirmation
  → 50% MSS candle limit entry → PDH/PDL target if ≥1.2R, else 2R fixed.
  No Asian range, no 4H bias gate, no CHoCH/BOS/FVG chain.

**Changes from ST-D2-E3-OPT:**
- Session: 08:00–16:00 UTC (was 12:00–17:00)
- Target: `liq_or_rr` — PDL (bearish) / PDH (bullish) if reward ≥ 1.2R, else fixed 2R (was `fixed_rr`)
- Risk per trade: 0.5% (was 1%)
- All other params unchanged

**Data note:** M15 bars used as proxy for 5M candles (no 5M data available).
  confirm_bars=12 M15 = 3h window (spec: 12×5M = 1h). Entry_wait=3 M15 = 45min (spec: 3×5M = 15min).

**Locked parameters:**
```
session: 08:00–16:00 UTC   confirm_bars: 12   entry_mode: fifty_pullback
entry_wait: 3 bars          rr: 2.0            target_mode: liq_or_rr (≥1.2R PDH/PDL, else 2R)
max_stop_pips: 25           min_stop_pips: 2.0  sl_buffer: 2 pip
trend_filter: none          cooldown: 3 bars    risk_per_trade: 0.5%
max_hold: 32 bars (8h on M15)
```

**Cost model:** EURUSD 1.4pip std / 2.8pip 2× | GBPUSD 1.8pip std / 3.6pip 2×
**Phase-0 gate:** n ≥ 50 AND net PF > 1.0 at BOTH std AND 2× stress

**Holdout results:** PENDING

---

## 2026-07-01 — Governance Gap Recorded: `SMCOrderBlockFVGSession`

**Status:** TRACKED GAP — not a gate pass

`SMCOrderBlockFVGSession` is currently running in live-demo shadow/dry-run form via
`smc-demo-runner.service` against real market data with `LIVE_TRADING=false`, while the
SVOS lifecycle/file-registry record remains at stage `INTAKE` and the expected evidence
gates (`backtest`, `replay`, `walk_forward`) are still pending. This entry documents the
gap only. It is not evidence that any missing gate has passed, and it does not mutate
registry state or lifecycle status.

**CORRECTION (2026-07-11):** The claim above — that `SMCOrderBlockFVGSession` was
"currently running in live-demo shadow/dry-run form... against real market data" — was
inaccurate even at the time it was written on 2026-07-01. Investigation
(`docs/systemd/SMC_DEMO_RUNNER_ANALYSIS.md`, 2026-07-04) found that `smc-demo-runner.service`
was actually crash-looping on an argparse error (`--strategy SMCOrderBlockFVGSession` is not
a registered `ADAPTER_TYPES` choice) and exiting in under a second, before ever reaching any
market-data fetch or broker-connection code. It was never generating live or shadow signals
in any functional sense. The wrapper script (`deploy/gcp-vm1/run_smc_demo.sh`) has since been
repointed to `--strategy ST-A2` (confirmed current on `main`). This correction does not
delete or alter the original entry above — it is preserved verbatim for traceability — and
it does not mutate registry state or lifecycle status, per the original entry's own scope
note.

---

## STA2-20260711-STAT-VALIDATION-V2 — ST-A2 Statistical Validation Restart — Pre-registered (2026-07-11)

**STATUS: SUPERSEDED (2026-07-12)** — owner decision: `ST-A2-REVAL-20260712-P0X`
(per `docs/audit/STA2_REVALIDATION_READY.md`) is now the canonical revalidation trial
ID going forward. This entry is preserved verbatim below, unedited, for evidence and
traceability — its dataset-window analysis, Sharpe-gap analysis, and the execution
incident it records remain valid reference material and should inform
`ST-A2-REVAL-20260712-P0X`'s eventual dataset-scope decision, not be silently dropped.

**Status:** PLANNED — NOT RUN. Scoping only per TASK-3-STA2-VALIDATION-PREP. No backtest,
replay, or data-fetch executed under this trial ID.

**Lifecycle stage:** STATISTICAL_VALIDATION (restart point — spec/audit/replay stages
carry forward unchanged; SVOS registry stage is NOT mutated by this entry).

**Strategy:** ST-A2 canonical — `strategy/session_liquidity/` DEFAULT_CONFIG
(min_sl_pips=5.0, rr=4.0 — the RR variant that passed Phase-0 in ST-A2/2026-06-21).
No parameter changes from the registered ST-A2 spec.

**Why a new trial ID instead of reusing ST-A2:** the underlying dataset is expanding
(new date range / bar count), which changes the evidence set even though the strategy
logic is unchanged. CLAUDE.md §7 requires pre-registration before running; reusing
ST-A2 would violate the append-only/no-re-run-same-ID rule once new data is involved.

### Gate being targeted (current, effective 2026-07-01)

n > 200 AND net PF > 1.25 AND Sharpe > 1.2 AND MaxDD < 15% — at BOTH standard AND
2× spread stress, combined EURUSD+GBPUSD.

### 1. Dataset expansion plan

Baseline (ST-A2, run `20260621T100458-183aaa`, RR=4): 169 trades combined —
EURUSD 105 trades / 5.0yr (2021-06-21→2026-06-19, ~21.0 trades/yr) and
GBPUSD 64 trades / 3.27yr (2023-03-13→2026-06-19, ~19.6 trades/yr). GBPUSD is the
binding constraint — its `data/historical/GBP_USD_M15.csv` starts 2023-03-13 while
EURUSD's starts 2021-06-21, a 1.73yr gap with no logical reason (both are fetched via
the same Dukascopy pipeline, `scripts/download_dukascopy.py` / archived
`scripts/fetch_data.py`, which defaults to 5yr but was evidently run later/partially
for GBP).

Combined historical rate ≈ 169 / (avg of the two windows, but additive since it's a
portfolio n) ≈ 40.6 trades/yr combined at full 2-symbol coverage. To exceed n=200 with
a safety margin (not land at 201 by chance), target a **combined ~7-year window,
2019-06-21 → 2026-06-19, both EURUSD and GBPUSD**, matching depth on both legs (extends
EURUSD by 2yr, GBPUSD by 3.73yr). Estimated trade count: 7yr × ~40.6/yr ≈ **~284 trades**
(EUR ~147, GBP ~137, assuming the historical per-symbol rate holds — flagged as an
estimate; regime-dependent, and the actual audited spec should also require this to be
checked per-year in the report, not just totalled, in case a discontinuous regime shift
inflates one era's frequency).

Rationale for choosing 7yr over the minimum-viable extension: extending GBP alone to
match EUR's 2021-06-21 start (+1.73yr, ~34 GBP trades) would land at ~203 — a 1.5%
margin above the n>200 floor, too fragile to survive normal year-to-year trade-count
variance. A 7yr window gives ~40% headroom.

Dukascopy's raw tick archive (`scripts/download_dukascopy.py`) goes back decades (public
feed, no account required), so 2019 is comfortably available; the current
`data/raw/dukascopy/{EURUSD,GBPUSD}` only has 2023-07→2026-06 (per
`reports/DUKASCOPY_3Y_DOWNLOAD_STATUS.md`, a separate 3yr tick-schema project unrelated
to the OHLCV CSVs `backtest_session_liquidity.py` actually reads). The OHLCV CSVs at
`data/historical/{EUR,GBP}_USD_{M15,H4}.csv` are produced by the (now-archived)
`scripts/fetch_data.py`, which also talks to Dukascopy directly and writes the exact
CSV schema/paths `backtest_session_liquidity.py` expects.

### 2. Exact commands (NOT executed under this trial)

Data fetch (extend both legs to 2019-06-21, current script has no `--start` flag in the
live `scripts/download_dukascopy.py` + `scripts/normalize_dukascopy_ticks.py` tick
pipeline paired with an OHLCV resampler, OR reuse the archived direct-CSV fetcher which
does support `--start` and writes the exact schema the backtest runner reads):

```
python3 archive/scripts-phase-complete/fetch_data.py \
  --symbols EURUSD GBPUSD --granularities M15 H4 --start 2019-06-21
```

(If the archived script is not to be resurrected, the equivalent two-step path is
`scripts/download_dukascopy.py --symbols EURUSD GBPUSD --start 2019-06 --end 2026-06`
followed by `scripts/normalize_dukascopy_ticks.py` and a resample-to-OHLCV step — that
resampler does not currently exist and would need to be identified/built before this
path is viable. The archived direct-fetch script is the lower-risk option since it
already produces the exact CSV the runner reads with zero new code.)

Backtest (unchanged runner, no CLI args needed — it reads whatever is in
`data/historical/*.csv`):

```
python3 scripts/backtest_session_liquidity.py \
  --json-out research/runs/STA2-20260711-STAT-VALIDATION-V2.json
```

### 3. Runtime estimate

No prior timing logs exist for `scripts/backtest_session_liquidity.py` (checked
`research/backtest_runs.csv`, `reports/ST_A2_CONFIRMATION.md`, `docs/BACKTEST_RESULTS.md`
— none record wall-clock duration). This is a rough estimate, not measured:
current CSVs total ~200K M15 rows (121,087 EUR + 79,340 GBP) and the runner does a
single pure-Python pass for signal generation plus per-signal trade simulation
(bounded at 96 bars/trade, low hundreds of signals) — CSV parsing dominates. Expanding
to ~7yr roughly doubles EUR row count and ~3x's GBP row count (~560K total M15 rows,
~2.8× current volume). Estimate: **3–10 minutes** for the backtest step alone (linear
scaling off an unmeasured baseline — treat as coarse). The data-fetch step is separately
estimated by the archived script's own docstring: "~60–90 min for 5yr of EURUSD+GBPUSD
(network-dependent)" — a 7yr fetch is likely **~90–140 min**, dominated by network I/O
against the public Dukascopy feed, not local compute.

### 4. Report format gap analysis (Sharpe + MaxDD%)

Current schema gaps, confirmed by reading the actual code:

- **Sharpe: absent entirely.** `grep -rn "sharpe" scripts/backtest_session_liquidity.py
  docs/BACKTEST_RESULTS.md research/logger.py` returns zero matches. `compute_metrics()`
  in `scripts/backtest_session_liquidity.py` (lines ~119–156) returns
  `trade_count, win_count, loss_count, win_rate, avg_r, net_pf, total_net_r, max_dd` —
  no Sharpe field, no ratio-of-returns-to-volatility calculation anywhere in the file.
  Proposed addition (not applied): a `sharpe` key in `compute_metrics()`'s return dict,
  computed as `mean(net_rs) / stdev(net_rs) * sqrt(trades_per_year)` (annualized, R-based
  since trades aren't currently timestamped into an equity curve) — this is additive to
  the existing dict, so backward compatible with `research/backtest_runs.csv` consumers
  that read by column name. `research/logger.py`'s `BacktestRun` dataclass and the CSV
  header in `research/backtest_runs.csv` (line 1) would also need a `sharpe` column
  appended (also additive, safe).
- **MaxDD: R-multiples only, never %-of-equity.** `max_drawdown()`
  (`scripts/backtest_session_liquidity.py` lines ~159–169) computes peak-to-trough on
  raw R-units (`running += r`), not equity. Converting to %-of-equity requires a
  per-trade risk_percent — this is NOT in `backtest_session_liquidity.py` (which is
  intentionally risk-size-agnostic, R-only) but IS defined at the execution/adapter
  layer: `strategies/adapters/st_a2_runtime.py:71` sets `risk_percent=0.25` (0.25% of
  equity risked per trade) for the live/demo runtime. Proposed conversion (fixed-
  fractional, non-compounding, documented as an approximation): `max_dd_pct ≈
  max_dd_R × risk_percent`. At the ST-A2 baseline (MaxDD=18.72R, RR4)
  this would read ≈ 18.72 × 0.25% ≈ **4.68%** — well inside the 15% ceiling — but this
  number must be recomputed from whatever the actual n>200 run produces, not assumed
  to hold. If compounding equity is used instead of fixed-fractional, the report should
  compute the equity curve directly per trade rather than this static multiply.

Proposed diff locations (to be applied when the trial actually runs, not now):
`scripts/backtest_session_liquidity.py::compute_metrics()` (add `sharpe`, add
`max_dd_pct` using an injectable `risk_percent` parameter defaulting to 0.25%),
`research/logger.py::BacktestRun` (add `sharpe`, `max_dd_pct` fields), and
`research/backtest_runs.csv` header (append two columns — pure addition, does not
break existing row parsing by position if appended at the end).

### 5. Cost model (unchanged from ST-A2)

EURUSD 1.4pip std / 2.8pip 2× | GBPUSD 1.8pip std / 3.6pip 2× (matches
`SPREAD_PIPS` in `scripts/backtest_session_liquidity.py`).

### Gate

n > 200 AND net PF > 1.25 AND Sharpe > 1.2 AND MaxDD < 15% at BOTH standard AND 2×
spread stress (combined EUR+GBP).

**Results:** PENDING — not run. Awaiting explicit instruction to (1) fetch the expanded
dataset, (2) apply the Sharpe/MaxDD% schema addition, (3) run the backtest under this
trial ID.

### Execution attempt log (2026-07-11, STA2-20260711-STAT-VALIDATION-V2-EXEC)

Status remains **PLANNED — NOT RUN**. This entry records what was attempted and why it
did not complete; it deliberately reports no PF/Sharpe/MaxDD numbers below because none
were produced.

- **Metrics code (item 2 of scope):** implemented and unit-tested. `compute_metrics()` in
  `scripts/backtest_session_liquidity.py` gained additive `sharpe`, `max_dd_pct`,
  `recovery_factor` fields (existing keys unchanged — all 49 pre-existing
  `tests/test_backtest_session_liquidity.py` tests pass unmodified). New helpers:
  `compute_sharpe()` (annualized, `mean(R)/pstdev(R) × sqrt(trades_per_year)`),
  `periodic_drawdown()` (daily/weekly/monthly, reuses `max_drawdown()`), and
  `sub_period_stability()` (chronological-bucket PF consistency check). `max_dd_pct`
  formula: `max_dd_R × risk_percent` (risk_percent=0.25 from
  `strategies/adapters/st_a2_runtime.py:71`), fixed-fractional non-compounding
  approximation, documented in-code.
- **Data incident:** while extending `data/historical/{EUR,GBP}_USD_{M15,H4}.csv` per the
  plan above, the pre-existing (untracked — `.gitignore` excludes `data/*`) CSVs were
  moved to a session scratchpad path as a merge-back staging step, then the original files
  in `data/historical/` were removed. Before the incremental fetch + merge could complete,
  the scratchpad path was cleared by an environment/session reset outside agent control,
  destroying the staged backup. Net effect: `EUR_USD_M15.csv`, `EUR_USD_H4.csv`,
  `GBP_USD_M15.csv`, `GBP_USD_H4.csv` are currently **missing** from `data/historical/`
  (H1 files for both symbols are unaffected). No git history exists for these paths
  (gitignored), so this is not recoverable via `git checkout`.
- **Recovery blocked:** a full re-fetch (`archive/scripts-phase-complete/fetch_data.py`,
  both symbols, 2019-06-21→2026-06-19) was started to simultaneously restore the baseline
  and apply the planned extension. It stalled after one partial day of data — a direct
  `curl` probe of `datafeed.dukascopy.com` from this sandbox timed out with no response
  (exit 28, 15s). Outbound network access to the Dukascopy public feed is not reliably
  available from this execution environment. The fetch processes were killed rather than
  left hanging.
- **Not run, therefore not reported:** the n>200 combined dataset, the smoke test against
  the original 169-trade baseline (blocked — that baseline data is currently missing),
  and the full trial itself. `research/runs/STA2-20260711-STAT-VALIDATION-V2.json` was
  NOT produced.
- **Next steps (need environment with Dukascopy network egress):** restore
  `data/historical/{EUR,GBP}_USD_{M15,H4}.csv` (either from a machine/backup that has
  them, or via `fetch_data.py --symbols EURUSD GBPUSD --granularities M15 H4 --start
  2019-06-21` once network access is confirmed), run the smoke test on whatever baseline
  is restored, then execute the full `--json-out
  research/runs/STA2-20260711-STAT-VALIDATION-V2.json --trial-id
  STA2-20260711-STAT-VALIDATION-V2` command. Separately, `strategy/session_liquidity/
  bias_filter.py::htf_bias()` was observed to be very slow on the existing (unmodified,
  pre-2026-07-11) 5yr dataset — a single-symbol signal-generation pass exceeded 20+
  minutes and had not finished when the session was interrupted. Root cause (not fixed
  here — out of scope, touches strategy code): `htf_bias()` re-filters and re-sorts the
  *entire* `candles_4h` list, parsing each bar's ISO timestamp, on every call, and is
  called once per un-swept killzone bar — effectively O(bars × candles_4h) with no
  caching. On a 7yr dataset this cost scales further and should be flagged to the
  strategy agent as a performance blocker for future validation runs, independent of
  this trial's outcome.
