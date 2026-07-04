# Strategy Engineering Platform Implementation Plan

Date: 2026-06-29
Status: Authoritative
Version: 1.1
Updated: 2026-07-03
Owner: Platform Lead
Authority: Level 2 — Product Implementation Plan
Supersedes: CURRENT_SCOPE.md, IMPLEMENTATION_STATUS.md, ESTIMATED_DEVELOPMENT_ROADMAP.md (all archived)

Governing scope: `docs/00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md`. This plan
implements that truth and may not broaden Production beyond the simple execution
chain or combine Backtest with Statistical Validation.

Current readiness: **SYSTEM 2 STABILIZATION — LIVE DISABLED**

Owner priority amendment (2026-07-03): complete System 2 controlled demo/paper
readiness before continuing System 1 platform construction. This changes delivery
order, not system ownership: System 1 still produces approved packages and System
2 still only verifies and executes them.

Implementation prerequisites and reusable-component inventory:
`docs/svos/PLATFORM_IMPLEMENTATION_REQUIREMENTS.md`.

Approved two-node infrastructure boundary and migration rules:
`docs/svos/DEPLOYMENT_TOPOLOGY.md`.

## 1. Product Objective

Build a strategy-agnostic **Strategy Engineering Platform** for systematic
Forex strategies, with an offline Virtual Demo engine and a deliberately simple
Vantage execution bot.

The platform accepts a strategy idea or specification and produces one of two
honest outcomes:

- a versioned, evidence-backed **Production Approval strategy package**; or
- a rejected or blocked strategy with findings, evidence, and a remediation
  route.

The trading bot is the first implementation priority. It remains a downstream
runtime that may load only a valid Production Approval package; signed synthetic
fixtures may be used only for offline/demo readiness tests and are never approval
evidence.

```text
Strategy Input
  -> Specification and Versioning
  -> Strategy Audit and Refinement
  -> Historical Replay
  -> Backtest
  -> Statistical Validation
  -> Robustness Validation
  -> Offline Virtual Demo
  -> Production Approval
  -> Approved Strategy Package
  -> Simple Vantage Forex Bot
  -> Monitoring and Revalidation
```

### Product boundaries

- The platform supports new strategies through contracts and adapters; its
  architecture must not encode ST-A2 assumptions.
- “Any strategy” means any systematic Forex strategy that can provide an
  objective specification, required data declaration, executable adapter, and
  measurable qualification policy.
- Virtual Demo is accelerated historical replay through the same order, risk,
  and position-management interfaces intended for the bot. It does not connect
  to a broker or wait for real market time.
- Production Approval authorizes packaging, not automatic deployment.
- Vantage is the first broker target, but broker-specific behavior remains
  behind an execution adapter.
- `LIVE_TRADING=false` and `DEMO_ONLY=true` remain enforced during platform
  construction. No agent may enable live trading.

## 2. ST-A2 Reset and Preservation

ST-A2 is deferred for later revalidation. It is not deleted and is not treated
as current evidence for platform readiness.

### Cleanup policy

- Mark ST-A2 `DEFERRED_REVALIDATION`, `approved: false`, `current: false`, and
  remove its execution deployment target when lifecycle mutation is routed
  through the new authority.
- Start the platform with no current strategy and no strategy authorized for
  broker execution.
- Preserve ST-A2 specifications, code, datasets, reports, and historical
  findings as legacy research material.
- Import existing ST-A2 evidence with `LEGACY_IMPORTED` or `SYNTHETIC` trust;
  it cannot satisfy a qualification gate.
- Remove ST-A2 names and paths from generic defaults, report generators,
  dashboard assumptions, health checks, and platform tests.
- Retain strategy-specific implementation and regression tests until the new
  adapter contracts have parity coverage. Archive superseded operational
  scripts and documents only after dependency analysis; do not delete them.
- Reintroduce ST-A2 later as an ordinary new strategy version entering at
  Intake and passing the complete pipeline from zero.

## 3. Canonical Platform Architecture

Implement a Python 3.12 modular monolith under the `svos` namespace.

