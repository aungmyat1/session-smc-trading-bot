# Phase 6 — PM Operating System: Audit, Gap Analysis, and Design

Date: 2026-07-07
Status: Analysis and design only — no production changes, per this phase's
own instruction. No governance document replaced; existing authority
(`pm-governance-cowork.md`, `pm.md`, `docs/00_Project/DOC_AUTHORITY.md`,
`docs/00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md`) remains canonical.

## 1. Executive Summary

This repository has **more existing PM-operational infrastructure than the
prior gap analysis (`docs/governance/GOVERNANCE-GAP-ANALYSIS.md`) captured**.
Most notably: a machine-readable task registry already exists
(`tasks/*.yaml` + `schemas/task.schema.json`), and a real 4-job CI pipeline
already runs. What's missing is not the data model — it's the tooling that
reads/aggregates it, and one field (agent assignment) the schema doesn't
yet capture. Separately, this audit found a **genuine, previously-uncaught
documentation conflict**: two competing SYS1/SYS2 boundary documents
(`docs/SYSTEM_BOUNDARIES.md` vs. `docs/00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md`)
— flagged per this phase's own rule, not silently resolved.

## 2. Repository Audit (Phase 1 — evidence-backed)

| Capability | Evidence | Classification |
|---|---|---|
| Machine-readable task definitions | `schemas/task.schema.json` (JSON Schema, `task`/`priority`/`status`/`depends`/`done_when` fields) + `tasks/*.yaml` (10 files, P0-1 through P1-6) | **Existing** |
| Task registry usage | 7/10 tasks `status: COMPLETE`, 3 `PENDING` — tied to an older stabilization effort (`feature_freeze_lift` language, `docs/svos/STABILIZATION_STATUS.md` cross-reference in `P0-1.yaml`) | **Existing, but dormant** — not used for this week's ADR-0011 through ADR-0014 / infra work, which tracked progress via chat + ADR documents instead |
| Dependency tracking | `depends:`/`blocks:` fields exist in the schema and are populated in task files | **Existing (basic)** — a `depends` list is not the same as a computed dependency graph with cycle detection or blocking-chain visualization |
| Agent assignment tracking | Searched `schemas/task.schema.json` for `agent`/`assign` — zero matches | **Missing** — no field records which specialist agent owns a task |
| Acceptance gate workflow | Task schema has `done_when` (verifiable completion criteria); CI (`ci.yml`) has a `required` job gating merge on `quality`+`tests`+`security`+`docs-and-package` | **Existing (CI-side)**, **Partial (task-side)** — `done_when` states criteria but there's no recorded approval/sign-off step distinct from the criteria being met |
| Evidence tracking | `docs/VERDICT_LOG.md` (append-only, Level 7 authority) for strategy trials specifically; ADRs (`docs/svos/ADR-*.md`) for architecture decisions; no general-purpose evidence ledger for arbitrary PM tasks | **Partial** — strong in its two specific domains (trials, architecture), absent for general task evidence |
| Automatic dashboard generation | None found — `docs/systems/system2/STATUS.md` is hand-maintained prose, `docs/github/REPOSITORY_HEALTH_REPORT.md` exists but its generation mechanism wasn't verified as automated in this pass | **Missing** (or unverified-automated) |
| Progress calculation | No script computes % complete from `tasks/*.yaml` or ADR status | **Missing** |
| Repository health reporting | `docs/github/REPOSITORY_HEALTH_REPORT.md` exists (content/freshness not verified this pass) | **Partial** — exists as a document; automation unverified |
| Sprint tracking | `docs/systems/system2/DEMO_SMOKE_TEST_SPRINT.md` found — a sprint-shaped doc exists for System 2 | **Partial** — one historical sprint doc, not a repeatable sprint-tracking mechanism |
| Milestone tracking | `SYSTEM2_MASTER_PLAN.md`'s numbered phases + `docs/systems/system2/ROADMAP.md` | **Existing** — this is real, current, actively maintained |
| CI/CD automation | `.github/workflows/ci.yml`: `quality`, `tests`, `security`, `docs-and-package` jobs + a `required` gate job | **Existing** |

## 3. Governance Validation

