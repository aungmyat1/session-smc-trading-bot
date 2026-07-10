---
Date: 2026-06-30
Status: Authoritative
Version: 1.0
Updated: 2026-06-30
Owner: Platform Architecture
Authority: Level 0 — Root (navigation layer; does not override DOC_AUTHORITY.md)
Related: 00_Project/DOC_AUTHORITY.md, SYSTEM_ARCHITECTURE.md, DEVELOPER_HANDBOOK.md, AGENT_RULES.md
---

# Documentation Index

This is the canonical entry point for humans and AI agents working in this
repository. It is a **navigation layer**, not a new authority source.
[DOC_AUTHORITY.md](00_Project/DOC_AUTHORITY.md) governs conflicts between docs.

---

## Read First

Before touching any code, strategy, or governance decision:

1. [DOC_AUTHORITY.md](00_Project/DOC_AUTHORITY.md) — conflict resolution and authority hierarchy
2. [TWO_SYSTEM_ARCHITECTURE_TRUTH.md](00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md) — original SVOS and Production scope
3. [GLOSSARY.md](00_Project/GLOSSARY.md) — canonical term definitions
4. [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) — platform-level design
5. [DEVELOPER_HANDBOOK.md](DEVELOPER_HANDBOOK.md) — coding standards, workflow, branch policy
6. [AGENT_RULES.md](AGENT_RULES.md) — mandatory rules for AI agents touching this repo
7. [project_manifest.yaml](../docs/project_manifest.yaml) — machine-readable project state (~600 tokens)

---

## Current State

Point-in-time status snapshots — these files do **not** auto-update; treat
the `2026-06-29` date in their filenames as a snapshot anchor, not live truth:

- [PROJECT_STATUS_REPORT_2026-06-29.md](svos/PROJECT_STATUS_REPORT_2026-06-29.md) — full 11-phase audit, 12 deliverables
- [STABILIZATION_STATUS.md](svos/STABILIZATION_STATUS.md) — live feature-freeze gate tracker
- [CURRENT_STATE.md](svos/CURRENT_STATE.md) — concise current-state summary
- [PREFLIGHT_STATUS.md](svos/PREFLIGHT_STATUS.md) — pre-live checklist status

---

## Architecture

- [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md)
- [SUPPORTED_SYMBOLS.md](SUPPORTED_SYMBOLS.md) — canonical symbol scopes and market metadata
- [VIRTUAL_DEMO_GUIDE.md](VIRTUAL_DEMO_GUIDE.md) — offline virtual-demo procedure, including BTCUSDT
- [CORE_ARCHITECTURE.md](svos/CORE_ARCHITECTURE.md) — SVOS lifecycle state machine (Mermaid diagram)
- [QUANT_PLATFORM_ARCHITECTURE.md](QUANT_PLATFORM_ARCHITECTURE.md)
- [AI_WORKFLOW_ARCHITECTURE.md](AI_WORKFLOW_ARCHITECTURE.md)
- [architecture_summary.md](architecture_summary.md) — module map, persistence authority table (~800 tokens)
- [Architecture Review — 2026-06-29](svos/architecture-review-2026-06-29/README.md) — 7-document review set, verdict: NOT READY
  - [00 Executive Summary](svos/architecture-review-2026-06-29/00_EXECUTIVE_SUMMARY.md)
  - [01 Architecture Assessment](svos/architecture-review-2026-06-29/01_ARCHITECTURE_ASSESSMENT.md)
  - [02 Database Assessment](svos/architecture-review-2026-06-29/02_DATABASE_ASSESSMENT.md)
  - [03 Code Quality](svos/architecture-review-2026-06-29/03_CODE_QUALITY.md)
  - [04 Gap Analysis](svos/architecture-review-2026-06-29/04_GAP_ANALYSIS.md)
  - [05 Risk Assessment](svos/architecture-review-2026-06-29/05_RISK_ASSESSMENT.md)
  - [06 Upgrade Roadmap](svos/architecture-review-2026-06-29/06_UPGRADE_ROADMAP.md)

### Architecture Separation Migration