```text
svos/
  domain/          strategies, versions, lifecycle, policies, evidence
  application/     intake, qualification, approval, packaging, revalidation
  ports/           persistence, data, engines, artifacts, execution
  adapters/        PostgreSQL, DuckDB/Parquet, filesystem, Vantage
  interfaces/      CLI, HTTP API, workers
  reports/         schemas, builders, renderers, index and evidence bindings
```

Dependencies point inward. Domain code cannot import Flask, scripts, broker
SDKs, SQLAlchemy models, or concrete filesystem paths.

### 3.1 Strategy contracts

Every strategy version supplies:

- immutable strategy ID, semantic version, parent version, owner, and hash;
- instruments, timeframes, sessions, and required data;
- objective entry, confirmation, invalidation, exit, and risk rules;
- typed parameters with units, bounds, and defaults;
- executable strategy adapter identifier and code hash;
- declared metrics and qualification-policy version.

AI may propose a new draft and remediation notes. A human must accept the draft
before it becomes the version evaluated by Audit.

### 3.2 Lifecycle and mutation authority

Use one lifecycle vocabulary and one `LifecycleAuthority`. No other module may
change strategy state.

Required transition inputs:

- strategy version ID;
- from/to stage;
- actor and reason;
- qualification-policy version;
- current-state revision;
- qualifying evidence IDs.

The authority validates transition legality, evidence trust, evidence currency,
and approval requirements before committing the decision and state atomically.
Direct catalog updates and legacy promotion helpers are prohibited by an
architecture test.

### 3.3 Persistence and artifacts

- PostgreSQL 16 is authoritative for strategies, versions, stage state, runs,
  decisions, evidence metadata, approvals, packages, and deployments.
- Alembic owns all relational migrations.
- Parquet stores frozen market and feature datasets; DuckDB provides local
  analytical queries.
- Large report and evidence bodies use content-addressed filesystem storage
  initially, with an S3-compatible adapter later.
- YAML is a generated read-only compatibility projection, never a mutation
  fallback.
- SQLite is allowed only for isolated simulation and must export canonical
  events and evidence.

### 3.4 Reproducible run manifest

Every replay, backtest, robustness, and Virtual Demo run records:

- strategy specification and executable code hashes;
- full Git commit and dirty-tree state;
- hashed dependency lock;
- configuration and policy hashes;
- dataset snapshot ID plus input hashes, row counts, and time range;
- cost-model ID, source, values, and measurement window;
- deterministic seed, UTC timezone, engine version, and timestamps.

A missing or inconsistent manifest makes a run `BLOCKED`; it cannot produce
qualifying evidence.

## 4. Qualification Pipeline

### Stage 0 — Intake

- Validate file format, identity, ownership, instruments, timeframes, and data
  availability.
- Create the immutable initial version and intake report.
- Reject empty, non-systematic, or unversionable inputs.

### Stage 1 — Strategy Audit and Refinement

- Extract and normalize rules.
- Check completeness, ambiguity, contradictions, measurability, risk controls,
  execution feasibility, and lookahead risk.
- Treat explicit long/short branches as valid branching, not contradictory
  logic.
- AI generates a separate draft only; failed audit loops back after human
  acceptance of a new version.

### Stage 2 — Historical Replay

- Feed frozen candles or ticks chronologically without future access.
- Record state transitions, expected and actual signals, skipped setups, and
  traceable rule decisions.
- Fail on missing data, temporal violations, invalid order geometry, or signal
  disagreement outside policy tolerance.

### Stage 3 — Backtest

- Use the replay-approved strategy version and frozen dataset.
- Apply spread and commission; a result without costs is invalid.
- Produce immutable performance measurements for the Statistical Validation
  stage; Backtest does not approve its own output.

### Stage 4 — Statistical Validation

- Canonical Phase-0 minimum: `n >= 50` and net PF strictly above `1.0` at both
  standard and 2x cost stress, plus policy-defined expectancy and drawdown
  limits.
- Preserve genuine failed results. Parameter changes create a new version/run;
  no mid-trial tuning is permitted.

