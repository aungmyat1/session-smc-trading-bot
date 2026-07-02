# Strategy Portfolio Roadmap
# Research-08 — Future Strategy Pipeline
# Date: 2026-06-23 | Specification only — no implementation

---

## ⚠ Known drift vs. actual deployment (added 2026-07-01)

This document describes a strict sequential A→B→C→D ladder, gated on Strategy A's
paper-trade result. `config/strategy_portfolio.yaml` has since diverged from that: it
runs **five** strategies concurrently in tiered demo/shadow execution — ST-A2 (demo,
tier1), LondonBreakout (demo, tier2), NYMomentum (demo, tier2), AdaptiveSMC (shadow,
tier3), VWAPMeanReversion (shadow, tier3) — none of which map onto this ladder's B/C/D
strategies, and none of which have cleared this document's Phase-0 gates. See specs
under `docs/strategy_audit/strategies/`. This is a tracked governance gap (CLAUDE.md
§1, `docs/VERDICT_LOG.md` 2026-07-01 entry), not resolved by this note — reconciling
"what this roadmap says should be blocked" against "what the config actually runs" is
open work for the owner, not something to silently pick a side on.

---

## Purpose

Define the four-strategy portfolio roadmap for this trading system. Each strategy
targets a distinct market condition and occupies a non-overlapping position in the
trade frequency / holding-time / setup-type space. This document is a planning spec
only — no implementation until the prior strategy clears its gate.

**Important distinction:** D2 E3 is a separate research branch tracked in
`docs/VERDICT_LOG.md`. It is not part of the core A→B→C→D deployment ladder
unless and until it clears its own holdout gate and is explicitly promoted.

**Deployment constraint:** Each strategy below is BLOCKED until the strategy
immediately before it has cleared Phase-0 gate AND completed a 30-day paper trade
with n ≥ 50 trades and no critical execution failures. No two strategies share
backtest time periods or signal-chain logic.

---

## Strategy A — Session Liquidity Reversal (CURRENT)

| Field | Detail |
|---|---|
| **Status** | Phase-0 PASS ✅ — current production path; OPS-01 / DEP-02 paper trade in progress |
| **Purpose** | Capture the institutional sweep-and-reverse pattern at session open liquidity pools |
| **Signal chain** | 4H+1H bias → session range build → sweep detection → 15M displacement → FVG retest |
| **Sessions** | London 07:00–10:00 UTC, New York 13:00–16:00 UTC |
| **Expected frequency** | ~34 trades/year (~3/month, ~1–2 per active week) |
| **Expected holding time** | 400–700 min per trade (avg 632 min at RR5) |
| **Pairs** | EURUSD, GBPUSD |
| **RR target** | 5R (TP1: 4R / 75%, SL→BE; TP2: 5R+) |
| **Phase-0 result** | 169 trades, PF_std=1.151, PF_2x=1.025 ✅ |
| **Primary edge** | NY session (PF 1.731) driven by GBPUSD (PF 1.313) |
| **Primary drag** | London session (PF 0.949), GBPUSD London specifically |

**Required modules (all built):**
- `strategy/session_liquidity/session_builder.py`
- `strategy/session_liquidity/bias_filter.py`
- `strategy/session_liquidity/sweep_detector.py`
- `strategy/session_liquidity/displacement_detector.py`
- `strategy/session_liquidity/entry_engine.py`
- `strategy/session_liquidity/session_strategy.py`
- `execution/` (all modules)

**Deployment order:** First. Bot running. OPS-01 stability run 2026-06-22 through 2026-06-28.

---

## Strategy B — SMC Reversal