- [Phase 0 baseline](migration/baseline.md)
- [Phase 0 test status](migration/current_test_status.md)
- [Phase 0 safety state](migration/safety_state.md)
- [Current architecture state](architecture/current_state.md)
- [Target architecture](architecture/target_architecture.md)
- [Module inventory](architecture/module_inventory.md)
- [Module boundaries](architecture/module_boundaries.md)
- [Dependency graph](architecture/dependency_graph.md)
- [Risk assessment](architecture/risk_assessment.md)
- [Dashboard boundary](architecture/dashboard_boundary.md)
- [Shared library design](architecture/shared_library_design.md)
- [Strategy registry](architecture/strategy_registry.md)
- [API contracts](architecture/api_contracts.md)
- [Deployment flow](architecture/deployment_flow.md)
- [Migration plan](architecture/migration_plan.md)
- [Production/SVOS rollout index](architecture/production_svos_rollout_index.md)
- [Implementation plan](architecture/production_svos_implementation_plan.md)
- [Implementation completion report](architecture/production_svos_implementation_completion_report.md)
- [Remaining real-world rollout tasks](architecture/remaining_real_world_rollout_tasks.md)
- [Institutional platform plan](implementation/INSTITUTIONAL_TRADING_PLATFORM_PLAN.md)

---

## Operations

- [Current operational status](operations/current_operational_status.md)
- [Production readiness report](operations/production_readiness_report.md)
- [Disabled deployment runbook](operations/deployment_runbook.md)
- [Monitoring endpoints](operations/monitoring_endpoints.md)
- [GitHub operating model](operations/github_operating_model.md)
- [OPERATING_MANUAL.md](OPERATING_MANUAL.md) — run, monitor, pause, recover
- [VPS_DEPLOYMENT_RUNBOOK.md](VPS_DEPLOYMENT_RUNBOOK.md)
- [DEPLOYMENT_READINESS.md](DEPLOYMENT_READINESS.md)
- [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md)
- [DEPLOYMENT_TOPOLOGY.md](svos/DEPLOYMENT_TOPOLOGY.md)
- [VANTAGE_DEMO_CONNECTION_CHECKLIST.md](VANTAGE_DEMO_CONNECTION_CHECKLIST.md)
- [LIVE_CAPITAL_SCALING_PLAN.md](LIVE_CAPITAL_SCALING_PLAN.md)
- [OPS02_ACTIVATION_CHECKLIST.md](OPS02_ACTIVATION_CHECKLIST.md)
- [OPS02_REVISED_GATE.md](OPS02_REVISED_GATE.md)

---

## System 2 — Execution Platform (Production, 2026-07-04)

- [CANONICAL_EXECUTION_PIPELINE.md](systems/system2/CANONICAL_EXECUTION_PIPELINE.md) — the one canonical execution lifecycle
- [STATUS.md](systems/system2/STATUS.md) — living status index (execution/risk + dashboard integration workstreams)
- [ROADMAP.md](systems/system2/ROADMAP.md) — phased roadmap, platform + dashboard integration
- [EXECUTION_PIPELINE_INVENTORY.md](systems/system2/EXECUTION_PIPELINE_INVENTORY.md) — full inventory of execution-engine implementations
- [PIPELINE_CONSOLIDATION_PLAN.md](systems/system2/PIPELINE_CONSOLIDATION_PLAN.md) — consolidation/dedup plan for the above
- [INFRASTRUCTURE_READINESS.md](systems/system2/INFRASTRUCTURE_READINESS.md) — VPS/systemd readiness assessment
- [DASHBOARD_READINESS_INTERFACES.md](systems/system2/DASHBOARD_READINESS_INTERFACES.md) — backend interfaces the dashboard can consume
- [SMC_DEMO_RUNNER_ANALYSIS.md](systemd/SMC_DEMO_RUNNER_ANALYSIS.md) — root-cause analysis of the deployed `smc-demo-runner.service`

## GitHub Repository Governance (2026-07-05)

PR/branch audit trail and the 2026-07-05 repository stabilization pass:

