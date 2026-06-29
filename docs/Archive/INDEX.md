# Documentation Archive Index

Date: 2026-06-29
Status: Authoritative
Version: 1.0
Updated: 2026-06-29
Owner: Platform Architecture

---

## Purpose

This index records every archived document, the reason it was archived, and
what supersedes it (if anything). Documents in this archive must never be
used as implementation guidance.

To access a document's content, navigate to its path below.
To find the current authoritative version, follow the "Superseded By" column.

---

## Archive/SUPERSEDED/ — Superseded Documents

Documents that were once active but have been replaced by a governing document.

| File | Original Purpose | Archived Date | Reason | Superseded By |
|---|---|---|---|---|
| CURRENT_SCOPE.md | Defined project scope | 2026-06-29 | Directly contradicts the governing plan: states EVF/RGM/SMO is out of scope while the governing plan explicitly builds them | STRATEGY_ENGINEERING_PLATFORM_IMPLEMENTATION_PLAN.md |
| IMPLEMENTATION_STATUS.md | Tracked implementation status | 2026-06-29 | Superseded by the governing plan and STABILIZATION_STATUS.md; the implementation summary it contains is stale | STRATEGY_ENGINEERING_PLATFORM_IMPLEMENTATION_PLAN.md + architecture-review-2026-06-29/06_UPGRADE_ROADMAP.md |
| ESTIMATED_DEVELOPMENT_ROADMAP.md | Estimated development phases | 2026-06-29 | Phase numbering conflicts with canonical lifecycle; aspirational gate thresholds differ from CLAUDE.md; superseded by governing plan | STRATEGY_ENGINEERING_PLATFORM_IMPLEMENTATION_PLAN.md |
| PROJECT_OBJECTIVE_FASTEST_PATH.md | Fastest path to live trading | 2026-06-29 | Centered on deploying ST-A2 as a live bot; inconsistent with current platform mission and ST-A2 DEFERRED_REVALIDATION status | STRATEGY_ENGINEERING_PLATFORM_IMPLEMENTATION_PLAN.md |
| PROJECT_LIVE_STATUS_TIMELINE.md | Live deployment status timeline | 2026-06-29 | Live deployment timeline for ST-A2 which is deferred; inconsistent with current platform status | STABILIZATION_STATUS.md |
| PROJECT_STATUS.md | General project status | 2026-06-29 | Stale status snapshot; superseded by STABILIZATION_STATUS.md and architecture review | docs/svos/STABILIZATION_STATUS.md |

---

## Archive/ST-A2_LEGACY/ — ST-A2 Legacy Research

ST-A2 status is DEFERRED_REVALIDATION (approved: false, current: false).
These documents are preserved as legacy research material. They cannot satisfy
any current qualification gate and must not be used as implementation guidance.
See CLAUDE.md §6.

| File | Purpose | Archived Date | Note |
|---|---|---|---|
| ST_A2_CONFIRMATION.md | EXP-01 backtest confirmation | 2026-06-29 | Historical research evidence; preserved but not current |
| ST_A2_D1_COMPARISON_REPORT.md | D1 filter comparison report | 2026-06-29 | Superseded by VERDICT_LOG.md trial entries |
| ST_A2_D1_FINAL_VERDICT.md | D1 filter final verdict (FAIL) | 2026-06-29 | Verdict recorded in VERDICT_LOG.md |
| ST_A2_D1_IMPLEMENTATION_REPORT.md | D1 filter implementation | 2026-06-29 | Implementation context for deferred strategy |
| ST_A2_DEMO_GO_LIVE_REPORT.md | Demo go-live report | 2026-06-29 | ST-A2 is deferred; live deployment plans are obsolete |
| ST_A2_DEMO_RISK_POLICY.md | Demo risk policy for ST-A2 | 2026-06-29 | ST-A2 is deferred; general risk policy is in RISK_SPEC.md |
| ST_A2_FIRST_30_TRADES_PLAN.md | First 30 trades execution plan | 2026-06-29 | ST-A2 is deferred |
| ST_A2_OPPORTUNITY_ANALYSIS.md | Opportunity analysis | 2026-06-29 | Historical research; DEFERRED_REVALIDATION |
| ST_A2_VANTAGE_DEMO_RUNBOOK.md | Vantage demo runbook | 2026-06-29 | ST-A2 is deferred; general runbook is in VPS_DEPLOYMENT_RUNBOOK.md |
| TRIAL_ST_A2_D1_SPEC.md | D1 trial specification | 2026-06-29 | Trial complete (FAIL); recorded in VERDICT_LOG.md |

---

## Archive/HISTORICAL_EVIDENCE/ — Historical Evidence

Point-in-time research artifacts. Preserved for audit trail. Not prescriptive.

| File | Purpose | Archived Date | Note |
|---|---|---|---|
| HISTORICAL_DATA_AUDIT.md | Early data audit | 2026-06-29 | Superseded by current data pipeline documentation |
| HISTORICAL_DATA_PIPELINE_FINAL_REPORT.md | Pipeline completion report | 2026-06-29 | Historical completion report; pipeline is now operational |
| PHASE22_COLLECTION_HEALTH.md | Collection health check | 2026-06-29 | Point-in-time health snapshot |
| DRY_RUN_2023_03_14.md | Early dry-run | 2026-06-29 | Historical operational record |
| BUG01_RUNTIME_VALIDATION.md | Bug runtime validation | 2026-06-29 | Bug resolved; historical record |
| DEP_02_CONNECTION_REPORT.md | Connection report | 2026-06-29 | Historical deployment record |
| VALIDATION_01_SINGLE_DAY.md | Single-day validation | 2026-06-29 | Early validation; superseded by full validation suite |
| PRE_E6_BASELINE.md | Pre-E6 baseline | 2026-06-29 | Historical baseline snapshot |
| DEMO_GATE_DECISION.md | Demo gate decision | 2026-06-29 | Historical gate decision for deferred ST-A2 |
| CLEANUP_SUMMARY.md | Repository cleanup summary | 2026-06-29 | Historical cleanup record |
| ADAPTIVE_ENGINE_V1.md | Adaptive engine V1 spec | 2026-06-29 | Historical specification; adaptive engine is in adaptive/ package |

---

*Archive created: 2026-06-29*
*All moves preserve git history via git mv.*
*To restore any document to active status: move it back to docs/ and update its status header.*
