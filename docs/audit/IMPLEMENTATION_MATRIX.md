# Implementation Matrix — Full Subsystem Audit

Date: 2026-07-04
Status: Read-only audit finding
Companion: `CURRENT_PROJECT_STATUS.md` (diagram + summary), `PRODUCTION_READINESS.md` (readiness
ratings), `TECHNICAL_DEBT.md`, `ROADMAP.md`.
Method: 5 parallel read-only research passes verified against current code (including uncommitted
changes as of 2026-07-04), cross-checked against the existing 07-01→07-03 audit corpus. Every
claim below traces to file:line evidence gathered during those passes.

Legend: ✅ Complete 🟡 Partial 🔴 Missing

---

## A. Infrastructure & Operations

### Infrastructure
Status: 🟡 Partial | Completion: 55%
Purpose: Host and process topology for the two-node platform.
Current implementation: Only VPS 1 (`auto-trade-vps`) is confirmed live — `smc-demo-runner.service`
and `live-dashboard.service` are the only two systemd units actually installed. `deploy/gcp-vm1/systemd/`
holds 7 unit files but `d2e3.service`, `d2e3-journal-sync.*`, `reconcile-positions.*` exist as
files only, not enabled.
Missing: No scheduled/systemd presence for any SVOS research pipeline; no crontab entries.
Blocking issues: `deploy/gcp-vm1/` directory name collides with VPS 2's hostname while holding
VPS 1's own units — a confirmed non-fatal but confusing naming footgun.
Files: `deploy/gcp-vm1/systemd/*`, `deploy/gcp-vm1/docker-compose.yml`, `docs/svos/DEPLOYMENT_TOPOLOGY.md`.

### Cloud (two-VPS topology)
Status: 🟡 Partial | Completion: 45%
Purpose: Physically separate SVOS research (VPS 2) from production execution (VPS 1).
Current implementation: VPS 2 is real and reachable (GCP e2-micro, Tailscale-verified, Docker +
`quant-postgres` healthy), not aspirational.
Missing: Dedicated SVOS Postgres roles/DB, restricted network exposure, and checksummed dataset
cutover from VPS 1 have not happened — authoritative Postgres (`vmassit`) still runs on VPS 1
loopback.
Blocking issues: VPS 2 Postgres publishes port 5432 on all interfaces on the live host (acknowledged,
unfixed); VPS 2 has 955 MiB RAM/no swap, below the 8 GB gate for real research workloads.
Files: `docs/svos/DEPLOYMENT_TOPOLOGY.md`, `docs/svos/PREFLIGHT_STATUS.md`, `.env` (DATABASE_URL).

### Docker
Status: 🟡 Partial | Completion: 40%
Purpose: Containerize the VPS 2 Postgres + Adminer stack.
Current implementation: One live compose file, `deploy/gcp-vm1/docker-compose.yml`
(`postgres:16-alpine` + `adminer:4`, healthcheck, tuned memory settings). Three more
docker-compose/Dockerfile sets exist only under `archive/` — dead.
Missing: No Dockerfile/image for the production execution path or SVOS application code — only
the database is containerized.
Blocking issues: Compose file defaults to `127.0.0.1` bind but the deployed VPS 2 instance
actually publishes on all interfaces — the live environment overrides the safe repo default.
Files: `deploy/gcp-vm1/docker-compose.yml`.

### Redis
Status: 🔴 Missing (by design, not a deficiency) | Completion: N/A
Purpose: N/A — no caching/queue/pub-sub layer is designed into this platform.
Current implementation: Zero references anywhere in code, config, or lockfiles.
Missing: N/A. State/coordination uses Postgres + JSONL registries + flat files instead.
Blocking issues: None.

### Postgres
Status: 🟡 Partial | Completion: 65%
Purpose: Single control-plane database for governance, research, and execution-adjacent state.
Current implementation: Live `vmassit` instance (Postgres 16), `db/control_plane.py`/`db/models.py`,
12 schemas, 4 real Alembic migrations (CI-verified offline). Real backup/restore path
(`agtrade/admin.py`, `application/admin_service.py`: pg_dump + SHA-256 + passphrase support),
covered by `tests/database/test_backup_contract.py`.
Missing: Not split by node/concern — co-located on VPS 1 contrary to target topology; no
dedicated least-privilege SVOS roles.
Blocking issues: DB still on VPS 1, not VPS 2 as topology requires — the largest live
infrastructure gap per the topology doc itself.
Files: `db/control_plane.py`, `db/models.py`, `db/migrations/versions/*.py`, `agtrade/admin.py`.

