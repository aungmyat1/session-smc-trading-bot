---
Date: 2026-07-12
Author: Lead Architect audit (Claude)
Authority: Level 8 — informational evidence. Does not supersede `docs/00_Project/DOC_AUTHORITY.md`.
Scope: Consolidated technical debt remaining after this reconciliation program's Phases 1-8.
---

# Technical Debt After Reconciliation

Consolidated from the 2026-07-12 demo-readiness audit (`ARCHITECTURE_REALITY_MAP.md`,
`DOCUMENTATION_ALIGNMENT_REPORT.md`) and this reconciliation program's Phases 1-8.
Nothing here blocks demo readiness — all items are explicitly deferred, not hidden.

## Code debt

1. **Three parallel broker-client implementations**: `execution/mt5_connector.py`
   (live), `execution/metaapi_client.py` + `execution/mt5_executor.py`
   (dormant, serve only the disconnected `bot.py`/`order_manager.py` path).
   Risk: a future change could touch the wrong one. Not urgent — only one is
   on the live call path.
2. **No duplicate-order prevention** in `TradeManager.open_position()` — see
   `SYSTEM2_CORRECTNESS_AUDIT.md`. Tracked as the next PR in
   `NEXT_IMPLEMENTATION_SEQUENCE.md`, not carried forward as unaddressed debt.
3. **`session_smc/` directory status unresolved** — appears to be nested
   full-repo copies, not a normal package; no confirmed live import found,
   but not fully import-verified either. Needs a dedicated check before any
   deletion/archival decision.
4. **Possible duplicate SYS2-T014 implementations** — `main`'s `d140783`
   (PR #27) vs. `codex/demo-smoke-test`'s `81f7adf`. `SYSTEM2_CORRECTNESS_AUDIT.md`
   confirms `main`'s version already resolves the underlying defect; the
   branch version is very likely fully superseded, pending the explicit diff
   comparison recommended in `EXTRACTION_PLAN.md`.
5. **`config/risk.yaml` vs. per-strategy risk tiers in `config/strategy_portfolio.yaml`**
   — not confirmed which code path actually consumes `risk.yaml`; may be
   dead/legacy. Not verified this session.
6. **`config/validation.yaml` stale gate** — still encodes the pre-2026-07-01
   threshold (n≥50, PF>1.0, no Sharpe). Flagged in `STA2_REVALIDATION_PLAN.md`
   as a preparation-phase fix, not yet applied.

## Documentation debt

7. **Root-level docs outside `DOC_AUTHORITY.md`'s hierarchy**:
   `SYSTEM2_MASTER_PLAN.md`, `ARCHITECTURE_STABILIZATION_ROADMAP.md` both
   self-declare "Authoritative" status without being registered in the
   Level 0-9 authority table. In practice they are kept current and reliable
   (verified repeatedly this session), but the governance structure doesn't
   formally say so.
8. **`README.md` describes a conflicting lifecycle taxonomy** (EVF/RGM/SMO/ISOP)
   that matches neither CLAUDE.md's canonical enum nor `svos/lifecycle/manager.py`'s
   actual 11-stage enum. Unmaintained (`Owner`/`Last Reviewed`: TODO).
9. **SVOS feature-freeze reconciliation ambiguity**: `docs/svos/STABILIZATION_STATUS.md`
   (2026-06-30, "NOT READY") was never formally updated, while root-level
   docs describe unblocked System2 work in the same window. Needs one
   written decision, not more code.
10. **Documentation sprawl**: 180+ files under `docs/`, ~25 pre-existing files
    already in `docs/audit/` alone before this program added five more.
    `docs/svos/CURRENT_STATE.md` and `docs/audit/CURRENT_PROJECT_STATUS.md`
    both already flag this independently. Not adding to it further than
    required is itself part of managing this debt.
11. **`svos/lifecycle/manager.py`'s actual enum (11 stages) diverges from
    CLAUDE.md §3's documented enum (16 stages)** — the documented "canonical
    lifecycle lives in `svos/lifecycle/manager.py`" claim isn't byte-for-byte
    accurate today.

## Product/architecture debt (explicitly not touched by this program)

12. **Dual SVOS orchestrators**: `research/svos/engine.py` (script-driven,
    active) vs. the newer `svos/` backend package. Tracked in
    `docs/svos/CURRENT_STATE.md`; out of scope for System2-first work by
    design.
13. **`"New Dashborad/"` frontend prototype** — disconnected from the Python
    backend, zero effect on demo readiness. Ignore until a deliberate
    frontend-integration decision is made.
14. **Wine/mt5linux path** (`execution/mt5linux_connector.py`, `ADR-0011`,
    `ADR-0013`) — confirmed broken, explicitly superseded by `ADR-0014`'s
    decision to stay on MetaAPI and investigate FIX API instead. Not debt to
    "pay down" — a closed, correctly-rejected path. Listed here only for
    completeness; see Phase 9 / `BRANCH_RECONCILIATION_REPORT.md` for the
    full rejection rationale.

## Explicitly not debt (verified this session, do not re-flag)

- Emergency-stop enforcement, resume-scoping, close-reconciliation edge
  cases, recovery reconciliation — all confirmed fixed/working by direct
  code read, not just docs. Do not re-open these as "possible gaps" in a
  future audit without first checking `SYSTEM2_CORRECTNESS_AUDIT.md`.
