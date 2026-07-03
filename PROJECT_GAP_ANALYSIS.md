# Project Gap Analysis

- Date: 2026-07-03
- Status: Review
- Scope: Read-only repository architecture audit at commit `81fa2abbfa8232c066f2c5fcfd2eb9aa25812bad`
- Branch: `codex/demo-smoke-test`
- Authority: Audit finding; does not supersede `docs/00_Project/DOC_AUTHORITY.md` or `docs/00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md`
- Safety: No live broker connection, order submission, strategy change, deployment, or runtime implementation was performed

## 1. Executive verdict

The repository has credible implementations for most named capabilities, but it is not yet an operationally unified institutional platform. The dominant gap is integration authority: multiple replay engines, execution stacks, package formats, dashboards, lifecycle views, and report stores coexist. Several are tested in isolation, but the canonical end-to-end paths do not yet connect every required stage or enforce every safety control at the lowest shared boundary.

The two-system separation is structurally present and protected by architecture tests. It is not yet independently deployable in practice. System 1 can validate evidence and build packages, and System 2 can verify packages and execute in demo/shadow modes, but the canonical SVOS pipeline, deployment-package pipeline, and active portfolio runtime use partially different contracts.

The highest-priority work is therefore consolidation and qualification, not feature expansion:

1. Establish one canonical artifact and handoff contract.
2. Make replay exercise the same execution services used by demo runtime.
3. Close runtime lifecycle, reconciliation, and loss-feedback gaps.
4. Prove the result with deterministic replay and demo qualification evidence.

PR #20 must remain limited to the Demo Smoke Test Sprint. CircleCI parity belongs in PR #21.

## 2. Audit method and evidence

The audit inspected the authoritative architecture documents, Python package boundaries, lifecycle manager, SVOS application pipeline, approval-package tooling, production import and verification services, portfolio runner, broker abstractions, replay implementations, demo readiness helpers, dashboards, reports, deployment files, tests, and GitHub Actions workflow.

Evidence checks performed:

- Architecture/readiness/package/identity focused tests: **38 passed in 7.67 seconds**.
- GitHub Actions configuration contains quality, unit, integration, security, documentation/package, and aggregate required gates.
- `.circleci/config.yml` is absent from this branch.
- The working tree had no pre-existing changes at audit start.
- Full-suite execution was not repeated because the current readiness report already records a native pandas crash and a pre-existing adapter failure; this audit did not attempt remediation.

## 3. Target architecture and qualification flow

```text
SYSTEM 1 — STRATEGY ENGINEERING PLATFORM (never executes broker orders)

 Idea -> INTAKE -> AUDIT -> REFINEMENT -> HISTORICAL_REPLAY
                                            |
                                            v
              Backtest -> Statistical Validation -> Robustness
                                            |
                                            v
                           VIRTUAL_DEMO -> PRODUCTION_APPROVAL
                                            |
                              signed, versioned, immutable package
                                            |
================================ HANDOFF BOUNDARY ================================
                                            |
                                            v
SYSTEM 2 — THIN EXECUTION LAYER

 Package Import -> Signature/Identity/Expiry Verification -> Startup Preflight
                                            |
                                            v
 Market Data -> Strategy Adapter -> Risk Firewall -> Execution Manager
                                            |                |
                                            v                v
                                      Journal/Audit <- Broker Abstraction
                                            |
                                            v
                           Reconciliation -> Monitoring -> Recovery

QUALIFICATION LADDER

 Current -> Replay Qualified -> Demo Qualified -> Operational Qualified
         -> Security Qualified -> Long-running Demo -> Production Candidate
         -> Limited Live Trading -> Production
```

## 4. Implemented capabilities

### 4.1 System 1 — Strategy Engineering Platform

