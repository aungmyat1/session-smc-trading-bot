---
Date: 2026-07-12
Author: Lead Architect / Quant (Claude)
Authority: Level 8 — informational evidence. Does not supersede `docs/00_Project/DOC_AUTHORITY.md`.
Scope: Phase 3 of the owner-approved live-trading-readiness sequence
(`docs/audit/STA2_REVALIDATION_READY.md` precondition 3 — "dataset window
decision"). Assessment only — no data fetched, no backtest run.
---

# ST-A2 Dataset Assessment

## Executive Summary

This sandbox's clone has **zero historical market data files** — not "hard to
find," genuinely absent (`data/*` is gitignored repo-wide; confirmed empty
except the 3 tracked `.py` modules). Every dataset-completeness claim in the
repo's own docs is therefore **unverifiable from this session** — I can only
report what the documents claim and flag the gap. Separately, an unmerged
branch (`origin/ST-A2_v2_candidate`) recorded a **real data-loss incident**
on 2026-07-11: the exact CSVs the backtest runner reads were deleted during a
failed extension attempt and are gone, not just absent from this clone. This
changes the starting point for Phase 5 — it's not "extend the existing 169
trade baseline," it's "confirm the baseline data exists anywhere before
planning an extension of it."

This environment also cannot reach the Dukascopy feed by network policy
(confirmed below) — any fetch has to happen elsewhere, same constraint as
Phase 1's broker connection.

## 1 — Inventory: claimed vs. verifiable

| Claim | Source | Verifiable from this session? |
|---|---|---|
| `data/historical/{EUR,GBP}_USD_{M15,H4}.csv` — the files `scripts/backtest_session_liquidity.py` actually reads, produced the 169-trade Phase-0 PASS | `docs/VERDICT_LOG.md` (ST-A2 row), code path in `scripts/backtest_session_liquidity.py:677` | **No** — path does not exist in this clone (gitignored; confirmed via `find`) |
| Those same files were deleted 2026-07-11 during a botched dataset-extension attempt, unrecoverable via git (gitignored, no history) | `origin/ST-A2_v2_candidate`'s `VERDICT_LOG.md` entry (now preserved on `main`, see below) | **Corroborated, not contradicted** — this session independently confirms `data/historical/` is empty, consistent with the incident report. Cannot confirm the incident's *cause* (only its *effect*, which matches) |
| 3-year raw Dukascopy Parquet for EURUSD/GBPUSD/XAUUSD, 2023-07→2026-06, under `data/raw/dukascopy/` — Status: PASS | `reports/DUKASCOPY_3Y_DOWNLOAD_STATUS.md` | **No** — path does not exist in this clone. This is a *different* dataset (tick-schema Parquet, not the OHLCV CSVs the backtest reads) and, per the report's own text, was validated in whatever environment ran that job — possibly `gcp-vm1`, possibly a now-discarded sandbox. Not confirmed false, not confirmed true from here |
| H1 CSVs for both symbols unaffected by the deletion incident | Same branch entry | Unverifiable — no H1 files present here either, but the entry only claims they were unaffected *relative to the incident*, not that they exist in every clone |
| Partial spread-capture data exists (`research/cost_model.json`, 1 London + 1 NY session, 2026-06-24) | `docs/SPREAD_RESEARCH_FINAL_REPORT.md` (Phase 1 territory, not dataset) | **Yes** — these files are tracked in git and present in this clone. Not a Phase 3 concern; noted for completeness only |

**Bottom line:** every claim about the actual backtest input data (OHLCV
CSVs) traces back to either an environment this session has no visibility
into, or a documented deletion incident. Neither confirms nor refutes that
usable data exists somewhere (`gcp-vm1` is the most likely place, per the
architecture's SVOS/execution split) — but nothing here should be assumed
present without a direct check on that host.

## 2 — Network constraint (same shape as Phase 1)

Direct test from this session:
```
curl https://datafeed.dukascopy.com/... → CONNECT tunnel failed, 403
```
Confirmed via the proxy's own status endpoint: `"kind": "connect_rejected",
"detail": "gateway answered 403 to CONNECT (policy denial or upstream
failure)"`. This is a network-policy denial for this session, not a transient
error — consistent with (though distinct in failure mode from) the branch's
own 2026-07-11 report of a Dukascopy timeout from its sandbox. **Any dataset
fetch or extension has to run in an environment with real Dukascopy egress
— not this session, and not necessarily the same sandbox type the prior
incident happened in either.**

## 3 — Trade-count math (reconstructed and rechecked from the branch's own analysis)

Baseline (`ST-A2`, run `20260621T100458-183aaa`, the run that produced the
current Phase-0 PASS the whole revalidation effort is measured against):

