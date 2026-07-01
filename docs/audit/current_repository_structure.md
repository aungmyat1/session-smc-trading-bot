# Current Repository Structure Audit

Date: 2026-07-01
Status: Read-only audit finding — not authoritative architecture, describes observed state
Scope: Phase 1 of the deployment-topology validation audit (see `deployment_topology_validation.md`, `architecture_gap_report.md`)

This document catalogues the repository as it actually exists on disk, on the host currently
checked out (`auto-trade-vps.asia-southeast1-b.c.auto-489108.internal`). It does not change,
move, or rename anything.

## Production (live-demo execution) components

| Path | Purpose |
|---|---|
| `bot.py` | Legacy live trading loop (MetaAPI client, ST-A2 chain, order manager, Telegram alerts). Superseded by `scripts/run_st_a2_demo.py` / `scripts/run_strategy_demo.py` per `docs/AUDIT_IMPLEMENTATION_PLAN_2026-07-01.md`; treated as legacy/retired. |
| `execution/` | Live order management, position tracking, `trade_manager.py`, `vantage_demo_executor.py`, `risk_manager.py` (legacy path), `demo_risk_manager.py` (current path), `governance_guard.py`. |
| `execution_events.py`, `execution_gate.py` | Event dataclasses and a gate validator shared between live and simulated paths. |
| `strategies/` | Adapter layer translating internal strategy signals to a canonical `core.Signal` for execution (ST-A2, London Breakout, NY Momentum, Adaptive SMC, SMC OB+FVG, VWAP, ShadowTracker). |
| `monitoring/` | Logging, metrics, `telegram.py` alerter used by the live runners. |
| `dashboard/` | Flask/FastAPI dashboard backend (`app.py`, `status_server.py`) — read-only status API plus an emergency-stop control route. |
| `New Dashborad/` | React/Vite frontend migration for the dashboard; frontend-only, still depends on the Flask/FastAPI backend. |
| `config/demo.yaml` | Live-demo execution config: magic number, traded pairs, risk limits. |

## SVOS / research components

| Path | Purpose |
|---|---|
| `svos/` | SVOS orchestration: lifecycle state machine (`svos/lifecycle/manager.py` — exclusive stage-mutation authority), governance, registry, experiments. |
| `research/`, `research_db/`, `research_engine/`, `research_sweep/` | Not duplicates but distinct layers: `research_db/` is the feature database (DuckDB/Parquet: candles, structure, liquidity, FVGs, order blocks); `research/` holds output analytics (spreads, execution-quality reports); `research_engine/` and `research_sweep/` are per-symbol/per-sweep result caches, both last modified 2026-06-26 and appear cold — candidates for archival, not active pipelines. |
| `pipeline/` | Phase-0 backtest / deterministic replay engine (net-of-fees P&L, stress testing, writes to the Postgres control plane). |
| `strategy_audit/` | Static rule-audit framework (10-validator gate: rules, stats, robustness, risk, regime, monitoring). |
| `strategy_validation/` | AI-assisted validation pipeline (quality/schema validators, approval workflow). |
| `execution_validation/`, `execution_simulator/`, `virtual_broker/` | Offline execution/behavior validation: simulated broker, latency/cost models, order-lifecycle replay — no live broker calls. |
| `adaptive/`, `session_smc/` | SMC strategy research code. `session_smc/` is the reusable detector library (liquidity, structure, swings, POI); `adaptive/` is a larger research suite that should consume `session_smc/`, not duplicate it. |
| `strategy/` vs `strategies/` | `strategy/` holds original strategy modules (`session_liquidity/`, `d2_e3/`); `strategies/` wraps them as thin execution adapters. `strategy/` is effectively deprecated in favor of SVOS-registered strategies — not deleted, but not the place for new work. |
| `data/` | Layered market/feature data (raw, normalized, processed candles, labels, replay, backtests). Also holds `data/svos/registry/*/state.json` — the file-based strategy lifecycle registry. |
| `agents/`, `agent/` | AI-orchestration modules (approval, quality testing, schemas) and prompt/rule templates for the audit/enhancement phases. |
| `src/`, `simulator/` | Feature-database builder, analytics, backtest engine; forward-test and historical-replay simulators. |

## Infra / governance / shared

| Path | Purpose |
|---|---|
| `db/` | Postgres control plane: `control_plane.py`, SQLAlchemy models, evidence repository, Alembic migrations. Single authoritative transactional database (`vmassit`). |
| `core/` | Shared `Signal`/`BaseStrategy` interfaces and strategy registry used by both production and research code — this is intentional shared surface, not a boundary violation. |
| `deploy/gcp-vm1/` | Docker Compose, systemd units, and run scripts for the services actually running on **this** host. The directory name does not match this host's identity — see `deployment_topology_validation.md`. |
| `config/`, `tasks/`, `schemas/` | YAML/JSON configuration, phase task definitions, strategy/task JSON schemas. |
| `docs/` | Documentation, including the authoritative `docs/svos/DEPLOYMENT_TOPOLOGY.md` and `docs/svos/PREFLIGHT_STATUS.md`. |
| `archive/` | Old implementations (Database-F prototype, prior Docker runtime, retired bot versions) — legacy, not live. |
| `quality/` | Architecture/import/security/style rule definitions used by CI quality checks. |

## Flagged duplicates / ambiguities (informational, no action taken)

1. **`strategy/` vs `strategies/`** — originals vs. adapters; `strategy/` should be documented as deprecated for new work.
2. **`research/` / `research_db/` / `research_engine/` / `research_sweep/`** — functionally distinct, but `research_engine/` and `research_sweep/` look stale (no modifications since 2026-06-26) and are undocumented as active or archived.
3. **`strategy_audit/` vs `strategy_validation/`** — both governance-adjacent; the hand-off between the two is not explicit in `DEVELOPER_HANDBOOK.md`.
4. **`adaptive/` vs `session_smc/`** — overlapping SMC logic; `session_smc/` is correctly the reusable library, but it is not verified here whether `adaptive/` actually imports from it or reimplements equivalent logic (see `module_boundary_analysis.md`).
5. **`dashboard/` vs `New Dashborad/`** — an intentional, in-progress frontend migration (Flask/FastAPI backend retained, React/Vite frontend added). The space in the directory name is a pre-existing typo, not something this audit corrects.
6. **`bot.py`** — superseded by `scripts/run_st_a2_demo.py` per prior audit work, but not deleted; still present at repo root and could be mistaken for the live entry point.

No conclusions about correctness of separation are drawn here — see `module_boundary_analysis.md` and `dependency_boundary_report.md` for the actual coupling analysis, and `architecture_gap_report.md` for the synthesized verdict.
