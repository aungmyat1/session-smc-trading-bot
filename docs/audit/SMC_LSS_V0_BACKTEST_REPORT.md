---
Date: 2026-07-12
Author: Quant Research (Claude)
Authority: Level 8 — informational evidence. Does not supersede `docs/00_Project/DOC_AUTHORITY.md`.
Scope: SMC-LSS_v0 (Liquidity Sweep System) — Phase 0/2 pipeline build and
validation-gate attempt. Trial pre-registered: `docs/VERDICT_LOG.md`
(SMC-LSS-V0-2026-07-12).
---

# SMC-LSS_v0 — Backtest & Validation Report

## Implementation Status: BUILT, UNIT-TESTED, NOT VALIDATED ON REAL DATA

The full deterministic SMC-LSS_v0 pipeline is implemented and passes 42
synthetic-data unit tests. It was NOT run against real EURUSD/GBPUSD/XAUUSD
market data because none is available in this environment (see "Dataset
Used" below). `research/experiments/smc_lss_backtest.py` was run for real
against this environment and correctly detected the missing data, writing
documented `BLOCKED` artifacts to `reports/backtest/SMC-LSS_v0/` instead
of fabricating trades or metrics — the same discipline already established
in `docs/audit/ST_B1_VALIDATION_REPORT.md` for an unrelated strategy hitting
the identical environment limitation.

**No trades, no metrics, no PASS/FAIL verdict were fabricated for this
trial.** Status remains `experimental` / stage `historical_replay` per
`config/strategies/SMC-LSS_v0.yaml` — unchanged from registration, because
no evidence exists yet to justify advancing it.

### What was built

| Component | Path | Status |
|---|---|---|
| Registration | `config/strategies/SMC-LSS_v0.yaml` | Done — isolated, not in `strategy_portfolio.yaml` or `strategy_catalog.yaml` |
| Liquidity sweep engine | `strategies/smc_lss/liquidity.py` | Done — 8 unit tests |
| CHoCH + inducement | `strategies/smc_lss/structure.py` | Done — 9 unit tests |
| Displacement engine | `strategies/smc_lss/displacement.py` | Done — 12 unit tests |
| Supply/demand shift (FVG) | `strategies/smc_lss/entries.py` | Done — exercised via the pipeline tests below |
| HTF context builder | `strategies/smc_lss/context.py` | Done — exercised via the pipeline tests below |
| Exit / trade simulation | `strategies/smc_lss/exits.py` | Done — exercised via the pipeline tests below |
| Shared setup pipeline | `research/experiments/smc_lss_common.py` | Done — 3 no-lookahead integration tests |
| E1 Gap Fill Reaction | `research/experiments/smc_lss_e1.py` | Done — wired, not run on real data |
| E2 POI Reaction | `research/experiments/smc_lss_e2.py` | Done — wired, not run on real data |
| E3 Liquidity Sweep | `research/experiments/smc_lss_e3.py` | Done — wired, not run on real data |
| Combined (E1∨E2∨E3) | `research/experiments/smc_lss_combined.py` | Done — wired, not run on real data |
| Backtest integration + walk-forward | `research/experiments/smc_lss_backtest.py` | Done — ran for real, produced BLOCKED artifacts |
| Unit tests | `tests/strategies/test_smc_lss_{liquidity,structure,displacement}.py`, `tests/research/test_smc_lss_backtest.py` | Done — 42/42 passing |

Reused, not duplicated: `src/data/loader.py` (data access), pandas/pyarrow
for parquet I/O, and the metrics-inline-per-script convention already
established by `scripts/backtest_session_liquidity.py` and
`strategies/st_b1_backtest.py` (no shared metrics module exists in this
repo yet for any strategy — this trial follows the existing pattern rather
than introducing an unrequested one).

---

## Assumptions

Documented here per task instruction — none of these were silently
resolved; all are visible in code comments at the cited location.

1. **Bearish CHoCH clause corrected for symmetry**
   (`strategies/smc_lss/structure.py` module docstring). The literal spec
   text — "Bearish CHoCH: higher high forms / previous higher low breaks /
   close below previous **lower low**" — does not mirror the bullish
   clause and does not match any standard CHoCH definition (a genuine
   bearish CHoCH breaks the most recent **higher low** in an uptrend, not
   an unrelated lower low). Implemented symmetrically: bearish CHoCH
   requires closing below the previous **higher low**. Treated as a
   spec typo, not silently "fixed" — called out here and in-code.

2. **Displacement quartile/body gates use non-strict inequality** (`>=`,
   `<=`), matching the spec's literal "`>=`" wording. This differs from
   the pre-existing `strategy/session_liquidity/displacement_detector.py`
   (strict `>`, different strategy, different spec) — intentional, not a
   copy-paste inconsistency.

3. **FVG / pullback window has no explicit max-bars bound.**
   `detect_supply_demand_shift()` scans forward from the displacement
   candle until the first FVG-overlapping candle, with no configured
   timeout. A production revision should add one (mirrors the
   `sweep_timeout_bars` pattern already used in
   `strategy/session_liquidity/config.yaml`) — deferred here since no
   real dataset exists yet to tune it against.

4. **SL/TP construction is a fixed, undocumented-by-spec convention**
   (`research/experiments/smc_lss_common.py::build_setup_trade`): entry at
   the FVG-pullback bar's close; SL beyond the actual sweep wick extreme
   plus a fixed `0.1×ATR` buffer; TP at a fixed `2.0R`. The task spec does
   not define SL/TP mechanics, so a single frozen convention was chosen
   and applied identically across E1/E2/E3/combined — **not** swept or
   optimized, per CLAUDE.md §0.2 / task instruction 9 ("do not optimize
   parameters").

5. **Cost model is an isolated placeholder**
   (`config/strategies/SMC-LSS_v0.yaml` `cost_model`), not measured
   against a live Vantage account and not read from `config/costs.json`
   (that file's `active_profile` is itself a placeholder per its own
   `_comment`, and has no XAUUSD entry). Net-of-fees is still applied
   (CLAUDE.md §0.3) — the fee inputs are simply unvalidated.

6. **Max-drawdown-as-percentage uses a fixed-fractional approximation**
   (`ASSUMED_RISK_PCT_PER_TRADE = 1.0` in
   `research/experiments/smc_lss_backtest.py`): `max_dd_pct = max_dd_R ×
   1.0`. Same convention already used for ST-A2
   (`max_dd_pct = max_dd_R × risk_percent`), with a placeholder 1.0%
   risk-per-trade since SMC-LSS_v0 has no live risk-sizing model yet.

7. **`E1 OR E2 OR E3` is mathematically E3 alone for this trial.** E3 has
   no confluence filter beyond the base sweep→CHoCH→inducement→
   displacement→shift chain; E1 (gap-zone) and E2 (POI-zone) only ever
   narrow that same setup universe. The combined script still evaluates
   the OR explicitly (not short-circuited) so this is a falsifiable
   observation, not a hard-coded equivalence — a future revision with
   different confluence parameters could break it.

---

## Rule Definitions (as implemented)

All thresholds below are `config/strategies/SMC-LSS_v0.yaml`
`components.*` defaults; a parameter change requires a new trial ID per
CLAUDE.md §7.

- **Liquidity sweep** (`swing_lookback=10`, `sweep_atr_threshold=0.25`):
  bullish — `low < swing_low(10) AND close > swing_low AND (swing_low −
  low) ≥ 0.25×ATR(14)`; bearish — mirror on highs.
- **CHoCH** (`structure_lookback=10`): two non-overlapping 10-bar windows
  compared; see Assumption 1 for the bearish-clause correction.
- **Inducement** (`inducement_window=3`): a liquidity sweep must exist in
  the 3 candles strictly before CHoCH confirmation.
- **Displacement** (`displacement_body_atr=1.5`): `body ≥ 1.5×ATR(14) AND`
  close in outer 25% of the candle's range, direction-matched.
- **Supply/demand shift**: sweep + displacement + structure break (the
  CHoCH's `broken_level`) + a later candle's range overlapping the
  3-candle FVG centered on the displacement candle.
- **E1 Gap Fill Reaction**: shift qualifies only if its pullback price
  falls inside the daily opening-gap zone, direction-consistent with a
  genuine gap-fill move.
- **E2 POI Reaction**: shift qualifies only if `SessionContext.H1_POI` is
  set, within `1.0×ATR` of the pullback price, and direction-consistent
  with the daily HTF bias.
- **E3 Liquidity Sweep**: every confirmed shift, unfiltered.
- **Combined**: `E1 ∨ E2 ∨ E3` per setup (see Assumption 7).

---

## Dataset Used

**None.** Required: `config/strategies/SMC-LSS_v0.yaml` `symbols` ×
`timeframes` = EURUSD/GBPUSD/XAUUSD × D1/H1/M5, real market history.

Evidence this is genuinely blocked, not merely unattempted:

1. `data/historical/` is empty of any EURUSD/GBPUSD/XAUUSD files —
   confirmed by `research/experiments/smc_lss_backtest.py`'s real
   execution reporting all three symbols `MISSING` for all three
   timeframes.
2. `docs/VERDICT_LOG.md`'s own 2026-07-11/12 ST-A2 entry documents this
   environment's Dukascopy fetch stalling (curl timeout, exit 28) — the
   same network-egress limitation, not re-attempted independently here
   since it would inherit the identical failure.
3. `docs/audit/ST_B1_VALIDATION_REPORT.md` documents the same blocker
   from a `403 Forbidden` angle for an unrelated strategy — this is a
   standing environment limitation, not something specific to this trial.

`research/experiments/smc_lss_backtest.py` writes the four required
artifact files (`trade_ledger.parquet`, `performance_report.json`,
`equity_curve.csv`, `drawdown_report.json`) even in the blocked case —
empty/blocked-flagged, never fabricated — so downstream tooling has a
stable contract to depend on once real data is supplied.

---

## E1 / E2 / E3 / Combined Results

**Not available.** `reports/backtest/SMC-LSS_v0/performance_report.json`
contains `"blocked": true` and no branch metrics. The pipeline that would
populate `branch_metrics.{E1,E2,E3,combined}.{standard,stress2x}` is built
and unit-tested (see `TestFindSetupsNoLookahead` in
`tests/research/test_smc_lss_backtest.py`, which proves the full
sweep→CHoCH→inducement→displacement→shift→entry chain fires correctly and
without lookahead on a hand-constructed synthetic scenario) but has never
been exercised against real price history.

## Walk-Forward Results

**Not available**, same root cause. `is_report.json`, `oos_report.json`,
`forward_report.json` are not written by a blocked run (only the four
always-written artifacts above are). The walk-forward split logic itself
(`split_by_period`, frozen IS 2021-01-01..2023-12-31 / OOS
2024-01-01..2024-12-31 / Forward 2025-01-01..2025-12-31 per the YAML spec)
is unit-tested in isolation (`TestSplitByPeriod`) and does not require
real data to verify correctness of the splitting mechanics.

---

## PASS/FAIL Decision

**FAIL / remains `experimental`.**

Per task instruction 13: "PASS only if Trades ≥300, PF>1.25, Sharpe>1.2,
Max DD<15%, OOS PF>1.15. Otherwise keep experimental." With zero trades
generated (blocked on data), every gate condition is unmet by definition.
`config/strategies/SMC-LSS_v0.yaml` is unchanged (`status: experimental`,
`stage: historical_replay`) and no lifecycle registry entry was created —
none of `svos/lifecycle/manager.py`'s mutation APIs were called, consistent
with this strategy having no registry entry at all yet (CLAUDE.md §9,
§3: no script may advance stage without going through the lifecycle
manager, and no evidence exists here to justify a call to it).

---

## Recommendation — what the owner must do next

1. Resolve OHLCV data access for EURUSD/GBPUSD/XAUUSD at D1/H1/M5 from an
   environment with real Dukascopy (or equivalent) egress — same
   prerequisite already blocking ST-B1 and the ST-A2 revalidation.
2. Place data under `data/historical/` in the layout `src/data/loader.py`
   expects (`discover_raw_files` — `{SYMBOL}*{TIMEFRAME}*.csv` or
   `.parquet`, or the `{SYM3}_{SYM3}` split-symbol naming).
3. Run `python3 research/experiments/smc_lss_backtest.py`. It requires no
   code changes — the moment data exists, it produces real
   `branch_metrics`, `walk_forward`, and a real `gate.passed` verdict.
4. If the combined-branch gate passes, this report should be regenerated
   (new trial ID — do not overwrite this row in `docs/VERDICT_LOG.md`) with
   the real numbers, and the strategy can be proposed for
   `svos/lifecycle/manager.py`-mediated stage advancement. If it fails,
   per CLAUDE.md §0.2, do not tune parameters against this same trial ID —
   register a new trial.

## Priority

Medium — this is a net-new experimental strategy with no deployment
target and no lifecycle registration; it is not blocking any existing
Phase gate or deployed strategy (§1, §6 of `CLAUDE.md`).

## Rollback

N/A — no existing file was modified. Every file listed in "What was
built" is new; `reports/backtest/SMC-LSS_v0/` contains only
BLOCKED-flagged placeholder artifacts.

## Acceptance criteria

- [x] Full deterministic component pipeline implemented per spec (with
      documented, non-silent assumptions where the spec was ambiguous or
      internally inconsistent)
- [x] 42 unit tests passing, including explicit no-lookahead coverage for
      sweep detection, CHoCH, and the full setup-detection pipeline
- [x] Backtest integration script run for real against this environment
- [x] Real data access attempted and confirmed blocked (not assumed)
- [x] No trades, metrics, or verdict fabricated
- [x] Trial pre-registered in `docs/VERDICT_LOG.md` before any run
- [x] Strategy remains `experimental` — no lifecycle or portfolio file
      touched
