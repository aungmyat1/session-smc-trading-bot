---
Date: 2026-07-12
Author: PM/Architect audit (Claude)
Authority: Level 8 — informational evidence. Does not supersede
`docs/00_Project/DOC_AUTHORITY.md`. Where this report and a Level 0-5 document
disagree, the higher-authority document wins per that hierarchy's own rules.
Scope: Phase 1 of the demo-readiness audit requested 2026-07-12.
---

# Documentation Alignment Report

## Method

Read `docs/00_Project/DOC_AUTHORITY.md` first (per its own rule). Classified
the highest-traffic docs governing the demo-trading objective against it:
GREEN = current source of truth, YELLOW = partially outdated / authority
ambiguous, RED = obsolete or actively conflicting. Full-repo doc inventory
(180+ files under `docs/`, three more large root-level `.md` files, 25+ files
already in `docs/audit/`) was not read file-by-file — that volume is itself a
finding (see §3).

## 1. Classification table

| Doc | Date | Status header | Class | Why |
|---|---|---|---|---|
| `docs/00_Project/DOC_AUTHORITY.md` | 2026-06-29 | Authoritative, Level 0 | GREEN | Root authority, internally consistent, no conflicts found |
| `docs/00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md` | 2026-07-02/03 | Authoritative, Level 1 | GREEN | Matches CLAUDE.md §1; consistent with SYSTEM_ARCHITECTURE.md |
| `docs/SYSTEM_ARCHITECTURE.md` | reviewed 2026-07-03 | Authoritative, Level 3 | GREEN | Consistent with Level-1 doc |
| `docs/svos/CORE_ARCHITECTURE.md` | reviewed 2026-06-29 | Authoritative, Level 4 | GREEN | Consistent; honestly flags its own implementation debt |
| `svos/lifecycle/manager.py` | current | code, not doc | YELLOW | Defines 11 stages (`DRAFT…RETIRED`); CLAUDE.md §3 documents 16 stages (adds `VERIFICATION_READY, EXECUTION_VALIDATION, PAPER_TRADING, LIVE_DEMO, PRODUCTION_CANDIDATE, PRODUCTION, MONITORING`) that do not exist in code. CLAUDE.md's claim "the canonical lifecycle lives in `svos/lifecycle/manager.py`" is not byte-for-byte true today — the doc describes a target superset, not the shipped enum. |
| `docs/svos/architecture-review-2026-06-29/README.md` | 2026-06-29 | Decision: NOT READY (53/100) | YELLOW | Controlling gate; no later doc in `docs/svos/` formally revises this verdict, yet root-level docs describe unblocked follow-on work in the same window |
| `docs/svos/STABILIZATION_STATUS.md` | 2026-06-30 | Verdict: NOT READY | YELLOW | Same issue — last word from the SVOS-governance side is still "freeze active"; no lifting record found |
| `SYSTEM2_MASTER_PLAN.md` (root) | 2026-07-04 | self-declared "Authoritative — single source of truth for System 2" | YELLOW | Most detailed, most current account of what's actually deployed — but it lives **outside** `DOC_AUTHORITY.md`'s Level 0-9 hierarchy entirely. Self-declared authority is not governance-hierarchy authority. |
| `ARCHITECTURE_STABILIZATION_ROADMAP.md` (root) | 2026-07-03 | self-declared Authoritative | YELLOW | Same out-of-hierarchy problem; its own source doc (`PROJECT_GAP_ANALYSIS.md`) is only Review-status |
| `PROJECT_GAP_ANALYSIS.md` (root) | 2026-07-03 | Review | YELLOW | Honest about its own non-authority ("does not supersede DOC_AUTHORITY.md / TWO_SYSTEM_ARCHITECTURE_TRUTH.md") — the two docs above it feed are less careful |
| `config/validation.yaml` | current | config, not doc | RED | Still encodes the **old**, superseded (2026-07-01) Phase-3 gate: `minimum_trade_count: 50, minimum_profit_factor: 1.0, maximum_drawdown: 10.0`, no Sharpe field at all. Any tooling reading this file instead of CLAUDE.md §0.3/§0.6 will wrongly PASS strategies. |
| `docs/VERDICT_LOG.md` | last entry 2026-07-01 | append-only, no single status | GREEN (as record) | Ground truth for trial history; no new ST-A2 trial has been registered since the gate change despite live demo execution continuing |
| `docs/STRATEGY_PORTFOLIO_ROADMAP.md` | 2026-06-23 | none | RED (self-admitted) | Doc itself flags it predates the 5-strategy `strategy_portfolio.yaml` |
| `docs/PROJECT_OBJECTIVE.md` | undated | **no Status header** | RED | Per DOC_AUTHORITY.md's own rule, no header = Draft = do not act on it |
| `README.md` (root) | Status "Active (audit in-progress)", Owner/Last Reviewed: TODO | — | RED | Defines a **third, unauthorized lifecycle taxonomy** (EVF/RGM/SMO/ISOP, "Verification Ready," "Risk Approved") that matches neither CLAUDE.md's canonical enum nor the actual `svos/lifecycle/manager.py` enum. Unmaintained (TODO fields). Violates DOC_AUTHORITY.md's own "Must Never Do #9/#13." |
| `docs/audit/CURRENT_PROJECT_STATUS.md` | 2026-07-04 | "informational only — does not supersede DOC_AUTHORITY.md" | GREEN (as evidence) | Most candid single doc; documents the doc-sprawl and dual-orchestrator problems directly |
| `docs/audit/UPDATED_PROJECT_READINESS_SCORECARD.md` | 2026-07-02 | "DEMO INTEGRATION COMPLETE; MERGE POLICY PENDING" | YELLOW | Predates the 2026-07-04 crash-loop bug fix and the 2026-07-05 execution-layer/risk audits — superseded by more recent evidence, not itself wrong |
| `docs/audit/EXECUTION_LAYER_GAP_ANALYSIS.md`, `docs/audit/DEMO_TRADING_RISK_ASSESSMENT.md` | 2026-07-05 | — | GREEN (most current) | Most recent, code-verified accounts of the live execution path; treat as the current execution-readiness baseline |
| `docs/VANTAGE_DEMO_CONNECTION_CHECKLIST.md` | 2026-06-29 | — | GREEN | 0 FAIL items on connection/order/SL-TP checks; still consistent with later findings |
| Remaining ~23 files in `docs/audit/` + ~150 other files in `docs/` | mostly 2026-07-04 | mixed | not individually classified | See §3 — volume itself is the finding |

