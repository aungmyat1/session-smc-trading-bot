# Project Readiness Assessment — Gap Analysis

Date: 2026-07-01
Status: Read-only audit finding — no code was modified to produce this document
Scope: Full-repository gap analysis against the target two-system architecture
(SVOS research platform + Production trading engine). Companion document:
`CURRENT_ARCHITECTURE.md` (diagram + component inventory + problems list).
Authority: informational only — does not supersede `docs/00_Project/DOC_AUTHORITY.md`
or any Level 0-5 document; where this report and an authoritative doc disagree, this
report cites the exact code evidence that prompted the disagreement rather than
asserting itself as authoritative.

Method: 5 parallel read-only research passes (SVOS pipeline/capability, strategy
artifact system, production execution engine, database/deployment architecture,
testing/dashboard) plus direct review of `docs/audit/*` and `docs/migration/*`
(dated 2026-07-01, same day) for repository-structure and module-boundary findings.
Every finding below is anchored to file:line evidence surfaced during those passes.

---

# Executive Summary

## Current maturity

```
Prototype
   |
   ▼
Research Platform  ◄── CURRENT POSITION
   |
   ▼
Validation Platform
   |
   ▼
Production Ready
```

**Current position: solidly past Prototype, inside Research Platform, with real but
disconnected pieces of Validation Platform already built.** This is not a green-field
state — SVOS has a working lifecycle/registry/governance core, a real content-addressed
evidence store, a working offline virtual-demo simulator, and genuine robustness-testing
code. But three structural gaps keep it from being a coherent Validation Platform and
several more keep the Production side from being trustworthy even at its current
demo-only, no-live-capital scope:

1. **Two parallel SVOS pipeline orchestrators coexist** (new `svos/application/*` vs.
   legacy `research/svos/engine.py` + `research/validation/engine.py`), neither retired.
2. **No strategy artifact/packaging system exists** — the target
   `strategy.yaml + parameters.json + risk_config.json + validation_report.json +
   performance.json + checksum` bundle has zero code assembling it; production has no
   checksum/artifact-verification gate at all.
3. **Production's own declared risk config is not actually loaded at runtime** —
   `config/strategy_portfolio.yaml` is cosmetic to the live process, and the
   daily/weekly/monthly loss-limit halt is structurally dead code because the
   close-event feedback that would update its P&L counter is never called. This is
   currently harmless only because `LIVE_TRADING=false`/`DEMO_ONLY=true` are enforced.

**Target completion estimate:** given the roadmap in this document (5 phases), reaching
a genuinely production-ready state — one artifact-gated strategy, running through a
unified execution stack, with real risk-halt enforcement and DB/node separation
complete — is a **3-4 month build**, assuming one engineering owner and no new strategy
research work competing for the same time. This estimate is for closing the
architectural/safety gaps identified here; it does not include the time for any
strategy to actually clear the (now stricter, see `CLAUDE.md` §0.6) Phase-3 statistical
gate — that is research work, not engineering work, and is independently timed.

---

# Implementation Gap Matrix

