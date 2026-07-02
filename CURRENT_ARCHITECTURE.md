# Current Architecture — Read-Only Audit Snapshot

Date: 2026-07-01
Status: Read-only audit finding — describes observed state, not target architecture
Scope: Repository architecture audit performed for the Project Objective Gap Analysis.
Companion document: `docs/project_readiness_assessment.md` (gap matrix + roadmap).
This document does not change, move, or rename anything.

> Historical baseline: the artifact/deployment gaps recorded below were accurate
> when this audit was captured. The July 2 repository implementation added
> deterministic strategy packages, Production import and verification, preflight,
> and disabled staging. See
> `docs/architecture/production_svos_rollout_index.md` for current status.

---

## 1. Current Architecture Diagram

```
                         ┌───────────────────────────────────────────┐
                         │   VPS 1 — auto-trade-vps (this host)       │
                         │   Role: Production / execution + Postgres  │
                         │                                             │
                         │  ┌───────────────────────────────────────┐  │
                         │  │ bot.py (legacy, dormant but importable)│  │
                         │  │ execution/ (order/risk/trade mgmt)     │  │
                         │  │ scripts/run_st_a2_demo.py (CURRENT)    │  │
                         │  │ scripts/run_d2_e3_demo.py (separate)   │  │
                         │  │ strategies/ (execution adapters)       │  │
                         │  │ monitoring/ (Telegram, logs)            │  │
                         │  │ dashboard/ (app.py + live_app.py +      │  │
                         │  │             status_server.py — 3 procs) │  │
                         │  └───────────────┬───────────────────────┘  │
                         │                  │ in-process import         │
                         │                  ▼                           │
                         │  ┌───────────────────────────────────────┐  │
                         │  │ svos/ (lifecycle, registry, governance,│  │
                         │  │ orchestration, reports, api, monitoring,│  │
                         │  │ deployment, experiments)                │  │
                         │  └───────────────┬───────────────────────┘  │
                         │                  │                           │
                         │  ┌───────────────▼───────────────────────┐  │
                         │  │ Postgres `vmassit` (loopback 127.0.0.1) │  │
                         │  │ 12 schemas: market/research/governance/ │  │
                         │  │ strategy/analytics/execution/experiments│  │
                         │  │ /robustness/evidence/operations/config  │  │
                         │  │ — PRODUCTION + RESEARCH MIXED, one host │  │
                         │  └─────────────────────────────────────────┘  │
                         └───────────────────────────────────────────┘
                                          │ (Tailscale — data transfer
                                          │  documented, not executed)
                                          ▼
                         ┌───────────────────────────────────────────┐
                         │   VPS 2 — gcp-vm1                          │
                         │   Role: SVOS research plane (target)       │
                         │   Actual: Docker + Postgres container       │
                         │   (`trading_research`, empty schemas,        │
                         │   exposed on 0.0.0.0:5432 — unfixed),        │
                         │   955 MiB RAM / no swap (below the 8 GB      │
                         │   gate for real research workloads),         │
                         │   no systemd units for any SVOS pipeline —   │
                         │   research runs ad hoc via scripts only      │
                         └───────────────────────────────────────────┘

Research code (scripts/replay_*.py ×7, scripts/backtest_*.py ×5,
research/, research_db/, research_engine/, research_sweep/,
strategy_validation/, strategy_audit/, execution_validation/,
execution_simulator/, virtual_broker/, pipeline/, adaptive/,
session_smc/, svos/application/{audit,replay,backtest,robustness,
virtual_demo}.py) → all currently run/develop ON VPS 1 alongside
production, not on VPS 2, because VPS 2 lacks capacity and has no
scheduled pipeline presence yet.
```

**Governing principle (target, not yet fully real):** research never trades; production
loads only approved artifacts. Today: research code never places live orders (verified —
see §3), but node/DB separation and artifact-based deployment are not yet built.

---

## 2. Component Description

### 2.1 Production / execution side (intended: `auto-trade-vps` only)

