# SVOS Current State Audit

Date: 2026-06-28

This audit reviews the active repository as an SVOS transitional platform and
evaluates it against the stated project direction:

> "Determine whether a trading strategy deserves capital through a governed,
> reproducible, evidence-based validation lifecycle."

The repository already contains substantial research, execution-validation, and
operational tooling. The main gap is not absence of code. The main gap is that
the code is still organized around a transitional, ST-A2-centric workflow
instead of a first-class institutional operating platform.

Audit scope:

- Active repository code and docs
- Non-archive packages and scripts
- Registry/config/governance paths
- Test suite status

Audit evidence highlights:

- Architecture source of truth: `docs/SYSTEM_ARCHITECTURE.md`
- Current implementation status: `docs/IMPLEMENTATION_STATUS.md`
- Strategy state source of truth: `config/strategy_catalog.yaml`
- Current SVOS orchestrator: `research/svos/engine.py`
- Current execution validation layer: `execution_validation/engine.py`
- Current registry implementation: `core/strategy_registry.py`
- Current dashboard/control surface: `dashboard/app.py`
- Test status at audit time: `1144 passed`

The active codebase contains roughly `360` non-archive Python files plus a
large operational/docs surface.

## 1. Current Architecture

The repository is currently a transitional architecture, not yet the target
`svos/` operating platform.

### Actual active layers

1. Governance and catalog layer
   - `config/strategy_catalog.yaml`
   - `core/strategy_registry.py`
   - `config/validation.yaml`
   - `config/strategy_change_pipeline.yaml`

2. Research qualification layer
   - `research/svos/`
   - `research/validation/`
   - `research/regression/`
   - `strategy_audit/`
   - `simulator/`
   - `strategy/`
   - `src/` research pipeline

3. Execution validation layer
   - `execution_validation/`
   - `execution_simulator/`
   - `execution_gate.py`
   - `virtual_broker/`

4. Runtime execution and demo operations layer
   - `execution/`
   - `adaptive/`
   - `strategies/`
   - `bot.py`
   - multiple `scripts/run_*demo*.py`

5. Monitoring and reporting layer
   - `dashboard/`
   - `monitoring/`
   - `scripts/generate_reports.py`
   - report-producing scripts under `scripts/`

6. Data and analytics layer
   - `src/data`, `src/features`, `src/backtest`, `src/analytics`
   - `research_db/`
   - `db/`
   - `data/`

### Architectural summary

The repository already behaves like a multi-layer validation platform, but the
layers are coupled through scripts, YAML files, and shared filesystem state
rather than through a dedicated backend package boundary such as:

```text
svos/
  lifecycle/
  registry/
  orchestration/
  governance/
  monitoring/
  deployment/
  experiments/
  reports/
  api/
  shared/
```

### Current lifecycle in code

The actual executable lifecycle is still closer to:

```text
research -> replay -> backtest -> walk_forward -> shadow -> demo -> live
```

This lifecycle is encoded in:

- `core/strategy_registry.py`
- `config/validation.yaml`
- `config/strategy_catalog.yaml`

At the same time, `docs/SYSTEM_ARCHITECTURE.md` defines a different target:

```text
SVOS -> EVF -> RGM -> Governance -> SMO
```

That mismatch is the central architectural issue in the repository.

## 2. Implemented Modules

### Research qualification

- Strategy text intake, audit, enhancement, and staged reporting in
  `research/svos/engine.py`
- Replay and backtest gate validation in `research/validation/engine.py`
- Regression comparison in `research/regression/engine.py`
- Auto-generated SVOS payload creation in `research/svos/payload_builder.py`
- Research queue orchestration in `research/research_queue.py`
- Rich strategy audit scoring in `strategy_audit/`
- Historical replay in `simulator/historical_replay.py`
- Session-liquidity strategy research implementation in `strategy/session_liquidity/`
- Research-grade modular pipeline in `src/`

### Execution qualification

- EVF orchestration in `execution_validation/engine.py`
- Rule pack loading and check model in `execution_validation/`
- Replay bridge into EVF in `execution_validation/replay_bridge.py`
- Broker/replay/risk simulation in `execution_simulator/`
- Deterministic execution gate in `execution_gate.py`
- Virtual broker implementation in `virtual_broker/`