| Field | Detail |
|---|---|
| **Status** | BLOCKED — pending Strategy A paper-trade result (n ≥ 50, no critical failures) |
| **Purpose** | Trade smart-money structural reversals (CHoCH + displacement) independent of session timing |
| **Hypothesis** | Structural breaks after liquidity sweeps hold edge outside session killzones, adding trade frequency without session-window constraints |
| **Signal chain** | Multi-TF swing detection → CHoCH identification → displacement confirmation → FVG or OB retest entry |
| **Sessions** | All hours (no session filter) — or London + NY extended windows if backtest shows session sensitivity |
| **Expected frequency** | ~60–80 trades/year (if no session filter); actual TBD by backtest |
| **Expected holding time** | 2–6 hours (shorter than Strategy A — CHoCH entries are closer to structure) |
| **Pairs** | EURUSD, GBPUSD, USDJPY (candidate) |
| **RR target** | TBD — likely 3R–5R; depends on FVG retest distance vs SL |
| **Phase-0 gate** | n ≥ 100, PF_std > 1.0, PF_2x > 1.0 on 5yr holdout |

**Required modules (partially built):**
- `session_smc/swing_detector.py` ✅ (127 tests)
- `session_smc/structure_detector.py` ✅
- `session_smc/liquidity_detector.py` ✅
- `session_smc/poi_detector.py` ✅
- `session_smc/confirmation_entry.py` ✅
- `session_smc/smc_strategy.py` — NOT YET BUILT (SB-06 blocked)
- Backtest script for SMC — NOT YET BUILT

**Deployment order:** Second. Begin SB-06 after Strategy A DEP-02 paper trade passes.

**Known risk:** Strategy A's session CHoCH filter (Phase 6 of signal chain) already
incorporates CHoCH detection. Strategy B must be verified to not overlap with
Strategy A signals (run simultaneously = double-entry risk on same setup).
Mitigation: separate magic numbers (21001/21002 for A; 21003/21004 for B).

---

## Strategy C — Trend Continuation

| Field | Detail |
|---|---|
| **Status** | BLOCKED — pending Strategy B gate |
| **Purpose** | Capture sustained directional moves in trending market regimes by entering on pullbacks to structure, not reversals |
| **Hypothesis** | In strong-trend environments (ADX > 25), pullbacks to BOS levels or HTF FVGs produce continuation trades with higher win rate and longer holding times than reversal setups |
| **Signal chain** | 4H regime classification (ADX > 25 + EMA alignment) → BOS on pullback TF → entry at BOS level or FVG fill → trail stop via swing highs/lows |
| **Sessions** | London + NY overlap (13:00–16:00 UTC primary; extended to 10:00–17:00 UTC if data supports) |
| **Expected frequency** | ~20–40 trades/year (lower — trending regimes are episodic) |
| **Expected holding time** | 8–24 hours (overnight holds expected for trend runners) |
| **Pairs** | EURUSD, GBPUSD, USDJPY, AUDUSD (broader set for trend capture) |
| **RR target** | 5R–10R (wider targets enabled by trailing stop) |
| **Phase-0 gate** | n ≥ 100, PF_std > 1.0, PF_2x > 1.0 on 5yr holdout including trending years |

**Required modules (none built):**
- `strategy/trend_continuation/regime_classifier.py` — ADX + EMA regime tagging
- `strategy/trend_continuation/bos_detector.py` — pullback BOS detection on 1H
- `strategy/trend_continuation/entry_engine.py` — BOS-level or FVG retest entry
- `strategy/trend_continuation/trailing_stop.py` — swing-based trail management
- `strategy/trend_continuation/trend_strategy.py` — orchestrator
- Backtest script

**Deployment order:** Third. Begin after Strategy B Phase-0 PASS.

**Known risk:** Overnight holds require either a session-close rule (sell at daily
close) or a wider SL that survives overnight gaps. The current execution layer's
`session_close_rule` will close all positions at session end — this must be disabled
for Strategy C. Execution layer change requires explicit task and test coverage.

**Known risk 2:** Strategy A is a reversal strategy. Strategy C is a trend strategy.
They will often have opposite HTF bias signals (A goes short when trend goes up; C
goes long). Concurrent deployment requires clear per-strategy magic numbers and
no shared position tracking. The MAX_OPEN_TRADES=1 per symbol rule must be enforced
per strategy, not globally — or strategies must trade different symbols.

