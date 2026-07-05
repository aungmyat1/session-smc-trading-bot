# Objective Gap Analysis

Date: 2026-07-04
Status: Read-only audit finding
Companion: `CURRENT_PROJECT_STATUS.md`, `IMPLEMENTATION_MATRIX.md`

---

## Part 2 — Project Objective (as stated in governing docs)

Source: `CLAUDE.md` §1–§2, `docs/svos/STRATEGY_ENGINEERING_PLATFORM_IMPLEMENTATION_PLAN.md`,
`docs/svos/CORE_ARCHITECTURE.md`, `docs/svos/DEPLOYMENT_TOPOLOGY.md`.

This is a two-system quantitative trading platform, not a single trading bot:

```
SVOS (System 1, research, gcp-vm1)  →  Validated Strategy Artifact  →  Production Execution
(System 2, auto-trade-vps, Vantage Forex Bot)  →  Broker Execution (MetaAPI/Vantage)
```

**Governing principle: research never trades.** SVOS discovers, audits, enhances, replays,
backtests, validates, and (eventually) approves strategies. Production loads and executes only an
approved strategy package — it never audits, backtests, optimizes, or approves anything itself.

**Canonical 7-phase pipeline** (`CLAUDE.md` §2): Strategy Audit → Strategy Enhancement →
Historical Replay → Backtesting → Robustness Tests → Offline Virtual Demo → Production Approval
(record-only, out of build scope). **Implementation ceiling is Phase 5** — build through the
Vantage bot running under a Phase-5 virtual demo; Phase 6 (live capital) is explicitly out of
scope until unlocked by the owner.

**Input:** any systematic Forex strategy with an objective specification.
**Output:** a versioned, evidence-backed Production Approval package, or an honest FAIL with
findings and a remediation route.

**Non-negotiable invariants:** never enable live trading until a strategy holds valid Production
Approval AND the execution bot passes its own execution gate (`LIVE_TRADING=false`,
`DEMO_ONLY=true` until the owner manually flips them); never tune parameters mid-trial (every
change = new registered trial); net-of-fees-only results; no secrets in code; one position per
symbol; phase gates are mandatory (no skipping, no retroactive evidence — the 2026-07-01 gate
tightening explicitly does not grandfather prior evidence).

---

## Part 4 — Gap Analysis: Objective vs. Current Implementation

### Already implemented (matches objective, working as intended)

- **Strategy lifecycle/registry with immutable, append-only evidence** — `svos/lifecycle/manager.py`,
  `svos/registry/service.py`. Correctly makes `PRODUCTION_APPROVAL` unreachable by forward
  promotion alone; legacy direct-mutation paths hard-raise.
- **Phase-3 backtest gate matching the current tightened threshold exactly** —
  `svos/application/backtest.py::_evaluate_gate` (n>200, PF>1.25 std+2×, Sharpe>1.2, MaxDD<15%).
- **Trial registration discipline** — `docs/VERDICT_LOG.md` records every trial; no evidence of a
  mid-trial parameter change being silently reused under the same trial ID.
- **Net-of-fees enforcement** — the backtest gate module applies spread + commission; no
  fee-free result found presented as evidence.
- **Live-trading hard block at the entrypoint** — `--mode live` is rejected before any
  package/runtime work in the canonical runner; `LIVE_TRADING=false`/`DEMO_ONLY=true` are
  unconditionally enforced at the CLI layer.
- **Strategy packaging, signing, import, and disabled-runtime staging** — a full repo-side
  implementation landed 2026-07-02 (`svos/deployment/service.py`, `production/importer.py`,
  `production/verifier.py`, `production/activation.py`), closing what was a total gap as of the
  2026-07-01 baseline audit.
- **Broker integration in demo mode** — real MetaAPI/Vantage connectivity, confirmed live
  balance/candle data, not stubbed.
- **Secrets discipline** — `.env` gitignored and CI-enforced; no tracked secrets found; no literal
  keys in `config/llm.yaml` or other config files.
- **CI quality/security/docs gates** — real, not decorative (ruff/mypy/bandit/pip_audit/link-checker
  actually run and actually gate merges on the paths they cover).

### Partially implemented (real but incomplete or disconnected)

- **"Research never trades" / phase-gate discipline vs. actual deployment**: the objective's
  "research never trades" principle holds at the code-boundary level, but `config/strategy_portfolio.yaml`
  declares 5 strategies running demo/shadow execution while formal SVOS lifecycle registration
  lags behind — a tracked governance gap (`CLAUDE.md` §1, `docs/VERDICT_LOG.md` 2026-07-01 entry),
  not a contradiction silently resolved.
- **Offline Virtual Demo (Phase 5)**: `svos/application/pipeline.py` includes a VIRTUAL_DEMO
  phase, but `tests/svos/test_pipeline.py` currently fails 7 tests around missing VIRTUAL_DEMO
  evidence recording — the phase exists in the state machine but its evidence-capture is not
  fully correct yet.