| Component | Current Status | Target State | Gap | Priority |
|---|---|---|---|---|
| SVOS lifecycle/registry/governance core | **Complete** | Sole mutation authority, evidence-gated transitions | None functionally; one real UI-side bypass (dashboard overlay) not covered by the architecture test | P1 |
| SVOS pipeline orchestration | **Partial (duplicated)** | One canonical orchestrator | Two full parallel implementations (`svos/application/pipeline.py` vs. `research/svos/engine.py`+`research/validation/engine.py`), neither retired | P1 |
| Strategy Audit (Phase 0) | **Complete** (2 engines, 1 wired) | One audit engine | Legacy `strategy_audit/` (10-validator) unused but present alongside the real, wired `strategy_validation/` (8-validator) — naming-collision/confusion risk, not a coverage gap | P3 |
| Strategy Enhancement (Phase 1) | **Missing** (as integration service) | `svos/application/enhancement.py` wrapping a generic AI-suggestion engine | Real engine exists (`strategy_validation/ai/editor_engine.py`) but wired only into the legacy orchestrator, not the new pipeline | P2 |
| Historical Replay engine | **Fragmented** | One canonical replay engine feeding the Phase-2 gate | 7 independent scripts each reimplement simulate/metrics logic; a real cohesive engine (`execution_simulator/replay_engine/runner.py`) exists but is unused by most of them | P1 |
| Backtest engine | **Fragmented** | One canonical metrics library feeding the Phase-3 gate | 5+ independent PF/metrics implementations across scripts, `pipeline/`, `src/backtest/`, `research/validation/engine.py` | P1 |
| Robustness testing (Phase 4) | **Partial** (2 of 4 checks broken) | All 4 checks (walk-forward, Monte Carlo, parameter sensitivity, regime analysis) functioning | Walk-forward + Monte Carlo work; parameter-sensitivity + regime-analysis raise on every call due to a signature mismatch between `research/robustness.py` and its caller, silently caught and downgraded to WARN | P1 |
| Offline Virtual Demo (Phase 5) | **Complete** | Deterministic, network-free, drift-detected | Functionally complete; does not reuse `execution_simulator`'s `MarketFeed`/`VirtualBroker` for tick synthesis (builds a lighter-weight synthetic path instead) | P3 |
| Production Approval (Phase 6) | **Correctly out of scope** | Record-only, structurally unreachable by forward promotion | None — confirmed correctly disabled | — |
| Strategy configuration (catalog vs. portfolio config) | **Partial** | Catalog is a generated, read-only projection of registry state | `config/strategy_catalog.yaml` is hand-edited YAML (confirmed via git history), not generated; no sync job between it and the new `data/svos/registry/` JSONL store — two unreconciled systems of record | P2 |
| Strategy Artifact/Packaging system | **Missing** | Versioned bundle (spec+params+risk+validation+performance+checksum) per strategy version, checksum-verified on import | No code assembles a multi-file bundle; the one real hashing primitive (`svos/adapters/artifacts.py`, genuine SHA-256 CAS) is wired only to individual per-stage report files. `bot.py` has zero artifact/checksum awareness | P1 |
| Production execution layer | **Fragmented (3 stacks)** | One unified execution path | `bot.py` (dormant, live-capable), `scripts/run_st_a2_demo.py` (deployed), `scripts/run_d2_e3_demo.py` (deployed, separate) each with independent risk/position-guard logic and magic numbers | P1 |
| Production risk layer | **Partial (config not loaded)** | Config-driven, single source of truth, real-time enforcement | `strategy_portfolio.yaml` never loaded by the live runner; 3 disconnected hardcoded default sets; daily/weekly/monthly loss-halt is dead code (close events never fed back); per-strategy risk tiers bypassed | **P0** |
| Multi-strategy portfolio runner | **Built but not deployed** | Concurrent multi-strategy execution with per-strategy isolation | `scripts/run_portfolio.py` genuinely loads the 5-strategy YAML but has no systemd unit; even if deployed, loss-limit counters are shared/global, not per-strategy | P1 |
| Trade management (SL/TP/lifecycle) | **Partial** | Full lifecycle incl. break-even/partial-TP, single source of truth for trade state | `modify_sl_tp()` exists but is never called live — no BE/partial/trailing in the live path; 3 separate trade journals with no single canonical table | P2 |
| Monitoring/alerting | **Partial** (push for events, no heartbeat) | Automated push alerts incl. liveness/heartbeat | Telegram alerts for trades/errors/emergency-stop are real and wired; heartbeat/watchdog alerting exists in code but only wired to the dormant `bot.py`, not the live path — a silent hang would not page anyone | P2 |
| Emergency stop / kill switch | **Complete** | Single, reliable, CONFIRM-gated halt | Fully wired end-to-end; two independent HTTP surfaces (Flask + FastAPI) share the same underlying state file — functionally consistent but a duplication/confusion risk | P3 |
| One-position-per-symbol / concurrency guard | **Partial, degrading** | Real-time, broker-verified enforcement | Guard exists but never receives close events, so it degrades into a one-shot lock rather than accurate real-time state | P1 |
| Database architecture | **Missing (separation)** | Postgres on VPS2 only, least-privilege roles, production/research schema separation | Single `vmassit` instance on VPS1 (loopback) holds all 12 schemas across both concerns; VPS2's own Postgres container is unmigrated and exposed on all interfaces | P1 |
| Deployment/node topology | **Partial** | Two independently-deployable nodes | Physical node split is real (VPS1 executes, VPS2 is online with Docker+Postgres) but DB hasn't cut over, VPS2 has no SVOS systemd presence, and VPS2 lacks RAM (955 MiB, no swap) for full research workloads (8 GB gate) | P2 |
| Secrets management | **Complete** | `.env`-based, gitignored, no leakage | Verified clean — `.env` gitignored/untracked, `.env.example` placeholders only, zero hardcoded secrets found in tracked source | — |
| Testing — unit/simulation tiers | **Complete** | Full-suite green baseline | 171 tests pass in the safety-relevant subset (72% coverage); execution-validation/simulator tests present and passing | P3 |
| Testing — integration/regression tiers | **Missing** | Dedicated integration/regression suites | `tests/{integration,regression,replay,strategy,unit}` exist as empty scaffolds — zero tests despite the directories existing | P2 |
| Testing — full-suite CI gate | **Missing/Broken** | Green `pytest` run across the whole repo | Blocked by a pre-existing pandas segfault at collection time (`scripts/validate_dataset.py` module-level `pd.Timedelta` call); explicitly deferred, not attributed to this audit | P1 |
| Testing — failure-recovery/chaos | **Partial** | End-to-end broker-disconnect simulation | Strong incident-driven unit coverage (BUG-01 RPC-timeout regression, reconnect/backoff logic) exists and a real fix shipped (commit `621cf0d`); no full end-to-end chaos-level test exists | P3 |
| Dashboard — SVOS/research side | **Partial** | Dedicated research/validation/strategy-performance UI | Real and actively served (`New Dashborad/` React SPA) but auth inconsistently applied to mutation routes; SVOS/EVF jobs run via subprocess inside the same process serving live routes | P2 |
| Dashboard — Live trading side | **Partial (3 surfaces)** | One dedicated live-trading UI (positions/orders/P&L/risk/health) | Three code surfaces exist (`app.py` merged routes, standalone `live_app.py`, FastAPI `status_server.py`); no P&L/equity-curve view, no realtime transport (polling only), two independent emergency-stop authorities | P2 |
| Research/Production code separation | **Mostly clean, one real coupling** | Zero cross-imports in the risk-relevant direction | No SVOS/research code can place live orders except one script (`adaptive/run_shadow.py`) that imports the live broker executor + MetaAPI SDK directly for a market-data feed (no order calls found) | P2 |

