# ST_B_RESEARCH_PLAN.md
# Strategy B — Full SMC Session Reversal
# Research plan | 2026-06-24 | Version 1.0

---

## Context

ST-A2 passed Phase-0 (n=169, PF_2x=1.025, RR=5). EXP05 optimization failed to lift any
variant above the 4-gate target (n≥100, PF_2x>1.25, WR≥40%, DD<15R). The strongest signal
from EXP05 is the NY-only edge (Variant B: PF_2x=1.562, WR=41.2%, n=51 — failed on n alone).

ST-B is the next pre-registered research track: the full 11-phase SMC chain, differing from
ST-A2 in two critical ways:
1. Entry is at the FVG *retest* bar close, not the displacement close.
2. CHoCH + BOS + FVG are AND-gated before any entry; ST-A2 used displacement only.

All session_smc modules required by ST-B already exist and pass 127 tests.
ST-B Phase-0 is a backtest-only task. No execution layer is involved.

---

## A — Strategy Definition

### A.1 Identity

| Field | Value |
|---|---|
| Strategy name | ST-B (Full SMC Session Reversal — Setup A) |
| Instruments | EURUSD, GBPUSD (identical to ST-A2) |
| Timeframes | 4H + 1H (HTF bias) → 15M (all confirmation + entry) |
| Sessions | London 07:00–10:00 UTC | New York 13:00–16:00 UTC |
| Entry rule | Bar-close only. Entry = close of FVG retest bar (15M). |
| Max signals | One per session per day. |
| Status | UNVALIDATED — Phase-0 backtest required. |

### A.2 Full Signal Chain (11 phases, all AND-gated)

```
Phase 1  Session Active             Caller enforces session boundary (07-10 / 13-16 UTC)

Phase 2  HTF Bias (4H + 1H)
         4H structure (swing_n=3): classify_structure(h4_bars) → bullish | bearish
         1H structure (swing_n=3): classify_structure(h1_bars) → bullish | bearish | neutral
         Gate: 4H bullish AND 1H not bearish  → long bias
               4H bearish AND 1H not bullish  → short bias
               All other combinations         → SKIP SESSION

Phase 3  Session Range Build
         build_session_range(session_bars, range_bars=8, min_range_pips=10.0)
         Uses first 8 M15 bars (= first 2 hours of session).
         Gate: range ≥ 10 pip. Narrower sessions = SKIP.

Phase 4  Session Classification (informational, not a hard gate)
         classify_session(session_bars, session_range) → RANGE | TREND | MIXED
         Logged for analysis. Does not block signal.

Phase 5  Liquidity Sweep
         detect_sweep(session_bars, session_range, bias, from_idx=8)
         Bullish: wick below session LOW, close back above LOW.
         Bearish: wick above session HIGH, close back below HIGH.
         Sweep checked from bar 8 onwards (after range is built).

Phase 6  CHoCH (Change of Character)
         detect_choch(session_bars, sweep_idx, bias, lookback=8)
         Reference level = max/min of the 8 bars immediately before the sweep.
         CHoCH = first bar after sweep whose CLOSE breaks the reference in trade direction.

Phase 7  BOS (Break of Structure)
         BOS level = last confirmed swing high (bullish) or low (bearish) before sweep.
         detect_bos(session_bars, choch_idx, bias, bos_level)
         BOS = first bar after CHoCH whose CLOSE breaks the swing level.
         Gate: if no prior swing exists → SKIP (insufficient structure history).

Phase 8  Displacement
         detect_displacement(session_bars, sweep_idx, bos_idx, bias, atr_vals, atr_mult=1.5)
         Search window: [sweep_idx, bos_idx] inclusive.
         Displacement = first bar with range ≥ 1.5×ATR(14) and body in trade direction.
         The displacement bar is the impulse that drives price to the BOS level.

Phase 9a FVG Detection
         find_fvg(session_bars, displacement_idx, bias)
         Bullish FVG: session_bars[d+1].low > session_bars[d-1].high
         Bearish FVG: session_bars[d+1].high < session_bars[d-1].low
         Gate: gap must exist. No gap → SKIP.

Phase 9b FVG Retest
         check_fvg_retest(session_bars, fvg, bias, from_idx=displacement_idx+2)
         Bullish: bar.low ≤ fvg.top AND bar.close ≥ fvg.bottom (held above bottom)
         Bearish: bar.high ≥ fvg.bottom AND bar.close ≤ fvg.top
         Invalidated if close exits the opposite edge of the FVG.
         Gate: retest must occur within the session window (before session end).

Phase 10 Risk Parameters
         Entry   = session_bars[retest_idx].close
         SL      = tighter of:
                     (a) sweep wick extreme ± sl_buffer_pips (default 3.0)
                     (b) entry ± 25% of session range
         Gate: SL must be on the opposite side of entry. Degenerate SL → SKIP.

Phase 11 Minimum bars remaining
         bars_remaining = len(session_bars) - 1 - retest_idx
         Gate: bars_remaining ≥ 2 (need room to trade before session ends)
```