| Capability | Evidence | Assessment |
|---|---|---|
| Canonical lifecycle vocabulary and transition topology | `svos/lifecycle/manager.py` | Implemented; promotion into `PRODUCTION_APPROVAL` is intentionally disabled. |
| Intake, audit, replay, backtest, robustness, and virtual-demo integration services | `svos/application/` | Implemented as stage services; orchestration gaps remain. |
| Governance-backed registry transitions | `svos/registry/service.py`, `svos/governance/service.py` | Implemented and tested. |
| Strategy validation | `strategy_validation/` | Eight-validator implementation exists. |
| Research and robustness engines | `research/`, `research_engine/`, `research/robustness.py` | Substantial implementation exists; authority and integration are fragmented. |
| Evidence reports and content-addressed artifacts | `svos/reports/`, `svos/adapters/artifacts.py` | Implemented for stage evidence. |
| Approval package construction and validation | `approval_package/` | Signed, expiry-aware, fail-closed directory package implemented. |
| Deployment artifact construction and production import | `svos/deployment/service.py`, `production/importer.py`, `production/verifier.py` | Implemented for a separate archive contract. |
| Registry and identity validation | `svos/registry/`, `scripts/validate_strategy_identity.py` | Implemented and covered by focused tests. |

### 4.2 System 2 — Thin Execution Layer

| Capability | Evidence | Assessment |
|---|---|---|
| Canonical portfolio entrypoint | `scripts/run_portfolio.py` | Validates a package before connection in demo mode and blocks `live`. |
| Market data and broker abstractions | `execution/market_data.py`, `core/broker_interface.py` | Implemented, with multiple concrete stacks. |
| Risk, permission, and governance controls | `execution/demo_risk_manager.py`, `execution/control_plane.py`, `execution/governance_guard.py` | Implemented individually; not all are wired into the canonical runner. |
| Order and position lifecycle | `execution/trade_manager.py`, `execution/execution_state.py` | Durable state model and retry/reconciliation policy exist. |
| Journaling | `execution/trade_journal.py`, `core/trade_journal_db.py` | Multiple journal implementations exist. |
| Emergency control and reconciliation surfaces | `dashboard/control_state.py`, `execution/control_plane.py`, reconciliation scripts | Implemented as services and operational surfaces. |
| Health and observability | `production/observability.py`, `scripts/health_check.py`, dashboard status APIs | Implemented, but fragmented across processes and data sources. |
| Demo-only broker simulator | `execution_simulator/` | Real virtual broker, fill/risk/position engines, and execution log exist. |

### 4.3 Governance, documentation, testing, and CI

| Capability | Evidence | Assessment |
|---|---|---|
| Architecture import boundaries | `tests/architecture/` | Active and passing. |
| Authoritative documentation hierarchy | `docs/00_Project/DOC_AUTHORITY.md` | Clear and enforceable as policy. |
| GitHub Actions quality gates | `.github/workflows/ci.yml` | Active and passing for the current PR scope. |
| Demo package smoke fixture | `tests/fixtures/demo_approved_package/`, `tests/portfolio/test_demo_smoke_test.py` | Deterministic offline preflight implemented. |
| Dashboard | `dashboard/`, `New Dashborad/` | Broad feature coverage exists; authority and operational deployment remain fragmented. |

## 5. Missing or incomplete capabilities

### 5.1 Canonical lifecycle orchestration is incomplete

`svos/application/pipeline.py` runs `INTAKE`, `AUDIT`, `REPLAY`, `BACKTEST`, `ROBUSTNESS`, and `VIRTUAL_DEMO`. It omits the canonical `REFINEMENT` stage and does not represent Backtest and Statistical Validation as distinct responsibilities, despite the Level-1 architecture requiring that distinction. Its successful output is labeled `APPROVED_PHASE5`, not a governance transition into `PRODUCTION_APPROVAL`.

### 5.2 Package handoff has competing formats

At least three package concepts coexist:

- `svos/application/pipeline.py` writes a JSON approval summary.
- `approval_package/` builds a signed evidence directory consumed by `run_portfolio.py`.
- `svos/deployment/service.py` and `production/verifier.py` use a signed tar archive with a different manifest and signature contract.

