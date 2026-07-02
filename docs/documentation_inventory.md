# Documentation Inventory

---
Owner: Documentation Team
Status: Generated (needs review)
Version: 0.1
Last Reviewed: TODO
Next Review: TODO
Related Documents: docs/documentation_gap_analysis.md, docs/_full_inventory_files.md
---

This file is an automated-first inventory created during the documentation audit (Phase 1).

Notes:
- Fields marked `TODO` require manual review and verification.
- This inventory focuses on authoritative documents and high-value artifacts. A fuller machine-generated CSV exists in the audit working artifacts.

| Document Name | Path | Purpose | Current Status | Last Updated | Referenced By | Used by CI? | Duplicate? | Outdated? | Recommended Action |
|---|---:|---|---|---|---|---|---|---|---|
| README | README.md | Project entrypoint / overview | REVIEW_NEEDED | TODO | TODO | No | No | Possibly | UPDATE -> link to `docs/project_overview.md` |
| Project Objective | docs/PROJECT_OBJECTIVE.md | Canonical project objective draft | EXISTS | TODO | TODO | No | Possible duplicates | TODO | MERGE/VERIFY into `docs/project_overview.md` |
| SVOS Core Arch | docs/svos/CORE_ARCHITECTURE.md | SVOS architecture reference | EXISTS | 2026-06-29 | TODO | No | No | Likely current | KEEP as authoritative for SVOS; link from `docs/architecture/` |
| Deployment Topology | docs/svos/DEPLOYMENT_TOPOLOGY.md | Deployment topology for SVOS | EXISTS | 2026-06-29 | TODO | No | No | Likely current | KEEP / VERIFY against infra code |
| System Architecture (legacy) | CURRENT_ARCHITECTURE.md | Older architecture snapshot | EXISTS | TODO | TODO | No | Duplicate of docs/SYSTEM_ARCHITECTURE.md | Possibly | ARCHIVE or MERGE after review |
| Strategy Audit docs | docs/strategy_audit/** | Per-strategy specs and audits | EXISTS | Varies | TODO | No | No | Some files archived | KEEP but standardize location and headers |
| Operations & Runbooks | docs/operations/** + docs/VPS_DEPLOYMENT_RUNBOOK.md | Runbooks and ops checklists | EXISTS | Varies | TODO | No | Possible duplicates | TODO | CONSOLIDATE into `docs/operations/` |
| Archive folders | docs/Archive/** and archive/** | Historical artifacts and reports | ARCHIVE | Varies | TODO | No | Yes | ARCHIVE | Leave in `docs/Archive/` but index them (see docs/archive/README.md)
| CLAUDE instructions | CLAUDE.md | Agent-specific instruction (internal) | EXISTS | TODO | TODO | No | No | TODO | KEEP; add owner and last-reviewed
| Readiness & Gates | docs/READINESS_CRITERIA.md, docs/DEPLOYMENT_READINESS.md | Deployment/readiness gates | EXISTS | Varies | TODO | No | Possible duplicates | TODO | MERGE into standardized `docs/roadmap`/`docs/operations`
| Architecture collection | docs/architecture/** | Modular architecture docs | EXISTS | Varies | TODO | No | Partial duplication | TODO | Consolidate under `docs/architecture/system_architecture.md`

--

This inventory is intentionally conservative: many files are marked `TODO` where verification against code is required. Next step: gap analysis (docs/documentation_gap_analysis.md) which will validate references and list mismatches.
