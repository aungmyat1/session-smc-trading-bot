# Repository Consistency Report

Date: 2026-07-02
Status: Draft — repository consistency audit findings
Scope: Mapping current repository structure, documentation coverage, implementation gaps, and traceability for the session-smc trading platform.

## Purpose

This report summarizes the current code-to-documentation consistency audit for the platform. It identifies where documented architecture, pipeline, and governance claims align with actual implementation, and where gaps remain.

## Methodology

- Reviewed repository top-level directories, Python modules, and documentation coverage counts.
- Cross-referenced code modules against documentation references in `docs/`.
- Identified high-risk implementation gaps from code duplication, missing packaging or runtime checks, and mismatched pipeline wiring.
- Used existing audit artifacts in `docs/project_readiness_assessment.md`, `docs/REPOSITORY_AUDIT.md`, and `docs/svos/DOC_AUDIT_2026-06-29.md` as baseline context.

## Code / Documentation Coverage Summary

| Component | Python modules | Docs referencing component | Notes |
|---|---|---|---|
| `svos` | 46 | 109 | Strong documentation density. Documentation is broad but some coverage is architectural/intent rather than implementation tracing.
| `strategy_validation` | 21 | 30 | Core validation docs exist, but there is incomplete explicit code-to-doc traceability for phase wiring.
| `execution` | 16 | 166 | High reference count; execution architecture is heavily documented, yet runtime path differences remain.
| `dashboard` | 14 | 85 | Dashboard features are documented in many places, but there are multiple UI/code surfaces and no single traceability map.
| `adaptive` | 23 | 45 | Adaptive execution has dedicated docs, but a consistent implementation status narrative is absent.
| `core` | 10 | 75 | Shared platform core is documented; risk and portfolio guard wiring need stronger code link documentation.
| `pipeline` | 6 | 80 | Pipeline docs identify target architecture, but current code fragmentation is not fully represented.
| `strategy_audit` | 17 | 26 | Legacy vs. active audit engines are documented; the gap is largely one of active/archived state clarity.
| `approval_package` | 6 | 2 | Documentation exists only in broad package reports and not in a dedicated packaging architecture doc.
| `production` | 10 | 97 | Production import and deployment are referenced; the current execution gate implementation is not fully traced.
| `simulator` | 3 | 25 | Simulator code has limited docs; this is a small but important coverage gap.
| `reports` | 0 | 88 | Report generation is well documented, but implementation traceability to the report pipeline is weak.

## Key Consistency Findings

### 1. Pipeline implementation vs documented target

- Documentation defines a two-system architecture: SVOS research + production execution.
- Actual repository contains both systems, but there is duplication and parallel implementation:
  - `svos/application/*` vs `research/svos/engine.py` and `research/validation/engine.py`
  - `strategy_audit/` legacy audit engine alongside `strategy_validation/` active validators
- The target pipeline is not represented by a single canonical code path; the current repo has multiple alternate paths that are not clearly disambiguated in docs.

### 2. Strategy artifact and packaging gap

- Existing docs describe an approved strategy package and checksum verification.
- There is no code that assembles a multi-file strategy package or enforces bundle checksum in the production path.
- `approval_package/` currently contains validator and registry helpers, but not the full packaging/runtime verifier described by docs.

### 3. Production risk and runtime enforcement gap

- Documentation expects production risk limits to be loaded from strategy configuration.
- The live/demo execution path contains hardcoded defaults and risk code that is not fully wired to the actual strategy portfolio config.
- The daily/weekly/monthly loss-halt path appears present in code but is functionally unsupported because close-event feedback is not propagated.

### 4. Traceability gaps

- Several architectural and project-level docs cite the same modules, but they do not provide a consistent traceability matrix.
- There is no single document mapping:
  - `docs/CLAUDE.md` / `docs/SYSTEM_ARCHITECTURE.md` phases → concrete code modules
  - `docs/PROJECT_OBJECTIVE.md` / `docs/SVOS_DESIGN_REFERENCE.md` → tests
  - strategy trial verdicts in `docs/VERDICT_LOG.md` → runner scripts and report producers

### 5. Documentation coverage imbalance

- Core infrastructure and execution are heavily documented.
- Specialized flow areas such as `approval_package`, `simulator`, and `strategy_input` are under-documented relative to the code.
- `reports` are documented as a domain; the actual report producer code is not consistently mapped to the documented report types.

## Recommendations

1. Consolidate the active pipeline implementation and document the canonical path vs legacy/archived alternatives.
2. Add a dedicated `docs/approval_package_architecture.md` or similar to bridge `approval_package/` code with docs.
3. Create a code-to-doc traceability matrix for the SVOS lifecycle, execution path, and report pipeline.
4. Capture the production risk configuration wiring in a separate implementation note.
5. Use the new audit artifacts created alongside this report as a baseline for the next revision.

## Next deliverables

- `docs/implementation_gap_matrix.md`
- `docs/TRACEABILITY_MATRIX.md`
- `docs/PROJECT_READINESS_v2.md`
- `docs/IMPLEMENTATION_PRIORITY_BACKLOG.md`

These are generated in support of the current repository consistency audit.