There is no single adapter or schema proving that the package approved by System 1 is exactly the package imported and executed by System 2.

### 5.3 Replay does not yet prove runtime equivalence

`historical_replay.ReplayEngine` calls a strategy callback over an expanding pandas window, while `execution_simulator.ReplayRunner` feeds events to `VirtualBroker`. Neither is assembled with the canonical portfolio runtime's strategy adapter, permission service, risk firewall, `TradeManager`, durable execution-state store, and journal. Replay therefore validates components, not equivalence with demo execution.

### 5.4 Canonical runtime does not close the operational feedback loop

`scripts/run_portfolio.py` increments open-position/risk state after an order, but it does not consume closed-trade results to update `PortfolioManager`, `CircuitBreaker`, or `demo_risk_manager.record_result()`. It also does not invoke `TradingPermissionService` or persist its order flow through `ExecutionStateStore`. This leaves daily-loss enforcement, position release, restart recovery, and ambiguous-submission recovery incomplete in the canonical loop.

### 5.5 Live-trading prevention is not enforced at one lowest boundary

The canonical runner unconditionally rejects `--mode live`, and activation services fail closed. However, legacy `execution/metaapi_client.py` and `execution/mt5_executor.py` still contain `LIVE_TRADING=true` write paths, while `execution/vantage_demo_executor.py` can write when `DEMO_ONLY=false`. An alternate caller could bypass the entrypoint-level invariant.

### 5.6 Configuration validation is partial

Package and identity validation are strong. Runtime configuration remains spread across environment variables, YAML, module constants, and fallback defaults. `_load_strategy_config()` catches all exceptions and silently falls back to hardcoded strategy settings. Institutional startup should reject malformed or missing authoritative configuration rather than change behavior silently.

### 5.7 Dashboard coverage exists, but authority is fragmented

The repository contains a Flask control panel, a FastAPI status server, a separate live Flask application, and React dashboards. `svos/dashboard`, `svos/ui`, and `svos/notifications` remain placeholders. Operational state is aggregated from several JSON, JSONL, log, registry, and overlay sources. Required views are present in pieces, but there is no single documented data authority for System Health, Current Package, Risk Firewall, Replay Progress, Qualification Status, Audit Log, Incident History, and Health Timeline.

### 5.8 Operational runbooks are incomplete as a coherent set

Incident and deployment documents exist, but the requested startup, shutdown, recovery, replay, and qualification procedures are not a single versioned runbook set tied to the canonical runner and its exact commands. Existing documents include historical and deployment-specific variants, increasing operator ambiguity.

### 5.9 Qualification evidence is incomplete

The offline smoke preflight passes, but there is no current multi-year canonical replay qualification, no connected demo qualification report, no restart/recovery evidence, and no two-to-four-week observation record. `reports/live_readiness/`, `reports/incidents/`, `reports/risk/`, and `reports/system_health/` contain only placeholders.

### 5.10 CI is not portable across providers yet

GitHub Actions is authoritative and passing. CircleCI has only a placeholder workflow on a separate setup branch and no pipeline on PR #20. Project triggers and branch protection requiring both providers are not configured.

## 6. Technical debt

| Debt | Consequence | Priority |
|---|---|---:|
| Multiple replay, broker, journal, dashboard, and execution implementations | Fixes and controls can land in a non-authoritative path. | P0 |
| Full repository test suite is not green | Regression confidence is limited to curated CI tiers. | P0 |
| Repository-wide Ruff/mypy baseline debt | Refactoring canonical boundaries carries avoidable risk. | P1 |
| Empty test-package scaffolds and placeholder SVOS UI packages | Names overstate implemented coverage. | P2 |
| Broad exception handling and silent fallbacks | Configuration, dashboard, and analytical failures can be hidden. | P0/P1 |
| Mixed research and execution storage/deployment topology | Independent deployment and least privilege are not proven. | P1 |
| Historical and current documents coexist in large numbers | Operators may follow non-authoritative procedures. | P1 |

