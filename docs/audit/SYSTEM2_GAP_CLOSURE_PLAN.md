---
Date: 2026-07-12
Author: PM Agent (Claude) — System 2 Completion and Execution Platform Hardening, Phase S0
Authority: Level 8 — informational evidence. Does not supersede `docs/00_Project/DOC_AUTHORITY.md`.
Scope: Audit only. No code changes. Source of truth for readiness: `docs/audit/SYSTEM2_READINESS_FINAL.md` (2026-07-12),
corrected below where its "pending merge" caveats are now stale.
---

# System 2 — Gap Closure Plan

## 0. Correction to the source-of-truth snapshot

`SYSTEM2_READINESS_FINAL.md` scored Execution/Risk/Governance PASS/PASS/PARTIAL with caveats
that PR #37 (duplicate-order prevention), PR #25 (Emergency-Stop RiskFirewall), and PR #33
(shadow containment) were "pending merge." Verified via `gh pr view` at the time of this audit:
all three are **MERGED to `main`** (`#33` 17:15 UTC, `#37` 15:04 UTC, `#25` 17:11 UTC, all
2026-07-12). This does not change any PASS/PARTIAL/FAIL verdict — the readiness doc already
scored them as if merged, pending confirmation — but it removes the "pending" qualifier: those
three items are now unconditionally verified-on-`main`, not merely test-verified-on-branch.

Separately confirmed this session (2026-07-12, live `auto-trade-vps` check): `smc-demo-runner.service`
is currently **inactive/dead**, and `vps-health-check.service` reports **UNHEALTHY**
(`runner:tick` FAIL, `runner:broker` FAIL, `dashboard:health_score=15`, `disk:root` 90% WARN).
This is directly relevant to Phase S4/S5 below — the runtime this mission needs to observe for
sustained-operation evidence is not currently running.

## 1. Inventory

### PASS (do not redesign — preserve per mission rules)

