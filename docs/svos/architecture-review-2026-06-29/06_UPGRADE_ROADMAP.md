# Upgrade Roadmap

Feature development remains paused through Phase 2. Each phase is deliberately
bounded; do not run all phases in parallel.

## Phase 0 — Authority freeze and decisions (Critical)

Objectives:

- prevent new lifecycle mutation paths;
- establish architectural authority and ownership.

Deliverables:

- ADRs for canonical lifecycle, persistence, artifact storage, identity,
  timestamps/precision, and package boundaries;
- inventory of every caller that mutates catalog/status/approval;
- deprecation map for legacy packages and nested repository;
- architecture test that initially records, then blocks forbidden imports and
  direct promotion calls.

Dependencies: none.

Success criteria:

- one named lifecycle API and one stage vocabulary;
- no new feature PRs or mutation paths accepted;
- every Critical/High finding has an owner and acceptance test.

## Phase 1 — Governance closure and operator security (Critical)

Objectives:

- make bypass impossible;
- secure operational mutations.

Deliverables:

- all research runners call the governance application service;
- legacy `promote_strategy_stage` becomes private/read-only or is removed;
- evidence policy is versioned and stage-specific;
- authenticated API with RBAC, restricted CORS, CSRF protection where
  applicable, loopback-safe default, and immutable actor identity;
- production/live-demo approvals require separate qualified approver and
  support revocation/expiry;
- synthetic evidence cannot qualify a real execution gate.

Dependencies: Phase 0 ADRs.

Success criteria:

- negative tests prove every known bypass fails;
- unauthorized requests cannot mutate any state;
- lifecycle, approval, and emergency-control security tests pass;
- no Critical security/governance findings remain.

## Phase 2 — Transactional control and evidence persistence (Critical/High)

Objectives:

- establish the institutional system of record;
- make changes atomic, migratable, and recoverable.

Deliverables:

- Alembic baseline and canonical PostgreSQL schemas;
- repository ports and PostgreSQL adapters;
- transactional strategy version, evidence, decision, approval, transition,
  and outbox writes;
- idempotent YAML/JSONL import and read-only catalog projection;
- object/filesystem artifact port with SHA-256 and immutable addressing;
- backup, restore, integrity, and concurrency tests.

Dependencies: Phases 0–1 domain/policy decisions.

Success criteria:

- concurrent promotion tests produce one valid transition;
- process failure cannot leave decision/state/catalog disagreement;
- migration and restore exercises pass declared RPO/RTO;
- YAML is no longer authoritative.

Architecture checkpoint: if Phases 0–2 pass, change verdict to **READY WITH
IMPROVEMENTS** and permit bounded feature work.

## Phase 3 — Reproducible research contracts (High)

Objectives:

- make every result reproducible and comparable.

Deliverables:

- typed/versioned strategy specification, dataset snapshot, run, metric,
  evidence, and event schemas;
- mandatory commit, dependency lock, config hash, dataset hash, seed, timezone,
  and cost-model identities;
- experiment manager and immutable run manifests;
- locked dependency groups and CI quality gates.

Dependencies: Phase 2 repositories and artifacts.

Success criteria:

- a clean environment reproduces a sampled run within declared tolerances;
- schema compatibility tests and quantitative golden tests pass;
- coverage/static/security thresholds block regressions.

## Phase 4 — Research-engine consolidation (High)

Objectives:

- reduce duplicate implementations while preserving validated mathematics.

Deliverables:

- canonical audit port and stage handler;
- replay/backtest/robustness adapter interfaces;
- parity corpus comparing old and new outputs;
- split SVOS orchestrator and report services;
- archive/remove nested repository and superseded paths.

Dependencies: Phase 3 contracts.

Success criteria:

- one active implementation per responsibility or an explicit adapter choice;
- no reciprocal package dependencies;
- parity tolerances approved by quantitative review;
- large orchestrator modules reduced to focused application services.

## Phase 5 — Execution qualification and deployment (High)

Objectives:

- prove simulated and broker-demo behavior use the same execution semantics.

Deliverables:

- canonical order/fill/position event model;
- deterministic spread, slippage, latency, partial-fill, rejection, reconnect,
  restart, and idempotency scenarios;
- deployment records, rollback, secrets isolation, and broker capability matrix;
- performance and recovery qualification evidence.

Dependencies: Phases 1–4.

Success criteria:

- execution parity and failure-injection suites pass;
- no research process can access live credentials;
- recovery meets declared SLOs;
- governance alone authorizes demo/production handoff.

## Phase 6 — Monitoring, drift, and institutional operations (Medium)

Objectives:

- sustain qualification after deployment.

Deliverables:

- production telemetry and correlation IDs;
- drift policies and automated revalidation cases;
- incident workflow, outbox notifications, retention policy, capacity tests,
  and disaster-recovery drills;
- generated operator/status documentation from canonical state.

Dependencies: qualified deployment lifecycle.

Success criteria:

- drift creates a governed revalidation transition;
- alerts, incidents, approvals, and evidence are traceable end to end;
- operational and recovery drills pass.

## Work explicitly deferred

- new discretionary strategy features;
- microservice decomposition;
- multi-tenant UI expansion;
- additional broker integrations;
- advanced notification channels;
- production capital scaling.

These do not resolve the current architectural blockers.