## 7. Architectural risks

| Risk | Likelihood | Impact | Evidence |
|---|---:|---:|---|
| Executed artifact differs from approved artifact | Medium | Critical | Three package contracts without a canonical conversion. |
| Runtime loss controls do not reflect closed trades | High | Critical | Canonical loop does not call close-result feedback methods. |
| Alternate entrypoint enables broker writes | Low while current policy holds | Critical | Lower-level modules retain environment-enabled write paths. |
| Replay passes while demo behavior differs | High | High | Replay is not assembled from the demo runtime service graph. |
| Restart duplicates or loses an ambiguous order | Medium | Critical | Durable execution state exists but is not wired into `run_portfolio.py`. |
| Dashboard reports stale or conflicting state | Medium | High | Multiple state stores and dashboard processes. |
| Research and production cannot be independently deployed | Medium | High | Shared host/database history and legacy cross-imports. |
| Quality regressions escape curated CI paths | Medium | High | Full suite and repository-wide static checks are not green. |

## 8. Prioritized recommendations

Every recommendation below includes the required quality-gate fields.

### R1 — Define one canonical strategy package and handoff adapter

- **Reason:** Three incompatible package representations currently cross the SVOS/Production boundary.
- **Expected benefit:** A cryptographically verifiable chain from lifecycle evidence to the exact runtime-loaded strategy version.
- **Risk:** Migration could invalidate existing fixtures or deployment records.
- **Dependencies:** Owner approval of the canonical schema; mapping of existing package fields; signing-key policy.
- **Priority:** P0.
- **Estimated effort:** 5–8 engineering days.
- **Acceptance criteria:** One versioned schema; one signing policy; deterministic build; System 1 emits it; System 2 imports and verifies it; identity, expiry, evidence, risk, live-disabled policy, and executable adapter version are bound by the signature; legacy formats are rejected or converted explicitly.
- **Rollback strategy:** Keep existing package readers behind read-only compatibility adapters; revert consumers to the prior reader without changing stored artifacts.
- **Testing strategy:** Golden-package fixtures, tamper tests, expiry tests, identity mismatch tests, deterministic rebuild test, cross-system contract test, and migration fixture tests.

### R2 — Establish a canonical runtime service graph

- **Reason:** Production services exist, but `run_portfolio.py` bypasses permission and durable execution-state services.
- **Expected benefit:** One auditable order path with governance, permission, risk, idempotency, reconciliation, and journaling applied consistently.
- **Risk:** Consolidation can alter timing or legacy demo behavior.
- **Dependencies:** R1; selection of canonical broker, journal, risk, and state interfaces.
- **Priority:** P0.
- **Estimated effort:** 8–12 engineering days.
- **Acceptance criteria:** Every new order traverses package guard, permission service, risk firewall, execution state machine, `TradeManager`, journal, and reconciliation; no active runner calls broker write methods directly.
- **Rollback strategy:** Preserve the existing runner as a demo-disabled diagnostic entrypoint until parity evidence is accepted.
- **Testing strategy:** Service-graph contract tests, failure injection at every transition, idempotency tests, broker-timeout ambiguity tests, and end-to-end virtual-broker tests.

### R3 — Close trade-result, reconciliation, and restart feedback loops

- **Reason:** Open and closed position state does not reliably feed canonical portfolio and loss controls.
- **Expected benefit:** Daily/weekly/monthly loss limits, max-position limits, circuit breakers, and recovery operate on broker truth.
- **Risk:** Incorrect reconciliation could block safe trading or double-count P&L.
- **Dependencies:** R2; canonical position and deal identifiers; journal schema.
- **Priority:** P0.
- **Estimated effort:** 5–8 engineering days.
- **Acceptance criteria:** Closed trades update all relevant risk counters exactly once; startup reconciles broker, execution state, and journal before allowing new orders; critical mismatch blocks new trading; restart resumes without duplicate submission.
- **Rollback strategy:** Force `BLOCK_NEW`/close-only mode and restore the previous state snapshot; reconciliation must never auto-open orders.
- **Testing strategy:** Restart fixtures, duplicated-deal tests, missing-journal tests, orphan-position tests, P&L boundary tests, and crash-at-each-state tests.