### API
Status: 🟡 Partial | Completion: 60%
Purpose: Expose SVOS operational state and live-trading status/control to the dashboard/operators.
Current implementation: Three real REST surfaces — `dashboard/app.py` (Flask, merged
SVOS/EVF/legacy/React shell), `dashboard/live_app.py` (Flask, own systemd unit),
`dashboard/status_server.py` (FastAPI :8090, the one actually deployed/audited live).
`svos/api/service.py` is a thin read-oriented facade.
Missing: Consolidation — 3 unconsolidated surfaces instead of one; no OpenAPI spec for the Flask apps.
Blocking issues: `dashboard/strategy_service.py`'s `promote_strategy()`/`demote_strategy()` swallow
governance exceptions (`except Exception: pass`) and unconditionally write
`reports/dashboard_strategies.json` regardless of outcome — a real governance-bypass bug.
Files: `dashboard/app.py`, `dashboard/live_app.py`, `dashboard/status_server.py`, `dashboard/strategy_service.py`.

### Authentication
Status: 🟡 Partial | Completion: 70%
Purpose: Gate dashboard/API mutation endpoints to trusted operators with role-based permissions.
Current implementation: Real implementation in `dashboard/auth.py` — trusted-proxy mode (HMAC
shared secret, OIDC-fronted) and bearer-token mode, both with a role→action permission map and
CSRF double-submit protection for mutation routes.
Missing: No MFA or session-expiry mechanism; tokens are static shared secrets, not
per-user/rotatable.
Blocking issues: Fail-closed only if secrets are actually set in the deployed `.env` (not
verified by this audit, by design).
Files: `dashboard/auth.py`, `deploy/dashboard/oauth2-proxy.cfg.example`.

### Configuration
Status: 🟡 Partial | Completion: 55%
Purpose: Externalize strategy portfolio, risk, demo, and platform parameters from code.
Current implementation: 16 YAML/JSON files under `config/`; `.env.example` documents ~27
required secrets/env vars.
Missing: `config/strategy_portfolio.yaml` (5 strategies, per-strategy risk tiers) is **not loaded
at runtime** by the deployed `scripts/run_st_a2_demo.py` — editing the YAML has zero effect on
the live process. The runner that does load it (`scripts/run_portfolio.py`) has no systemd unit.
Blocking issues: Config/code drift is a correctness trap for anyone auditing risk limits from
YAML alone.
Files: `config/*.yaml`, `.env.example`, `scripts/run_st_a2_demo.py`, `scripts/run_portfolio.py`.

### Logging
Status: ✅ Complete (for demo scale) | Completion: 80%
Purpose: Durable, rotated operational logs for the live demo runner, dashboard, and shadow processes.
Current implementation: `monitoring/logging_utils.py` — real gzip-rotating `TimedRotatingFileHandler`,
daily UTC rotation. Live evidence: multiple rotated log families, JSONL event streams, daily/weekly
summaries with real timestamps through 2026-07-04. `deploy/gcp-vm1/logrotate/smc-demo-runner`
provides a second, OS-level layer.
Missing: No centralized log aggregation/shipping (no ELK/Loki/CloudWatch) — single-host, local-file only.
Blocking issues: None at current scale.
Files: `monitoring/logging_utils.py`, `logs/*`.

### CI/CD
Status: 🟡 Partial | Completion: 60%
Purpose: Gate merges on quality/tests/security/docs; controlled release/deploy workflows.
Current implementation: 3 workflows — `ci.yml` (4-job required gate: quality/tests/security/docs),
`strategy-release.yml` (GCP-KMS-signed package + immutable GitHub Release),
`deploy-production.yml` (`workflow_dispatch` only, `LIVE_TRADING=false DEMO_ONLY=true` hardcoded
into the remote command).
Missing: Full-suite pytest is **not** what CI runs — the `tests` job exercises only specific
subsets (~28% of 152 test files); no true full-suite green baseline in CI.
Blocking issues: The previously-blocking pandas segfault at collection time is now resolved
locally (`pandas==2.3.3`), but CI's narrow path selection means real regressions (e.g. a failing
`tests/core` adapter test) can land on `main` undetected.
Files: `.github/workflows/ci.yml`, `.github/workflows/strategy-release.yml`, `.github/workflows/deploy-production.yml`.