---

# 1. Repository Architecture Audit

## Current architecture

See `CURRENT_ARCHITECTURE.md` §1-2 for the full diagram and component inventory. Summary:
the repo hosts both systems in one checkout, running on two physically separate,
Tailscale-connected VPS hosts (`auto-trade-vps` = production/execution, `gcp-vm1` =
intended SVOS research plane). Today, almost all research code also runs on VPS1
because VPS2 lacks the RAM (955 MiB, no swap) for full research workloads.

## Separation between research and production

**Import-level coupling (verified by grep across both directions):**

| Direction | Finding | Severity |
|---|---|---|
| Production → SVOS | `execution/governance_guard.py`, `dashboard/app.py` import SVOS governance/registry/API modules | MEDIUM — documented, intentional (the lifecycle gate) |
| SVOS/research → Production/broker | `adaptive/run_shadow.py` imports `execution.mt5_executor` and the MetaAPI SDK directly for a market-data feed (no order-placement calls found) | HIGH — the one finding that blocks independently-deployable packages |

No other SVOS/research package (`svos/`, `research/`, `research_db/`, `research_engine/`,
`research_sweep/`, `strategy_validation/`, `pipeline/`) imports MetaAPI, MT5,
`place_order`, `open_position`, `trade_manager`, or `order_manager`.

## Shared libraries

`core/` (Signal/BaseStrategy contract) is deliberately shared by both sides — correct
by design, not a boundary violation.

## Code duplication / technical debt (see `CURRENT_ARCHITECTURE.md` §3.9 for full list)