### A.3 Risk Model

| Parameter | Value | Rationale |
|---|---|---|
| risk_per_trade | 1% of account | Standard per CLAUDE.md §4 |
| max_daily_loss | 3R | Halt for the day on 3 consecutive losses |
| max_drawdown | 10% of peak | Kill switch |
| max_consecutive_losses | 5 | Halt until next day |
| SL logic | Tighter of wick±3pip or 25% range | Wick-based is tighter in slow sweeps; range-based catches fast reversals |
| min_sl_pips | 5.0 | Inherited from ST-A2 to prevent spread-dominated stops |

### A.4 Exit Model

| Exit | Condition | Action |
|---|---|---|
| TP1 | +4R | Close 75% of position; move SL to breakeven |
| TP2 | +5R or session end | Trail remaining 25% to session structure target or close at session end |
| SL | Price hits stop | Full close |
| Session end | Open trade at session close bar | Close 100% at market (no overnight) |

**Partial-close simulation note:**
Backtest must track two sub-positions (75% lot and 25% lot) with different exit conditions.
TP1 is at +4R from entry; TP2 at +5R (or session-end close, whichever comes first).
The SL moves to breakeven after TP1. BE = entry price (rounded to pip).

---

## B — Architecture Mapping

### B.1 Modules That Can Be Reused Unchanged

| Module | Location | Function | ST-B Usage |
|---|---|---|---|
| `swing_detector.py` | `session_smc/` | Swing H/L detection, classify_structure | HTF bias, BOS level |
| `structure_detector.py` | `session_smc/` | htf_bias, detect_choch, detect_bos, detect_displacement, atr | All structural phases |
| `liquidity_detector.py` | `session_smc/` | build_session_range, classify_session, detect_sweep | Phases 3–5 |
| `poi_detector.py` | `session_smc/` | find_fvg, check_fvg_retest | Phases 9a–9b |
| `confirmation_entry.py` | `session_smc/` | generate_signal_A() — full 11-phase chain | Primary signal generator |
| `session_builder.py` | `strategy/session_liquidity/` | classify_session() → session boundary detection | Session slicing in backtest |
| `scripts/fetch_data.py` | `scripts/` | Data download | Already used; no changes |
| `data/historical/*.csv` | `data/historical/` | M15 + H4 + H1 CSVs | Direct reuse |

**Note:** `session_smc/liquidity_detector.py` and `strategy/session_liquidity/session_builder.py`
both export a function called `classify_session` but they have different signatures and purposes:
- `session_smc` version: classifies RANGE/TREND/MIXED from ATR ratio (Phase 4)
- `session_liquidity` version: classifies 'london' | 'new_york' | 'asian' | None from UTC hour (session boundary)
The backtest orchestrator must import these carefully to avoid name collision.

### B.2 New Modules Required

| File | Responsibility | Notes |
|---|---|---|
| `scripts/backtest_stb.py` | Phase-0 backtest runner — session orchestration, signal generation, partial-close simulation, metric report | The only new file for Phase-0. ~300–400 lines. |

That is the entirety of the new code required for Phase-0. All SMC signal logic already exists.

### B.3 Modules That Must Remain Untouched

| Scope | Files | Reason |
|---|---|---|
| ST-A2 strategy | `strategy/session_liquidity/` (all) | ST-A2 is the active benchmark; must not be contaminated |
| Execution layer | `execution/` (all) | AGENT_RULES §7; not involved in Phase-0 |
| Risk manager | `execution/risk_manager.py` | AGENT_RULES §8 |
| Deployment / ops | `bot.py`, `scripts/health_check.py`, OPS-01 infrastructure | Stability run in progress |
| SMC modules | `session_smc/` (all) — read-only for Phase-0 | Modules are stable and tested; do not refactor during backtest |

---

## C — Development Breakdown