### Security
Status: 🟡 Partial | Completion: 60%
Purpose: Prevent secret leakage, catch vulnerable dependencies, static-scan for insecure patterns.
Current implementation: `ci.yml` security job runs tracked-secrets rejection, `pip_audit` (4
time-boxed CVE ignores, justified "only while broker execution remains live-disabled"), and
`bandit -ll` over a partial path list.
Missing: `bandit`/`ruff` scans don't cover `execution/`, `dashboard/`, `scripts/`, `core/`,
`bot.py` — i.e. the actual live demo execution path is not bandit-scanned.
Blocking issues: CVE ignores must be re-reviewed before any live-trading flip.
Files: `.github/workflows/ci.yml`, `pyproject.toml`.

### Secrets Management
Status: 🟡 Partial | Completion: 60%
Purpose: Keep broker/Telegram/LLM/GCP credentials out of source control; support signed-release key material.
Current implementation: `.gitignore` excludes `.env`; CI hard-fails on tracked secrets or
literal secret-shaped assignments. Real GCP Secret Manager adapter (`infrastructure/google_cloud.py`)
exists and is tested. GCP KMS asymmetric signing for strategy releases exists.
Missing: No confirmation `SecretManagerAdapter` is wired into the live demo runner's credential
loading (appears used only by SVOS deployment/signing, not MetaAPI/Vantage/Telegram, which load
from `.env` directly).
Blocking issues: None found; no secrets tracked in git.
Files: `.env.example`, `infrastructure/google_cloud.py`, `svos/deployment/service.py`.

### Disaster Recovery
Status: 🟡 Partial | Completion: 40%
Purpose: Ensure the control-plane database and strategy artifacts can be restored after data loss.
Current implementation: Documented rollback procedure; real restore code (`agtrade/admin.py::restore()`,
passphrase-gated).
Missing: No evidence of an executed/rehearsed restore drill; no documented DR plan for the VPS 1
execution host itself (dashboard/bot process failure), only for the database.
Blocking issues: DR is code-ready but not operationally proven.
Files: `docs/svos/DEPLOYMENT_TOPOLOGY.md` §6-7, `agtrade/admin.py`.

### Backup
Status: 🟡 Partial | Completion: 55%
Purpose: Take periodic, verifiable backups of the control-plane Postgres database.
Current implementation: Real, tested implementation — `pg_dump` via libpq env vars, SHA-256
checksum, optional passphrase encryption, explicit-confirm restore. Exposed via `agtrade admin
backup|restore` CLI.
Missing: No confirmed scheduled/automated backup job (no cron/systemd timer) — invocation appears
manual/on-demand only.
Blocking issues: Backup cadence depends on an operator remembering to run it.
Files: `application/admin_service.py`, `agtrade/admin.py`, `tests/database/test_backup_contract.py`.

---

## B. Execution & Trading (System 2)

### Live Trading Engine
Status: 🟡 Partial | Completion: 65%
Purpose: Canonical entrypoint that connects to the broker and runs the strategy tick loop under a
validated package.
Current implementation: `scripts/run_portfolio.py` is the canonical runner, routing orders through
`production.engine.RuntimeAuthority` (preflight, single-process lock) and
`CanonicalExecutionPipeline` (journaled events, test-verified). `--mode live` is hard-rejected
before any package/runtime work. `bot.py` self-declares `LEGACY_RUNTIME_ENTRYPOINT = True`,
preserved not deleted.
Missing: The canonical runner does not invoke `TradingPermissionService`, `StrategyExecutionGuard`,
or `ExecutionStateStore.recover_incomplete()` at all (zero hits by grep) — while the **legacy**
`scripts/run_st_a2_demo.py` *does* wire all three. The legacy path is currently more defensive
than the canonical one meant to supersede it.
Blocking issues: No restart-recovery reconciliation before new orders in the canonical loop; no
governance/permission gate in the canonical loop.
Files: `scripts/run_portfolio.py`, `bot.py`, `production/engine/runtime.py`, `scripts/run_st_a2_demo.py`.