| Symbol | Trades | Window | Rate |
|---|---|---|---|
| EURUSD | 105 | 2021-06-21 → 2026-06-19 (5.0yr) | ~21.0/yr |
| GBPUSD | 64 | 2023-03-13 → 2026-06-19 (3.27yr) | ~19.6/yr |
| **Combined** | **169** | — | ~40.6/yr combined |

n>200 floor requires **≥31 more trades** than the baseline. GBPUSD's shorter
window (starting 1.73yr later than EURUSD, for no stated reason — both
notionally come from the same Dukascopy pipeline) is the binding constraint.

I rechecked this arithmetic independently rather than trusting it at face
value — it holds up: 169/8.27 combined-symbol-years ≈ 20.4/yr per symbol
average, consistent with the per-symbol rates shown.

## 4 — Options for reaching n>200

| Option | Window | Est. trades | Margin over floor | Fetch cost (per branch's own estimate, unverified/coarse) | Risk |
|---|---|---|---|---|---|
| **A — Match GBP to EUR's start** | 2021-06-21→2026-06-19 (extend GBP only, +1.73yr) | ~203 | ~1.5% | Smallest fetch (GBP-only) | Thin margin — a single below-average year could drop it under 200 |
| **B — 7-year combined window** (branch's recommendation) | 2019-06-21→2026-06-19 (extend both legs) | ~284 (EUR ~147, GBP ~137) | ~40% | ~90–140 min fetch (network-bound, per archived script's own docstring) + 3–10 min backtest (coarse, scales off an *unmeasured* baseline — no prior timing log exists) | Estimate is a straight-line extrapolation from the historical per-symbol rate; regime shifts could move the real number either way. Also inherits the `htf_bias()` performance issue below at greater severity |
| **C — Wait for `ST-A2-REPLAY-5YR`** (real-tick Dukascopy pipeline, referenced in `VERDICT_LOG.md` but never executed) | Unspecified — depends on that pipeline's own scope | Unknown | Unknown | Unknown — that pipeline doesn't exist yet in runnable form | Cleanest long-term answer (real tick data vs. resampled OHLCV) but adds a dependency on unbuilt tooling; timeline unknown |

**My recommendation for your sign-off:** Option B, but only after Option A's
alternative is explicitly rejected on the record (thin-margin risk is real —
this is exactly the kind of thing that produces a fragile PASS/FAIL flip
across a single bad quarter). I'm not picking for you — this is the
dataset-scope decision that gates Phase 4 pre-registration per your
instruction. Flagging one more factor before you decide:

## 5 — A blocker that exists independent of which option you pick

The branch's execution log recorded `strategy/session_liquidity/
bias_filter.py::htf_bias()` taking **20+ minutes and not finishing** a
single-symbol signal-generation pass on the *existing, unmodified* 5-year
dataset. Root cause identified but not fixed: it re-filters and re-sorts the
entire `candles_4h` list, parsing every bar's ISO timestamp, on *every call*
— O(bars × candles_4h) with no caching, called once per un-swept killzone
bar. A 7-year dataset (Option B) makes this worse, not better. This needs a
fix (cache the sorted/parsed H4 series once, not per-call) before any
expanded-window backtest can realistically complete — independent of which
dataset option you choose, and independent of whether the data itself is
available. I have not touched `strategy/session_liquidity/` — flagging per
governance mode's "don't build toward a phase silently," since fixing
strategy code is a bigger scope change than "cherry-pick Sharpe" and should
be an explicit decision, not something I do as a side effect of dataset prep.

## What I did NOT do

- No data fetched, no Dukascopy job started (blocked by network policy
  anyway, per §2).
- No backtest run.
- No fix to the `htf_bias()` performance issue (flagged, not touched — it's
  strategy code, out of this phase's scope; call this out explicitly if you
  want it picked up next).
- No dataset-option decision made — presenting A/B/C above for your call.

## Recommendation to you

1. Decide A vs. B vs. C (§4) — or a different scope entirely.
2. Separately decide whether the `htf_bias()` performance fix (§5) should be
   scheduled now (it blocks Option B/C regardless of data availability) or
   deferred until data is confirmed available on whichever host will run
   the actual fetch + backtest.
3. Whoever has access to `gcp-vm1` (or wherever the 2026-06-21 baseline data
   and the 3-year Dukascopy Parquet actually live) should confirm presence
   and integrity of `data/historical/{EUR,GBP}_USD_{M15,H4}.csv` before any
   fetch/extension work starts — extending a baseline that may itself be
   gone would compound the 2026-07-11 incident rather than recover from it.