- [PR_AUDIT.md](github/PR_AUDIT.md) — every PR, state, purpose, recommendation
- [BRANCH_AUDIT.md](github/BRANCH_AUDIT.md) — every branch, merge status, recommendation
- [BRANCH_DELETE_VERIFICATION.md](github/BRANCH_DELETE_VERIFICATION.md) — verified-safe-to-delete branches
- [DRAFT_PR_REVIEW.md](github/DRAFT_PR_REVIEW.md) — stale draft PR closure evidence
- [DEPENDABOT_REVIEW.md](github/DEPENDABOT_REVIEW.md) — dependency PR audit
- [LOCAL_MAIN_AUDIT.md](github/LOCAL_MAIN_AUDIT.md) — local `main` divergence investigation
- [CLEANUP_PLAN.md](github/CLEANUP_PLAN.md) — proposed cleanup execution order
- [PR21_PR22_INTEGRATION_REPORT.md](github/PR21_PR22_INTEGRATION_REPORT.md) — merge conflict/sequencing analysis
- [PR22_FIX_REPORT.md](github/PR22_FIX_REPORT.md) — safety-critical review findings fixed before PR #22 merged
- [REPOSITORY_HEALTH_REPORT.md](github/REPOSITORY_HEALTH_REPORT.md) — cleanup Phase 2 execution outcome
- [REPOSITORY_CLEANUP_REPORT.md](github/REPOSITORY_CLEANUP_REPORT.md) — 2026-07-05 root-doc reorganization + branch deletion
- [CI_CD_HEALTH_REPORT.md](audit/CI_CD_HEALTH_REPORT.md) — CI/CD workflow coverage audit
- [DEPENDENCY_UPDATE_PLAN.md](audit/DEPENDENCY_UPDATE_PLAN.md) — dependency maintenance plan
- [EXECUTION_LAYER_GAP_ANALYSIS.md](audit/EXECUTION_LAYER_GAP_ANALYSIS.md) — System 2 completeness gap analysis
- [STABILIZATION_ROADMAP.md](audit/STABILIZATION_ROADMAP.md) — prioritized implementation roadmap
- [DEMO_TRADING_RISK_ASSESSMENT.md](audit/DEMO_TRADING_RISK_ASSESSMENT.md) — risk register for proceeding toward demo trading

## Dashboard Integration (2026-07-04)

- [DASHBOARD_STATUS.md](dashboard/DASHBOARD_STATUS.md) — assessment of the deployed dashboard backend
- [DASHBOARD_BACKEND_MAPPING.md](dashboard/DASHBOARD_BACKEND_MAPPING.md) — per-endpoint, per-widget backend contract mapping
- [DASHBOARD_GAP_ANALYSIS.md](dashboard/DASHBOARD_GAP_ANALYSIS.md) — gap analysis vs the Gai dashboard frontend
- [DASHBOARD_IMPLEMENTATION_PLAN.md](dashboard/DASHBOARD_IMPLEMENTATION_PLAN.md) — phased frontend integration plan
- [DASHBOARD_READINESS.md](systems/system2/DASHBOARD_READINESS.md) — fail-closed readiness aggregator (2026-07-05): `/api/system2/readiness`, `/system2/readiness`

## VPS Operations (2026-07-04)

- [OPERATOR_RUNBOOK.md](vps/OPERATOR_RUNBOOK.md) — daily checks, incident response, rollback, backup restore
- [VPS_INVENTORY.md](vps/VPS_INVENTORY.md) — host/service inventory
- [RUNNING_SERVICES.md](vps/RUNNING_SERVICES.md) — systemd unit audit
- [PROJECT_AUDIT.md](vps/PROJECT_AUDIT.md) — project/directory audit on the VPS
- [DISK_USAGE_REPORT.md](vps/DISK_USAGE_REPORT.md)
- [CLEANUP_PLAN.md](vps/CLEANUP_PLAN.md)
- [CLEANUP_REPORT.md](vps/CLEANUP_REPORT.md)
- [LOG_RETENTION_POLICY.md](vps/LOG_RETENTION_POLICY.md)
- [PERFORMANCE_RECOMMENDATIONS.md](vps/PERFORMANCE_RECOMMENDATIONS.md)
- [RESOURCE_OPTIMIZATION.md](vps/RESOURCE_OPTIMIZATION.md)
- [OPERATIONS_BASELINE.md](vps/OPERATIONS_BASELINE.md)
- [STABILIZATION_REPORT.md](vps/STABILIZATION_REPORT.md)

---

## Data & Database

- [HISTORICAL_DATA_ARCHITECTURE.md](HISTORICAL_DATA_ARCHITECTURE.md)
- [RESEARCH_FEATURE_DATABASE.md](RESEARCH_FEATURE_DATABASE.md)
- [RESEARCH_ENGINE.md](RESEARCH_ENGINE.md)
- [DATABASE_ARCHITECTURE_VERIFICATION.md](DATABASE_ARCHITECTURE_VERIFICATION.md)
- [DOWNLOADER_USAGE.md](DOWNLOADER_USAGE.md)
- [db/README.md](../db/README.md)

---

## Strategy Specifications

Inventory and governance:
- [01_strategy_inventory.md](strategy_audit/01_strategy_inventory.md)
- [02_execution_flow.md](strategy_audit/02_execution_flow.md)
- [03_governance_and_risk.md](strategy_audit/03_governance_and_risk.md)
- [parameters.md](strategy_audit/parameters.md)
- [rules.md](strategy_audit/rules.md)