- `strategy/` (deprecated originals) vs. `strategies/` (execution adapters)
- `research_engine/`/`research_sweep/` — cold since 2026-06-26, undocumented as active or archived
- `strategy_audit/` (legacy, unused by SVOS) vs. `strategy_validation/` (real, wired) — two Phase-0 audit engines
- `adaptive/` vs. `session_smc/` — unverified whether `adaptive/` reuses or reimplements SMC detection
- Two SVOS pipeline orchestrators (see Gap Matrix) — the single largest duplication found

---

# 2. SVOS Capability Audit

## Strategy Management

| Sub-capability | Status |
|---|---|
| Strategy registry (`svos/registry/service.py`) | **Complete** — append-only JSONL, version-bound evidence, hard-gated transitions |
| Strategy metadata / version control | **Complete** — `VersionRecord`, `EvidenceRecord`, `TransitionRecord` dataclasses (`svos/shared/models.py`) |
| Lifecycle management (`svos/lifecycle/manager.py`) | **Complete** — 11-stage enum, adjacency-only transitions, `PRODUCTION_APPROVAL` correctly unreachable by forward promotion |
| Strategy configuration system | **Partial** — `config/strategy_catalog.yaml` is hand-edited, not a generated projection as documented; no reconciliation with the new JSONL registry |

**Legacy bypass status:** the 2026-06-29 architecture review's Critical Finding
("legacy promotion functions mutate catalog state without a governance decision") is
now **stale/fixed** — `core/strategy_registry.py`'s mutation functions hard-raise
`DirectCatalogMutationError`, enforced by an AST-based architecture test
(`tests/architecture/test_lifecycle_authority.py`). A **separate, current** bypass
exists in `dashboard/strategy_service.py` (see `CURRENT_ARCHITECTURE.md` §3.4) — not
covered by that same test.

## Historical Research Pipeline

- Data ingestion/normalization/feature-extraction scripts (`download_dukascopy.py`,
  `build_timeframes.py`, `extract_features.py`, `validate_dataset.py`,
  `normalize_dukascopy_ticks.py`) each exist as complete, standalone CLIs.
- **Not automated end-to-end by design**: `download_dukascopy.py`'s own docstring
  states manual invocation is required (cites CLAUDE.md §0 — live-data downloads are
  intentionally gated). No single command chains ingestion → normalization → features
  → validation even for the fully-deterministic post-download steps.
- `run_pipeline.py` (repo root) only builds the feature database from
  already-processed data; it is not a data-pipeline orchestrator.

**Can a new strategy run without manual intervention?** No — every stage requires a
human to invoke the next script.

## Validation Pipeline (stage-by-stage)

| Stage | Existing implementation | Missing implementation | Problems |
|---|---|---|---|
| Strategy Audit | `strategy_validation/` (8 validators), wired via `svos/application/audit.py` | — | Legacy `strategy_audit/` (10-validator) engine unused but present — confusion risk |
| Historical Replay | `execution_simulator/replay_engine/runner.py` (real, cohesive) | A single canonical entrypoint that all strategies use | 7 independent one-off scripts with duplicated simulate/metrics logic; `svos/application/replay.py` is a gate that accepts pre-computed trades, doesn't execute a replay itself |
| Backtest | `svos/application/backtest.py` (gate, `_evaluate_gate`, matches CLAUDE.md gate exactly) | A single canonical metrics-computation library | 5+ independent PF/metrics implementations; two duplicate gate implementations (`research/validation/engine.py`, `pipeline/pipeline_03_replay_engine.py`) alongside the real one |
| Statistical Validation | Same as Backtest (same gate module) | — | Same fragmentation |
| Robustness Testing | `research/robustness.py` (all 4 functions genuinely implemented) | Fix the `svos/application/robustness.py` call-site signature mismatch | Parameter-sensitivity and regime-analysis silently fail every call (wrong argument types/names) and degrade to WARN — only walk-forward + Monte Carlo function as a real gate today |
| Offline Virtual Demo | `svos/application/virtual_demo.py` (415 lines, network-free, real drift detection) | Reuse of `execution_simulator`'s `MarketFeed`/`VirtualBroker` for tick synthesis (currently builds a lighter synthetic path) | Minor — functionally complete either way |
| Production Approval | `svos/lifecycle/manager.py` hard-discards forward promotion into this stage | — (correctly out of scope) | None |