---

## Strategy D — Market Regime Filtered Session

| Field | Detail |
|---|---|
| **Status** | BLOCKED — pending Strategy A + B results (requires empirical regime data from both) |
| **Purpose** | A meta-layer that dynamically allocates between Strategy A (reversal) and Strategy C (trend) based on quantified market regime, reducing time spent in wrong-regime setups |
| **Hypothesis** | Strategy A underperforms in trending years (2023, 2025 negative). Strategy C underperforms in ranging years. A classifier that gates each strategy by regime will produce higher combined PF and lower drawdown than either alone |
| **Signal chain** | Weekly regime classifier (ADX, ATR trend, BTC correlation optional) → allocate signals to A or C → unified execution layer |
| **Sessions** | Inherits from active strategy (A or C) |
| **Expected frequency** | Combined: 40–80 trades/year (net of regime filtering) |
| **Expected holding time** | Variable (Strategy A holding time in ranging regime; Strategy C in trending) |
| **Pairs** | EURUSD, GBPUSD (minimum) |
| **RR target** | Inherits from active sub-strategy |
| **Phase-0 gate** | Requires backtested performance of combined regime-gated result vs each sub-strategy alone. n ≥ 100 combined. |

**Required modules (none built):**
- `strategy/regime/classifier.py` — weekly ADX + volatility regime tagger
- `strategy/regime/allocator.py` — routes signal generation to A or C based on regime
- Backtest framework: joint A+C simulation with regime switching

**Deployment order:** Fourth — and only after Strategy A AND Strategy C have
individually cleared their Phase-0 and paper-trade gates. Strategy D requires
empirical regime data from live/paper runs of A and C, not purely from backtests.

**Known risk:** Regime classifiers overfit to historical regime boundaries. Any
regime filter must be validated on a holdout period that includes a full regime
transition (ranging → trending → ranging). The 2021–2026 dataset has 2–3 such
transitions — sufficient for validation but only if the classifier parameters are
not tuned on the same period.

---

## Portfolio Deployment Timeline (Target)

| Strategy | Gate Condition | Earliest Start |
|---|---|---|
| A — Session Liquidity | Phase-0 PASS ✅ | Running (OPS-01 in progress) |
| B — SMC Reversal | A DEP-02 complete (n≥50, 30 days) | ~2026-09 (if paper trade starts by Aug) |
| C — Trend Continuation | B Phase-0 PASS | ~2027-01 (optimistic) |
| D — Regime Filter | A + C both paper-trade cleared | ~2027-06 (earliest) |

**Note:** These dates assume each strategy backtests and paper-trades successfully.
Most strategies require 1–3 additional backtest cycles before clearing Phase-0.
Failed strategies restart the gate from the beginning with a new trial ID.

---

## Cross-Strategy Risk Controls

1. **Symbol isolation:** Each strategy must use unique magic numbers. Position sizing
   and halt logic are per-strategy, not global. One strategy's drawdown must not
   affect another's position sizing.

2. **Capital allocation:** The current system is 100% in Strategy A. When B is added:
   allocate 60% A / 40% B by capital at risk, rebalance quarterly. Strategy D
   inherits A and C allocations dynamically.

3. **Max portfolio drawdown:** At any time, if combined equity drawdown > 15%, halt
   all strategies and review. Strategy D's regime allocator may reduce this by routing
   capital away from wrong-regime setups.

4. **Session overlap:** Strategies A, B, C can all fire in the same session. OrderManager
   must prevent positions in the same symbol from two strategies simultaneously.

5. **Fee floor:** All strategies must clear the 0.40% spread-equivalent gate before
   any parameter is considered. This is non-negotiable per VT Markets cost model.

---

*No implementation in this document. Specification only.*
*Next action: continue Strategy A OPS-01 / DEP-02 paper trade before any B work.*