| Item | Evidence | Note |
|---|---|---|
| Execution | Duplicate-order gap closed, 21 new tests incl. 100-requests→1-order (`SYSTEM2_DUPLICATE_ORDER_REPORT.md`) | PR #37 now on `main` |
| Risk | Circuit breakers on real P&L; dual emergency-stop (per-tick + pipeline `EmergencyStopRiskGate`), 157/157 tests | PR #25 now on `main` |
| Recovery | `reconcile_pending_executions()` startup + periodic (SYS2-T014/PR #27, already on `main`) | unchanged |
| Broker | MetaAPI/Vantage demo integration stable, out of scope for changes | Live connectivity check this session: account `DEPLOYED`, `connectionStatus: DISCONNECTED` at check time (2026-07-12, Sunday/market-closed, not confirmed as a fault) |
| Testing | 256/256 in mission scope | preserve — no breaking changes permitted |

### PARTIAL (close, do not redesign)

| Item | Current state | Closure requires |
|---|---|---|
| Monitoring | Backend real, load-tested once; no sustained 24h accuracy proof; `/api/v1/production/health` heartbeat gap open | Phase S1 (design), Phase S4 (evidence) |
| Dashboard | Backend solid (RBAC, real endpoints); frontend incomplete, no `/ws` subscriber | Phase S2 |
| Database | Postgres `operations.*` audit trail wired; `risk_state`/`portfolio_state` remain JSON-file, not transactional | Phase S3 (design only, no migration) |
| Operations | `operations_recorder.py` real and wired; no sustained gap-free-recording evidence over 24h | Phase S4, S5 |
| Governance | LondonBreakout/NYMomentum now confirmed shadow-contained (PR #33 merged); ST-A2 running despite `DEFERRED_REVALIDATION` — tracked gap, not hidden | Phase S6 (document, do not resolve) |
| Documentation | Prior-sprint doc-authority gaps unchanged; this mission's own 9 docs internally consistent | ongoing, no dedicated phase — folded into each phase's own deliverable |

### FAIL (track, do not bypass)

| Item | Current state | Blocker |
|---|---|---|
| Validation (ST-A2) | n=169, PF_2x=1.025, no Sharpe — fails current gate (`n>200, PF>1.25, Sharpe>1.2, MaxDD<15%` per repo `CLAUDE.md` §0.6/§7) | Owner-only live spread capture (`PHASE4_COST_MODEL_BLOCKER.md`) — no credentials in this environment, and the capture tool itself requires hours-to-days of live wall-clock operation even with credentials |

## 2. Dependency graph

```
S0 (this doc)
 ├─→ S1 Monitoring design ─────────────┐
 ├─→ S2 Dashboard design ──────────────┤
 ├─→ S3 Database/state persistence design ┤
 │                                      ├─→ S4 Sustained Ops Qualification (24h+ live run)
 ├─→ S5 Operations Recorder Verification ┘   [BLOCKED: requires smc-demo-runner.service ACTIVE —
 │        (root-cause current inactive        currently inactive/dead per this session's live check;
 │         runner state first)                S4 cannot start until S5's root-cause step restores it
 │                                             or documents why it can't]
 ├─→ S6 Governance Alignment doc (independent — can run parallel to S1-S3)
 └─→ S7 ST-A2 Blocker Tracking doc (independent — no code dependency, already substantially
          covered by PHASE4_COST_MODEL_BLOCKER.md + STA2_REVALIDATION_READY.md; S7 formalizes/
          re-confirms rather than starting fresh)

S8 Future Strategy Integration design — independent of S1-S7, can run any time after S0.
   No dependency on the 24h evidence (S4) or the ST-A2 blocker (S7); it defines a contract
   (Signal in / execution out) that doesn't require either to be resolved.
```

**Critical path:** S5 (root-cause why the runner is down right now) gates S4 (cannot produce
24h live evidence from a dead process). S1/S2/S3 are design-only deliverables and do not block
S4/S5, but their design decisions (e.g. what monitoring/dashboard data S4 should capture) are
more useful if sequenced before S4 so the qualification run captures the right signals the first
time. Recommended order: **S0 → S5 (root cause first) → S1 → S2 → S3 → S4 → S6 → S7 → S8**,
deviating from the prompt's literal S1→S8 order only on S5, because S4 is meaningless while the
runner is down and S5 is what diagnoses that. S6/S7/S8 have no hard dependency and could run in
parallel with S1-S3 if parallel PRs are acceptable; the prompt's "one phase per PR, stop after
each phase" rule makes this a proposal for the *next* phase, not something this doc executes.

## 3. Implementation sequence (proposed, pending owner approval per "stop after each phase")

1. **S5 first** (reordered from prompt's S1→S8): root-cause `smc-demo-runner.service` inactive
   state before designing monitoring/dashboard work that assumes a running process to observe.
   Read-only — `journalctl`, `systemctl status`, check for a governance-driven intentional stop
   (e.g. was it manually stopped, or did it crash) before treating it as a defect.
2. **S1 Monitoring Completion** — design doc only, per prompt.
3. **S2 Dashboard Completion** — design doc only, per prompt; depends conceptually on S1's metrics
   taxonomy for what the health/metrics views should show, but no file dependency.
4. **S3 Database Hardening** — design doc only, explicitly not a migration.
5. **S4 Sustained Operations Qualification** — cannot start until S5 confirms the runner is
   active again (or documents why a 24h run isn't currently possible). This phase is owner
   wall-clock time, not engineering time, regardless of sequencing.
6. **S6 Governance Alignment** — no code dependency, safe any time after S0.
7. **S7 ST-A2 Blocker Tracking** — no code dependency; largely re-confirms `PHASE4_COST_MODEL_BLOCKER.md`
   and `STA2_REVALIDATION_READY.md` already produced this same day.
8. **S8 Future Strategy Integration** — no dependency on S1-S7's outcomes; the Signal-contract
   design can be written against the *already-PASS* execution/risk/recovery core.

## 4. Risk matrix

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| S4 (24h evidence) attempted before S5 root-causes the dead runner | High if sequence not followed | Produces no evidence at all — wasted phase | Sequence S5 before S4 (this doc's recommendation) |
| S3's "design only, no migration" boundary is not respected in a future phase | Medium (JSON→Postgres migrations are a common place for scope creep) | Could destabilize the PASS-rated Risk/Recovery dimensions the mission explicitly says not to touch | Enforce via PR review: S3's PR must contain zero changes under `execution/demo_risk_manager.py`, `core/portfolio_manager.py` runtime write paths |
| S7 duplicates work already done today in `PHASE4_COST_MODEL_BLOCKER.md`/`STA2_REVALIDATION_READY.md` | Medium | Wasted effort, doc sprawl | S7's deliverable should explicitly cite and consolidate those two docs rather than re-deriving the blocker analysis |
| Governance gap (ST-A2 running despite `DEFERRED_REVALIDATION`) is misread by a future agent as authorization to expand scope | Low but high-severity if it happens | Could lead to enabling more strategies without SVOS approval | S6 must explicitly restate the CLAUDE.md §1/§6 framing: this is a tracked gap, not a precedent |
| Disk at 90% (flagged by `vps-health-check.service` this session) fills further during a 24h qualification run (S4) with added logging/monitoring instrumentation from S1 | Medium | Could crash the VPS mid-qualification-run, invalidating the evidence | Flag disk headroom as an explicit precondition check before starting S4, not an afterthought |

## 5. Evidence requirements per phase

- **S1**: metrics-endpoint verification (does the endpoint exist and return real data — same
  standard the readiness doc already applied to `/api/operations/*`), no fabricated sample
  dashboards.
- **S2**: integration design + sequence diagrams are sufficient per the prompt; no live frontend
  build required for this phase's deliverable (that's explicitly deferred, matches
  `docs/dashboard/DASHBOARD_IMPLEMENTATION_PLAN.md`'s existing unbuilt-frontend status).
- **S3**: design doc + rollback plan; explicitly no state migrated. Verification = read-review
  only, not runtime evidence.
- **S4**: the only phase requiring genuine, non-simulated, non-placeholder runtime evidence
  (`reports/system2/*.md`) — per the prompt's own "No gaps. No simulated evidence. No
  placeholders" rule and this repo's CLAUDE.md §0.6/§0.7 evidence discipline.
- **S5**: `journalctl`/`systemctl` output, not narrative — root cause must be quoted from actual
  log lines, matching this mission's existing standard (`SMC_DEMO_RUNNER_ANALYSIS.md` precedent).
- **S6**: inventory table cross-checked against the live `config/strategy_portfolio.yaml` and
  `config/strategy_catalog.yaml`, not memory or the stale `STRATEGY_PORTFOLIO_ROADMAP.md`.
- **S7**: must not execute any backtest or revalidation step — documentation of the existing
  blocker only, consistent with `PHASE4_COST_MODEL_BLOCKER.md`'s own explicit non-completion.
- **S8**: a Signal dataclass/contract proposal is a design artifact; no strategy code should be
  touched to produce it (existing strategies are out of scope per the mission's hard rules).

## 6. Acceptance criteria for this phase (S0)

- [x] PASS/PARTIAL/FAIL inventory produced, cross-checked against `SYSTEM2_READINESS_FINAL.md`
      and corrected where stale (PR merge status)
- [x] Dependency graph produced
- [x] Implementation sequence proposed, with a documented deviation (S5 before S1-S4) and rationale
- [x] Risk matrix produced
- [x] Evidence requirements stated per phase
- [x] No code changes made
- [x] Live verification performed where cheap and read-only (PR merge status, current runner
      state) rather than trusting the source doc's snapshot uncritically

## Recommendation for next phase

Proceed to **Phase S5** (reordered ahead of S1 per §3 above) to root-cause why
`smc-demo-runner.service` is currently inactive, before investing in S1-S3 design work that
presumes a running process. Awaiting approval to proceed.

**Update, post-S5**: root cause found and documented in `docs/audit/SYSTEM2_RUNTIME_OUTAGE_RCA.md`
(not `SYSTEM2_RUNTIME_VERIFICATION.md` — that path already holds an unrelated 2026-07-12
race-condition audit; overwriting it would destroy that evidence). Summary: an unmerged branch
commit (`cf92a9e`, `codex/demo-smoke-test`) reached the live deployment's working directory on
2026-07-11, adding a fail-closed startup governance gate that crash-looped the service until it was
manually disabled. The condition is absent from current `main`. Corrective action (re-enable +
start) is scoped as a distinct next step, not performed by the forensics-only S5 phase — awaiting
approval before S4 can begin.
