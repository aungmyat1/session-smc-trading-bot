---

# Documentation Authority Hierarchy

Date: 2026-06-29
Status: Authoritative
Version: 1.0
Updated: 2026-06-29
Owner: Platform Architecture
Authority: Level 0 — Root
Supersedes: (none — new document)

---

## Purpose

This document is the **root documentation authority** for the SVOS repository.

It must be read first — before any other document — whenever a documentation
conflict must be resolved or when authoritative guidance is needed.

Every document in `docs/` has an authority level. When two documents
contradict each other, the **higher-authority document wins**. The lower
document must be updated or archived, not both followed.

---

## Authority Order

| Level | Authority | Documents |
|---|---|---|
| 0 | Root authority | `docs/00_Project/DOC_AUTHORITY.md` (this document) |
| 1 | Product authority | `docs/svos/STRATEGY_ENGINEERING_PLATFORM_IMPLEMENTATION_PLAN.md` |
| 2 | Architectural authority | `docs/SYSTEM_ARCHITECTURE.md` |
| 3 | Implementation authority | `docs/svos/CORE_ARCHITECTURE.md` |
| 4 | Decision authority | `docs/svos/ADR-*.md` |
| 5 | Phase specification authority | `docs/STAGE1_AUDIT_SPEC.md`, `docs/HISTORICAL_REPLAY.md`, `docs/BACKTEST_SPEC.md`, etc. |
| 6 | Module documentation | `pipeline/README.md`, `db/README.md`, etc. |
| 7 | Historical reports and evidence | `reports/`, `research/` |
| 8 | Superseded / archive | `docs/Archive/` — never authoritative |

**Rule:** A document at level N may not contradict a document at level N−1 or
above. If such a contradiction is found, the lower-level document must be
updated or archived. Do not follow both.

---

## Conflict Resolution Rules

When documents disagree:

1. Identify the authority level of each conflicting document.
2. The document at the lower level number (higher authority) is correct.
3. Update or archive the document at the higher level number.
4. If both documents are at the same level, stop and escalate to a human owner.

**If two documents at the same level directly contradict each other on a
critical point (lifecycle stage, broker access, phase gate):** STOP. Do not
choose one. Report the conflict with exact citations and wait for resolution.

---

## Canonical Lifecycle Vocabulary

All documents must use the stage names from `svos/lifecycle/manager.py`.

| Canonical Stage Enum | Do Not Use |
|---|---|
| `DRAFT` | "new", "initial" |
| `INTAKE` | "Phase 0 intake", "strategy intake" |
| `AUDIT` | "Phase 0", "Phase 1", "strategy audit phase" without citing source |
| `REFINEMENT` | "Phase 1", "enhancement", "AI editing phase" |
| `HISTORICAL_REPLAY` | "Phase 2", "replay", "historical replay phase" |
| `STATISTICAL_VALIDATION` | "Phase 3", "backtest", "backtesting phase" |
| `ROBUSTNESS_VALIDATION` | "Phase 4", "robustness" without citing source |
| `VERIFICATION_READY` | "Phase 5", "verification ready" |
| `VIRTUAL_DEMO` | "Phase 5 demo", "Virtual Demo Trading" — must always specify OFFLINE |
| `EXECUTION_VALIDATION` | "Phase 6", "EVF", "execution validation phase" |
| `PAPER_TRADING` | "shadow", "paper trade" |
| `LIVE_DEMO` | "demo", "Live MT5 Demo" — must always specify ONLINE/POST-APPROVAL |
| `PRODUCTION_CANDIDATE` | "pre-production" |
| `PRODUCTION` | "live", "deployed" |
| `MONITORING` | "monitoring phase" |
| `REVALIDATION` | "re-validation" |
| `RETIRED` | "deprecated strategy", "stopped" |

**Legacy phase numbers** (Phase 0–6 from CLAUDE.md, IMPLEMENTATION_PLAN stages 0–6)
are summary views only. They do not name individual stages. Use canonical
enum names when writing code, documentation, or configuration.

---

## Document Status Values

Every document in `docs/` must have one of these statuses in its header:

| Status | Meaning | May be acted upon? |
|---|---|---|
| `Draft` | Being written; not validated | No |
| `Review` | Submitted for review; not yet approved | No |
| `Approved` | Approved; may not yet match implementation | With caution |
| `Authoritative` | Approved and verified against current code | Yes |
| `Deprecated` | Superseded; still readable | No — read successor |
| `Archived` | Moved to `Archive/` | Never |

A document with no `Status:` header must be treated as `Draft`.

---

## AI Coding Agent Rules

AI agents MUST follow these rules when working in this repository.

### Must Do

1. Read this document (`DOC_AUTHORITY.md`) before reading any other doc.
2. Check the `Status:` header of every document before acting on it.
3. Use canonical lifecycle stage names (table above) in all code and docs.
4. When two Authoritative documents disagree, stop and report the conflict.
5. Verify lifecycle transitions against `svos/lifecycle/manager.py`.
6. Use `docs/00_Project/GLOSSARY.md` for all domain term definitions.
7. Trace every feature to its governing plan section before implementing.

### Must Never Do

8. Act on documents with status `Deprecated`, `Archived`, or no header.
9. Introduce a new lifecycle stage name without updating `svos/lifecycle/`, `CORE_ARCHITECTURE.md`, and `GLOSSARY.md` in the same change.
10. Write lifecycle state via YAML — `config/strategy_catalog.yaml` is a read-only projection.
11. Enable live trading — `LIVE_TRADING=false` and `DEMO_ONLY=true` are platform invariants until an explicit `CONFIRM-LIVE-ON` token is issued by a human operator.
12. Treat `docs/Archive/` content as prescriptive — it is historical record only.
13. Extend `README.md` with architecture content — README is navigation only.
14. Resolve a conflict between two Authoritative documents by choosing one — always escalate.

---

## Related Documents

- `docs/00_Project/GLOSSARY.md` — canonical domain term definitions
- `docs/SYSTEM_ARCHITECTURE.md` — authoritative lifecycle and architecture reference
- `docs/svos/STRATEGY_ENGINEERING_PLATFORM_IMPLEMENTATION_PLAN.md` — governing product plan
- `docs/svos/CORE_ARCHITECTURE.md` — SVOS implementation authority
- `docs/svos/ADR-0001-STABILIZATION-FOUNDATION.md` — accepted architecture decisions

---

*This document is immutable except by the Lead Architect and is superseded only*
*by a new version of itself.*