## Strategy Enhancement (Phase 1) — called out separately per the audit request

**Status: Partial.** `strategy_validation/ai/{question_engine,editor_engine}.py` are
real, working, generic implementations — not stubs. But there is no
`svos/application/enhancement.py`; these engines are wired only into the legacy
`research/svos/engine.py` orchestrator. Every other phase (0, 2, 3, 4, 5) has a
dedicated integration service in the new pipeline; Phase 1 does not, making it a
manual step and an asymmetric gap in an otherwise-complete new pipeline.

---

# 3. Strategy Artifact System Audit

**Target model:** `ST-A2-v1.2.0/{strategy.yaml, parameters.json, risk_config.json,
validation_report.json, performance.json, checksum}`.

| Question | Answer |
|---|---|
| Is artifact creation implemented? | **No.** No module in `svos/application/` or elsewhere assembles a multi-file bundle. Files that would compose one exist independently and unlinked: parameters in `config/strategy_portfolio.yaml`, catalog fields in `config/strategy_catalog.yaml`, performance in `docs/VERDICT_LOG.md` (markdown) and per-stage JSON reports, risk config in a *global* `config/risk.yaml` (not per-strategy-version). |
| Is artifact hashing/content-addressing implemented? | **Partial.** `svos/adapters/artifacts.py`'s `FilesystemArtifactStore` is a genuine, production-quality SHA-256 CAS (atomic writes, `verify()` re-hashes and compares) — but it stores individual per-stage report files via `svos/reports/service.py`, never a bundled multi-file strategy package. |
| Is artifact validation/checksum verification implemented? | **No.** `execution/governance_guard.py` (the one real gate in the execution path, used only by `scripts/run_st_a2_demo.py`) checks catalog YAML fields (`approved`, `status`) and JSONL governance decisions — it does not verify any hash of a packaged bundle. |
| Can production import an artifact safely today? | **No.** `bot.py` — the actual, still-live-capable execution entrypoint — has zero catalog lookup, zero governance check, and zero hash verification of any kind; it hardcodes ST-A2. |

**Gap to close:** (1) a packaging module that assembles the 5-file bundle on Production
Approval, (2) reuse of the existing, working `FilesystemArtifactStore` to hash the whole
bundle, (3) a verify-on-import step in the execution path, (4) a real generator for
`config/strategy_catalog.yaml` from registry state instead of hand-editing, (5) a
production-side loader with zero imports from research/backtest/replay code.

---

# 4. Production Trading Engine Audit

## Execution Layer — Partial (3 non-unified stacks)

See `CURRENT_ARCHITECTURE.md` §3.1. Deployed live path (confirmed via the actual
systemd unit): `smc-demo-runner.service` → `run_st_a2_demo.py` → signal router →
circuit breaker → portfolio manager → governance guard → demo risk manager → trade
manager → Vantage demo executor → MT5 connector → MetaAPI SDK. `bot.py` and
`run_d2_e3_demo.py` are two more independent, fully-wired stacks.

## Risk Layer — Partial, config is largely decorative

| Mechanism | Status |
|---|---|
| Position sizing | **Complete** (duplicated — two separate formulas across the bot.py and demo paths) |
| `max_trades_per_day` / `max_open_positions` | **Partial** — enforced, but on hardcoded defaults that disagree between modules, never on the YAML |
| Daily/weekly/monthly loss-limit halt | **Missing (dead code)** — the P&L counter it checks is never updated by real trade closes |
| Per-strategy risk tiers (0.30/0.20/0.10%) | **Missing (bypassed)** — tier lookup exists but has zero call sites; live sizing uses a flat, separately-hardcoded percentage |
| Portfolio max-exposure / correlation-group check | **Partial** — implemented but against hardcoded fallback groups, not the YAML's 3 groups, and the underlying open-symbol set never clears |
| Emergency stop / kill switch | **Complete** — fully wired, CONFIRM-token gated, verified working end to end |

## Trade Management — Partial