Confirmed still authoritative and unchanged this pass: `pm-governance-cowork.md`
(with last session's Task Lifecycle/Format/Dashboard amendments),
`docs/00_Project/DOC_AUTHORITY.md`, `docs/VERDICT_LOG.md`, the ADR sequence
(`docs/svos/ADR-0001` through `ADR-0014`), `docs/systems/system2/ROADMAP.md`.

**New finding — documentation conflict, not silently resolved:**
`docs/SYSTEM_BOUNDARIES.md` (13 lines, git history traces to `#17`/`#19`,
an older "Original Truth"/"Project Readiness v1" era) states the SYS1/SYS2
boundary in different, shorter terms than `docs/00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md`
(137 lines, the document `pm-governance-cowork.md` actually cites as
canonical). `docs/SYSTEM_BOUNDARIES.md` is **not listed anywhere in
`docs/00_Project/DOC_AUTHORITY.md`'s 14-item authority order** — it appears
to be a superseded document that was never archived when
`TWO_SYSTEM_ARCHITECTURE_TRUTH.md` became canonical.
**Recommendation** (not actioned — this is a call for the owner, per "never
silently choose"): archive `docs/SYSTEM_BOUNDARIES.md` under an `archive/`
path once confirmed superseded, or add it explicitly to `DOC_AUTHORITY.md`'s
order if it still serves a distinct purpose. Do not delete without that
confirmation.

## 4. Operational Gap Analysis (Phase 2 summary)

| Capability | Status |
|---|---|
| Task registry | Existing |
| Machine-readable task definitions | Existing |
| Dependency tracking | Existing (basic) |
| Agent assignment tracking | **Missing** |
| Acceptance gate workflow | Partial |
| Evidence tracking | Partial |
| Automatic dashboard generation | Missing |
| Progress calculation | Missing |
| Repository health reporting | Partial |
| Sprint tracking | Partial |
| Milestone tracking | Existing |

## 5. PM Operational Design (Phase 3 — design only, not implemented)

Reusing existing governance rather than replacing it:

- **Task management**: extend `schemas/task.schema.json` with an optional
  `assigned_agent` enum (matching `docs/governance/AGENT_DIRECTORY.md`'s
  6 agents) and an optional `evidence` array (paths to reports/logs proving
  `done_when` was met). Additive fields only — every existing `tasks/*.yaml`
  file remains valid without modification (JSON Schema `required` list
  unchanged).
- **Dependency graph**: a read-only script (`scripts/task_graph.py`,
  proposed name) that parses `tasks/*.yaml`'s `depends`/`blocks` fields and
  reports cycles/blocking chains — pure analysis, no new data format.
- **Agent orchestration**: `docs/governance/AGENT_DIRECTORY.md` (created
  last session) is the assignment reference; the new `assigned_agent` field
  above links a task to it.
- **Acceptance gates**: formalize what "PM Review" (Phase 10-11 of this
  prompt's own workflow) actually checks — a checklist referencing
  `done_when` + evidence array + existing CI `required` gate, not a new gate
  mechanism.
- **Evidence collection**: point at what already exists per domain
  (`VERDICT_LOG.md` for trials, ADRs for architecture, CI artifacts for
  tests) rather than building a new general ledger — a general one is only
  justified if task-level evidence genuinely doesn't fit any existing
  domain-specific log, which hasn't been demonstrated yet.
- **Progress reporting**: a script that reads `tasks/*.yaml` status fields +
  `docs/systems/system2/ROADMAP.md`'s phase table + ADR statuses, and
  renders the Progress Dashboard fields already specified in
  `pm-governance-cowork.md`'s amendment from last session — generation, not
  a new manually-maintained file.
- **Decision history**: already exists (ADRs + VERDICT_LOG) — no new
  mechanism proposed.
- **Review workflow**: matches this prompt's own Phase 5 workflow diagram
  almost exactly to `pm.md`'s existing "Before assigning any task" +
  "Output format" sections — the workflow already exists in policy; what's
  missing is the tooling to check its steps mechanically instead of by PM
  attention alone.

## 6. Recommended Implementation Roadmap (Phase 4)

| Step | Objective | Repo impact | Dependencies | Risk | Complexity | Rollback | Acceptance criteria |
|---|---|---|---|---|---|---|---|
| 1 | Add `assigned_agent` + `evidence` fields to `schemas/task.schema.json` | 1 file, additive only | None | Low | Trivial | Revert the diff | Existing `tasks/*.yaml` still validate |
| 2 | Resolve the `SYSTEM_BOUNDARIES.md` vs. `TWO_SYSTEM_ARCHITECTURE_TRUTH.md` conflict | Archive or formally register 1 file | Owner decision (§3) | Low | Trivial | Restore from archive | `DOC_AUTHORITY.md` has zero unlisted boundary docs |
| 3 | Build `scripts/task_graph.py` (read-only dependency/status report over `tasks/*.yaml`) | 1 new script | Step 1 (for agent field, optional) | Low | Small | Delete the script | Produces correct output against the existing 10 task files |
| 4 | Build a Progress Dashboard generator reading ROADMAP/ADR/task status | 1 new script | Steps 1, 3 | Low | Medium | Delete the script | Matches the field list in `pm-governance-cowork.md`'s amendment |
| 5 | Decide whether the dormant `tasks/` registry should be revived for current work (this week's MT5/ADR work wasn't tracked there) or left as historical stabilization-era record | 0 files (decision only) | None | Medium (affects future PM workflow adoption) | N/A | N/A | Owner decision recorded |

Each step is independently reviewable and small, per this phase's
"prefer small, independently reviewable changes" instruction. **None of
these steps are implemented in this phase** — this is the plan only.

## 7. PM Workflow Validation (Phase 5)

| Workflow step | Supported today by | Gap |
|---|---|---|
| Owner → PM | This conversation | None |
| Task Analysis | `pm.md`'s "Before assigning any task" | None |
| Architecture Review | ADR process, `TWO_SYSTEM_ARCHITECTURE_TRUTH.md` | None |
| Risk Review | `docs/operations/risk-register.md` | None |
| Agent Assignment | `docs/governance/AGENT_DIRECTORY.md` | **Missing the machine-readable link** — Roadmap step 1 closes this |
| Implementation | `coder-agent` | None |
| Testing | CI (`ci.yml`) | None |
| Evidence Collection | VERDICT_LOG / ADRs / CI artifacts, per-domain | **No task-level evidence field** — Roadmap step 1 closes this |
| PM Review | `pm.md`'s "Output format" | None |
| Owner Approval | This conversation | None |

**Conclusion**: the workflow is almost entirely supported already. The two
real gaps (agent-assignment linkage, task-level evidence field) are both
closed by Roadmap Step 1 alone — a single, small, additive schema change.

## 8. Agent Contract Review (Phase 6)

All 6 existing agents (`pm`, `strategy`, `risk`, `backtest`, `execution`,
`coder`) already have consistent frontmatter: `name`, `description`, `tools`.
Responsibilities/scope are stated in each `description` field (verified
directly, not assumed — see `docs/governance/AGENT_DIRECTORY.md` for the
consolidated table built last session). **No inconsistency found** —
standardization is not recommended, per this phase's own "recommend
standardization only if inconsistencies exist" instruction. The only gap is
the missing `assigned_agent` schema field noted above, not the agent
definitions themselves.

## 9. Dashboard Automation Feasibility (Phase 7)

Evidence sources confirmed available for automatic generation:
`tasks/*.yaml` (status), `docs/systems/system2/ROADMAP.md` (phase progress,
already a markdown table — parseable), `docs/svos/ADR-*.md` (status field
in each ADR's frontmatter, already consistent across all 14), `docs/operations/risk-register.md`
(already a markdown table), `scripts/disk_report.py` (already produces
JSON via `--json`), CI status (`gh` CLI or GitHub API). **Feasible** — no
missing data source; Roadmap Step 4 is the only remaining work.

## 10. Immediate Next Actions

1. **Owner decision needed**: resolve `SYSTEM_BOUNDARIES.md` vs.
   `TWO_SYSTEM_ARCHITECTURE_TRUTH.md` (Roadmap Step 2) — a real conflict,
   not something to silently pick a side on.
2. **Owner decision needed**: is the dormant `tasks/` registry meant to be
   revived for current PM tracking, or left as historical stabilization
   record (Roadmap Step 5)? This determines whether Steps 1/3/4 are worth
   doing now or deferred.
3. If both are answered, Steps 1, 3, 4 are small, low-risk, independently
   approvable — ready to implement on confirmation.