### Execution Engine
Status: 🟡 Partial | Completion: 55%
Purpose: Deterministic, idempotent order submission pipeline from strategy intent to broker call.
Current implementation: `production/engine/execution_pipeline.py` enforces package-scope match,
intent validation, and risk-gate evaluation before calling the adapter (test-verified rejected
decisions never reach the adapter). Underneath, `execution/trade_manager.py` drives real order
placement with retry/backoff and ambiguity classification, writing to `ExecutionStateStore`.
Missing: `production/engine/orders.py`/`positions.py` — a newer idempotency/position-dedup layer
built in commit `e009d5f` — are never imported/used outside their own module and tests. The
actually-used order path is still the older `execution/trade_manager.py`, re-exported as a pure
facade.
Blocking issues: Two competing execution stacks exist in the same package; only one is wired to
the live loop — scaffolding was added without consolidation.
Files: `production/engine/execution_pipeline.py`, `production/engine/orders.py`,
`production/engine/positions.py`, `execution/trade_manager.py`, `execution/execution_state.py`.

### Risk Management
Status: 🔴 Missing (for the live loop — components exist but are disconnected) | Completion: 35%
Purpose: Enforce SL/TP, daily/weekly/monthly loss limits, and circuit breakers against real trade outcomes.
Current implementation: Rich component logic exists: `production/engine/risk.py` (`RiskFirewall`,
fail-closed multi-check), `execution/demo_risk_manager.py` (`check_limits`, `record_result`),
`core/portfolio_manager.py` (daily/weekly/monthly loss tracking).
Missing: **`record_result()` — the only function that updates `daily_loss_pct`/`consecutive_losses`/
`halted` from a closed trade's real P&L — is never called anywhere in production code** (grep:
only test callers). `core/portfolio_manager.record_close()` has zero production callers either.
`run_portfolio.py` calls `_breaker.record_trade(..., won=True)` at **open** time with a hardcoded
`won=True` and never corrects it at close.
Blocking issues: Daily/weekly/monthly loss halts and consecutive-loss halts cannot trigger from
real outcomes — a losing streak will not stop the bot via these paths. This is the single most
consequential open P0 safety gap (tracked as WS2 in `ARCHITECTURE_STABILIZATION_ROADMAP.md`,
confirmed still open in this pass).
Files: `execution/demo_risk_manager.py`, `core/portfolio_manager.py`, `production/engine/risk.py`,
`scripts/run_portfolio.py`.

### Order Management
Status: 🟡 Partial | Completion: 55%
Purpose: Idempotent submission, retry, and broker/local reconciliation of orders.
Current implementation: `execution/execution_state.py` provides a real state machine with
idempotency keys and a legal-transition table, including `RECOVERY_PENDING` for ambiguous broker
timeouts. `execution/trade_manager.py` does exponential-backoff retry with error classification.
`production/engine/orders.py.OrderService.reconcile()` exists.
Missing: No component calls `ExecutionStateStore.recover_incomplete()` from the canonical
`run_portfolio.py` startup path (only the legacy runner does) — orders left `RECOVERY_PENDING`
after a crash are not resolved before new orders in the canonical loop.
Blocking issues: Restart-during-order-submission is not safely handled end-to-end in the
canonical path (tracked as WS5, open).
Files: `execution/execution_state.py`, `execution/trade_manager.py`, `production/engine/orders.py`.

### Position Management
Status: 🟡 Partial | Completion: 50%
Purpose: Enforce CLAUDE.md §0.7 "one position per symbol" and keep local/broker position state reconciled.
Current implementation: `core/portfolio_manager.py` enforces one-per-symbol at signal-routing
time via `_open_symbols`, populated by `record_trade()`. `production/engine/positions.py.PositionService.open()`
independently raises on duplicate symbol — but is unused in the live loop.
Missing: `core/portfolio_manager.record_close()` (the only method that releases a symbol from
`_open_symbols`) has zero production callers — once a symbol trades once in a day, it never
releases even after the position closes, degrading the rule to "at most one trade per symbol per
day." `max_positions_per_symbol` is never set in config, so a secondary check is a no-op.
Blocking issues: Position state can drift from broker truth for an entire trading day.
Files: `core/portfolio_manager.py`, `production/engine/positions.py`, `config/strategy_portfolio.yaml`.