### R4 — Make replay use the canonical runtime services

- **Reason:** Existing replay engines do not prove parity with demo execution.
- **Expected benefit:** Deterministic qualification of strategy adapter, risk firewall, order lifecycle, journal, and reports without live broker access.
- **Risk:** Runtime services may contain wall-clock or external-state assumptions that break determinism.
- **Dependencies:** R2 and R3; canonical event clock; virtual broker interface parity.
- **Priority:** P0.
- **Estimated effort:** 8–12 engineering days.
- **Acceptance criteria:** Historical candles pass through market-data port, approved strategy adapter, permission/risk services, `TradeManager`, virtual broker, execution state, journal, and report builder; repeated runs produce identical event and report hashes.
- **Rollback strategy:** Retain current replay engines as comparison-only tools until equivalence is demonstrated; do not delete historical evidence.
- **Testing strategy:** Golden event streams, no-lookahead tests, deterministic hash tests, stop/target collision policy tests, latency/slippage tests, and replay-versus-demo service-graph assertions.

### R5 — Complete canonical lifecycle stage orchestration

- **Reason:** `REFINEMENT` and distinct Statistical Validation responsibilities are absent from the canonical pipeline flow.
- **Expected benefit:** Lifecycle reports and approvals match the authoritative product architecture.
- **Risk:** Changing stage semantics can invalidate existing registry transitions and reports.
- **Dependencies:** Architecture-owner decision on representing Backtest versus `STATISTICAL_VALIDATION` without inventing an unauthorized enum; R1 package evidence mapping.
- **Priority:** P1, with an owner decision required before implementation.
- **Estimated effort:** 5–10 engineering days after the decision.
- **Acceptance criteria:** Every authoritative lifecycle responsibility has a named service, evidence schema, gate, registry transition, and report; no successful pipeline labels itself approved without governance authority.
- **Rollback strategy:** Version the pipeline and retain previous registry records unchanged; downgrade only by starting a new run under the old version.
- **Testing strategy:** Transition topology tests, failed-stage loop tests, missing-evidence tests, lifecycle report schema tests, and approval-denial tests.

### R6 — Enforce demo/live policy at the broker write boundary

- **Reason:** Entrypoint blocking is strong but lower-level legacy clients remain live-capable through environment flags.
- **Expected benefit:** No alternate caller can enable broker writes accidentally.
- **Risk:** Demo broker qualification may be blocked if demo writes are not modeled separately from live writes.
- **Dependencies:** Explicit broker environment model (`virtual`, `demo`, `live`); human authorization design for future live stages.
- **Priority:** P0 safety.
- **Estimated effort:** 3–5 engineering days.
- **Acceptance criteria:** Live account/order construction is impossible without a separately implemented, default-deny authorization boundary; current builds reject live mode in every broker adapter; no System 1 module imports broker-write implementations.
- **Rollback strategy:** Revert adapter wiring while leaving the global deny policy active; never roll back to an enabled live path.
- **Testing strategy:** Environment permutation tests, direct-adapter invocation tests, import-boundary tests, and negative broker-write tests.

### R7 — Replace runtime configuration fallbacks with validated startup configuration

- **Reason:** Silent fallback can change portfolio composition and risk behavior.
- **Expected benefit:** Deterministic, explainable startup and safer operations.
- **Risk:** Existing ad hoc invocations may stop until configuration is corrected.
- **Dependencies:** Canonical config schema and ownership; secret/reference separation.
- **Priority:** P1.
- **Estimated effort:** 3–5 engineering days.
- **Acceptance criteria:** Startup validates mode, package, strategy identity, symbols, risk limits, journal/state paths, broker environment, and monitoring requirements before connection; malformed/missing authoritative config fails closed with actionable errors.
- **Rollback strategy:** Permit an explicit test-only fixture configuration, never an implicit production fallback.
- **Testing strategy:** Schema tests, malformed-file tests, missing-key tests, conflicting-env tests, and startup-before-connect assertions.