Position tracking and SL/TP-at-open are real. Break-even/partial-TP logic
("TP1 at 4R → BE, TP2 at 5R", as documented in strategy specs) exists only in offline
backtest/replay scripts — never wired into the live path; the deployed strategy
explicitly documents "single TP, no partials." Three separate, uncoordinated trade
journals exist with no single canonical table.

## Monitoring — Partial

Event-driven Telegram alerts (trade open, signal detected, errors, emergency stop,
daily summary) are real and automated. Heartbeat/watchdog alerting exists in code but
is wired only to the dormant `bot.py`, not the live path — a silent hang in the live
runner would not page anyone; health must be pulled from the dashboard.

## Concurrency / isolation — Partial, degrading over a process's lifetime

The one-position-per-symbol guard exists but never receives close events, so it
degrades from real-time enforcement into a one-shot lock. True cross-strategy risk
isolation does not exist even in the not-yet-deployed multi-strategy runner, since
loss-limit counters are shared/global by design.

**Most urgent production-safety gap (repeated from the Executive Summary):** the
daily/weekly/monthly loss-limit halt cannot fire in the live path because the
functions that would feed real P&L into its counters are never called. Not a live-risk
issue today (`DEMO_ONLY=true`) but a real gap in the platform's own safety model that
must close before any live-trading conversation is possible.

---

# 5. Research / Production Separation Audit

Already covered in §1 (Repository Architecture Audit) — repeated summary: mostly
clean in the risk-relevant direction. `adaptive/run_shadow.py`'s direct import of the
live broker executor + MetaAPI SDK is the one finding that would block packaging the
two sides as independently-deployable units; it does not place orders, but it creates
a hard runtime dependency from research code onto the production package and the
broker SDK.

**What should move:** `adaptive/run_shadow.py`'s market-data feed should be extracted
behind a thin interface implemented by both live execution and shadow/research code,
rather than importing `execution.mt5_executor` directly.

**Shared libraries required:** `core/` already serves this role correctly for the
`Signal`/`BaseStrategy` contract; the governance-guard/API coupling
(`execution/governance_guard.py`, `dashboard/app.py` → `svos/`) is intentional and
would only need to become a network boundary if independent per-node packaging/
containers become an explicit future goal.

---

# 6. Database Architecture Audit

**Current:** A single, authoritative Postgres instance (`vmassit`) runs on VPS1
(loopback `127.0.0.1:5432`), holding 12 schemas spanning both concerns:
production/execution-adjacent (`execution`, `operations`) and research/governance
(`market`, `research`, `governance`, `strategy`, `analytics`, `experiments`,
`robustness`, `evidence`, `config`). Production code does not import `db.*` directly —
its only path to this database is transitive, through in-process imports of SVOS
governance/API modules (`execution/governance_guard.py`, `dashboard/app.py`). Separate
DuckDB/SQLite files (`research.db`, `research_sweep.db`,
`research_db/feature_database.duckdb`) are correctly isolated research-only stores.
Live broker order/position state lives in a file (`logs/bot_state.json`), not in
Postgres at all.

A second, standalone `docker-compose.yml` under `deploy/gcp-vm1/` defines a *different*
Postgres container (`trading_research` DB) intended for VPS2 — not the instance
currently in use, and not yet populated.

**Target** (`docs/svos/DEPLOYMENT_TOPOLOGY.md`, Level 5 authority): Postgres lives on
VPS2 only, with dedicated least-privilege SVOS roles, bound to loopback/Tailscale.

**Recommendation:** proceed with the already-planned Postgres cutover to VPS2
(`docs/svos/PREFLIGHT_STATUS.md`'s own next step) — this is the single highest-leverage
infrastructure move available, and it's already scheduled, not a new proposal from this
audit. Keep DuckDB/SQLite research-only stores as-is (already correctly separated).

---

# 7. Deployment Architecture Audit

**Current:** Two real, Tailscale-connected hosts. VPS1 (`auto-trade-vps`) runs the live
demo/dashboard services as bare systemd units (`smc-demo-runner.service`,
`live-dashboard.service`, `d2e3.service` confirmed running; 3 more unit files present
but installation status ambiguous). VPS2 (`gcp-vm1`) is online with Docker + a Postgres
container, but has zero SVOS systemd presence — research runs ad hoc via scripts only,
and its 955 MiB RAM / no swap is below the 8 GB gate `DEPLOYMENT_TOPOLOGY.md` itself
sets for real research workloads.

**Missing infrastructure:**
- Postgres cutover to VPS2 (planned, not executed)
- Loopback/Tailscale-only binding for VPS2's Postgres (currently exposed on all
  interfaces per its own `docker-compose.yml`, plus an unflagged `adminer` web-UI
  exposure on the same file)
