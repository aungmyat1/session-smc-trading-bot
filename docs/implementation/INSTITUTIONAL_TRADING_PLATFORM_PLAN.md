# Institutional Trading Platform Implementation Plan

## Summary

Consolidate the repository into one governed modular monolith with:

- One `agtrade` CLI
- One authenticated FastAPI backend
- One portfolio execution service and broker adapter
- PostgreSQL as the authoritative control plane
- Immutable, governance-issued deployment artifacts
- A deterministic, human-approved strategy factory
- Continuous performance and edge-decay monitoring
- Rule-based capital allocation
- Strict demo and micro-capital production gates

Live trading remains disabled until every preceding safety and evidence gate passes.

## Phase 0 — Complete Existing Stabilization Gate

1. Execute and document the encrypted backup/restore drill.
2. Declare and verify control-plane RPO/RTO.
3. Confirm all Alembic migrations on empty and adopted databases.
4. Run concurrency, atomicity, artifact-integrity, and restore tests.
5. Formally update the architecture verdict to `READY WITH IMPROVEMENTS`.
6. Keep all feature and live-trading work blocked until this phase passes.

Acceptance criteria:

- A restored database reproduces lifecycle, evidence, approvals, and outbox state.
- No decision, transition, or evidence record can be partially committed.
- PostgreSQL failure causes all control-plane mutations to fail closed.

## Phase 1 — Runtime and Repository Consolidation

### Canonical command surface

Create an installable `agtrade` console command:

```text
agtrade research ingest|build|sweep|status
agtrade strategy intake|validate|replay|backtest|robustness
agtrade governance review|approve|reject|revoke|status
agtrade execution paper|demo|live|stop|reconcile|status
agtrade reports generate|verify
agtrade admin migrate|backup|restore|health
```

Commands must call application services directly. Existing scripts become temporary compatibility wrappers that emit deprecation warnings and delegate to the same handlers.

### Repository cleanup

- Create and tag a permanent archive branch containing the current repository.
- Remove `archive/`, nested repository copies, prototypes, and superseded runbooks from the production branch after parity verification.
- Classify every partially used module as canonical, adapter, compatibility wrapper, or removable.
- Add architecture tests preventing imports from removed or legacy namespaces.
- Exclude experiments, data, credentials, logs, and generated artifacts from production packages.

### Runtime dependencies

- Add and lock FastAPI, Uvicorn, and required security dependencies.
- Separate runtime, research, dashboard, and development dependency groups.
- Require reproducible hashed installations and `pip check` in CI.

Acceptance criteria:

- Only `agtrade`, the API launcher, Alembic, and explicitly documented systemd workers are public entry points.
- Legacy commands produce equivalent outputs during their compatibility window.
- A clean locked environment starts every supported service.

## Phase 2 — Single API and Operator Surface

Make FastAPI the only backend. Migrate Flask and standalone status routes into versioned routers:

```text
/api/v1/strategies
/api/v1/runs
/api/v1/evidence
/api/v1/governance
/api/v1/deployments
/api/v1/execution
/api/v1/portfolio
/api/v1/monitoring
/api/v1/incidents
/api/v1/reports
/api/v1/admin
/health/live
/health/ready
/metrics
```

Requirements:

- Typed Pydantic request/response models and generated OpenAPI.
- Bearer authentication initially, with an OIDC-compatible identity boundary.
- Roles: `viewer`, `researcher`, `operator`, `approver`, `administrator`.
- Four-eyes approval for demo-to-live transitions.
- Idempotency keys for mutations and immutable actor identity.
- Restricted CORS, request-size limits, audit logging, and rate limits.
- Readiness fails when PostgreSQL, artifacts, migrations, or control state are unavailable.
- Serve the React dashboard as static assets or from a separate static web process; it may only call the FastAPI API.
- Retire the combined Flask app, standalone Flask live app, Express compatibility server, and duplicated emergency-control endpoints after route parity.

Acceptance criteria:

- Unauthorized or incorrectly authorized requests cannot mutate state.
- Every mutation creates an audit record and correlation ID.
- Dashboard actions cannot diverge from authoritative lifecycle state.
- Contract tests cover every endpoint and role combination.

## Phase 3 — Canonical Governance and Deployment Artifacts

Use `SVOSPlatform`, `GovernanceService`, and PostgreSQL repositories as the sole lifecycle authority.

Define an immutable deployment package containing:

```text
manifest.json
strategy_spec.json
parameters.json
risk_policy.json
dataset_manifest.json
validation_summary.json
execution_profile.json
artifact_checksums.json
approval.json
```

The manifest must identify:

- Strategy and version UUIDs
- Git commit and dependency-lock hash
- Configuration, dataset, and cost-model hashes
- Validation policy version
- Evidence and report IDs
- Allowed symbols, timeframes, mode, and account
- Risk limits and expiry
- Approver identities
- Artifact checksums

Execution accepts only a non-expired, non-revoked package authorized for the requested environment. YAML remains a generated read-only projection.

Fix the robustness integration so parameter sensitivity and regime analysis use the actual research function contracts. Errors must fail the robustness phase rather than become warnings.

Acceptance criteria:

- Hand-edited YAML cannot enable execution.
- Synthetic, stale, revoked, or mismatched evidence cannot qualify a strategy.
- Artifact modification, policy drift, or version mismatch blocks startup.
- Robustness requires successful walk-forward, Monte Carlo, sensitivity, and regime results.

## Phase 4 — Research Data and Reproducibility

Build the canonical research database through one ingestion pipeline:

```text
raw ticks/candles
→ normalized market data
→ sessions and structure
→ sweeps, order blocks, FVGs, displacement
→ strategy signals
→ simulated executions
→ trade outcomes
→ metrics and evidence
```

Requirements:

- Cover 2020 through the latest complete month for supported instruments.
- Partition by symbol and period with UTC timestamps and explicit price precision.
- Validate gaps, duplicates, ordering, session boundaries, outliers, and corporate/broker anomalies.
- Store source identity, ingestion version, schema version, and content hash.
- Produce immutable dataset snapshots for every qualification run.
- Standardize replay, backtest, metrics, and cost-model interfaces.
- Build a parity corpus before retiring duplicate replay/backtest implementations.
- Require deterministic seeds and golden quantitative fixtures.

Research qualification retains the stricter existing gate:

- At least 200 trades
- Profit factor ≥ 1.25
- Sharpe ≥ 1.2
- Maximum drawdown ≤ 15%
- Win rate ≥ 40%
- Reward/risk ≥ 1.5
- Positive expectancy
- Walk-forward, Monte Carlo, parameter stability, and regime gates passing

Acceptance criteria:

- A clean environment reproduces sampled results within declared numeric tolerances.
- All evidence traces to immutable code, configuration, cost model, and dataset versions.
- Duplicate engines are retired only after approved parity results.

## Phase 5 — One Execution Service

Refactor the multi-strategy portfolio runner into the sole execution service:

```text
governed deployment package
→ shared market-data feed
→ canonical strategy adapter
→ signal router
→ portfolio risk service
→ execution permission service
→ order state machine
→ broker adapter
→ event journal and reconciliation
```

Unify the ST-A2, D2-E3, portfolio, and legacy bot paths behind this service.

Requirements:

- One canonical order, fill, position, P&L, and execution-event model.
- Shared account-wide position and risk state across all strategies.
- Closed trades must update daily, weekly, and monthly loss limits.
- Restart-safe state reconstruction from broker state and the event journal.
- Idempotent order submission and duplicate-fill protection.
- Explicit handling for partial fills, rejection, slippage, latency, disconnect, reconnect, stale prices, and orphan positions.
- Research processes receive no broker credentials.
- `paper`, `demo`, and `live` use identical execution semantics; only the broker adapter and permission policy differ.
- Emergency stop is centralized, persistent, audited, and close-only capable.

Acceptance criteria:

- Failure-injection and restart tests produce no duplicate orders or orphan positions.
- Reconciliation reaches zero unexplained differences.
- One strategy cannot bypass account-wide risk through a separate process or magic number.
- No execution begins without a valid governance package.

## Phase 6 — Demo Qualification

Run only governance-approved strategies in broker demo.

Minimum live-eligibility gate:

- At least 30 consecutive calendar days
- At least 30 closed demo trades
- No critical safety incident
- No orphan position
- No unresolved reconciliation error
- Signal match ≥ 99%
- Missing-order rate ≤ 1%
- Slippage ≤ 0.5 pip where instrument-appropriate
- Demo/backtest profit-factor difference ≤ 0.10
- Positive realized expectancy
- Risk-limit, restart, reconnect, and emergency-stop drills passing
- No unresolved High/Critical security or governance findings

A calendar day with unavailable infrastructure does not count as a successful demo day. Any critical incident resets the consecutive-day counter after remediation and requalification.

Acceptance criteria:

- The demo evidence package contains broker events, latency, slippage, reconciliation, incidents, and drift analysis.
- Governance independently approves or rejects live eligibility.
- Completing 30 days/30 trades never causes automatic promotion.

## Phase 7 — Monitoring and Edge-Decay Control

