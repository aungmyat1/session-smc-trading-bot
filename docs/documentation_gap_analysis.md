# Documentation Gap Analysis

---
Owner: Documentation Team
Status: Draft
Version: 0.1
Last Reviewed: TODO
Next Review: TODO
Related Documents: docs/documentation_inventory.md, docs/documentation_health_report.md
---

Generated during Phase 2 of the documentation audit. This document lists high-level gaps found so far and directs further verification tasks.

Summary findings (initial pass):
- Many docs exist for SVOS and strategy audits and appear recent (2026-06-29). These should be treated as authoritative for SVOS unless contradicted by code.
- Several legacy guides exist in `docs/Archive/` and `archive/` — these are historical and should be indexed but not used as authority.
- Root-level files (CURRENT_ARCHITECTURE.md, CLAUDE.md, LOOKAHEAD_AUDIT.md) may duplicate content in `docs/`; mark for consolidation.
- README.md needs to be rewritten to point to the new docs root.

High-priority mismatches to verify (TODOs):
1. Confirm that `docs/svos/DEPLOYMENT_TOPOLOGY.md` matches `deploy/` and `deploy/gcp-vm1` README contents.
2. Verify `docs/architecture/` references (module names, service names) against `src/`, `svos/`, and `execution/` folders.
3. Check CI/CD workflows for references to docs (GitHub Actions may depend on location of runbooks).
4. Validate all runbook commands in `docs/operations/deployment_runbook.md` against existing scripts in `deploy/` and `scripts/`.

Architecture duplication and lifecycle mismatch (findings)
- `docs/SYSTEM_ARCHITECTURE.md` and `docs/svos/CORE_ARCHITECTURE.md` are both authoritative-looking documents but target different authority levels (Level 2 vs Level 3). They currently contain overlapping content and differing lifecycle stage lists.
- There is a documented mismatch between the lifecycle stages enumerated in `SYSTEM_ARCHITECTURE.md` (17 stages) and the implementation in `svos/lifecycle/manager.py` (11 stages). This is a source of confusion and must be resolved by adding a clear cross-reference table and making one document the lifecycle authority.
- `CURRENT_ARCHITECTURE.md` appears in multiple locations and is referenced by status reports; it duplicates content in `docs/`. Recommend archiving or merging after verification.
- `CLAUDE.md` contains lifecycle references and phases that appear to be stale; treat agent-only operational instructions separately from architecture authority.

Evidence: automated grep found many references across `docs/` and code; see `docs/documentation_inventory.md` and `docs/_full_inventory_files.md` for the full list.

Recommended immediate fixes:
1. Declare canonical lifecycle document (proposed: `docs/svos/CORE_ARCHITECTURE.md` for SVOS lifecycle authority) and add a cross-reference table into `docs/SYSTEM_ARCHITECTURE.md` mapping legacy phase names to `svos/lifecycle` enums.
2. Add `Owner:` and `Last reviewed:` headers to `docs/SYSTEM_ARCHITECTURE.md`, `docs/svos/CORE_ARCHITECTURE.md`, and `CURRENT_ARCHITECTURE.md` before merging.
3. Create a small validation script or CI job that fails if `svos/lifecycle/manager.py` and the chosen canonical lifecycle doc deviate. (Next step — implement as a follow-up.)


For each file listed in `docs/documentation_inventory.md`, the next step is to:
- open and verify header metadata (owner, last reviewed)
- check all links (internal and external)
- confirm referenced scripts/paths exist
- mark recommended action (KEEP / UPDATE / MERGE / ARCHIVE)

Automated checks pending:
- Link scan across repository (internal markdown links and absolute paths) — TODO
- Image path verification — TODO
- Cross-reference index (which files reference which docs) — TODO

Next actions:
- Perform link scan and create `docs/documentation_health_report.md` (Phase 12)
- Consolidate duplicate architecture docs into `docs/architecture/system_architecture.md` (Phase 8)
- Standardize `README.md` to reference `docs/project_overview.md` and `docs/current_status.md` (Phase 10)