### STB-01: Backtest Orchestrator Skeleton

**File:** `scripts/backtest_stb.py`

**Responsibility:**
Load M15 + H4 + H1 CSVs. Group M15 bars by date and session (London 07-10, NY 13-16 UTC).
For each session, call `generate_signal_A()` bar-by-bar (incrementally), stopping on the first
valid signal. Output: a list of `Signal` objects with global bar index for simulation.
No simulation in this task — stop at "here is the signal list."

**Interface contract:**
```python
def run_stb(
    m15_bars: list[dict],
    h4_bars: list[dict],
    h1_bars: list[dict],
    symbol: str,
    config: dict | None = None,
) -> list[Signal]
```

**Key design decisions:**
- `h4_before` = H4 bars whose open time ≤ session_start_time − 4h (bar-close safe)
- `h1_before` = H1 bars whose open time ≤ session_start_time − 1h
- Call `generate_signal_A()` from bar `range_bars + 5` onwards, once per additional bar
- Stop at first Signal per session (one signal per session per day rule)
- Session boundary: reuse `session_builder.classify_session(dt)` from `strategy/session_liquidity/`

**Required tests:**
- `tests/stb/test_backtest_stb_orchestrator.py`
- Test: no lookahead (h4/h1 bars respect cutoff time)
- Test: one signal per session per day enforced
- Test: session boundary detection (London 07-10, NY 13-16 UTC)
- Test: correct H4/H1 slicing at DST boundaries

**Acceptance criteria:**
- `run_stb()` on EURUSD M15+H4+H1 CSVs returns a list of Signal objects
- Signal count is deterministic (same count on two runs)
- No lookahead: h4/h1 slice never includes bars closed after session start
- All session boundary tests pass

---

### STB-02: Partial-Close Simulation Engine

**File:** `scripts/backtest_stb.py` (added to STB-01)

**Responsibility:**
Simulate each Signal forward on M15 bars. Implement TP1/TP2 partial-close logic:
- 75% position exits at TP1 (+4R from entry)
- 25% position: SL moves to breakeven after TP1; exits at TP2 (+5R) or session end
- SL checked before TP on every bar (same discipline as ST-A2 backtest)
- Session-end close: if trade open when session boundary ends, close remaining lot at session-end bar close

**Simulation returns per trade:**
```python
{
    "signal": Signal,
    "tp1_hit": bool, "tp1_r": float,   # R earned on 75% lot
    "tp2_exit": str,                    # 'tp2' | 'session_end' | 'sl_after_tp1'
    "tp2_r": float,                     # R earned on 25% lot
    "total_r": float,                   # 0.75*tp1_r + 0.25*tp2_r (weighted)
    "spread_cost_r_std": float,
    "spread_cost_r_2x": float,
    "net_r_std": float,                 # total_r − spread_cost_r_std
    "net_r_2x": float,
}
```

**Required tests:**
- `tests/stb/test_backtest_stb_simulation.py`
- Test: SL hit before TP1 — full loss (total_r = −1.0 before spread)
- Test: TP1 hit, then TP2 hit — full sequence correct
- Test: TP1 hit, then SL after BE — 75% win + 25% at 0R (≈ breakeven on runner)
- Test: TP1 hit, then session end — close 25% at last session bar close
- Test: spread cost applied correctly at both standard and 2× stress

**Acceptance criteria:**
- All 5 exit scenarios simulated correctly
- weighted R = 0.75 × tp1_r + 0.25 × tp2_r in every path
- Net R = total_r − spread_cost at both spread levels

---

### STB-03: Metrics Report

**File:** `scripts/backtest_stb.py` (added) + `docs/STB_PHASE0_RESULTS.md` (output)

**Responsibility:**
Aggregate simulation output into:
- PF (std) and PF (2×): sum(positive net_r) / abs(sum(negative net_r))
- Win rate: trades where net_r_std > 0 / total
- Max drawdown: running R equity curve peak-to-trough
- Per-symbol breakdown (EURUSD / GBPUSD)
- Per-session breakdown (london / new_york)
- Per-year breakdown (2021–2026)
- Trades per year

Write `docs/STB_PHASE0_RESULTS.md` in the same format as `docs/BACKTEST_RESULTS.md`.

**Required tests:**
- `tests/stb/test_backtest_stb_metrics.py`
- Test: PF = infinity when no losses
- Test: PF = 0 when no wins
- Test: max drawdown with known R sequence
- Test: per-year grouping correct (key = year from Signal.bar_time)