### Stage 5 — Robustness Validation

- Run walk-forward, parameter stability, regime slices, Monte Carlo/bootstrap,
  and execution-cost sensitivity.
- Record stable regions and failure boundaries rather than only a summary
  score.
- Invalidate this and all downstream evidence when relevant code, data,
  parameters, policy, or costs change.

### Stage 6 — Offline Virtual Demo

- Reuse the bot-facing signal, order, risk, and position interfaces.
- Replay sequential market events with deterministic spread, commission,
  slippage, latency, rejection, partial-fill, disconnect, restart, and duplicate
  scenarios.
- Compare expected backtest behavior with simulated execution and report drift.
- No Vantage credentials or network access are available to this worker.

### Stage 7 — Production Approval

- Require current PASS evidence from every prior hard gate.
- Require matching strategy, code, policy, dataset, and cost-model lineage.
- Produce an approval decision and immutable Approved Strategy Package.
- Missing, failed, blocked, stale, synthetic, or legacy-imported evidence denies
  approval.

### Approved Strategy Package

The downstream bot consumes one signed package containing:

- strategy and version IDs;
- strategy adapter and code hash;
- immutable parameters and supported instruments/timeframes;
- risk and execution policies;
- qualification certificate and evidence hashes;
- package schema/version, issue/expiry dates, and revocation status.

The bot validates the package at startup and before every order. It rejects an
unknown, expired, revoked, altered, or unapproved package.

## 5. Canonical Report System

Reporting is a core platform subsystem, not presentation added after testing.
Reports explain how evidence was produced, why a gate passed or failed, and
what must happen next.

### 5.1 Current-system assessment

Keep and extend:

- paired canonical JSON and Markdown stage reports;
- immutable run directories;
- hard-gate results, findings, remediation, evidence hashes, version comparison,
  run summaries, failure analysis, improvement reports, and final qualification;
- read-only report generation that never contacts a broker.

Consolidate or replace:

- the six-stage report schema that does not represent Intake, Refinement, or the
  full operational lifecycle;
- duplicate indexes under `data/svos/reports` and `reports/index.json`;
- compatibility reports under `reports/current_strategy_svos`;
- path-derived report identity;
- recurring report generators tied to ST-A2 log filenames and catalog state;
- Markdown-only operating reports that cannot serve as machine evidence.

### 5.2 Report principles

- JSON is the automation and evidence source of truth.
- Markdown is a deterministic human-readable rendering of the same JSON.
- Every JSON/Markdown pair shares a report ID and content relationship.
- Every report is immutable, schema-versioned, content-hashed, and bound to a
  strategy version and run manifest.
- Reports never mutate lifecycle state. Governance evaluates structured
  evidence and records a separate decision.
- `PASS`, `FAIL`, `BLOCKED`, `IN_PROGRESS`, `NOT_RUN`, and `INVALIDATED` have
  distinct meanings.
- Downstream stages become `BLOCKED` after the first failed or blocked hard
  gate; they are never silently omitted.
- Regenerating Markdown cannot change the underlying decision or evidence.

### 5.3 Report domain model

Add canonical records:

- `ReportRecord`: ID, schema version, type, strategy/version/run/stage, status,
  generator version, JSON artifact, Markdown artifact, hashes, created time;
- `EvidenceRecord`: evidence type, trust, validity, dependency hashes, metrics,
  source artifact IDs;
- `GateDecisionRecord`: policy version, evaluated evidence, checks, blockers,
  decision, actor, time;
- `QualificationCertificate`: completed gates, evidence hashes, package hash,
  validity and revocation state.

Trust values:

- `QUALIFYING_REAL`;
- `SYNTHETIC`;
- `LEGACY_IMPORTED`;
- `INVALIDATED`.

Only current `QUALIFYING_REAL` evidence can satisfy Production Approval.

### 5.4 Required report set

Every pipeline run produces:

```text
reports/svos/<strategy-id>/<version>/<run-id>/
  run_manifest.json
  run_summary.json
  run_summary.md
  00_intake.json / .md
  01_strategy_audit.json / .md
  02_refinement.json / .md        # when refinement is required
  03_historical_replay.json / .md
  04_backtest.json / .md
  05_robustness.json / .md
  06_virtual_demo.json / .md
  07_production_approval.json / .md
  strategy_summary.json / .md
  strategy_evolution.json / .md
  version_comparison.json / .md
  failure_analysis.json / .md
  improvement_report.json / .md
  final_qualification.json / .md
  approved_strategy_package.json  # only after approval
```

Stage reports contain:

- identity, objective, scope, inputs, dependency hashes, and policy;
- checks and thresholds;
- metrics with units and sample windows;
- findings with severity and evidence references;
- PASS/FAIL/BLOCKED decision and promotion eligibility;
- remediation route and next action;
- prior-version comparison and appendices.

### 5.5 Platform and bot operating reports

Keep these separate from qualification evidence:

- dataset/data-quality report;
- research-run health and reproducibility report;
- strategy portfolio/registry report;
- Virtual Demo execution-quality report;
- Vantage bot daily execution report;
- runtime risk report;
- system health and recovery report;
- incident report;
- drift and revalidation report;
- deployment readiness report.

Operating reports also use JSON plus Markdown, but they cannot retroactively
change qualification evidence.

### 5.6 Report storage and indexing

- PostgreSQL stores report metadata and evidence relationships.
- Content-addressed artifact storage holds immutable JSON and Markdown bodies.
- One report index service queries PostgreSQL; filesystem scanning remains a
  temporary compatibility adapter only.
- Supported filters: strategy, version, run, stage, type, status, trust,
  validity, and time range.
- “Latest” always means latest valid report for a specific strategy version and
  report type, never filesystem modification time alone.
- Compatibility paths remain read-only until the dashboard migrates, then are
  retired.

### 5.7 Report interfaces

Provide read-oriented APIs:

- list/filter reports;
- retrieve JSON or rendered Markdown;
- retrieve complete run package;
- retrieve active blocker and remediation route;
- retrieve evidence lineage and version comparison;
- verify artifact/package hashes.

Stage completion emits an internal report-generation command. Manual rebuild is
allowed only for deterministic Markdown or indexes; it cannot replace canonical
JSON evidence.

## 6. Simple Vantage Trading Bot

The bot has only five responsibilities:

1. validate and load one Approved Strategy Package;
2. obtain Forex market data through the Vantage adapter;
3. invoke the packaged strategy adapter;
4. enforce packaged risk/order policies and submit/manage orders;
5. emit canonical execution events for reports, monitoring, and revalidation.

The bot does not audit, backtest, optimize, approve, or edit strategies. Broker
credentials are unavailable to research, reporting, and dashboard processes.

## 7. Delivery Sequence

### Wave 1 — System 2 controlled demo readiness

Implement in this order:

1. canonical Approved Strategy Package loading and per-order revalidation;
2. exclusive Single Runtime Authority and duplicate-process rejection;
3. one Canonical Execution Pipeline for intent, risk, adapter, result, and event;
4. demo/paper execution adapter with no real-capital path;
5. fail-closed risk firewall and one-position-per-symbol enforcement;
6. durable trade journal, decision events, and reconciliation state;
7. read-only runtime dashboard status for package, runtime, orders, risk, health,
   incidents, and recovery;
8. safety, restart, rejection, idempotency, and architecture tests.

System 2 reaches **STABLE DEMO READY** only when it can start from a valid signed
fixture package, reject invalid packages and duplicate runtime owners, enforce
risk before every order, execute paper/demo orders through the canonical adapter,
journal every decision, recover safely, and expose truthful dashboard status.

This wave must not implement or modify System 1 replay, backtest, optimization,
robustness, strategy enhancement, or approval behavior.

### Wave 2 — System 1 continuation

After the System 2 gate passes:

- complete transactional registry, evidence, reports, and lifecycle authority;
- implement strategy specification, audit/refinement, historical replay,
  backtest, Statistical Validation, robustness, and offline Virtual Demo;
