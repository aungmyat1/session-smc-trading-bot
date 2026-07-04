# Production Infrastructure Stabilization — Phase 3 Report

Date: 2026-07-04T16:54Z
Scope: Operational baseline, crash-loop investigation, log/resource policy, safe cleanup, System 2
readiness check. No repository audit was re-performed — existing documentation (VPS cleanup Batch
A-D, `SYSTEM2_MASTER_PLAN.md`, dashboard docs) was used as the source of truth throughout.

---

## Completed actions

| Action | Result |
|---|---|
| Operational baseline captured | `docs/vps/OPERATIONS_BASELINE.md` |
| `smc-demo-runner.service` crash-loop root-caused | `docs/systemd/SMC_DEMO_RUNNER_ANALYSIS.md` — **Replace** recommended, not yet applied |
| Log retention policy drafted | `docs/vps/LOG_RETENTION_POLICY.md` — proposal only, not applied |
| Resource optimization recommendations drafted | `docs/vps/RESOURCE_OPTIMIZATION.md` — proposal only, not applied |
| Safe cleanup re-reviewed | `docs/vps/CLEANUP_REPORT.md` Batch E — only regenerated Python/test caches deleted (7.5 MB, unambiguously safe); npm cache and Codex logs re-confirmed still in active use, left untouched; two dangling systemd unit files identified but **not** removed (see Outstanding risks) |
| System 2 readiness assessed | `docs/systems/system2/INFRASTRUCTURE_READINESS.md`; stale `STATUS.md`/`ROADMAP.md` (predated this session's Sprint 2.1-2.3 work) synced in place |

## Infrastructure health summary

| Component | Status |
|---|---|
| Dashboard (`live-dashboard.service`) | Active, HTTP 307, 0 restarts |
| PostgreSQL (`postgresql@16-main.service`) | Active, `SELECT 1` passes |
| Docker/containerd | Inactive (by design — no project dependency on it) |
| Systemd (platform-wide) | 0 failed units |
| Disk | 81% used, 7.4 GiB free — unchanged net from before this phase (cache cleanup gain ≈ cache regeneration since) |
| Memory | 2.3 GiB used / 3.8 GiB total, 1.3 GiB free, load average 0.31/0.36/0.35 on 2 vCPUs — healthy headroom |
| `smc-demo-runner.service` | **Still crash-looping — 212 restarts and climbing.** Root cause fully documented; fix requires owner approval (strategy selection is a governance decision, not a sysadmin one) |

## Remaining operational risks

1. **`smc-demo-runner.service` crash-loop, unresolved.** Beyond the CPU/log churn, the more
   important risk this pass surfaced: **no strategy has ever actually traded in demo through this
   unit** — everything validated this session was validated by tests, not live execution. This is
   the single highest-priority open item.
2. **npm cache (241 MiB) and Codex `logs_2.sqlite` (367 MiB)** remain un-cleaned — both confirmed
   still in active use as of this pass. Revisit once those tool sessions end.
3. **Two dangling systemd unit files** (`benchmark-bot.service`, `smc-bot.service`) point at
   directories deleted in the prior cleanup batch. Low risk, but an attempt to remove them in this
   pass was blocked by the environment's own safety guardrail for lacking a fresh, explicit
   per-item approval — deliberately not retried without asking (see question below).
4. **Log retention policy is documented but not applied** — disk pressure will return without it,
   though current headroom (7.4 GiB) is not urgent.
5. **PostgreSQL `effective_cache_size=4GB`** exceeds total host RAM (3.8 GiB) — a real
   misconfiguration, not yet corrected (see `RESOURCE_OPTIMIZATION.md`).
6. **Durable *risk/portfolio* ledger** (as distinct from Sprint 2.3's order/event/recovery ledger)
   remains open, unchanged from `SYSTEM2_MASTER_PLAN.md`'s existing tracking.

## Production readiness estimate

**Not a Production Candidate.** Still demo-only; `LIVE_TRADING=false`/`DEMO_ONLY=true` unaffected by
anything in this phase. More specifically: this phase's most important discovery is that the
platform's own readiness self-assessment (`SYSTEM2_MASTER_PLAN.md`, this session's own Sprint 1-3
work) has been accurate about *code*, but the actually-deployed process has not been executing any
of it against a live demo account. Readiness for the *next* milestone (dashboard integration,
monitoring) is gated on fixing that first — not on more platform code.

## Recommended next milestone

**Resolve `smc-demo-runner.service` first** (owner decision required — see
`docs/systemd/SMC_DEMO_RUNNER_ANALYSIS.md`), then **wire a dashboard read-path to the new
`operations.*` Postgres tables** (Sprint 2.3's natural follow-on: small, additive, no new
infrastructure required, and directly answers this phase's "production monitoring" readiness gap).
Execution Pipeline Consolidation (`SYSTEM2_MASTER_PLAN.md` Phase 2's full port) remains valid but
larger; sequence it after the two items above so it's validated against a runner that's actually
trading, not just passing tests.

---

## Outstanding items — resolved 2026-07-04 (later same day)

Both items below were approved and completed in the follow-on "Phase 3 continuation" pass. Full
detail: `docs/systemd/SMC_DEMO_RUNNER_ANALYSIS.md`, `SYSTEM2_MASTER_PLAN.md` ("Deployment fix" entry).

1. **`smc-demo-runner.service`** — fixed (`--strategy ST-A2`), verified stable, 0 restarts.
2. **Dangling unit files** (`benchmark-bot.service`, `smc-bot.service`) — archived to
   `/home/aungp/archives/systemd-units/` then removed; 0 failed units after.