Implement continuous expected-versus-realized monitoring by strategy, version, symbol, session, and regime.

Track:

- Profit factor, expectancy, win rate, drawdown, and return distribution
- Signal-to-order and order-to-fill conversion
- Slippage, latency, rejection, and missing-order rates
- Feature and regime distribution drift
- Broker connectivity and reconciliation health
- Evidence and approval freshness

Policy:

- Warn at the existing configured regression warning thresholds.
- Block new entries at configured fail thresholds.
- Critical safety or reconciliation failures trigger immediate block/close-only mode.
- A failure creates an incident and governed `REVALIDATION` transition.
- Recovery requires fresh evidence and approval; metrics cannot automatically re-enable trading.

Acceptance criteria:

- Simulated decay generates an alert, incident, execution block, and revalidation record.
- Every telemetry point links to strategy version, execution, deployment, and correlation IDs.
- Alerts and incidents are deduplicated and acknowledged through the API.

## Phase 8 — Deterministic Strategy Factory

Implement a bounded, reproducible experiment loop:

```text
approved strategy template
→ constrained parameter/rule variants
→ immutable experiment manifests
→ replay/backtest/robustness
→ out-of-sample comparison
→ ranking
→ human review
→ intake as a new version
```

Rules:

- Only approved templates and declared parameter ranges may generate variants.
- Holdout data remains inaccessible during generation and tuning.
- Correct for multiple testing and record rejected hypotheses.
- Rank by out-of-sample expectancy, robustness, drawdown, execution feasibility, and correlation—not raw return alone.
- Factory output is always `DRAFT`; it cannot approve, deploy, or trade.
- Limit concurrent experiments and compute budgets.
- Preserve full lineage from parent specification through every variant.

Acceptance criteria:

- Identical manifests produce identical variants and results.
- Holdout leakage and unregistered parameter changes fail validation.
- No factory-generated strategy can bypass intake or human approval.

## Phase 9 — Risk-Budget Capital Allocation

Introduce allocation only after at least two strategies independently pass production qualification.

The first allocator is deterministic:

- Eligibility requires current approval and fresh evidence.
- Base allocation derives from positive expectancy and approved drawdown.
- Reduce allocation for correlation, volatility, evidence age, and recent degradation.
- Enforce per-strategy, symbol, currency, correlation-group, and account caps.
- Rebalance weekly or immediately downward after risk deterioration.
- Upward changes require governance approval.
- No allocation is made when inputs are missing or stale.

Acceptance criteria:

- Property tests prove allocations never exceed account or concentration limits.
- A degraded or revoked strategy receives zero new risk.
- Correlated strategies cannot independently consume the full portfolio budget.
- Allocation decisions are reproducible and audited.

## Phase 10 — Controlled Production Activation

Activate one strategy on one dedicated account with:

- Maximum 0.10% risk per trade
- One open position initially
- Existing stricter daily, weekly, and monthly loss limits
- Manual four-eyes live approval
- Time-limited approval with revocation support
- Automated monitoring and reconciliation
- Immediate rollback to close-only or demo

Scaling requires a new approval after a defined observation window and may never be automatic. Multi-strategy production waits for successful single-strategy operation and the capital-allocation phase.

## Test and Release Gates

Every phase must add:

- Unit tests for domain rules
- Contract tests for CLI, API, schemas, and adapters
- PostgreSQL integration and migration tests
- Quantitative golden/parity tests
- Security and authorization tests
- Property tests for lifecycle and risk invariants
- Broker sandbox and deterministic failure-injection tests
- Backup, restore, restart, and disaster-recovery exercises
- End-to-end evidence-to-execution lineage tests

CI must enforce locked dependencies, Ruff, mypy on governed packages, security scanning, migration checks, documentation drift checks, and the repository’s approval thresholds. Releases use phased shadow → demo → live rollout with a documented rollback artifact.

## Assumptions and Fixed Decisions

- The existing stabilization roadmap and ADR authority remain in force.
- PostgreSQL 16 is authoritative; filesystem storage is content-addressed.
- The system remains a modular monolith rather than becoming microservices.
- FastAPI replaces Flask and Express backend surfaces.
- `agtrade` is the only public CLI.
- Archived code moves to a tagged archive branch after parity validation.
- The strategy factory is deterministic and human-gated; AI hypothesis generation is deferred.
- Demo eligibility uses the selected 30-day/30-trade minimum.
- Initial live activation is one strategy at 0.10% risk per trade.
- Capital allocation uses deterministic risk budgets; optimizer-based allocation is deferred.
- No architecture, test score, or elapsed time is treated as proof of profitability.