| Component | Purpose | Status |
|---|---|---|
| `bot.py` | Legacy standalone live-trading loop (own MetaAPI client, order manager, risk manager, Telegram). Not deleted, not systemd-deployed, but fully importable and runnable with `LIVE_TRADING=true` — nothing prevents ad-hoc execution. | Dormant but live-capable |
| `execution/` | Order management, risk (`risk_manager.py` legacy / `demo_risk_manager.py` current), trade management, MT5/MetaAPI connectors, governance guard | Real, but split across 3 parallel stacks (see §3) |
| `scripts/run_st_a2_demo.py` | Current production entrypoint, deployed as `smc-demo-runner.service`. Actually runs `SMCOrderBlockFVGSession` (one `--strategy` flag = one process = one strategy) | Running, demo-only |
| `scripts/run_d2_e3_demo.py` | Separate D2E3 strategy runner (`d2e3.service`), own risk/position-guard logic, does not share `core/portfolio_manager.py` | Running (per systemd files), fully independent stack |
| `strategies/` | Adapter layer: internal strategy signal → canonical `core.Signal` (ST-A2, LondonBreakout, NYMomentum, AdaptiveSMC, SMC OB+FVG, VWAP, ShadowTracker) | Real |
| `monitoring/` | `telegram.py` (13 push alert types, actively wired), log tailing | Real, automated/push-based |
| `dashboard/app.py` | Merged Flask app: SVOS/EVF, legacy ops, React SVOS workstation, AND live-dashboard routes — one process, multiple concerns | Real, unconsolidated |
| `dashboard/live_app.py` | Standalone Flask app, live-dashboard only, own systemd unit (`live-dashboard.service`) | Real, deployed |
| `dashboard/status_server.py` | Third surface: FastAPI live status + emergency-stop API | Real, deployed |
| `config/strategy_portfolio.yaml` | Declares 5 strategies (ST-A2, LondonBreakout, NYMomentum demo; AdaptiveSMC, VWAPMeanReversion shadow) with risk tiers/limits | **Not loaded by the live runner** — cosmetic today (see §3) |

### 2.2 SVOS / research side (intended: `gcp-vm1` only; actually runs on VPS 1)

| Component | Purpose | Status |
|---|---|---|
| `svos/lifecycle/manager.py` | Canonical stage enum + transition-adjacency validator (11 stages: DRAFT→...→RETIRED) | Complete, but scope-limited — pure topology validator, does not itself enforce evidence gates |
| `svos/registry/service.py` | `StrategyRegistryService` — versions, evidence, transitions; hard-gates `transition()` on a matching `GateDecision` | Complete |
| `svos/governance/service.py` | `GovernanceService` — evaluates/blocks transitions on evidence/approval gaps | Complete |
| `svos/orchestration/service.py` | `SVOSPlatform` — dual-backed JSONL + optional Postgres control plane | Complete |
| `svos/api/service.py` | Read-oriented operational facade | Complete, thin |
| `svos/experiments/`, `svos/deployment/`, `svos/monitoring/` | Experiment tracking, deployment status, log/health snapshot | Complete, undocumented in CORE_ARCHITECTURE.md's folder list |
| `svos/dashboard/`, `svos/notifications/`, `svos/ui/` | Placeholder packages | **Missing** — `__init__.py` docstring only, no implementation |
| `svos/application/{audit,replay,backtest,robustness,virtual_demo}.py` | Gate-evaluation wrappers per pipeline phase — validate externally-supplied evidence against thresholds; do not compute the evidence themselves | Complete as gates, but depend on unconsolidated upstream engines |
| `strategy_validation/` | Phase-0 audit: 8 real validators (input, completeness, ambiguity, consistency, measurability, institutional, risk, testability) | Complete |
| `strategy_audit/` | A **second**, legacy 10-validator audit framework (1335 lines, 16 files) not called by `svos/application/audit.py` | Duplicate engine, not a gap in coverage but a maintenance/confusion risk |
| `research/robustness.py` | Walk-forward, Monte Carlo, parameter sensitivity, regime analysis — all 4 real | Complete |
| Replay engines | 7 independent `scripts/replay_*.py` (3295 lines) each reimplementing simulate/metrics/load logic, plus a real cohesive `execution_simulator/replay_engine/runner.py` (canonical Phase-5 engine) that most scripts don't use | Fragmented |
| Backtest engines | `scripts/backtest.py` + 4 more per-strategy scripts, each with an independent PF/metrics function; ~45 files reference `profit_factor`/`net_pf` repo-wide | Fragmented, no shared metrics library |
| Strategy Enhancement (Phase 1) | `strategy_validation/ai/editor_engine.py` (`StrategyEditorEngine.build_plan()`) exists and is generic, but is not imported anywhere under `svos/` — no `enhancement.py` in `svos/application/` | Partial — engine exists, not wired in; manual step today |
| `svos/reports/` | Real SHA-256 content-addressed artifact store (`svos/adapters/artifacts.py`) + per-stage JSON/MD report builders + `reports/index.json` | Complete, but scoped to individual report files, not a strategy deployment bundle |
| `config/strategy_catalog.yaml` | Documented as a "read-only generated projection"; in reality hand-edited directly in git history (e.g. commit `600fbe1` set `approved: true` by hand) | Aspirational on the generation side; enforced only on the write-blocking side (`DirectCatalogMutationError`) |
| `dashboard/strategy_service.py` | UI promote/demote actions call `SVOSPlatform.audited_transition()` inside a bare `try/except: pass`, then unconditionally write a separate overlay file (`reports/dashboard_strategies.json`) regardless of whether governance approved, denied, or errored | **Real governance bypass** — UI-displayed stage can diverge from the authoritative registry |

