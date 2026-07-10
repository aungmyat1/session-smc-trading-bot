# PM Command Reference

Status: New — this is a genuine gap (no existing doc lists what each PM
"command" actually does). Maps the conversational commands an owner might
give to what the PM agent actually checks, per the existing governance
system in `.claude/agents/pm.md` / `pm-governance-cowork.md`.

| Command | What the PM agent actually does |
|---|---|
| "Review current project status" | Reads `docs/systems/system2/STATUS.md`, `docs/systems/system2/ROADMAP.md`, and the current System 1 lifecycle stage from `svos/lifecycle/manager.py`'s state — reports both, does not infer |
| "Generate implementation plan" | Scopes the request against `CLAUDE.md` §9's checklist (which system, which stage/phase, duplication check, production-boundary check) before proposing steps — per `pm.md`'s "Before assigning any task" |
| "Analyze repository health" | `git status`, recent commits, open ADRs, test suite status, known duplication debt (`docs/AUDIT_IMPLEMENTATION_PLAN_2026-07-01.md`) |
| "Review infrastructure" | Disk/memory/CPU/service health via the existing `scripts/disk_report.py` / `scripts/health_check.py`, cross-referenced against `docs/operations/production-readiness-infrastructure.md` |
| "Review architecture" | Checks the request against `docs/00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md` and existing ADRs (`docs/svos/ADR-*.md`) — flags any proposal that would introduce a competing structure |
| "Review SYS1" | System 1 (SVOS/research) — lifecycle stage from the canonical enum, `docs/VERDICT_LOG.md` for trial history, never trades |
| "Review SYS2" | System 2 (production execution) — `docs/systems/system2/ROADMAP.md`/`STATUS.md`, service health, current broker-connectivity ADR (`ADR-0014` as of 2026-07-07) |
| "Review testing" | Test suite pass/fail state, coverage gate status — reports facts, does not assume "tests pass" without running them |
| "Review documentation" | Checks for drift against `docs/00_Project/DOC_AUTHORITY.md`'s authority order; flags competing/duplicate docs (the exact check that produced `docs/governance/GOVERNANCE-GAP-ANALYSIS.md`) |
| "Prepare next sprint" | Backlog prioritized Critical/High/Medium/Low/Future per `pm-governance-cowork.md`'s startup behavior, scoped to the current canonical phase only |
| "Generate ADR" | New ADR at `docs/svos/ADR-NNNN-*.md`, continuing the existing sequence (currently through `ADR-0014`) — never a second ADR location |
| "Assign tasks" | Delegates to one of the specialist agents in `docs/governance/AGENT_DIRECTORY.md`, matched by scope; PM never implements directly except when explicitly required |
| "Approve implementation" | Requires: evidence provided, tests executed (or explicitly stated as unverified with why), no unresolved risk register item blocking it, matches an approved ADR/plan |
| "Reject implementation" | Requires a stated reason tied to one of: evidence gap, architecture conflict, duplication, safety/governance violation |
| "Generate final project report" | Structured per `pm-governance-cowork.md`'s REPORT FORMAT — no narrative-only reports |

## Not a new automation layer

These are conversational patterns for how the PM agent already behaves
(per `pm.md`/`pm-governance-cowork.md`), documented here for discoverability
— not new slash commands, scripts, or automation. No code was added by
this document.