## 2. Direct contradictions found

1. **Freeze-lifting ambiguity (real, unresolved).** `docs/svos/architecture-review-2026-06-29/README.md` and `docs/svos/STABILIZATION_STATUS.md` (2026-06-30) both say NOT READY / feature freeze active, with the freeze lifting only when "the architecture review verdict is formally updated." No later `docs/svos/` document records that update. Meanwhile `SYSTEM2_MASTER_PLAN.md` and `ARCHITECTURE_STABILIZATION_ROADMAP.md` (2026-07-03/04) describe several days of subsequent System-2 engineering as if authorized, citing an owner directive ("System 2 controlled demo readiness is the immediate priority"). No document states outright that this directive was intended as an explicit exception to the architecture-review freeze — it is reconcilable, but currently only by inference, not by a written decision. **This needs a one-paragraph explicit resolution, not more analysis.**
2. **`config/validation.yaml` vs. CLAUDE.md §0.3/§0.6.** The config still encodes the pre-2026-07-01 gate. This is a live drift risk: any script or agent that reads the YAML gate instead of CLAUDE.md would pass strategies that shouldn't pass.
3. **`config/strategy_portfolio.yaml` risk field vs. `execution/demo_risk_manager.py`.** Portfolio config sets ST-A2 tier1 risk at `0.30%`; the actual deployed risk manager enforces `0.25%` per trade. Not verified which one actually governs live order sizing — flag for reconciliation, not yet confirmed as a live bug.
4. **README.md's lifecycle taxonomy** (EVF/RGM/SMO/ISOP) conflicts with CLAUDE.md §3/§9's canonical enum and with `svos/lifecycle/manager.py` itself. README.md is unmaintained (TODO owner/review) and should be treated as Draft per DOC_AUTHORITY.md's own rule — but nothing currently marks it that way visibly, so a reader could mistake it for current.

## 3. The meta-finding: documentation sprawl is itself a demo-readiness risk

`docs/` contains 180+ files; `docs/audit/` alone already has ~25 audit/scorecard/gap-analysis documents (some, e.g. `function_inventory.md`, are ~300KB); three more large "authoritative" planning docs live at repo root outside the DOC_AUTHORITY.md hierarchy. `docs/svos/CURRENT_STATE.md` (2026-06-28) already flagged this as structural debt, and `docs/audit/CURRENT_PROJECT_STATUS.md` (2026-07-04) flags it again. Adding further large audit documents without consolidating what exists compounds the exact problem CLAUDE.md §9 warns against ("known duplication debt... don't add a third").

**Recommendation:** do not read or reconcile the full `docs/audit/` backlog as part of getting to demo — it is not blocking (the demo runner doesn't consult these files). Treat it as a `LATER` cleanup item (see `FASTEST_PATH_TO_DEMO.md` §4). The two items that *are* blocking-adjacent and cheap to fix now: (a) register `SYSTEM2_MASTER_PLAN.md` and `ARCHITECTURE_STABILIZATION_ROADMAP.md` into `DOC_AUTHORITY.md`'s hierarchy explicitly (or demote their self-declared "Authoritative" status), and (b) mark `README.md` and `docs/PROJECT_OBJECTIVE.md` with correct Status headers (Draft/Deprecated) so agents don't act on them by accident.

## Facts vs. assumptions

Everything in §1-2 is cited to a specific file, date, or Status header found in the repo. The reconciliation in item 2.1 (that the owner directive was *intended* as a freeze exception) is explicitly flagged as inference, not a quoted fact — it is the one open question in this report that needs a human decision rather than more code-reading.