- Any systemd/scheduled presence for SVOS pipeline stages on VPS2
- A capacity increase for VPS2 (explicitly a paid, owner-level decision per
  `DEPLOYMENT_TOPOLOGY.md` §6 — not something to silently do)

**Secrets management:** Complete — `.env` gitignored and untracked, `.env.example`
files use placeholders only, zero hardcoded secret-shaped strings found in tracked
source across both passes that checked.

---

# 8. Testing & Reliability Audit

117 test files across 17 subdirectories. A pre-existing pandas segfault
(`scripts/validate_dataset.py`'s module-level `pd.Timedelta` call, triggered on import
by `tests/test_validate_dataset.py`) crashes full-suite `pytest` at collection —
explicitly deferred as pre-existing, not attributable to this audit. A 171-test
safety-relevant subset (architecture, svos, demo-execution-safety, broker-interface,
execution) passes cleanly at 72% coverage. `tests/{integration,regression,replay,
strategy,unit}` exist as empty directory scaffolds — zero actual tests despite the
directories existing, so no dedicated integration/regression tier exists today; that
coverage (where it exists at all) lives ad hoc under `tests/` root or `tests/execution`.

Failure-recovery testing is genuinely incident-driven and real: a 2026-06-21
production RPC-timeout-hang incident produced both a shipped fix (commit `621cf0d`,
proactive liveness checks + reconnect-on-last-retry-only) and a regression test
(`tests/test_bug01_rpc_timeout.py`) that reproduces the exact failure mode. No
end-to-end chaos/fault-injection harness exists for a full live-broker-drop scenario
across the running system — all failure-recovery tests are fast unit-level mocks.

**Production readiness level for testing:** ready for the exercised subset only, not
for the whole repository — there is no full-suite green CI baseline today.

---

# 9. Dashboard Audit

Four distinct code surfaces exist, not a clean two-way SVOS/Live split:

1. `dashboard/app.py` — merged Flask app: SVOS/EVF, legacy ops, the React SVOS
   workstation, AND live-dashboard routes, all in one process.
2. `dashboard/live_app.py` — standalone Flask app, live-dashboard only, its own
   systemd unit, genuinely deployed independently.
3. `dashboard/status_server.py` — a third, FastAPI-based surface independently owning
   the emergency-stop path.