Individual strategy specs (detail files — flow, parameters, rules — are co-located in each strategy directory):

- [ST-A2 — Session Liquidity Reversal](strategy_audit/strategies/ST-A2 %28Session Liquidity Reversal%29/strategy_spec.md)
- [London Breakout](strategy_audit/strategies/London Breakout/strategy_spec.md)
- [NY Momentum](strategy_audit/strategies/NY Momentum/strategy_spec.md)
- [Adaptive SMC](strategy_audit/strategies/Adaptive SMC %28AdaptiveSMC%29/strategy_spec.md)
- [VWAP Breakout](strategy_audit/strategies/VWAP Breakout %28VWAPBreakout%29/strategy_spec.md)
- [VWAP Mean Reversion](strategy_audit/strategies/VWAP Mean Reversion %28VWAPMeanReversion%29/strategy_spec.md)
- [SMC Order Block + FVG Session](strategy_audit/strategies/SMC Order Block + FVG Session %28SVOSReady%29/strategy_spec.md)
- [D2E3](strategy_audit/strategies/D2E3/strategy_spec.md)
- [11-Phase SMC Session Chain](strategy_audit/strategies/11-Phase SMC Session Chain %28Strategy B _ session_smc%29/strategy_spec.md)

---

## Validation & Reports

- [STAGE1_AUDIT_SPEC.md](STAGE1_AUDIT_SPEC.md) — Phase-0 audit spec, 10-validator gate
- [HISTORICAL_REPLAY.md](HISTORICAL_REPLAY.md)
- [BACKTEST_SPEC.md](BACKTEST_SPEC.md)
- [VALIDATION_GATE_ENGINE.md](VALIDATION_GATE_ENGINE.md)
- [STRATEGY_VALIDATION_ENGINE.md](STRATEGY_VALIDATION_ENGINE.md)
- [EXECUTION_LAYER_VALIDATION_SPEC.md](EXECUTION_LAYER_VALIDATION_SPEC.md)
- [EXECUTION_SPEC.md](EXECUTION_SPEC.md)
- [REPORT_SYSTEM.md](REPORT_SYSTEM.md)
- [VERDICT_LOG.md](VERDICT_LOG.md) — immutable trial results; never re-run a trial ID
- [SYS1-T015_INITIAL_ASSESSMENT.md](experiments/SYS1-T015_INITIAL_ASSESSMENT.md) — ST-A2 SVOS revalidation: repository/governance review, registry-authority ambiguity, stale gate config findings
- [BACKTEST_COST_REVALIDATION_REPORT.md](BACKTEST_COST_REVALIDATION_REPORT.md) — E6 cost revalidation
- [BACKTEST_FAILURE_ANALYSIS.md](BACKTEST_FAILURE_ANALYSIS.md)
- [BACKTEST_RESULTS.md](BACKTEST_RESULTS.md)
- [FORWARD_TEST_VALIDATION.md](FORWARD_TEST_VALIDATION.md)

---

## SVOS / Governance

- [SVOS_LIFECYCLE_WORKFLOW.md](SVOS_LIFECYCLE_WORKFLOW.md)
- [SVOS_DESIGN_REFERENCE.md](SVOS_DESIGN_REFERENCE.md)
- [SVOS_EVF_USER_MANUAL.md](SVOS_EVF_USER_MANUAL.md)
- [ISOP_CONTROL_PANEL.md](ISOP_CONTROL_PANEL.md)
- [CHANGE_CONTROL_SYSTEM.md](CHANGE_CONTROL_SYSTEM.md)
- [ADR-0001-STABILIZATION-FOUNDATION.md](svos/ADR-0001-STABILIZATION-FOUNDATION.md)
- [STRATEGY_ENGINEERING_PLATFORM_IMPLEMENTATION_PLAN.md](svos/STRATEGY_ENGINEERING_PLATFORM_IMPLEMENTATION_PLAN.md)
- [PLATFORM_IMPLEMENTATION_REQUIREMENTS.md](svos/PLATFORM_IMPLEMENTATION_REQUIREMENTS.md)
- [DOC_AUDIT_2026-06-29.md](svos/DOC_AUDIT_2026-06-29.md) — point-in-time doc health audit
- [DOC_HEALTH_REPORT_2026-06-29.md](svos/DOC_HEALTH_REPORT_2026-06-29.md) — point-in-time health report
- [SVOS_STRATEGY_AUDIT_GAP_CLOSURE_PLAN.md](SVOS_STRATEGY_AUDIT_GAP_CLOSURE_PLAN.md)
- [SVOS_STRATEGY_AUDIT_LOOP_REPORT.md](SVOS_STRATEGY_AUDIT_LOOP_REPORT.md)
- [SVOS_STRATEGY_AUDIT_WORKFLOW_VALIDATION.md](SVOS_STRATEGY_AUDIT_WORKFLOW_VALIDATION.md)