### Broker Integration
Status: ✅ Complete (for demo scope) | Completion: 80%
Purpose: Real broker connectivity for market data and order execution via MetaAPI/Vantage MT5.
Current implementation: Genuinely real, not stubbed. `execution/mt5_connector.py` drives
`metaapi_cloud_sdk.MetaApi` with heartbeat/reconnect/latency tracking. `execution/vantage_demo_executor.py`
wraps it, gated by `DEMO_ONLY`. `production/engine/contracts.py.DisabledVantageAdapter` is a
deliberately-unreachable stub used only for the default-deny-boundary tests.
Missing: None for demo scope.
Blocking issues: Live-mode code paths still exist at the lower client layer, reachable by an
alternate caller — the default-deny boundary (ADR-0012/WS3) is enforced only at the CLI
entrypoint today, not at every layer.
Files: `execution/mt5_connector.py`, `execution/vantage_demo_executor.py`, `production/engine/contracts.py`.

---

## C. SVOS Research Pipeline & Multi-Agent (System 1)

### Data Pipeline
Status: 🟡 Partial | Completion: 70%
Purpose: Ingest, normalize, and feature-extract historical FX candle/tick data.
Current implementation: Complete standalone CLIs (`download_dukascopy.py`, `build_timeframes.py`,
`extract_features.py`, `validate_dataset.py`, `normalize_dukascopy_ticks.py`). 10-layer Parquet
layout under `data/`.
Missing: No single orchestrator chains ingestion → normalization → features → validation
(intentional — live-data downloads are gated).
Blocking issues: None currently (the historical pandas-segfault risk in `validate_dataset.py` is resolved).
Files: `download_dukascopy.py`, `build_timeframes.py`, `extract_features.py`, `data/`.

### Historical Replay
Status: 🟡 Partial | Completion: 55%
Purpose: Chronological, zero-lookahead candle replay for Phase-2 gate evidence.
Current implementation: Two real engines — `execution_simulator/replay_engine/runner.py` and the
newly-hardened `replay/replay_session.py`+`replay/replay_config.py` (uncommitted fixes: now
validates paths exist, raises on zero-candle windows instead of silently emitting empty replays).
`svos/application/replay.py` is the gate integration but accepts pre-computed trades rather than
executing a replay itself.
Missing: 7 independent one-off `scripts/replay_*.py` reimplement simulate/metrics logic instead of
one canonical engine; strategy execution still not wired into `replay/replay_session.py`.
Blocking issues: Fragmentation — no single canonical replay entrypoint all strategies use.
Files: `execution_simulator/replay_engine/runner.py`, `replay/replay_session.py`, `replay/replay_config.py`.

### Backtesting
Status: 🟡 Partial | Completion: 60%
Purpose: Statistical edge validation net of fees against the tightened Phase-3 gate.
Current implementation: `svos/application/backtest.py` implements `_evaluate_gate` matching the
current CLAUDE.md gate exactly. `svos/application/robustness.py` drives walk-forward/Monte
Carlo/sensitivity/regime analysis — the previously-reported call-signature mismatch against
`research/robustness.py` now appears fixed (call sites match current signatures; worth a targeted
pytest run to confirm).
Missing: 5+ independent PF/metrics implementations remain across `scripts/`, `pipeline/`,
`src/backtest/`, and the legacy engine — no single canonical metrics library. Two parallel SVOS
orchestrators still both exist on disk.
Blocking issues: Metrics fragmentation risks divergent PF numbers between the gate module and
ad-hoc scripts. No strategy currently clears the tightened gate.
Files: `svos/application/backtest.py`, `svos/application/robustness.py`, `research/robustness.py`,
`research/svos/engine.py`, `research/validation/engine.py`.

### Research Database
Status: ✅ Complete (for its scope) | Completion: 80%
Purpose: Store OHLCV/feature/SMC-structure data for backtest/replay, isolated from production state.
Current implementation: `research_db/feature_database.duckdb`+Parquet mirror, correctly isolated
from production (no `db.*` import path from production; only transitive governance-guard link).
Missing: Postgres cutover to VPS 2 still pending, unchanged since the 07-01 audit.
Blocking issues: None for research correctness; the VPS1/VPS2 placement is an infra gap.
Files: `research_db/client.py`, `db/control_plane.py`.

### SVOS / Strategy Registry
Status: ✅ Complete | Completion: 85%
Purpose: Sole, append-only source of truth for strategy versions, evidence, and lifecycle stage.
Current implementation: `svos/registry/service.py` + `svos/lifecycle/manager.py` (11-stage enum,
adjacency-only transition map; `PRODUCTION_APPROVAL` correctly unreachable by forward promotion).
Legacy direct-mutation functions hard-raise, enforced by an architecture test.
Missing: `config/strategy_catalog.yaml` remains hand-edited, not a generated projection of the
registry — two unreconciled systems of record.
Blocking issues: Catalog/registry reconciliation gap; a separate bypass in
`dashboard/strategy_service.py` is not covered by the same architecture test.
Files: `svos/registry/service.py`, `svos/lifecycle/manager.py`, `config/strategy_catalog.yaml`.