### R8 — Consolidate dashboard data authority and operational views

- **Reason:** Required views exist across multiple applications and state sources without one authority map.
- **Expected benefit:** Operators see consistent health, package, execution, risk, replay, qualification, registry, audit, incident, and timeline state.
- **Risk:** UI consolidation can accidentally create control authority or expose sensitive data.
- **Dependencies:** R1–R4 canonical state and report contracts; authentication/authorization policy.
- **Priority:** P1 after runtime contracts stabilize.
- **Estimated effort:** 8–15 engineering days.
- **Acceptance criteria:** Each page declares its authoritative backend source and staleness; read views cannot mutate lifecycle state; control actions are authenticated, audited, and fail closed; no secrets or broker credentials are returned.
- **Rollback strategy:** Keep existing dashboards read-only during migration and switch routes back if the unified projection is inconsistent.
- **Testing strategy:** Source-priority tests, stale-data tests, authorization/CSRF tests, governance-denial tests, accessibility smoke tests, and API contract tests.

### R9 — Establish operational qualification evidence and runbooks

- **Reason:** Code-level capabilities are not yet supported by repeatable operator procedures or long-running evidence.
- **Expected benefit:** Auditable promotion from Replay Qualified through Long-running Demo.
- **Risk:** Premature qualification language could be mistaken for live authorization.
- **Dependencies:** R2–R7; stable monitoring and report schemas.
- **Priority:** P1.
- **Estimated effort:** 5–8 engineering days for runbooks and automation, plus observation time.
- **Acceptance criteria:** Versioned startup, shutdown, incident, recovery, replay, qualification, and deployment procedures; generated replay, demo, recovery, health, risk, incident, and observation reports; every promotion is explicit and reversible; live remains blocked.
- **Rollback strategy:** Demote qualification status, activate `BLOCK_NEW`, preserve all evidence, and restore the last qualified package/config.
- **Testing strategy:** Tabletop incident exercise, cold-start/cold-stop drills, crash recovery drill, stale-data drill, broker-disconnect drill, and report completeness checks.

### R10 — Restore a repository-wide trustworthy quality baseline

- **Reason:** Curated CI is green, but full pytest, Ruff, and mypy are not repository-wide green.
- **Expected benefit:** Safer consolidation and clearer regression ownership.
- **Risk:** A broad cleanup PR could obscure functional changes.
- **Dependencies:** Debt inventory and ownership; no change to CI suppressions without explicit documentation.
- **Priority:** P1, delivered incrementally.
- **Estimated effort:** 8–20 engineering days across focused PRs.
- **Acceptance criteria:** Native crash isolated or removed; all tests complete deterministically; static-analysis debt is baselined transparently and reduced monotonically; no `|| true` or equivalent hidden failure is introduced.
- **Rollback strategy:** Revert individual narrow cleanup PRs; preserve the prior CI gates and published debt baseline.
- **Testing strategy:** Full-suite repeat runs, test-order randomization, subprocess isolation for native dependencies, and provider-parity CI comparison.

### R11 — Add CircleCI as a mirror without replacing GitHub Actions

- **Reason:** Provider parity and independent CI signal are planned but absent.
- **Expected benefit:** A second execution of the same gates and stronger branch protection.
- **Risk:** Command drift can create conflicting signals or weaker enforcement.
- **Dependencies:** Dedicated PR #21; CircleCI project triggers; repository administration access.
- **Priority:** P1; next after PR #20.
- **Estimated effort:** 1–2 engineering days plus administrator configuration.
- **Acceptance criteria:** CircleCI executes the exact GitHub Actions commands; the four documented `pip-audit` exceptions are unchanged; no failures are suppressed; GitHub Actions remains required; branch protection requires both after triggers work; no secrets, broker access, trading, or deployment behavior is added.
- **Rollback strategy:** Remove the CircleCI required check and disable its trigger while leaving GitHub Actions required; revert only the CircleCI configuration PR.
- **Testing strategy:** Compare command logs and outcomes on a passing commit and controlled failing commits for lint, unit, integration, security, and documentation gates.