**Acceptance criteria:**
- Metrics match manual calculation on a 10-trade fixture
- Output file written to docs/STB_PHASE0_RESULTS.md

---

### STB-04: Phase-0 Gate Evaluation + VERDICT_LOG Entry

**File:** `docs/STB_PHASE0_RESULTS.md` (from STB-03) + `docs/VERDICT_LOG.md` (updated)

**Responsibility:**
Run `scripts/backtest_stb.py` on the full 5yr dataset (EURUSD + GBPUSD).
Evaluate gate (see §D below).
Register result in `docs/VERDICT_LOG.md` as trial `ST-B`.
If FAIL: document the primary failure mode and propose a parameter adjustment as a new trial
(must be registered as ST-B2 before running — §9 trial discipline).

**Required tests:** None (this is a run task, not a code task).

**Acceptance criteria:**
- `docs/STB_PHASE0_RESULTS.md` exists with full metrics
- `docs/VERDICT_LOG.md` has a new row for ST-B with PASS or FAIL verdict
- If FAIL: root cause identified (see §E bottlenecks) and at most ONE follow-on trial proposed

---

### STB-05 (Conditional): Parameter Sensitivity

**Only if STB-04 FAIL and a specific, targeted fix exists.**

Proposed adjustment trials (register before running):
- ST-B2: Relax CHoCH lookback from 8 → 12 bars (more CHoCH candidates)
- ST-B3: Remove session-end close rule for runner (TP2 allowed overnight — measures impact)
- ST-B4: Add AUDUSD or USDJPY (pip-adjusted, same chain — measures pair count impact)

Each trial = one change. Register in VERDICT_LOG before running. Per CLAUDE.md §0.2.

---

## D — Phase-0 Gate Definition

| Gate | Threshold | Rationale |
|---|---|---|
| Trade count | n ≥ 50 | CLAUDE.md §7 minimum. 50 trades over 5yr is achievable even with strict confirmation. n < 50 indicates the confirmation chain is too strict for these instruments/sessions; requires structural rethink (not tuning). |
| PF (std spread) | > 1.0 | CLAUDE.md §7 gate. Net positive expectancy at real cost is the baseline requirement. |
| PF (2× spread) | > 1.0 | CLAUDE.md §7 gate. Must survive doubled spread stress (T29-GBP lesson: marginal at standard, failed 2×). |
| Years tested | ≥ 4 (actual coverage) | EURUSD has 4.9yr; GBPUSD has 3.3yr. Treat 2021–2024 as minimum valid window. Partial 2026 included if data available. |

**On the n ≥ 50 vs n ≥ 100 discrepancy:**
AGENT_RULES §5 specifies n ≥ 100. CLAUDE.md §7 specifies n ≥ 50. For ST-B Phase-0, n ≥ 50 applies:
the strict 11-phase confirmation chain will produce far fewer trades than ST-A2's 169. Requiring
100 would likely fail even before seeing whether the strategy has edge. The purpose of Phase-0
is to validate that edge exists at all — n = 50 is sufficient for that determination. If ST-B
passes at n = 50–99, the demo phase (Phase-1) remains mandatory and will accumulate more trades.

**Stress test variants to run in STB-03 (not separate trials):**
- RR3, RR4, RR5 (same as ST-A2 analysis — report all three, require at least one to pass)
- TP1-only simulation (no TP2 runner) — measures whether the partial close adds value
- London-only vs NY-only sub-sets (EXP05 finding: NY edge is 3× London edge)

---

## E — Expected Bottlenecks

### E.1 Low Trade Count (PRIMARY RISK — HIGH probability)

**Mechanism:** The FVG retest is the tightest gate. For a valid FVG retest:
1. Displacement must leave a price imbalance (gap between d−1 high and d+1 low)
2. Price must pull back into the gap before session end
3. The gap must not be invalidated (close through the opposite edge)

**Estimate:**
- ST-A2 generates ~34 signals/yr (169/5yr). Many of these will have sweeps but no FVG.
- Historical FVG formation rate on M15 after displacement: unknown; likely 40–60% of sweeps.
- FVG retest rate within session: likely 40–60% of formed FVGs (session time constraint).
- Combined: ~16–36% of sweeps → valid ST-B signal → ~5–12 signals/yr → 25–60 total over 5yr.
- The n ≥ 50 gate is at risk. n ≥ 100 is likely unachievable.