- **Strategy Enhancement (Phase 1)**: a new LLM-based drafting adapter
  (`svos/application/refinement.py`, `svos/adapters/llm/`) implements the intended
  human-in-the-loop AI-suggestion mechanic, but is not wired into `svos/application/pipeline.py`'s
  phase sequence and has zero test coverage — a real first step, not yet a working capability.
- **Production Approval evidence discipline**: the gate mechanism is real and current, but zero
  strategies currently pass it (`docs/VERDICT_LOG.md`: ST-A, ST-A2, EXP05, T27-T29 all FAIL/DEFERRED)
  — the pipeline correctly refuses to certify anything today, which is the intended honest-FAIL
  behavior, not a bug.
- **One-position-per-symbol invariant (§0.7)**: enforced at signal-routing time, but the release
  side (`record_close()`) is never called, so the invariant silently degrades to "one trade per
  symbol per day" rather than true per-position enforcement.

### Not implemented

- **Runtime risk-feedback loop**: the objective implicitly requires loss limits to actually halt
  the bot; `record_result()`/`record_close()` are never called from live code, so daily/weekly/
  monthly loss halts and consecutive-loss halts cannot trigger from real P&L. This is a gap
  against the spirit of §0's safety-first framing, not just a missing feature.
- **Single canonical execution path**: the objective implies one execution path per system;
  instead there are 3 competing entrypoints (bot.py, run_st_a2_demo.py, run_portfolio.py) and 2
  competing order/position stacks (execution/trade_manager.py vs. production/engine/orders.py+positions.py).
- **Node-separated deployment** (SVOS on gcp-vm1, execution on auto-trade-vps, per
  `docs/svos/DEPLOYMENT_TOPOLOGY.md`): the authoritative Postgres and most research/execution code
  still runs co-located on VPS 1; VPS 2 exists and is reachable but is not the cutover target yet.
- **Single canonical SVOS orchestrator**: the objective's 7-phase pipeline is meant to run through
  one engine; `svos/application/pipeline.py` (new) and `research/svos/engine.py` +
  `research/validation/engine.py` (legacy) both exist and both are actively edited.

### Deprecated / no longer needed but still present

- `bot.py` — explicitly self-declared `LEGACY_RUNTIME_ENTRYPOINT = True`, kept by owner decision
  (documented in `docs/AUDIT_IMPLEMENTATION_PLAN_2026-07-01.md`), not to be deleted.
- `PROJECT_READINESS_SCORECARD.md` (root) — superseded by `UPDATED_PROJECT_READINESS_SCORECARD.md`
  but not archived or marked as such; actively risks misleading a reader (see `TECHNICAL_DEBT.md`).
- `research/svos/engine.py` + `research/validation/engine.py` — superseded in intent by
  `svos/application/pipeline.py` per the 2026-07-01 finding, but the legacy engine was edited again
  on 2026-07-02, i.e. still receiving investment despite being flagged for retirement.
- `New Dashborad/Two system on one Dashboard/` — a 156 MB nested duplicate of the dashboard
  directory itself; no code references it.

### Needs refactoring

- `production/engine/orders.py` / `positions.py` — built but unused; either wire them in as the
  real execution path (retiring `execution/trade_manager.py`'s duplicate logic) or delete them —
  currently pure unused scaffolding that increases audit surface without adding capability.
- `scripts/run_portfolio.py` vs `scripts/run_st_a2_demo.py` — the "canonical" runner needs the
  governance/recovery wiring the "legacy" one already has; today refactoring should flow legacy→canonical,
  not the reverse.
- Root-level report sprawl (20 files, 3 unlinked "audit generations") — needs consolidation into
  `docs/00_Project/DOC_AUTHORITY.md`'s governance scheme or archival.

### Needs redesign

- **Risk-management feedback wiring**: this isn't a one-line fix — `record_result()`/`record_close()`
  need a real "trade closed" event source feeding back into both `execution/demo_risk_manager.py`
  and `core/portfolio_manager.py` consistently, which doesn't exist today (open close events are
  not currently observed by either component). This is architecturally the same class of problem
  as the two competing execution stacks — a data-flow gap, not a missing function.
- **Dashboard consolidation**: 3 backend processes + 1 frontend migration is a genuine design
  problem, not incremental debt — a prior independent assessment concluded the existing backends
  should be discarded in favor of extracting only their UI patterns into a single new service.

### No longer required

- Nothing found in this pass that was implemented against the objective but is now
  unambiguously unneeded — the platform's scope (7-phase SVOS + thin execution layer) has not
  shrunk since inception; all identified deprecated items above are duplicates/legacy, not
  scope-reductions.