### 2.3 Shared / infra

| Component | Purpose | Status |
|---|---|---|
| `core/` | Shared `Signal`/`BaseStrategy` contract, used by both sides by design | Correctly shared, not a violation |
| `db/` | Single Postgres control plane (`vmassit`, 12 schemas), Alembic migrations | Real, but not separated by concern (see §4) |
| `deploy/gcp-vm1/` | Docker Compose + 7 systemd unit files for **this host's own services** (misleading directory name — collides with VPS 2's actual hostname) | Real; 2 units confirmed installed (`smc-demo-runner`, `live-dashboard`), `d2e3.service` running per systemd file, 3 more (`d2e3-journal-sync.*`, `reconcile-positions.*`) ambiguous (file exists, install status unconfirmed from this audit) |
| `tests/` | 117 test files across 17 subdirectories | Unit/simulation tiers complete; `tests/{integration,regression,replay,strategy,unit}` are empty scaffolds |
| `New Dashborad/` | React/Vite SVOS workstation frontend | Real, actively served, not dead code (typo'd directory name is pre-existing) |

---

## 3. Problems Identified

### 3.1 Execution is fragmented into 3 non-unified stacks
`bot.py`, `scripts/run_st_a2_demo.py`, and `scripts/run_d2_e3_demo.py` each implement independent risk managers, position guards, and magic-number schemes. None shares `core/portfolio_manager.py`'s cross-strategy state. If more than one were ever run simultaneously against the same broker account, none would see the others' open positions (each filters by its own magic number) — "one position per symbol" is enforced per-process, not platform-wide.

### 3.2 The daily/weekly/monthly loss-limit halt is structurally dead code (most severe finding)
`PortfolioManager.record_close()` and `demo_risk_manager.record_result()` — the only functions that feed a closed trade's real P&L back into the risk-state counters — are imported but **never called** anywhere in `scripts/run_st_a2_demo.py`'s live tick loop. The daily/weekly/monthly loss-limit check runs every tick, but against a counter that never moves from actual trading outcomes. It is currently harmless only because `DEMO_ONLY=true`/`LIVE_TRADING=false` are enforced — but it means the platform's own documented "a losing streak halts trading" safety model does not actually work today, and would silently fail to protect capital the moment live trading is ever enabled. The same missing close-event feedback also means `open_positions`/`_open_symbols` counters only grow, never decrement — "one position per symbol" and "max open positions" degrade from real-time enforcement into one-shot locks that hold for a runner's entire process lifetime.

### 3.3 The declared strategy portfolio config is not actually loaded at runtime
`config/strategy_portfolio.yaml` declares 5 strategies and specific risk limits. `scripts/run_st_a2_demo.py` instantiates `PortfolioManager()` and `CircuitBreaker()` with no config argument, so real enforcement runs on hardcoded Python defaults spread across three uncoordinated sources (`core/portfolio_manager.py`, `core/circuit_breaker.py`, `execution/demo_risk_manager.py`) that only coincidentally resemble the YAML — e.g. `max_trades_per_day` defaults disagree between modules (8 vs. 4), and the documented per-strategy risk tiers (0.30/0.20/0.10%) are never actually applied; the live path uses a flat, separately-hardcoded 0.25% in `demo_risk_manager.py` and yet another hardcoded 1% in the strategy adapter itself. Editing the YAML today has **zero effect** on the running process.

### 3.4 Only 1 strategy is actually deployed; the real multi-strategy runner exists but isn't installed
`config/strategy_portfolio.yaml` lists ST-A2, LondonBreakout, NYMomentum (demo) and AdaptiveSMC, VWAPMeanReversion (shadow) as `enabled: true`. The only deployed systemd unit (`smc-demo-runner.service`) runs a single `--strategy` at a time — currently `SMCOrderBlockFVGSession`, which isn't even in the YAML's 5. A separate script, `scripts/run_portfolio.py`, genuinely does load `config/strategy_portfolio.yaml` and is architecturally the true multi-strategy runner — but it has **no systemd unit** and is not running anywhere. Even if it were deployed, `PortfolioManager`'s shared daily/weekly/monthly loss counters are global by design (not per-strategy), so one strategy's drawdown would halt every other strategy's signal processing — true cross-strategy risk isolation does not exist even in the not-yet-deployed multi-strategy path. The YAML's "5 strategies live" picture does not match the actual running topology — a documentation/reality gap distinct from, and in addition to, the SVOS lifecycle-registry gap already flagged in `CLAUDE.md` §1/§6.

### 3.4 A real governance bypass exists in the dashboard (distinct from, and newer than, a previously-fixed one)
A 2026-06-29 architecture review flagged legacy catalog-mutation functions (`core/strategy_registry.py`) as a governance bypass; that specific issue is now fixed — those functions hard-raise `DirectCatalogMutationError` and an AST-based architecture test (`tests/architecture/test_lifecycle_authority.py`) enforces no live callers remain. However, a **separate, current** bypass exists: `dashboard/strategy_service.py`'s `promote_strategy()`/`demote_strategy()` swallow any governance exception (bare `except Exception: pass`) and then unconditionally write the UI-facing overlay file (`reports/dashboard_strategies.json`) regardless of whether the authoritative `SVOSPlatform.audited_transition()` succeeded, was denied, or errored. `tests/architecture/test_lifecycle_authority.py` does not cover this path — it only guards against the already-disabled legacy functions, not this overlay write.

### 3.5 Database is not separated by concern or node
A single Postgres instance (`vmassit`, on VPS 1, loopback) holds all 12 schemas spanning production-adjacent (execution, operations), research (market, analytics, experiments, robustness), and governance (governance, strategy, evidence) concerns. The target topology (`docs/svos/DEPLOYMENT_TOPOLOGY.md`) requires this to live on VPS 2 with least-privilege roles. Additionally, VPS 2's own Postgres container publishes port 5432 on all interfaces (`deploy/gcp-vm1/docker-compose.yml:10-11`), an unfixed exposure the topology doc itself already flags.

### 3.6 No strategy artifact/packaging system exists
There is no code that assembles a versioned `strategy.yaml + parameters.json + risk_config.json + validation_report.json + performance.json + checksum` bundle. The real, working SHA-256 content-addressed store (`svos/adapters/artifacts.py`) is wired only to individual per-stage report files, never to a deployable strategy bundle. `bot.py` (the real execution entrypoint) has zero artifact/checksum/governance awareness at all.

### 3.7 Replay and backtest logic is fragmented across one-off scripts
7 replay scripts and 5+ backtest/gate implementations (`src/backtest/simulator.py`, `pipeline/pipeline_03_replay_engine.py::evaluate_gate`, `research/validation/engine.py::validate_backtest`, plus the ad-hoc scripts) each reimplement their own trade simulation and metrics functions, despite a real, cohesive `execution_simulator/replay_engine/runner.py` existing as a canonical alternative. `svos/application/{replay,backtest}.py` are gate-wrappers that expect pre-computed metrics — nothing upstream consolidates to feed them consistently, and no code enforces that a replay/backtest result actually came from an approved engine.

### 3.7a Two full SVOS pipeline orchestrators coexist, unreconciled
The new `svos/application/pipeline.py` (calling `svos/application/{audit,replay,backtest,robustness,virtual_demo}.py`) and the legacy `research/svos/engine.py` (1,917 lines) + `research/validation/engine.py` (646 lines) both independently implement the same intake→audit→replay→backtest→robustness→virtual_demo flow. Neither has been retired; `svos/application/pipeline.py` never imports the legacy engine, confirming true duplication rather than a wrapper relationship.

### 3.7b Robustness testing has a live signature-mismatch bug
`research/robustness.py` correctly implements all four robustness functions (walk-forward, Monte Carlo, parameter sensitivity, regime analysis). But `svos/application/robustness.py` calls `parameter_sensitivity()` with a list where the function expects a dict, and calls `regime_analysis()` with a `regime_labels` argument the function doesn't accept — both raise (`AttributeError`/`TypeError`) on every real invocation. The errors are silently caught by a broad `except Exception` and downgraded to a WARN-only `{"status": "ERROR"}`, so **only walk-forward and Monte Carlo actually function** as a robustness gate today; parameter stability and regime analysis are effectively dead code despite being individually implemented correctly.

### 3.7c Phase 1 (Strategy Enhancement) has no integration service
Every other pipeline phase (Audit, Replay, Backtest, Robustness, Virtual Demo) has a dedicated `svos/application/*.py` wrapper. Phase 1 does not — `strategy_validation/ai/{question_engine,editor_engine}.py` are real, working implementations, but they're only wired into the legacy `research/svos/engine.py` orchestrator, not into the new `svos/application/pipeline.py`. Strategy enhancement is a manual step today in the new pipeline.

### 3.7d Strategy catalog and the new registry are two unreconciled systems of record
`config/strategy_catalog.yaml` (hand-edited) and `data/svos/registry/<strategy>/state.json` (the new append-only JSONL registry) both track strategy stage/status, with no sync/reconciliation job between them — drift risk is real, not theoretical.

### 3.8 No full-suite green test baseline
A pre-existing pandas-related segfault (`pd.Timedelta` at import time in `scripts/validate_dataset.py`) crashes full-suite `pytest` at collection. A 171-test safety-relevant subset passes at 72% coverage, but the whole-repo suite has never produced a green run. `tests/{integration,regression,replay,strategy,unit}` exist as empty directory scaffolds with no actual tests.

### 3.9 Code duplication / stale directories flagged, not yet resolved
`strategy/` vs `strategies/` (deprecated originals vs. adapters), `research_engine/`/`research_sweep/` (cold since 2026-06-26, undocumented as active or archived), `strategy_audit/` vs `strategy_validation/` (two audit engines, unclear hand-off), `adaptive/` vs `session_smc/` (unverified whether `adaptive/` reuses or reimplements SMC detection logic).

### 3.10 One cross-package coupling blocks independent deployment
`adaptive/run_shadow.py` (a research/shadow script) imports `execution.mt5_executor` and the MetaAPI SDK directly for a live market-data feed. It places no orders, but it means research code has a hard runtime dependency on the production package and the broker SDK — the one finding that would block packaging research and production as independently-deployable units.

---

*This document is a snapshot as of 2026-07-01. It should be regenerated, not hand-edited, the next
time a comparable audit is performed — treat it as a point-in-time finding, not a living spec.*