---

## Strategy Research

Signal, execution, and feature specifications:
- [SIGNAL_SPEC.md](SIGNAL_SPEC.md)
- [RISK_SPEC.md](RISK_SPEC.md)
- [EXECUTION_SPEC.md](EXECUTION_SPEC.md)
- [SMC_FEATURE_SPEC.md](SMC_FEATURE_SPEC.md)
- [STRATEGY_AUDIT_FRAMEWORK.md](STRATEGY_AUDIT_FRAMEWORK.md)

Strategy-specific research:
- [STRATEGY_A_SESSION.md](STRATEGY_A_SESSION.md)
- [STRATEGY_B_SMC.md](STRATEGY_B_SMC.md)
- [STRATEGY_PORTFOLIO_ROADMAP.md](STRATEGY_PORTFOLIO_ROADMAP.md)
- [ST_B_RESEARCH_PLAN.md](ST_B_RESEARCH_PLAN.md)
- [WALK_FORWARD_RESEARCH_PLAN.md](WALK_FORWARD_RESEARCH_PLAN.md)
- [REPLAY_INTEGRATION_PLAN.md](REPLAY_INTEGRATION_PLAN.md)
- [SPREAD_CAPTURE_PLAN.md](SPREAD_CAPTURE_PLAN.md)
- [SPREAD_RESEARCH_FINAL_REPORT.md](SPREAD_RESEARCH_FINAL_REPORT.md)

---

## Research & Analysis Audits

- [BIAS_FILTER_AUDIT.md](BIAS_FILTER_AUDIT.md)
- [ENTRY_ENGINE_AUDIT.md](ENTRY_ENGINE_AUDIT.md)
- [SWEEP_DETECTOR_AUDIT.md](SWEEP_DETECTOR_AUDIT.md)
- [REPOSITORY_AUDIT.md](REPOSITORY_AUDIT.md)
- [EXPERIMENT_RESULTS.md](EXPERIMENT_RESULTS.md)
- [TIMEFRAME_GENERATION.md](TIMEFRAME_GENERATION.md)
- [TIMEZONE_AUDIT.md](TIMEZONE_AUDIT.md)
- [TASK_QUEUE.md](TASK_QUEUE.md)
- [strategy_execution_audit.md](audit/strategy_execution_audit.md)

## Dashboard Reuse Assessment

- [dashboard_audit.md](dashboard_reuse_assessment/dashboard_audit.md) — inventory and migration recommendation set

---

## Templates

- [implementation_spec_template.md](templates/implementation_spec_template.md)
- [daily_report_template.md](templates/daily_report_template.md)
- [weekly_report_template.md](templates/weekly_report_template.md)
- [incident_report_template.md](templates/incident_report_template.md)
- [live_readiness_template.md](templates/live_readiness_template.md)
- [risk_report_template.md](templates/risk_report_template.md)
- [strategy_report_template.md](templates/strategy_report_template.md)

---

## Archive

- [Archive/INDEX.md](Archive/INDEX.md) — explains every archived file; treat as historical record, non-prescriptive
- [Stratos SVOS prototype](archive/stratos-svos-prototype/README.md) — historical external prototype snapshot

---

## How to use this docs tree

- Start from this file (`docs/index.md`).
- When docs conflict, [DOC_AUTHORITY.md](00_Project/DOC_AUTHORITY.md) governs — not recency.
- Treat everything under `docs/Archive/` as historical record, non-prescriptive.
- For day-to-day change tracking, use `CHANGE_CONTROL_SYSTEM.md` and `scripts/document_change.py`.
- CI enforces: no dead links, no orphaned docs (new docs must be linked from here). Run `python scripts/lint_docs.py` locally before pushing.

**Known limitations:** this tree is organized by historical accretion rather than a designed taxonomy. This index is a stabilization bridge, not a restructure. The `scripts/lint_docs.py` CI gate keeps it from drifting, not goodwill.