### Strategy Package (packaging/signing)
Status: 🟡 Partial (repo-side substantially complete; real-world rollout not) | Completion: 70%
Purpose: Assemble a versioned, checksummed, signed strategy bundle for Production import.
Current implementation: Major update since 07-01 (which found this entirely missing).
`svos/deployment/service.py` (628 lines) implements deterministic bundle creation, immutable
SHA-256 CAS artifact storage, append-only metadata records — tested.
Missing: Real cloud resource provisioning (GCS bucket/KMS key, IAM, workload identity) — adapters
exist and are unit-tested but not yet rehearsed against live infra.
Blocking issues: Owner-level cloud provisioning decisions remain.
Files: `svos/deployment/service.py`, `svos/adapters/artifacts.py`.

### Deployment Pipeline
Status: 🟡 Partial | Completion: 55%
Purpose: Move an approved package from SVOS to Production with disabled-by-default runtime staging.
Current implementation: `production/importer.py` (checksum-verified fetch/staging),
`production/verifier.py` (preflight verdicts), `production/activation.py`
(`STAGED_DISABLED`/`BLOCKED`, hard-blocks live activation), `production/summary.py`. Full CLI +
API + test coverage (12 files under `tests/production/`).
Missing: No actual remote VPS/GCP rollout, no systemd units on target hosts, no runtime execution
of an imported package — staging only.
Blocking issues: Real infra rollout explicitly out of repo scope pending owner action.
Files: `production/importer.py`, `production/verifier.py`, `production/activation.py`, `agtrade/cli.py`.

### Strategy Verification
Status: 🟡 Partial | Completion: 60%
Purpose: Verify an imported package's integrity before it may be staged; gate lifecycle
transitions on evidence.
Current implementation: `production/verifier.py` performs staged-archive verification,
required-file checks, manifest validation, signature-presence checks, emits JSON+Markdown
readiness artifacts. Directly answers the 07-01 "no checksum-verification gate" finding.
Missing: No verification has run against a real signed package produced by real cloud (KMS)
signing end-to-end.
Blocking issues: Same cloud-provisioning dependency as packaging.
Files: `production/verifier.py`, `svos/lifecycle/manager.py`.

### Package Signing
Status: 🟡 Partial | Completion: 55%
Purpose: Cryptographically sign the strategy package for Production authenticity/integrity verification.
Current implementation: `svos/deployment/service.py` implements 3 signing schemes:
`sha256-attestation` (fallback), `hmac-sha256`, and real `gcp-kms-asymmetric-sha256` via
Application Default Credentials.
Missing: No real KMS key has been provisioned/exercised end-to-end.
Blocking issues: Cloud KMS key/IAM provisioning (owner-level decision).
Files: `svos/deployment/service.py`, `infrastructure/google_cloud.py`.

### Multi-Agent / LLM Architecture
Status: 🟡 Partial (standalone, not pipeline-wired) | Completion: 35%
Purpose: Implements SVOS Phase 1 "Strategy Enhancement" — an LLM drafts a suggestion on an
audited spec; a human must accept it before any parameter change counts as evidence.
Current implementation: Three new, uncommitted, internally consistent files:
`config/llm.yaml` (provider disabled by default, DeepSeek config block, no literal key),
`svos/adapters/llm/` (narrow `LLMProvider` protocol + `DeepSeekProvider`, lazy-imports `openai`),
`svos/application/refinement.py` (`RefinementService.generate_draft()` — writes a draft
artifact + emits an `LLM_DRAFT_GENERATED` change-control event; never mutates
catalog/lifecycle/evidence).
Missing: `svos/application/pipeline.py`'s phase tuple has no REFINEMENT phase and does not import
`refinement.py` at all — **not wired into the pipeline**. Zero test coverage found for
`refinement.py`, the LLM adapters, or `build_provider`/`load_llm_config`. `openai` is installed in
the venv but not declared in any requirements file — a dependency-declaration gap that would
break on a fresh environment rebuild. `.env.example` doesn't document `DEEPSEEK_API_KEY` yet
(though `.env` itself does have the entry). `scratch_deepseek_test.py` at repo root is redundant
scratch dev residue, untracked but not gitignored.
Blocking issues: Currently unreachable from any CLI/orchestrator path — cannot yet contribute a
real Phase-1 draft to a strategy's lifecycle. No tests guard its "never mutates state" invariant.
Files: `config/llm.yaml`, `svos/adapters/llm/__init__.py`, `svos/adapters/llm/deepseek.py`,
`svos/application/refinement.py`, `scratch_deepseek_test.py`.