## 9. Updated implementation priority list

| Order | Work item | Gate produced | Depends on |
|---:|---|---|---|
| 1 | Keep PR #20 limited to offline Demo Smoke Test Sprint | Current/offline preflight evidence | None |
| 2 | PR #21 CircleCI parity, triggers, and dual-provider branch protection | CI parity | PR #20 separation only |
| 3 | Canonical package and handoff contract | Artifact integrity gate | Architecture approval |
| 4 | Canonical runtime service graph and broker-boundary deny policy | Runtime safety gate | Canonical package |
| 5 | Reconciliation, close-result feedback, and restart recovery | Operational integrity gate | Runtime graph |
| 6 | Runtime-equivalent deterministic replay | Replay Qualified | Runtime graph and recovery |
| 7 | Lifecycle orchestration completion | Full System 1 qualification trace | Owner stage decision, package contract |
| 8 | Demo broker qualification and evidence reports | Demo Qualified | Replay Qualified |
| 9 | Unified operational dashboard projection and runbooks | Operational Qualified | Stable runtime/report contracts |
| 10 | Security hardening and long-running demo observation | Security Qualified / Long-running Demo | Operational Qualified |
| 11 | Production-candidate review | Production Candidate | All earlier gates |

## 10. Recommended next PR sequence

1. **PR #20 — Demo Smoke Test Sprint only.** No CircleCI or architecture consolidation.
2. **PR #21 — CircleCI mirror workflow, project trigger, status check, and branch protection documentation.** Commit: `ci: add CircleCI workflow mirroring GitHub Actions`.
3. **PR #22 — Canonical package contract ADR and schemas.** Documentation, schemas, fixtures, and compatibility mapping only.
4. **PR #23 — System 2 canonical package importer/loader integration.** No broker behavior changes.
5. **PR #24 — Canonical runtime composition with permission and execution state.** Virtual broker first.
6. **PR #25 — Reconciliation, close-result feedback, and restart recovery.** Failure-injection evidence required.
7. **PR #26 — Runtime-equivalent historical replay.** No duplicate execution logic.
8. **PR #27 — Replay qualification report generation and deterministic evidence run.**
9. **PR #28 — Demo broker qualification harness and reports.** Demo account only; live path remains blocked.
10. **PR #29 — Dashboard authority map and required operational pages.** Read-only projections before controls.
11. **PR #30 — Operational runbooks and qualification automation.**
12. **Subsequent focused PRs — full-suite stability, static-analysis debt, security qualification, and long-running demo observation.**

## 11. Deliverable sequencing decision

This report completes the requested repository-analysis phase. The remaining requested deliverables should not be treated as implementation authorization:

- `OPERATIONAL_READINESS_REPORT.md` should follow a dedicated operational audit of the canonical runtime and deployed topology.
- `REPLAY_ENGINE_ARCHITECTURE.md` should be designed after R1–R3 decisions, before replay code changes.
- `DEMO_RUNTIME_QUALIFICATION.md` should be produced from executed qualification evidence, not inferred from unit tests.
- `RUNTIME_DASHBOARD_PLAN.md` should follow the data-authority decision.
- `RUNBOOKS/` should follow stabilization of canonical commands and state paths.
- `CI_EVOLUTION_PLAN.md` may proceed independently as PR #21 planning.
- `PRODUCTION_READINESS_ROADMAP.md` should use the accepted findings and qualification evidence from the preceding reports.

No new runtime code should be implemented until this analysis is reviewed and the P0 authority decisions are accepted.
