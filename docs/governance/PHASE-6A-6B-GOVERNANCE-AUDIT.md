# Phase 6A/6B — Governance Audit, Task Registry Audit, CI Audit, PM Tooling Design

Date: 2026-07-07
Status: Governance work only — no execution/trading/broker code touched, per
this phase's own constraint. Verified: no files under `execution/`, `core/`,
`strategy/`, `bot.py` modified this pass.
Related: `docs/governance/GOVERNANCE-GAP-ANALYSIS.md`,
`docs/governance/PM-OPERATING-SYSTEM-PHASE6.md` (this document extends both
rather than re-deriving them), `docs/svos/PHASE-5B5-ARCHITECTURE-APPROVAL.md`
(pre-existing, committed `faed6d1` — discovered this pass, not authored by
this session)

## Note on a discovery this pass

Two files were found that this session did not author:
`docs/svos/PHASE-5B5-ARCHITECTURE-APPROVAL.md` (committed, `faed6d1`) and
`docs/audit/module_boundary_analysis.md` (committed, older, 2026-07-01).
Both are read and incorporated below rather than duplicated. The prompt's
"Current Project Status" claims (ExecutionService v1 approved, shim-first
approved, etc.) trace accurately to `PHASE-5B5-ARCHITECTURE-APPROVAL.md` —
**with one nuance**: that document's own language is "frozen... pending
owner sign-off" and "recommended... pending owner approval," not yet a
completed owner approval. Flagging this precisely rather than treating
"approved" as settled fact, per this phase's "never assume" rule.

---

## Task 1 — Governance Document Audit

| Finding | Evidence | Classification |
|---|---|---|
| `docs/SYSTEM_BOUNDARIES.md` has no `Status:` header | Full file read — starts directly with `# System Boundaries`, no frontmatter at all | Per `DOC_AUTHORITY.md`'s own rule ("a document with no Status header must be treated as Draft") — **not authoritative, "may not be acted upon"** |
| `docs/00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md` header | `Status: Authoritative`, `Authority: Level 1`, `Supersedes: Conflicting descriptions of SVOS and Production scope` | Explicitly authoritative, explicitly claims to supersede exactly this class of document |
| Two ADRs claim `docs/svos/` sequence continuity | `ADR-0001` through `ADR-0014`, all in one location, no gaps or duplicate numbers found | No conflict |
| `deploy-production.yml` | Manual `workflow_dispatch` only, hard-codes `LIVE_TRADING=false DEMO_ONLY=true` even in its remote command | Not "unused" — a deliberate, gated safety control, consistent with project posture. **Correcting a possible misreading**: this is not dead code to flag for removal |
| No broken cross-references found in the ADR chain (`ADR-0011`→`0012`→`0013`→`0014`, each correctly citing predecessors) | Read all four `Related:` headers | No broken references found in this chain |
| Outdated diagrams/architecture | Not exhaustively checked this pass (would require reading every `docs/` diagram — out of scope for the time available); no specific instance found in the files touched | Not confirmed either way — flagged as unverified, not claimed clean |

### Task 2 — `SYSTEM_BOUNDARIES.md` vs. `TWO_SYSTEM_ARCHITECTURE_TRUTH.md`