4. `New Dashborad/` (React/Vite, typo'd directory name, not dead code) — the active
   SVOS/strategy-validation workstation UI.

**SVOS/research side — what exists:** validation-stage tabs (audit, replay,
robustness, virtual demo, governance), a `/api/new-dashboard/*` API surface with
promote/demote/pipeline-report/run-pipeline endpoints. **What's missing:** consistent
auth on mutation endpoints (live-dashboard routes use `require_operator`; new-dashboard
write routes do not show the same decorator), and process isolation from live-trading
API handlers (SVOS/EVF jobs run via subprocess inside the same process serving live
routes).

**Live trading side — what exists:** positions/orders view, emergency-stop control,
demo-runner status. **What's missing:** P&L/equity-curve view, true portfolio-exposure
view, realtime transport (currently polling only, no WebSocket/SSE), TradingView/chart
integration, and a single owner of the emergency-stop authority (two independent HTTP
surfaces currently share the underlying state file, which is functionally consistent
but a duplication/confusion risk).

---

# Recommended Implementation Roadmap

## Phase 1 — Critical architecture fixes (P0/P1 items; est. 3-4 weeks)

1. Wire `config/strategy_portfolio.yaml` into `scripts/run_st_a2_demo.py`'s
   `PortfolioManager`/`CircuitBreaker`/`demo_risk_manager` construction so the config
   actually governs runtime behavior (currently cosmetic).
2. Fix the daily/weekly/monthly loss-limit halt: wire real trade-close events into
   `PortfolioManager.record_close()`/`demo_risk_manager.record_result()` so the P&L
   counters the halt checks actually move.
3. Fix the `svos/application/robustness.py` call-site signature mismatch so
   parameter-sensitivity and regime-analysis actually execute instead of silently
   failing.
4. Close the dashboard governance bypass (`dashboard/strategy_service.py`'s swallowed
   exception + unconditional overlay write) and extend
   `tests/architecture/test_lifecycle_authority.py` to cover this path.
5. Decide the fate of the two parallel SVOS pipeline orchestrators — retire
   `research/svos/engine.py` + `research/validation/engine.py` in favor of
   `svos/application/*`, or explicitly document why both must persist.

## Phase 2 — Complete the SVOS pipeline (est. 4-6 weeks)

1. Build `svos/application/enhancement.py` wrapping the existing
   `strategy_validation/ai/editor_engine.py` so Phase 1 has an integration service
   like every other phase.
2. Consolidate replay logic onto `execution_simulator/replay_engine/runner.py`;
   migrate the ad-hoc `scripts/replay_*.py` scripts to call it instead of
   reimplementing simulation logic.
3. Consolidate backtest/metrics logic onto one canonical function; retire the
   duplicate gate implementations in `research/validation/engine.py` and
   `pipeline/pipeline_03_replay_engine.py`.
4. Build a real generator for `config/strategy_catalog.yaml` from
   `data/svos/registry/` state (currently only the read side and the
   write-blocking side exist) so the two systems of record reconcile.

## Phase 3 — Complete production execution (est. 4-6 weeks)

1. Unify the 3 execution stacks (`bot.py`, `run_st_a2_demo.py`,
   `run_d2_e3_demo.py`) onto one execution path with one risk manager and one
   magic-number scheme, or explicitly retire `bot.py`'s code (not just its systemd
   presence) if it is truly dead.
2. Implement break-even/partial-TP management in the live path (currently only in
   offline backtest scripts).
3. Consolidate the 3 trade journals into one canonical trade-state table.
4. Wire heartbeat/watchdog alerting into the live path (currently only on the
   dormant `bot.py`).
5. Fix the two full-suite CI blockers: isolate the pandas segfault
   (`scripts/validate_dataset.py`) so it no longer crashes collection for the whole
   suite, and add real tests under the currently-empty
   `tests/{integration,regression}` scaffolds.

## Phase 4 — Artifact deployment system (est. 4-6 weeks)

1. Build `svos/application/packaging.py`: assemble
   `strategy.yaml + parameters.json + risk_config.json + validation_report.json +
   performance.json` into one versioned bundle on Production Approval.
2. Extend the existing, working `FilesystemArtifactStore`
   (`svos/adapters/artifacts.py`) to hash the whole bundle (or a manifest of
   component hashes).
3. Add a verify-on-import step to the production execution entrypoint — reject
   loading any strategy whose checksum doesn't match its registry-recorded hash.
4. Complete the Postgres cutover to VPS2 (already scheduled in
   `docs/svos/PREFLIGHT_STATUS.md`) and fix the all-interfaces port exposure on both
   the VPS2 Postgres container and its `adminer` companion.

## Phase 5 — Multi-instance production scaling (est. 6-8 weeks, contingent on Phase 1-4)

1. Deploy `scripts/run_portfolio.py` (the real multi-strategy runner, already built
   but not installed) with per-strategy loss-limit isolation instead of the current
   shared/global counters.
2. Split the dashboard's live-trading concern into its own fully independent process
   with one emergency-stop authority (retire the duplicate Flask/FastAPI surfaces
   down to one).
3. Add realtime transport (WebSocket/SSE) and a P&L/equity-curve view to the live
   dashboard.
4. Only after Phases 1-4 are verified: extend to additional broker/instrument
   instances per the two-node topology's original "one SVOS, many production
   instances" design intent.

**Sequencing note:** Phase 1 items are safety-relevant even at `DEMO_ONLY=true` scope —
they should not wait for a strategy to clear the Phase-3 statistical gate. Phases 2-5
can run in parallel with ongoing strategy research, since none of them depend on any
specific strategy's backtest result.