---

## D. Dashboards, Monitoring, Testing, Documentation

### Dashboard (general)
Status: 🟡 Partial | Completion: 45%
Purpose: Web UI surfaces for SVOS research state, live demo execution status, and operational control.
Current implementation: Three independent server processes (`dashboard/app.py`,
`dashboard/live_app.py`, `dashboard/status_server.py`) rather than one — self-documented as
"unconsolidated." A fourth frontend, `New Dashborad/` (React 19 + Vite + TS), is an active
migration, not abandoned, but its historical Express mock backend is dead code.
Missing: No single source of truth across the 3 backends; no auth on most read endpoints; no
WebSocket/SSE (30s polling only).
Blocking issues: A prior live audit found the deployed dashboard shows a stale system log
(~10h24m stale) and reads the wrong trades feed — "live" currently means HTTP 200, not data
freshness. An independent assessment concluded neither backend is production-ready as-is for a
Live Trading Dashboard.
Files: `dashboard/app.py`, `dashboard/live_app.py`, `dashboard/status_server.py`, `New Dashborad/`.

### Research Dashboard
Status: 🟡 Partial | Completion: 40%
Purpose: Visualize SVOS strategy lifecycle for research operators.
Current implementation: React SPA under `New Dashborad/src/components/` (Intake/Replay/Robustness/
VirtualDemo/Governance/Audit/Pipeline/Statistical/ExecutionSafety views) fed by
`dashboard/pipeline_service.py`/`strategy_service.py` and Flask routes.
Missing: Registry evidence counts are largely zero (every strategy shows 0 evidence/approvals
except one strategy's 3 decisions) — the UI has little real evidence to render yet. No typed API
client, no auth on mutation endpoints.
Blocking issues: None structural, but content-thin.
Files: `New Dashborad/src/App.tsx`, `dashboard/pipeline_service.py`, `dashboard/strategy_service.py`.

### Trading Dashboard
Status: 🟡 Partial | Completion: 50%
Purpose: Live operational view of the demo-mode Vantage execution runner.
Current implementation: `dashboard/status_server.py`, deployed and audited live. File-cache data
path only (no DB queries for most widgets). Confirmed real demo-broker account/candle data at
audit time.
Missing: No broker-freshness proof (never calls MetaAPI directly, only reads runner-written
cache); positions widget can't distinguish "zero positions" from "fetch failed"; pipeline cards
re-derive SMC analysis independently of the execution engine (duplicated, divergent logic).
Blocking issues: System-log selection bug picks a stale legacy log over the active one; Recent
Trades widget reads a stale journal file. Explicitly "not reliable enough for live-money
decisions" per the prior live audit's own verdict.
Files: `dashboard/status_server.py`, `scripts/run_st_a2_demo.py`.

### Analytics
Status: 🟡 Partial | Completion: 45%
Purpose: Statistical/quant analysis feeding backtest, robustness, and portfolio evidence.
Current implementation: Distributed across `strategy_validation/`, `svos/`, `production/reporting.py`,
plus one-off historical analyses under `reports/`.
Missing: No consolidated analytics/metrics DB queried by any dashboard; registry evidence counts
mostly zero.
Blocking issues: Analytics artifacts exist per-run as static Markdown, not as a queryable
cross-strategy layer.
Files: `strategy_validation/`, `production/reporting.py`, `reports/`.

### Reporting
Status: 🟡 Partial | Completion: 55%
Purpose: Generate governance/readiness/quality/testing reports feeding the Production Approval gate.
Current implementation: `scripts/generate_reports.py` plus per-domain report builders. Output
lands in `reports/` (51 markdown files) with a full subtree taxonomy (daily/weekly/monthly/
execution/risk/strategy/system_health/incidents/live_readiness) — mostly empty except
`reports/svos/` and `reports/change_control/`.
Missing: Most of the report-category directory scaffolding is unpopulated — the taxonomy exists
but isn't fed.
Blocking issues: An existing "APPROVED" production readiness report (2026-06-30) predates the
2026-07-01 gate tightening — it reflects an old, weaker gate and should not be read as current
Production Approval evidence.
Files: `scripts/generate_reports.py`, `reports/production_readiness_report.md`.

### Monitoring
Status: 🟡 Partial | Completion: 50%
Purpose: Runtime health tracking of the demo execution runner.
Current implementation: `monitoring/metrics.py` (`TradeJournal`), `monitoring/logging_utils.py`,
`monitoring/telegram.py`, consumed across `bot.py`, `run_st_a2_demo.py`, `trade_manager.py`.
Missing: No centralized health/metrics endpoint deployed live (`/api/health/summary`, `/metrics`
both 404 on the deployed status server).
Blocking issues: Loss-limit halt not wired to live close events (see Risk Management, same root cause).
Files: `monitoring/metrics.py`, `monitoring/telegram.py`.

### Alerting
Status: 🟡 Partial | Completion: 65%
Purpose: Push Telegram notifications for trade lifecycle, circuit breakers, emergency stops, connectivity.
Current implementation: `monitoring/telegram.py`'s `TelegramAlerter` is comprehensive — 15+ distinct
alert methods, wired into every execution entrypoint.
Missing: Not verified live in this pass whether alerts actually fire on the deployed VPS (would
require live credentials, out of audit scope); no alert dedupe/rate-limit review beyond code
presence.
Blocking issues: None found in code.
Files: `monitoring/telegram.py`.

### Testing
Status: 🟡 Partial | Completion: 70%
Purpose: Automated correctness/regression coverage across the platform.
Current implementation: 152 `test_*.py` files across 23 subdirectories. `pytest.ini` enforces
`--cov=svos --cov-fail-under=67`. **Verified this pass by running the full suite live**: 1509
passed, 8 failed, 4 skipped, completes in ~149s with no crash. The previously-documented
"native pandas crash blocks full run" is **no longer true** — current lockfiles pin
`pandas==2.3.3`, not the `3.0.4` that caused the earlier segfault.
Missing: CI runs only ~28% of test files (targeted subsets); `tests/core`, `tests/research_engine`,
`tests/adaptive_engine`, `tests/portfolio`, `tests/session_liquidity`, `tests/replay`,
`tests/shared`, `tests/scripts`, `tests/dashboard`, `tests/strategy_audit`,
`tests/strategy_validation`, `tests/readiness` never run in CI.
Blocking issues: 8 real failures exist — 1 in `tests/core` (never run in CI) and 7 in
`tests/svos/test_pipeline.py` (a real missing VIRTUAL_DEMO evidence gap, explicitly excluded from
CI rather than fixed).
Files: `pytest.ini`, `.github/workflows/ci.yml`, `tests/` (152 files).

### Documentation
Status: 🟡 Partial | Completion: 55%
Purpose: Govern strategy lifecycle vocabulary, architecture truth, and precedence across a large,
multi-contributor doc tree.
Current implementation: Severe sprawl, confirmed by direct count — **643 total `.md` files
repo-wide** (259 under `docs/`, 51 under `reports/`, 102 under `New Dashborad/`, 28 under
`docs/Archive/`, 20 root-level). `docs/00_Project/DOC_AUTHORITY.md` is a genuine, well-structured
precedence system (10-level authority table, canonical vocabulary mapping) — resolves precedence
in principle.
Missing: No enforcement of DOC_AUTHORITY's `Status:` header requirement across the corpus; the
readiness scanner still finds ~67 broken links and ~98 missing file refs; readiness-report trend
across generations is not a clean improvement (v3→v4: 84.4%→83.7%, a small regression on a
growing file count).
Blocking issues: Documentation gate (`DOC-001`) is the one non-passing dimension in
`reports/production_readiness_report.md` — explicitly non-blocking today but unresolved.
Files: `docs/00_Project/DOC_AUTHORITY.md`, `docs/documentation_readiness_report_v4.md`, `scripts/lint_docs.py`.

---

## Completion Summary by Group

| Group | Subsystems | Avg. completion |
|---|---:|---:|
| A — Infrastructure & Ops (excl. Redis N/A) | 13 | 57% |
| B — Execution & Trading (System 2) | 6 | 57% |
| C — SVOS Research Pipeline (System 1) | 10 | 63% |
| D — Dashboards/Monitoring/Testing/Docs | 9 | 53% |
| **Overall (38 rated subsystems)** | 38 | **~58%** |
