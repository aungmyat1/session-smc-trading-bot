# SYS1-T015 — Initial Assessment (Phase 1: Repository & Governance Review)

Date: 2026-07-07
Status: ASSESSMENT ONLY — no lifecycle mutation, no backtest run, no code change
Owner: Research governance review (this document)
Related: `CLAUDE.md` §6/§7, `docs/VERDICT_LOG.md`, `config/strategy_catalog.yaml`,
`config/strategy_portfolio.yaml`, `svos/lifecycle/manager.py`,
`svos/lifecycle/authority.py`, `svos/registry/service.py`

---

## 1. Current state — ST-A2

### 1.1 What ST-A2 actually is (code-verified, not assumed)

The deployed demo runner's `"ST-A2"` strategy name resolves to
`strategies.adapters.st_a2_adapter.ST2Adapter`
(`strategies/adapters/__init__.py:16`), which reads its configuration from
`strategy/session_liquidity/config.yaml` (`strategies/adapters/st_a2_runtime.py:15`).
This **is** the Sweep Reversal model described in `docs/VERDICT_LOG.md`
(4H+1H bias → Asian range → session sweep → 15M displacement, no CHoCH/BOS/FVG
chain) — confirmed by reading the actual adapter code, not by trusting any
description string.

**Documentation-drift finding, not a functional bug**: `config/strategy_portfolio.yaml`'s
`ST-A2` entry describes it as `"Session sweep + 15M CHoCH + BOS + FVG entry"` —
this description is wrong. That description actually matches the *different*,
separate `session_smc/` full-chain strategy (which VERDICT_LOG's 2026-07-01
entry identifies as `SMCOrderBlockFVGSession`, a distinct catalog entry at
`svos_stage: INTAKE`). The portfolio YAML's string is stale documentation —
the code wired to the `"ST-A2"` strategy name is unambiguously the Sweep
Reversal model. Recommend fixing this description string as a small, separate
documentation cleanup (not part of SYS1-T015's scope).

### 1.2 Lifecycle state — three different answers depending on where you look

This is the most consequential finding of this assessment.

| Source | ST-A2's recorded state | Authoritative? |
|---|---|---|
| `config/strategy_catalog.yaml` `status:` field | `DEFERRED_REVALIDATION` | Narrative/human-readable only — **not a recognized `StrategyStage` enum value** |
| File-based registry (`data/svos/registry/ST-A2/state.json`, written by `svos/registry/service.py`) | `current_stage: "DRAFT"`, `legacy_status: "DEFERRED_REVALIDATION"` | This is what `StrategyLifecycleManager.infer_stage()` actually computes — verified by reading the live file, not by inference |
| Postgres registry (`db.models.StrategyEntity`/`StrategyVersion`/`StageState`, the tables `svos/lifecycle/authority.py`'s `LifecycleAuthority` — described in its own docstring as "the single entry point through which ALL lifecycle transitions must flow" — actually reads/writes) | `StrategyEntity` row exists (`fc464b12-b4e7-4b5f-a0fb-6a3ef4992159`), **zero `StrategyVersion` rows, zero `StageState` rows** | Effectively uninitialized — this authority has no lifecycle history for ST-A2 at all |

**Verified directly** (not assumed): I queried the live local Postgres instance
(read-only `SELECT`) and confirmed `StrategyEntity` exists for `ST-A2` but no
child `StrategyVersion` exists — `LifecycleAuthority.transition()` (which
requires a `version_id` and `expected_revision`) has nothing to operate on
for ST-A2 today. Separately, I read `data/svos/registry/ST-A2/state.json`
directly and confirmed it already shows `current_stage: "DRAFT"` — this is
the *file-based* registry that `svos/registry/service.py::ensure_strategy()`
already bootstrapped on 2026-06-29 (per its own `versions.jsonl` entry).

**This means "DEFERRED_REVALIDATION → INTAKE" is not literally a transition
the lifecycle manager recognizes** — `DEFERRED_REVALIDATION` was never a
`StrategyStage`. The transition that's actually valid and already
pending-ready is **`DRAFT → INTAKE`**, per the file-based registry, which
already has ST-A2 correctly bootstrapped. `DRAFT → INTAKE` is directly
allowed by `svos/lifecycle/manager.py`'s `_ORDER` (§2 of that file).

**Open governance question, not resolved by this document**: this repo has
two parallel, not-obviously-reconciled registry mechanisms — the file-based
one (`svos/registry/service.py`, already has ST-A2 at `DRAFT`) and the
Postgres one (`svos/lifecycle/authority.py`, empty for ST-A2, and whose own
docstring claims it should be the *sole* entry point for all transitions).
This is the known "two parallel SVOS orchestrators" duplication debt
(previously flagged in project memory / prior audits), now confirmed to
extend to the registry/persistence layer, not just the pipeline orchestrator
layer. **Phase 2 cannot proceed correctly without an explicit decision on
which registry is authoritative for this trial** — proceeding against the
file-based one without addressing this risks writing evidence that the
Postgres-backed authority (if it's meant to be primary going forward) would
not recognize, or vice versa. Flagged for your decision before Phase 2 starts.

### 1.3 Previous trial evidence (from `docs/VERDICT_LOG.md`, read directly)

| Trial | Gate in force | Result | Current relevance |
|---|---|---|---|
| ST-A2 (2026-06-21) | Old gate (n≥50, PF>1.0) | **PASS** (n=169, PF_2x=1.025) | Preserved as historical record; catalog explicitly marks it "not current evidence" |
| EXP05 (2026-06-23) | Old gate | FAIL (no variant of ST-A2 optimization clears all 4 targets) | Confirms ST-A2 optimization is a dead end — do not re-attempt parameter tuning on this base |
| ST-A2-REPLAY-2024-REALDATA (2026-06-25) | N/A — pipeline validation only | CONDITIONAL PASS (n=14, PF_2x=0.621) | Too small a sample to be gate evidence either way; validated the real-data pipeline works |
| ST-A2-REPLAY-2025 (2026-06-25) | N/A — supplementary | CONDITIONAL PASS (n=16, PF_2x=0.948, marginal) | Single-year sample, explicitly not authoritative |
| ST-D2-6M / TRIAL_ST_A2_D1_001 (2026-06-25/26) | Old gate | FAIL / INCONCLUSIVE | D2/D1 gate additions over-filter — abandoned direction |
| ST-D2-E3-OPT (2026-06-26) | Old gate (n≥50, PF>1.0) | **FAIL — overfitting confirmed** (n=203, PF_2x=0.563 on holdout) | A *different*, standalone strategy (D2 E3), not an ST-A2 variant — dead end |
| ST-D2-E3-OPT2 | Pre-registered, not run | **PENDING** — holdout never executed | Not ST-A2 either; irrelevant to this task unless revived separately |

**No trial in the log meets the current (2026-07-01) tightened gate**
(n>200 AND net PF>1.25 AND Sharpe>1.2 AND MaxDD<15%, at both standard and 2×
spread stress) for ST-A2 or any variant. This confirms `CLAUDE.md` §6's own
statement precisely — not a new finding, but now grounded against every row
in the log rather than taken on faith.

### 1.4 What specifically is missing (per the catalog's own `requirements:` block)

```yaml
requirements:
  replay: pass
  backtest: pass
  walk_forward: pending
```

Taken literally, only `walk_forward` (robustness/Monte Carlo/walk-forward
validation, `StrategyStage.ROBUSTNESS_VALIDATION`) is marked incomplete. But
the catalog's own `deferred_reason` field overrides this narrower reading:
*"Platform construction in progress. Revalidate later via full pipeline from
Intake."* — and `CLAUDE.md` §6 is explicit: *"ST-A2 cannot satisfy any
qualification gate until it re-enters at Intake and passes the full pipeline
from zero with current evidence."* **The full pipeline must be re-run, not
just the one missing stage** — the `replay: pass`/`backtest: pass` markers
reflect the *old* gate, not the current one, and are not valid shortcuts.

---

## 2. Tooling functional? — verified, not assumed

This is the question most consequential to whether Phases 2–9 are realistic.

### 2.1 Lifecycle mutation authority

`svos/lifecycle/manager.py`'s `StrategyLifecycleManager` is a pure, stateless
state-machine validator (114 lines, no I/O) — confirmed functional by
reading it directly; `infer_stage()` and `validate_transition()` both work
as designed and were exercised (read-only) during this assessment.

`svos/registry/service.py`'s `ensure_strategy()`/`record_version()` (the
file-based registry) already successfully bootstrapped ST-A2 once
(2026-06-29) — proven functional by the existing `data/svos/registry/ST-A2/`
files on disk, not by inspection alone.

`svos/lifecycle/authority.py`'s `LifecycleAuthority` requires a reachable
Postgres instance and existing `StrategyVersion`/`StageState` rows — **the
DB is reachable** (verified via a live read-only query against
`DATABASE_URL` from `.env`) but **ST-A2 has no version/stage rows to
transition from**. This path is not yet usable for ST-A2 without first
creating a `StrategyVersion` — an action this assessment does not take.

### 2.2 Pipeline orchestration entrypoint

`scripts/run_current_strategy_svos.py` is a real, complete, purpose-built CLI
— confirmed by reading its argparse definition, not its docstring alone. It
supports `--strategy ST-A2` (explicit override; does not require ST-A2 to be
the catalog's `current: true` entry, which it currently is not),
`--symbol`/`--start`/`--end` for auto-generating backtest payloads from real
data, and separately-suppliable `--replay-json`/`--backtest-json`/
`--robustness-json`/`--virtual-demo-json` for manual evidence injection. It
calls `research.svos.engine.SVOSRunner` and `research.validation.engine`,
both of which exist and are non-trivial, implemented modules (confirmed by
reading their class/function definitions, not just their file sizes).

**This script is realistically invokable for Phases 5–6.** It is one of
five overlapping `scripts/run_*svos*.py`/`scripts/*svos*.py` entrypoints in
this repo (`run_svos_sample.py`, `svos_run.py` are explicitly labeled
"compatibility wrapper"s; `bootstrap_svos.py` is registry-init-only;
`run_svos_pipeline.py` is a fifth, not yet compared) — consistent with known
duplication debt, but `run_current_strategy_svos.py` is the one whose
docstring and argparse surface match this task's actual need (full pipeline,
single named strategy, evidence recording back to the catalog).

### 2.3 Gate configuration — confirmed stale, a real blocker if not addressed

**`config/validation.yaml` (the config `research/validation/engine.py`
loads by default) still encodes the OLD gate**, not the current one:

```yaml
minimum_trade_count: 50      # current gate requires > 200
minimum_profit_factor: 1.0   # current gate requires > 1.25
maximum_drawdown: 10.0       # current gate requires < 15 (this one is
                              # actually *stricter* than current — inverse
                              # mismatch direction from the other two)
```

`research/validation/engine.py`'s in-code defaults independently confirm
the same stale numbers (`minimum_profit_factor: float = 1.0`,
`maximum_drawdown: float = 10.0`, and a hardcoded `sharpe_ratio >= 1.0`
check at line 394 — current gate requires `> 1.2`). **No `n > 200` trade-count
check distinct from `minimum_trade_count` was found in this engine at all**
— trade-count gating appears to only exist via the single, currently-stale
`minimum_trade_count` value.

**Consequence**: if Phase 3–4 (validation gates) and Phase 5 (pipeline
execution) proceed using this tooling's own automated PASS/FAIL output
without overriding these numbers, **the tool will apply the wrong (looser)
gate and could report a false PASS** against the old thresholds while
actually failing the real, current one. Every prior VERDICT_LOG entry was
graded by manual comparison against the gate in force on its date, not by
trusting an automated verdict — this trial must follow the same discipline:
**compute the metrics, then manually compare each one against the exact
current-gate numbers in `CLAUDE.md`/`VERDICT_LOG.md`'s header, regardless of
what `research/validation/engine.py`'s own pass/fail flag says**, unless
`config/validation.yaml` is first updated to the current gate (a small,
legitimate fix, but a scope decision — updating shared validation config
affects every strategy, not just this trial).

### 2.4 Backtest script

`scripts/backtest_session_liquidity.py` exists (32,941 bytes, last modified
2026-06-27) — the catalog's own `backtest_script` field points to it, and it
predates this assessment, so it has presumably been exercised by the
original ST-A2 trials already in VERDICT_LOG. Not executed as part of this
Phase 1 assessment (per the "no backtest run" constraint) — its actual
behavior against 5+ years of current data has not been re-verified here.

---

## 3. Known gaps (summary)

1. **No current-gate-compliant evidence exists for ST-A2** — confirmed
   against every row in `VERDICT_LOG.md`, not assumed.
2. **Lifecycle-authority ambiguity** — two registries (file-based vs.
   Postgres-backed) disagree on what's authoritative for ST-A2; the
   Postgres one (which claims sole authority) has zero data for this
   strategy. Needs an explicit decision before Phase 2.
3. **Gate configuration is stale** in the shared validation tooling
   (`config/validation.yaml`, `research/validation/engine.py` defaults) —
   must be manually cross-checked against the real current gate regardless
   of the tool's own verdict, or the config fixed first (a scope decision).
4. **Documentation drift** — `strategy_portfolio.yaml`'s ST-A2 description
   string doesn't match the actual code (minor, not a functional blocker).
5. **`walk_forward: pending`** in the catalog is the only explicitly-flagged
   missing requirement, but per `CLAUDE.md` §6 the *entire* pipeline must
   re-run from Intake — the narrower reading is not sufficient.

None of these are blockers to *starting* Phase 2 — they are blockers to
doing so *correctly* and *reproducibly* without producing evidence that
later turns out to be graded against the wrong gate or written to the wrong
registry.

---

## 4. Validation requirements (current gate, restated precisely)

Per `CLAUDE.md` §0.3/§7 and `VERDICT_LOG.md`'s header, effective 2026-07-01:

- **n > 200** net trades
- **net PF > 1.25** at standard spread
- **net PF > 1.25** at 2× spread stress (both required, not either/or)
- **Sharpe > 1.2**
- **MaxDD < 15%**
- Fee model: per `VERDICT_LOG.md`, VT Markets Standard — spread + 0.6pip
  commission RT (note: this differs from `CLAUDE.md` §0.3's Vantage Standard
  figures (~0.8–1.2 pip EURUSD, ~1.2–1.8 pip GBPUSD) — **which fee model
  applies to a fresh ST-A2 revalidation is itself an open question**, since
  `VERDICT_LOG.md`'s historical rows used VT Markets pricing but the platform
  now executes against Vantage. Flagged, not resolved, here.

---

## 5. Execution plan for remaining phases (proposed, not started)

1. **Resolve the registry-authority question (§1.2)** before any lifecycle
   mutation — owner decision required: use the file-based registry (already
   has ST-A2 at DRAFT, immediately actionable) or first bootstrap ST-A2 into
   the Postgres-backed authority (more work, but matches that module's own
   claim to be the sole authority).
2. **Resolve the fee-model question (§4)** — confirm VT Markets vs. Vantage
   pricing for this revalidation, since it materially affects PF at both
   spread levels.
3. **`DRAFT → INTAKE`** transition via whichever registry is chosen in (1),
   recorded with actor/timestamp/reason — Phase 2 of the original mission.
4. **Pre-registered trial document** (`docs/experiments/ST-A2-REVALIDATION-001.md`)
   — Phase 3, per the mission's own template. Must lock the fee model and
   exact gate numbers *before* any results exist, consistent with `CLAUDE.md`
   §7's "pre-register before running the backtest" rule.
5. **Run Phase 0–3 of the SVOS pipeline** via `scripts/run_current_strategy_svos.py
   --strategy ST-A2 --symbol EURUSD --symbol GBPUSD --symbol XAUUSD ...`
   (XAUUSD's inclusion needs a decision — the catalog's ST-A2 entry only
   lists EURUSD/GBPUSD; the portfolio config adds XAUUSD but with a
   description that doesn't match the actual strategy code, per §1.1 — using
   XAUUSD for revalidation would be introducing a new symbol beyond what was
   ever historically tested, not a neutral choice).
6. **Manually cross-check every metric** against §4's exact current-gate
   numbers, independent of `research/validation/engine.py`'s own PASS/FAIL
   output (per §2.3).
7. **Record the verdict** in `VERDICT_LOG.md` under a new `ST-A2-REVALIDATION-001`
   entry, PASS or FAIL, no pending state left open.
8. **Update lifecycle** to `VALIDATED` (if PASS) or `REFINEMENT_REQUIRED`... 
   — **note**: neither of these exact strings exists in `StrategyStage`'s
   enum either (§1.2's problem recurs here). The nearest real stages are
   `STATISTICAL_VALIDATION` (passed through, not a resting state) and
   `REFINEMENT` (the actual FAIL-loop-back stage per `_ALLOWED`). This
   mapping needs to be resolved at the same time as item (1), not
   improvised at Phase 8.
9. **System 2 integration check** — confirm zero diff on `execution/`,
   `core/broker_interface.py`, `dashboard/`, `risk/` after the above,
   consistent with this whole task being System 1 (research) scoped.

---

## 6. Recommendation before proceeding to Phase 2

**Two decisions need your input before Phase 2 can start correctly**:

1. Which registry is authoritative for this trial — file-based
   (`svos/registry/service.py`, immediately usable) or Postgres-backed
   (`svos/lifecycle/authority.py`, requires bootstrapping ST-A2 into it
   first)? This determines the actual mechanics of every subsequent phase.
2. Fee model for the revalidation — VT Markets (matches all historical
   VERDICT_LOG rows for comparability) or Vantage (matches the platform
   that will actually execute this strategy)?

Everything else in this assessment (tooling functionality, gate numbers,
missing evidence) is settled and does not require further discussion before
proceeding once these two decisions are made.