**If confirmed low count:** EXP05 Variant B (NY only) showed strong edge but n=51 over 5yr.
ST-B's stricter confirmation will produce fewer. The fix is adding pairs or extending history,
not tuning the confirmation chain.

### E.2 FVG Rarity

**Mechanism:** True price imbalances (d+1.low > d−1.high) require the displacement body to be
large enough to gap over the prior bar's high. ATR_mult=1.5 screens for large displacements
but many 1.5×ATR bars will still have overlapping wicks with adjacent bars.

**Mitigation to test in STB-05:** Relax FVG to include "near FVGs" (gap ≤ 2 pip); this is a
separate trial and must be registered before running.

### E.3 Session Time Constraint

**Mechanism:** London 07–10 UTC = 12 bars. NY 13–16 UTC = 12 bars. After building the 8-bar
range and waiting for sweep (bar ≥ 8), at most 4 bars remain for CHoCH+BOS+displacement+FVG.
Then the FVG retest must occur within the same session window. This severely limits retest time.

**Impact:** Many valid FVGs will form in the last 1–2 bars of the session; price has no time
to retest. Estimated failure rate from this cause: 30–50% of FVG opportunities.

**Possible remediation (future trial):** Extend session end by 30–60 min (to 10:30 / 16:30 UTC).
Must be registered as a new trial before testing.

### E.4 CHoCH/BOS History Gap

**Mechanism:** `last_swing_high()` for BOS level requires `2n+1 = 7` bars before the sweep
at swing_n=3. If the sweep occurs at bar 8–10 of the session (early session), there may not
be enough prior swings for a confirmed BOS level. The session_smc modules only use the current
session's bars (no cross-session context).

**Impact:** BOS detection returns None → Phase-7 fails → signal dropped. Primarily affects
early-session sweeps (bars 8–10). Later sweeps (bars 10+) are less affected.

**Note:** This is different from the PRE_SESSION_BARS=30 issue in EXP05, which was a backtest
tooling issue. Here the question is whether `generate_signal_A()` passes session-only bars
or a wider context window. The current implementation passes session_candles only (starting
from session open), meaning early sweeps have insufficient BOS history.

**Mitigation:** Pass `pre_session_bars + session_candles` to generate_signal_A() so BOS
detection has prior-session swings available. This is a design decision for STB-01, not a
parameter change — document the choice and test both behaviors.

### E.5 Spread Sensitivity at Tight SL

**Mechanism:** ST-B's SL = tighter of (wick ± 3pip, 25% range). In low-volatility sessions
where sweeps are shallow (< 10 pip wick), the 3-pip buffer can produce SL < 5 pip, making
spread cost > 20% of 1R. The min_sl_pips=5.0 gate (from ST-A2) inherited in confirmation_entry
DEFAULT_CONFIG will help but may drop trades.

**Note:** `DEFAULT_CONFIG` in `confirmation_entry.py` does NOT currently have `min_sl_pips`.
The backtest runner should apply a post-signal SL floor of 5.0 pip (matching ST-A2) without
modifying the module.

### E.6 GBPUSD Data Coverage

**Mechanism:** GBPUSD M15 data starts 2023 (3.3yr). EURUSD has 4.9yr. Combined ST-B analysis
will be GBPUSD-light. If ST-B's edge is concentrated in GBPUSD (as implied by ST-A2's per-symbol
results: GBPUSD PF_2x=1.168 vs EURUSD PF_2x=0.945), the shorter history understates the true
sample size for GBPUSD.

---

## F — Research Hypotheses

Ranked by confidence level (highest to lowest):

**H1 (CONFIDENCE: HIGH):** FVG retest entry will produce a higher win rate than ST-A2's
displacement-close entry.

*Rationale:* Entry at a defined support/resistance zone (FVG midpoint) with price already
having reversed from the sweep gives a higher-probability entry point than entering at the
displacement close (which occurs into momentum). EXP05 Variant B WR=41.2% vs ST-A2 combined
WR=32.0% at NY-only already shows the session filter alone lifts WR. The FVG retest should
add another 5–10pp by filtering for confirmed pullback entries.

*What to measure:* WR of ST-B vs ST-A2 NY-only (51 trades, WR=41.2%). Target: WR ≥ 45%.

---

**H2 (CONFIDENCE: MEDIUM-HIGH):** NY-only (13–16 UTC) will again be the dominant edge carrier.