### Governance and lifecycle metadata

- Strategy catalog persistence in `core/strategy_registry.py`
- Promotion logic in `research/validation/engine.py`
- Current-strategy workflows in:
  - `scripts/run_current_strategy_svos.py`
  - `scripts/run_current_strategy_validation.py`

### Monitoring, reporting, operator control

- Dashboard API and control surface in `dashboard/app.py`
- Dashboard runtime/control-state/report services in `dashboard/`
- Telegram/metrics helpers in `monitoring/`
- Read-only report generation in `scripts/generate_reports.py`
- Health checks in `scripts/health_check.py` and related scripts

### Deployment and runtime operations

- MT5/MetaAPI execution adapters in `execution/`
- Demo/shadow runtime in `adaptive/`
- Portfolio adapter layer in `strategies/adapters/`
- VM deployment assets in `deploy/gcp-vm1/`

### Data and storage

- Feature database build path in `run_pipeline.py` and `src/research_feature_database.py`
- DuckDB analytics in `src/analytics/duckdb_store.py`
- PostgreSQL normalization helpers in `db/runtime.py`
- Research DB artifacts under `research_db/`

## 3. Missing Modules

The target operating-system layer is still missing as a first-class package.

### Missing backend packages

- `svos/lifecycle/`
  - No dedicated lifecycle manager for the new institutional stage model
- `svos/registry/`
  - No domain-level strategy registry service with rich strategy metadata,
    lineage, evidence references, approvals, and parent-child relationships
- `svos/orchestration/`
  - No unified orchestration service coordinating research, EVF, governance,
    reporting, and monitoring workflows
- `svos/deployment/`
  - No deployment orchestration service separate from execution scripts
- `svos/governance/`
  - No independent governance control plane with approvals, attestations,
    stage gates, and policy enforcement
- `svos/monitoring/`
  - No dedicated SMO backend service for production drift and revalidation
- `svos/experiments/`
  - No first-class experiment manager spanning research runs and evidence
    lineage
- `svos/reports/`
  - No report domain service with normalized report metadata and retrieval
- `svos/notifications/`
  - No central notifications/event bus layer
- `svos/api/`
  - No backend API package wrapping lifecycle, registry, governance, and
    orchestration services
- `svos/shared/`
  - No shared domain model package for stage enums, IDs, evidence records,
    lineage, approvals, and event schemas

### Missing functional capabilities

- Institutional lifecycle state machine for the requested stages:
  - `DRAFT -> INTAKE -> AUDIT -> REFINEMENT -> HISTORICAL_REPLAY -> ... -> RETIRED`
- Illegal transition rejection based on the requested lifecycle
- Strategy parent/child lineage model
- Governed experiment registry
- Central operational event model
- Unified evidence store
- First-class deployment approval workflow
- Separate RGM qualification backend
- Separate SMO monitoring and revalidation backend

## 4. Broken Integrations

There are no obvious repository-wide runtime breakages in the active codebase.
The full test suite passed during this audit.

However, there are important broken architectural integrations between intended
modules and current implementation boundaries.

### Architecture-to-code breaks

1. SVOS still owns EVF-adjacent stages
   - `research/svos/engine.py` still includes `virtual_demo` and
     `production_approval` behavior for backward compatibility.
   - This conflicts with the target separation in `docs/SYSTEM_ARCHITECTURE.md`.

2. Registry lifecycle does not match target lifecycle
   - `core/strategy_registry.py` and `config/validation.yaml` use
     `draft/research/replay/backtest/walk_forward/shadow/demo/live/retired`.
   - The project brief requires a much more granular institutional lifecycle.

3. Dashboard panels imply independent services that do not yet exist
   - `dashboard/app.py` exposes SVOS, EVF, RGM, Governance, and SMO panels.
   - RGM and SMO are mostly synthesized from config, logs, and health checks,
     not backed by distinct backend service packages.

4. Research orchestration is script-driven rather than service-driven
   - `research/research_queue.py`
   - `config/strategy_change_pipeline.yaml`
   - `scripts/run_*`
   - These bypass a central lifecycle/orchestration domain.