- preserve net-of-fees gates and immutable trial registration;
- produce signed Approved Strategy Packages only from current qualifying evidence;
- prove synthetic, demo-readiness, and legacy evidence cannot approve a strategy.

### Wave 3 — Approved package handoff

- System 1 publishes an approved, signed, immutable package;
- System 2 verifies identity, signature, code/policy hashes, expiry, and revocation;
- controlled broker-demo observation begins only after its separate execution gate;
- real-capital live trading remains disabled pending explicit owner authorization.

### Deferred until System 2 is stable and System 1 is approval-capable

- OIDC/RBAC and multi-user workflows;
- four-eyes approval;
- S3 deployment;
- additional brokers;
- multi-tenant UI expansion;
- production capital scaling.

Deferral never permits broker demo or live execution without the missing gates.

## 8. Test and Acceptance Plan

### Core tests

- lifecycle legality and failure loops;
- exclusive mutation authority and optimistic concurrency;
- immutable versioning and dependency-aware invalidation;
- database migration/import/projection integrity;
- fail-closed behavior when state, DB, evidence, or policy is unavailable.

### Research tests

- strategy-neutral intake and audit;
- explicit long/short branch parsing;
- lookahead prevention and chronological replay;
- deterministic backtests and net-of-fees gate boundaries;
- robustness reproducibility and honest failure preservation;
- sample, synthetic, and legacy evidence rejection.

### Report-system tests

- JSON Schema validation for every report type and status;
- deterministic JSON-to-Markdown rendering;
- immutable hash verification and tamper detection;
- correct strategy/version/run/stage linkage;
- downstream BLOCKED report creation after a hard-gate failure;
- invalidation without deletion;
- version comparison, failure analysis, remediation, and final qualification;
- approved package emitted only after all qualifying reports pass;
- one index returns correct filtered/latest-valid results;
- report generation performs no broker or lifecycle mutation;
- compatibility views match canonical reports during migration;
- generators contain no ST-A2-specific paths or assumptions.

### Virtual Demo and bot tests

- same order/risk interface used offline and by the Vantage adapter;
- spread, commission, slippage, latency, rejection, partial-fill, disconnect,
  restart, duplicate-order, and idempotency scenarios;
- startup/order rejection for missing, altered, expired, revoked, stale, or
  unapproved packages;
- broker credentials absent from research and reporting workers.

### Release gates

- Existing 1,170 tests remain green throughout migration.
- Each phase adds focused unit, integration, architecture, and failure tests.
- CI enforces pytest, schema validation, migration checks, type/lint checks,
  dependency/secret scanning, and `git diff --check`.
- The platform becomes **RESEARCH CAPABLE** only when a new non-ST-A2 strategy
  can enter Intake and produce reproducible PASS or honest FAIL evidence.
- It becomes **APPROVAL CAPABLE** only when Virtual Demo and package generation
  pass with real, current evidence.
- It becomes **BOT CAPABLE** only when the simple Vantage bot demonstrably
  refuses every strategy lacking a valid Approved Strategy Package.

## 9. Immediate Implementation Boundary

Work only on System 2 Wave 1 until the stable demo-readiness gate passes. Do not
mix System 1 replay, backtest, optimization, robustness, or approval changes into
System 2 stabilization changes.

Broker execution stays controlled demo/paper only. Do not enable real-capital
trading, change `LIVE_TRADING=false`, change `DEMO_ONLY=true`, promote a strategy,
or treat a signed test fixture as Production Approval.

## 2026-07-01 implementation note

The current file-based SVOS path still has an enforcement gap: `svos/lifecycle/manager.py`
is a topology validator and lifecycle vocabulary authority, but it does not enforce
evidence gates against `data/svos/registry/*/state.json`. Qualifying-evidence enforcement
exists today only in the PostgreSQL control-plane path through
`db/control_plane.py::_validate_evidence()`. See the 2026-07-01 governance-gap entry in
`docs/VERDICT_LOG.md` for the tracked live-demo consequence of that split.