*Rationale:* EXP05 Variant B demonstrated NY accounts for the entire net edge in ST-A2
(NY PF_std=1.731 vs London PF_std=0.949). The structural reason is likely NY session having
cleaner institutional order flow with stronger CHoCH/BOS sequences. ST-B's confirmation chain
should amplify this asymmetry.

*What to measure:* Per-session PF breakdown in STB-03. Expected: NY PF_2x > 1.25, London < 1.0.

---

**H3 (CONFIDENCE: MEDIUM):** Trade count will be < 50 over 5yr, requiring an architecture
decision before Phase-1.

*Rationale:* ST-A2 generates ~34 trades/yr. Adding CHoCH+BOS+FVG+retest gates reduces this
by an estimated 50–80% (based on EXP05 findings on CHoCH+BOS alone reducing 29→2 signals,
and separately estimating FVG formation at ~40-60% of displacements and retest at ~50-60%
of FVGs). The range of outcomes is wide but n < 50 is more likely than n ≥ 50.

*Implication if confirmed:* Do not tune parameters — add pairs or extend backtest window.
The confirmation chain is architecturally correct; it is just selective by design.

---

**H4 (CONFIDENCE: MEDIUM):** GBPUSD will outperform EURUSD in the ST-B framework.

*Rationale:* ST-A2 per-symbol: GBPUSD PF_2x=1.168, EURUSD PF_2x=0.945. EURUSD fails 2×
stress individually; combined passes only due to GBPUSD. ST-B's tighter confirmation may
expose this asymmetry more sharply. If EURUSD produces n < 20 signals over 5yr, it is a
candidate for exclusion in an ST-B2 trial.

*What to measure:* Per-symbol PF and n in STB-03.

---

**H5 (CONFIDENCE: MEDIUM-LOW):** The partial-close exit model (TP1=75%@4R, TP2=25%@5R+)
will produce better risk-adjusted returns than a single-exit model at 5R.

*Rationale:* The FVG retest is a mean-reversion entry within a sweep reversal. After TP1 (4R),
price has achieved a substantial move. The runner (TP2) benefits from trend continuation if
structural momentum is strong. However, the session-end close rule may truncate the runner in
many cases. This is testable by comparing TP1-only vs TP1+TP2 in STB-03 without a new trial
registration (it is a reporting variant within the same run, not a parameter change).

*What to measure:* Compare `PF_tp1_only` (simulated with full exit at 4R) vs `PF_tp1_plus_tp2`
in STB-03 metrics. If TP2 adds < 0.05 PF points, simplify to single exit.

---

## G — Implementation Order & Current Task

```
STB-01  scripts/backtest_stb.py: orchestrator skeleton
        → session slicing, bar-by-bar generate_signal_A() calling, signal list output
        ↓
STB-02  scripts/backtest_stb.py: partial-close simulation engine
        ↓
STB-03  scripts/backtest_stb.py: metrics + docs/STB_PHASE0_RESULTS.md writer
        ↓
STB-04  Run on 5yr data; evaluate Phase-0 gate; register in VERDICT_LOG.md
        ↓
STB-05  (conditional) If FAIL: one targeted adjustment trial → register → rerun
```

**Current task: STB-01** (registered below in PROJECT_STATUS.md).

---

## H — Files Reference

| Action | File |
|---|---|
| Read (signal chain) | `session_smc/confirmation_entry.py` |
| Read (modules) | `session_smc/structure_detector.py`, `swing_detector.py`, `liquidity_detector.py`, `poi_detector.py` |
| Read (session boundary) | `strategy/session_liquidity/session_builder.py` |
| Read (spread model reference) | `scripts/backtest_session_liquidity.py` |
| Read (data format) | `data/historical/EUR_USD_M15.csv` (header: time, open, high, low, close) |
| Create | `scripts/backtest_stb.py` |
| Create | `tests/stb/test_backtest_stb_orchestrator.py` |
| Create | `tests/stb/test_backtest_stb_simulation.py` |
| Create | `tests/stb/test_backtest_stb_metrics.py` |
| Create | `docs/STB_PHASE0_RESULTS.md` (output of STB-04 run) |
| Update | `docs/VERDICT_LOG.md` (STB-04) |
| Update | `docs/PROJECT_STATUS.md` (this task) |
| Do NOT touch | `session_smc/*.py`, `strategy/`, `execution/`, `bot.py` |

---

*ST_B_RESEARCH_PLAN.md | v1.0 | 2026-06-24*