5. The newer `src/` research pipeline is not fully unified with SVOS orchestration
   - `run_pipeline.py` and `src/` build the feature database.
   - `research/svos/payload_builder.py` still depends on older replay/backtest
     flows and script execution.

### Objective-to-implementation breaks

1. Older live-bot objective docs still exist
   - `docs/PROJECT_OBJECTIVE_FASTEST_PATH.md` remains centered on deploying
     ST-A2 as a live bot.
   - This is inconsistent with the current repository mission.

2. ST-A2-specific runtime remains the operational default
   - Many scripts, journals, comments, and execution paths remain strategy-
     specific rather than strategy-agnostic.

## 5. Duplicated Functionality

The repository has significant parallel implementations.

### Strategy logic duplication

- `strategy/session_liquidity/`
- `session_smc/`
- `adaptive/strategies/`
- `strategies/adapters/`

These represent overlapping strategy-definition, runtime, and adapter layers.

### Broker and execution simulation duplication

- `virtual_broker/`
- `execution_simulator/`
- `execution/`
- parts of `adaptive/execution/`

Some of this is legitimate layering, but naming and boundaries are not yet
clear enough to prevent overlap.

### Research/data pipeline duplication

- `src/`
- `research_db/`
- `pipeline/`
- `session_smc/`
- script-based historical replay/backtest flows in `scripts/`

The codebase contains both a newer modular research pipeline and older direct
script pipelines.

### Governance and readiness duplication

- `core/strategy_registry.py`
- `research/validation/engine.py`
- `research/svos/engine.py`
- `strategy_audit/deployment_gate.py`
- dashboard readiness surfaces

Promotion/readiness logic exists in more than one place.

### Reporting duplication

- `dashboard/report_service.py`
- `scripts/generate_reports.py`
- multiple Markdown-generating scripts
- manually maintained docs and reports

## 6. Architecture Inconsistencies

1. The repository name and older docs still imply "trading bot" first, while
   the newer architecture positions the project as a governed validation OS.

2. The authoritative architecture says governance is an independent control
   plane, but promotion is still mostly embedded in validation and registry
   code.

3. The target design separates SVOS, EVF, RGM, Governance, and SMO, but the
   current implementation still uses a mostly linear transitional flow.

4. `README.md`, `docs/SYSTEM_ARCHITECTURE.md`, and
   `docs/PROJECT_OBJECTIVE_FASTEST_PATH.md` describe different operating
   assumptions.

5. The `src/` research engine is modular and reusable, while many operational
   scripts remain imperative and strategy-specific.

6. The dashboard presents institutional components, but the backend model is
   still file-oriented rather than service-oriented.

7. The catalog is the current state authority, but several scripts also encode
   lifecycle meaning in CLI defaults, YAML maps, and report-generation logic.

## 7. Technical Debt

### Structural debt

- Heavy reliance on scripts as the orchestration layer
- Filesystem and YAML used as the primary integration contract
- Lack of a single domain model for strategy state, evidence, approval, and
  revalidation
- Transitional compatibility logic embedded in core flows

### Product debt

- ST-A2-specific defaults across execution, reporting, logs, and comments
- Operational behavior spread across docs, scripts, config, and code
- Missing unified backend package for platform responsibilities

### Codebase debt

- Multiple generations of architecture coexisting
- Large script surface area (`48` active scripts)
- Parallel implementations across `strategy`, `strategies`, `session_smc`,
  `adaptive`, and `src`
- Limited normalization of report metadata and evidence artifacts

### Documentation debt

- Strong architecture docs exist, but not all older docs have been brought into
  alignment
- Legacy "live bot" documents are still easy to treat as mission-defining

## 8. Dependency Graph

The following graph summarizes active first-party package dependencies in the
non-archive codebase.

```text
dashboard -> scripts
scripts -> core, db, execution, execution_simulator, execution_validation, research, research_db, session_smc, simulator, src, strategies, strategy

research -> core, execution_validation, scripts, session_smc, simulator, strategy
execution_validation -> execution_events, execution_gate, execution_simulator, models, research, simulator
execution_simulator -> core, execution, execution_events
execution -> core

strategy_audit -> data, execution, models, monitoring, research
strategies -> adaptive, core, strategy
adaptive -> data, execution, strategy
simulator -> strategy
session_smc -> strategies

run_pipeline -> src
research_db -> research
pipeline -> config, db, session_smc
virtual_broker -> execution_simulator
```

