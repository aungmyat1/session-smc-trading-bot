# DOCUMENTATION_GOVERNANCE

## Canonical documentation list

- `README.md`
- `docs/PROJECT_OBJECTIVE.md`
- `docs/SYSTEM_BOUNDARIES.md`
- `docs/SYSTEM_ARCHITECTURE.md`
- `docs/SVOS_DESIGN_REFERENCE.md`
- `docs/STRATEGY_VALIDATION_ENGINE.md`
- `docs/DEPLOYMENT_READINESS.md`
- `docs/REPORT_SYSTEM.md`
- `docs/SVOS_STRATEGY_AUDIT_WORKFLOW_VALIDATION.md`
- `docs/INDEX.md`
- `docs/documentation_health_report.md`
- `docs/documentation_readiness_report.md`
- `docs/documentation_coverage_report.md`
- `docs/documentation_freeze_checklist.md`
- `docs/DOCUMENTATION_GOVERNANCE.md`
- `docs/FINAL_DOCUMENTATION_STATUS.md`
- `docs/remaining_reference_decision_matrix.md`

## Ownership model

- Documentation is owned by domain stewards. Each doc SHOULD include an owning team or individual in its front-matter or first section.
- `docs/` content ownership is divided into:
  - Project/strategy: `docs/PROJECT_OBJECTIVE.md`, `docs/SYSTEM_BOUNDARIES.md`, `docs/PROJECT_READINESS_*.md`
  - Architecture: `docs/SYSTEM_ARCHITECTURE.md`, `docs/SVOS_DESIGN_REFERENCE.md`, `docs/architecture/*`
  - Validation and approval: `docs/STRATEGY_VALIDATION_ENGINE.md`, `docs/DEPLOYMENT_READINESS.md`, `docs/REPORT_SYSTEM.md`
  - Operations and runbooks: `docs/OPERATING_MANUAL.md`, `docs/VPS_DEPLOYMENT_RUNBOOK.md`
  - Governance and audit: `docs/documentation_*`, `docs/CHANGE_CONTROL_SYSTEM.md`, `docs/FINAL_DOCUMENTATION_STATUS.md`

## Metadata requirements

- Every canonical doc MUST include: title, last-updated date, owner, and status (draft/reviewed/approved).
- Preferred format is a top-level section such as:
  - `Owner: <name or team>`
  - `Last updated: YYYY-MM-DD`
  - `Status: Draft/Review/Approved`
- Documentation health reports MUST include scan date and issue counts.

## Archive policy

- Archive existing or superseded docs under `docs/archive/` or `archive/` and remove them from the canonical index.
- Archive entries remain searchable but are excluded from current docs scans and governance unless explicitly referenced as historical evidence.
- Files in `docs/archive/` are read-only by policy. New canonical links should not point into archive unless citing historical evidence.

## Generated document policy

- Generated documentation (including auto-generated API docs, package README fragments, or build artifacts) is NOT part of the canonical docs unless it is explicitly promoted by governance.
- Scans MUST exclude generated sources from `node_modules`, `.venv`, `build`, `dist`, `coverage`, `__pycache__`, `.pytest_cache`, and other transient build outputs.
- If generated docs are needed for review, they should be stored in a separate `docs/generated/` path and clearly labeled as generated.

## Review schedule

- Weekly documentation health review for canonical docs.
- Monthly audit of archive and generated docs scope.
- Immediate review whenever the project changes major architecture, deployment, or governance flows.

## Documentation lifecycle

- Draft → Review → Approved → Published → Archived.
- Approved docs remain in the canonical index until superseded or retired.
- Retired docs move to `docs/archive/` and are excluded from active governance scans.
- Documentation issues are tracked as `missing reference`, `missing image`, `broken anchor`, or `orphaned file`.