**Evidence (not a choice):**
1. `SYSTEM_BOUNDARIES.md`: 13 lines, no `Status:` header, no `Authority:` level, no `Date:`, no `Owner:` — fails every field `DOC_AUTHORITY.md` requires of an authoritative document.
2. `TWO_SYSTEM_ARCHITECTURE_TRUTH.md`: 137 lines, `Status: Authoritative`, `Authority: Level 1` (second-highest in the entire repo, per `DOC_AUTHORITY.md`'s own order table), and its header **explicitly states** `Supersedes: Conflicting descriptions of SVOS and Production scope`.
3. `DOC_AUTHORITY.md` rule #8 ("Must Never Do"): *"Act on documents with status Deprecated, Archived, or no header."* `SYSTEM_BOUNDARIES.md` has no header.
4. `DOC_AUTHORITY.md` rule #14 requires escalation only when **two Authoritative documents** conflict. `SYSTEM_BOUNDARIES.md` is not Authoritative by its own repo's rule — so this is not that case.

**This is not a genuine conflict between two authoritative sources** — it's an
orphaned, unheaded draft that predates (and is explicitly named as
superseded by) the current canonical document. High-confidence
**recommendation: Archive** `docs/SYSTEM_BOUNDARIES.md` (move under
`docs/Archive/`, per `DOC_AUTHORITY.md`'s own archive convention — do not
delete, per this repo's evidence-retention posture). **Not executed this
pass** — awaiting your confirmation, per this phase's explicit "do NOT
choose" instruction; the confidence is high, the action is not.

### Task 3 — Task Registry Audit

Already substantially audited in `docs/governance/PM-OPERATING-SYSTEM-PHASE6.md`
§2/§4 — not re-derived here. Summary: `schemas/task.schema.json` +
`tasks/*.yaml` (10 files, 7 `COMPLETE`/3 `PENDING`) is a real, valid,
schema-conformant registry tied to an older stabilization effort
(`feature_freeze_lift`). **No new evidence found this pass** that changes
that assessment. **Recommendation: Reuse (extend), do not retire** — the
schema is sound, just missing two fields (`assigned_agent`, `evidence`) and
unused for current-week work. Retiring it would mean re-inventing a data
model that already validates correctly.

### Task 4 — Additive Schema Changes (design only, per prior session's roadmap Step 1)

No change from `docs/governance/PM-OPERATING-SYSTEM-PHASE6.md` §5's design:
add optional `assigned_agent` (enum matching `docs/governance/AGENT_DIRECTORY.md`'s
6 agents) and optional `evidence` (array of paths) to
`schemas/task.schema.json`. Confirmed additive: neither field is in the
schema's `required` array, so all 10 existing `tasks/*.yaml` files remain
valid without modification. **Not implemented this pass**, per instruction.

### Task 5 — CI Audit

| Workflow | Jobs | Coverage | Gaps |
|---|---|---|---|
| `ci.yml` | `quality` (mypy + architecture tests + migration-SQL dry-run + whitespace check), `tests` (matrixed tiers), `security` (bandit), `docs-and-package`, `required` (gate on all 4) | Broad — architecture, types, tests, security, docs, package contracts | No dedicated job type-checks `execution/` specifically (only `svos/lifecycle`, `shared/models`, `shared/serialization` per the `mypy` command) — **a real, narrow gap**: the 3 files this session's audit identified as needing ExecutionService convergence (`order_manager.py`, `trade_manager.py`, `vantage_demo_executor.py`) are not in the `quality` job's mypy scope |
| `deploy-production.yml` | Manual dispatch, always deploys disabled | Not a gap — deliberate safety gate, see Task 1 |
| `strategy-release.yml` | Manual dispatch, requires approved strategy/version | Consistent with `CLAUDE.md`'s trial-registration governance |

**Recommendation**: consider adding `execution/` to the `quality` job's mypy
scope, given it's the module this session's audits identified as the
highest-risk area for a future migration — improves pre-migration safety
without replacing any existing pipeline. **Not implemented this pass.**

---

## Phase 6B — PM Tooling Design (prepared, not implemented)

No change from `docs/governance/PM-OPERATING-SYSTEM-PHASE6.md` §5-6's design
(PM Dashboard, Dependency Graph, Progress Generator) — all specified there
to consume `tasks/*.yaml` directly, explicitly ruled out creating a second
task database. Re-affirmed here as still the correct design; not re-authored.

**One addition this pass**: the Progress Generator's evidence sources list
should also include `docs/svos/PHASE-5B5-ARCHITECTURE-APPROVAL.md`-style
governance artifacts (status/decision fields already structured per-section)
as a source for "Architecture Health" dashboard metrics — these didn't exist
when the original design was specified last session.

---

## Immediate Next Actions

1. **Owner decision**: approve archiving `docs/SYSTEM_BOUNDARIES.md` (high-confidence recommendation, evidence above).
2. **Owner decision**: sign off on `PHASE-5B5-ARCHITECTURE-APPROVAL.md`'s ExecutionService v1 spec and shim-first migration recommendation — currently "frozen pending sign-off," not yet a completed approval.
3. Phase 5C's ExecutionRecord investigation is in progress (delegated to `execution-agent`, results to follow in a separate report — this document does not include those findings).