### High-level dependency interpretation

```text
config/catalog
    ->
core registry
    ->
research / validation / svos
    ->
execution_validation / execution_simulator
    ->
dashboard / reports / scripts
```

### Dependency observations

- `scripts/` is the largest orchestration hub.
- `research/` is the main integration hub for current validation workflows.
- `execution_validation/` already has enough substance to become a clean EVF
  backend boundary.
- `dashboard/` depends on scripts and filesystem artifacts more than on stable
  service interfaces.

## 9. Data Flow Diagram

### Current data flow

```text
Strategy spec docs / catalog metadata
        ->
core.strategy_registry
        ->
research.svos.engine
        ->
research.svos.payload_builder
        ->
historical data / replay / backtest / robustness
        ->
research.validation + research.regression
        ->
execution_validation + execution_simulator
        ->
JSON / Markdown reports + catalog updates
        ->
dashboard + report generation + operator scripts
```

### Expanded operational view

```text
docs/strategy specs
config/strategy_catalog.yaml
config/*.yaml
        ->
SVOS orchestration scripts
        ->
research engines and replay/backtest pipelines
        ->
validation artifacts
        ->
catalog promotion metadata
        ->
execution validation artifacts
        ->
logs / journals / reports
        ->
dashboard API and operator reports
```

### Key data stores

- YAML config and registry files under `config/`
- historical and processed market data under `data/`
- feature database outputs under `research_db/`
- JSON/Markdown reports under `reports/`
- execution validation reports under `execution_validation/reports/`
- runtime logs and journals under `logs/`

## 10. Recommended Implementation Order

The next work should unify existing modules into the new backend package rather
than rewriting validation math or adding new trading logic.

### Phase 1: Establish SVOS backend domain

1. Create `svos/shared/` with core domain types
   - strategy IDs
   - lifecycle stage enum
   - approval record
   - evidence reference
   - event/envelope types

2. Create `svos/lifecycle/`
   - implement the requested institutional lifecycle state machine
   - validate legal and illegal transitions
   - keep current registry statuses readable through an adapter layer

3. Create `svos/registry/`
   - wrap `config/strategy_catalog.yaml`
   - add richer strategy metadata model
   - support parent strategy, owner, lineage, evidence refs, and stage history

### Phase 2: Unify orchestration and governance

4. Create `svos/orchestration/`
   - centralize current script-driven workflows
   - orchestrate research, EVF, reporting, and revalidation as services

5. Create `svos/governance/`
   - move promotion policy out of scattered script/config code
   - treat approvals and stage gates as explicit governance actions

### Phase 3: Separate institutional operating modules

6. Create `svos/experiments/`, `svos/reports/`, and `svos/notifications/`
   - normalize experiment tracking
   - normalize report metadata
   - emit events for approvals, failures, and revalidation triggers

7. Create `svos/deployment/` and `svos/monitoring/`
   - separate deployment orchestration from execution scripts
   - separate SMO monitoring from dashboard-only synthesis

8. Add `svos/api/`
   - expose backend services to the dashboard
   - make the dashboard consume stable APIs instead of directly inferring state
     from files and scripts

### Phase 4: Migrate existing code without breaking math

9. Adapt existing modules rather than rewriting them
   - reuse `research/svos`, `research/validation`, `research/regression`,
     `execution_validation`, `execution_simulator`, and `strategy_audit`
   - do not change validation mathematics during the platform migration

10. Decommission duplicate paths gradually
   - reduce overlap between `src`, `strategy`, `session_smc`, `adaptive`,
     `virtual_broker`, and script-based orchestration

## Bottom Line

The repository already contains most of the building blocks needed for an SVOS
operational platform.

What is missing is the operating-system layer itself:

- one lifecycle model
- one registry service
- one governance control plane
- one orchestration backend
- one monitoring/revalidation backend

The correct next move is to build `svos/` as an integration and control layer
over the existing validated modules, not to build more strategy logic and not
to alter the existing research/validation mathematics.
