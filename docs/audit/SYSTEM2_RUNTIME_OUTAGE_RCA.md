---
Date: 2026-07-12
Author: PM Agent (Claude) — System 2 Completion and Execution Platform Hardening, Phase S5
Authority: Level 8 — informational evidence. Does not supersede `docs/00_Project/DOC_AUTHORITY.md`.
Scope: Runtime forensics only. No code changes, no service state changes (`smc-demo-runner.service`
was not started, stopped, enabled, or disabled by this phase).
---

# System 2 — Runtime Outage Root Cause Analysis

## Filename note

The Phase S5 objective named `docs/audit/SYSTEM2_RUNTIME_VERIFICATION.md`. That path already exists
and covers an unrelated topic — a 2026-07-12 race-condition audit of `CanonicalExecutionPipeline`
(Phase 3 of the prior System2 Completion Mission), not this outage. Overwriting it would destroy
that evidence, which this repo's own append-only evidence convention (`ARCHITECTURE_STABILIZATION_ROADMAP.md`
§2.6, cited in the earlier folder-cleanup review this session) says not to do. This document is
filed under a distinct name instead; `SYSTEM2_GAP_CLOSURE_PLAN.md` (Phase S0) is updated to point
here for the S5 deliverable.

## 1. Executive Summary

`smc-demo-runner.service` is not crash-looping. **It is cleanly stopped and disabled** (confirmed:
`ActiveState=inactive`, `SubState=dead`, `UnitFileState=disabled`, `Result=success`, `NRestarts=0`
this boot). The crash-loop happened once, on **2026-07-11 between 15:24 and 15:39 UTC** (`logs/strategy_demo.log`,
last write 2026-07-11 15:39:39), and was manually resolved by disabling the unit — not by fixing
the underlying cause. Nobody has re-enabled it since. Root cause: an unmerged branch commit
(`cf92a9e`, `codex/demo-smoke-test`, 2026-07-11) added a hard startup governance gate to
`scripts/run_st_a2_demo.py` and simultaneously flipped `config/strategy_portfolio.yaml`'s ST-A2 to
`enabled: false` / `execution_mode: shadow` — while the live deployment's working directory
(`/home/aungp/session-smc-trading-bot`, the same checkout this session operates in) was on or had
merged that commit, the gate raised `PermissionError` on every start attempt (ST-A2 is not
catalog-approved — `DEFERRED_REVALIDATION`), and systemd's `Restart=always`/`RestartSec=15` cycled
it every ~20-25s until someone stopped and disabled it.

**This session's earlier action is directly relevant**: this conversation's "update the repo and
check out on main" step (checked out `main`, fast-forwarded to `206027c`) moved the working
directory off whatever commit/branch was checked out during the 07-11 crash loop and onto `main`,
which does **not** contain the hard startup gate and where `config/strategy_portfolio.yaml` has
ST-A2 back at `enabled: true` / `execution_mode: demo` (per PR #33, merged 2026-07-12, which
explicitly preserves ST-A2 while shadow-containing the other four strategies). **The condition that
caused the crash loop no longer exists in the currently-checked-out code.** The service remains
disabled only because nobody has re-enabled it since the 07-11 incident — this is now an
operational/administrative gap, not an active defect.

## 2. Service Inventory

| Field | `smc-demo-runner.service` | `vps-health-check.service` |
|---|---|---|
| LoadState | loaded | loaded |
| ActiveState | inactive | failed |
| SubState | dead | failed |
| UnitFileState | **disabled** | static (triggered by `vps-health-check.timer`) |
| Result | success | exit-code |
| NRestarts (this boot) | 0 | n/a (oneshot, re-triggered every 15 min) |
| Restart policy | `Restart=always`, `RestartSec=15` | n/a |
| Last known activity | app log stopped 2026-07-11 15:39:39 UTC | fails every run since at least 2026-07-12 11:18 UTC (health-check history retained) |
| Dependencies | `After=network-online.target`, `Wants=network-online.target` | — |

`vps-health-check.service`'s failure is **downstream** of the runner being down, not a separate
root cause: its own output shows `runner:tick FAIL (unparseable last_tick_at=starting)` and
`runner:broker FAIL (broker_status=ST-A2)` — both direct consequences of `smc-demo-runner.service`
never having ticked since 07-11. `disk:root WARN` (82% at session start, now **90%** — degraded
further during this session, see §3) and `dashboard:health_score=15` are separate, real findings,
not artifacts of the runner outage.

## 3. Dependency Inventory

| Dependency | Status | Note |
|---|---|---|
| PostgreSQL | active | `systemctl is-active postgresql` → `active`; confirmed reachable in Phase 0 audit too |
| Disk (`/`) | **90% used, 5.1G free** | Up from 82% at this session's start (~2 hours earlier) — worsening, not static. No single cause identified in this phase; flagged as a precondition risk for Phase S4 |
| Memory | 953Mi free / 3.8Gi, swap 447Mi/4.0Gi in use | Improved vs. this session's earlier reading (110Mi free then) — likely reflects a different point-in-time load, not a fix |
| `.env` | present, `/home/aungp/session-smc-trading-bot/.env`, last modified 2026-07-11 09:28 | exists and is current; the `PHASE4_COST_MODEL_BLOCKER.md` finding of "no `.env` file" was scoped to a different, credential-less sandboxed session, not this live host |
| `EnvironmentFile` (`/etc/session-smc-trading-bot/live-dashboard.env`) | present | referenced by the systemd unit directly |
| Python syntax | `py_compile` clean on `scripts/run_st_a2_demo.py`, `execution/governance_guard.py`, `core/strategy_registry.py` | no import/syntax defect on current `main` |
| Redis | not applicable | grep of this repo's stack shows no Redis dependency for the execution runner; the prompt's investigation plan listed it generically, not confirmed as an actual System2 dependency here |
| MetaAPI/broker | account `DEPLOYED`, `connectionStatus: DISCONNECTED` at last check (this session, Phase covering "check MetaAPI connection") | most likely explained by it being Sunday (market closed) at the time of that check; not re-tested in this phase since it requires actually starting a connection, out of scope for a forensics-only phase |

## 4. Journal Findings

Current boot's journal (`journalctl -u smc-demo-runner.service`, boot started 2026-07-12 08:09:04 UTC)
contains **zero entries** for the service — it was never started this boot (consistent with
`disabled` + no manual `systemctl start`). The crash loop itself predates this boot and is not in
the systemd journal (single-boot retention, ~34M journal size); it is preserved instead in the
application's own log file, `logs/strategy_demo.log` (10.3MB, last write 2026-07-11 15:39:39 UTC).

Representative excerpt (repeats identically, one cycle per ~20-25s, from 15:24:04 to at least
15:39:11 UTC on 2026-07-11):

```
2026-07-11 15:24:04,655 INFO strategy_demo.runner — Vantage runner starting. strategy=ST-A2 mode=DEMO interval=60s once=False
2026-07-11 15:24:04,896 ERROR strategy_demo.runner — Startup governance check failed for ST-A2/demo — DEPLOYMENT_NOT_APPROVED: {'catalog_status': 'DEFERRED_REVALIDATION', 'catalog_approved': False, 'deployment_target': 'None', 'evidence_count': 0, 'decision_count': 0, 'approval_count': 0, 'latest_approval': {}}
```

Traced via `git log --all -S"Startup governance check failed"`: this exact log string was added by
commit `cf92a9e` ("feat(governance): implement strategy governance checks and disable unapproved
strategies", authored 2026-07-11 10:18:26 UTC, present on `codex/demo-smoke-test` and
`ST-A2_v2_candidate`, **confirmed NOT an ancestor of `main`** via `git merge-base --is-ancestor`).
The commit added, in `scripts/run_st_a2_demo.py::run()`:

```python
startup_guard = StrategyExecutionGuard(root=_ROOT, shadow_mode="block")
startup_result = startup_guard.evaluate(strategy_name, environment=startup_environment)
if not startup_result.allowed:
    ...
    raise PermissionError(f"strategy {strategy_name} is not approved for {startup_environment}: {reason}")
```

This is a **fail-closed, process-exiting** gate — distinct from the existing, softer, per-signal
`governance_guard.evaluate()` call already on `main` (line 583 of the current file) which only
blocks individual trade signals via `TradingPermissionService`, never exits the process. The same
commit also flipped `config/strategy_portfolio.yaml`'s ST-A2 to `enabled: false` /
`execution_mode: shadow`, `catalog_approved: false` being the correct, unchanged state of
`config/strategy_catalog.yaml` (ST-A2 remains `DEFERRED_REVALIDATION` there today too).

**No OOM kill, no disk-write failure, no Redis/Postgres failure, no missing-`.env`, no
`ModuleNotFoundError`/`ImportError` appears anywhere in the captured log window.** This rules out
failure Categories A, B, C, and D from the investigation plan. This is squarely **Category E**
(unhandled runtime exception) in the sense that `PermissionError` is unhandled by the outer loop —
but more precisely, the guard behaved exactly as its own code specifies; it is not a bug in the
gate, it's a **deployment/branch-management incident**: unmerged, stricter governance code reached
the live host's checkout before being reconciled with `main`'s deliberate policy (CLAUDE.md §1)
of keeping ST-A2 running in demo as a tracked, documented exception.

## 5. Root Cause

**A commit implementing stricter strategy-governance enforcement (`cf92a9e`, branch
`codex/demo-smoke-test`) reached the live deployment's working directory on 2026-07-11 without
being reconciled against `main`'s existing, documented policy of keeping ST-A2 running in demo
despite its `DEFERRED_REVALIDATION` status.** The new gate is not wrong in isolation — it correctly
enforces catalog approval — but it directly contradicts CLAUDE.md's explicit, standing instruction
(§1, §6): *"config/strategy_portfolio.yaml currently runs FIVE strategies... this is a tracked
governance gap, not evidence of approval"* and *"ST-A2 itself remains demo — do not disable it
here."* The crash loop is the mechanical symptom of two irreconcilable governance decisions
colliding in the same working directory. It was stopped by disabling the unit, not by resolving
which governance stance should win — that reconciliation still hasn't happened (see §7, "open
governance question").

**Why it self-resolved before this phase started acting**: this session's earlier, unrelated "update
the repo and check out on main" action (requested by the operator for a different reason — general
repo sync) happened to check out `main`, which lacks the hard gate and has ST-A2 re-enabled via PR
#33. The crash-causing condition is gone from the current checkout as a side effect, not because
anyone diagnosed or fixed it.

## 6. Is it reproducible?

**Not on current `main`** — verified: `grep` for `startup_guard`/`raise PermissionError` in
`scripts/run_st_a2_demo.py` on `main` returns nothing; `config/strategy_portfolio.yaml` on `main`
has ST-A2 `enabled: true`/`execution_mode: demo`. Starting the service today, from this checkout,
would not hit the same `PermissionError`.

**It would reproduce again if**: (a) `codex/demo-smoke-test` or `cf92a9e` specifically is ever
merged to `main` without also revisiting `config/strategy_portfolio.yaml`'s ST-A2 entry, or (b) the
live deployment's working directory is ever repointed at that branch directly (as it apparently was
on 07-11) instead of `main`.

## 7. Corrective Actions

1. **Immediate, low-risk**: re-enable and start `smc-demo-runner.service` from the current `main`
   checkout. Given `main` has neither the hard gate nor a portfolio-config block, this is expected
   to succeed and resume normal ticking — but this is a state-changing action on a live host and is
   **not executed by this phase** (explicitly scoped to forensics/evidence-gathering only, per this
   phase's own instructions). Recommend as the next explicit, approved step.
2. **Before S4 (24h qualification run)**: resolve disk usage — 90% and rising during this session
   alone; identify what's consuming space (not investigated in this phase, out of scope) before
   adding any S1-driven monitoring/logging volume on top of it.
3. **Open governance question, not resolved by this phase**: `cf92a9e`'s branch represents a
   real, considered position (no strategy should run without catalog approval) that conflicts with
   `main`'s current, documented policy. This is a decision for the owner, not something this
   phase should resolve by picking a side — flagging it for Phase S6 (Governance Alignment) to
   document explicitly, and for the owner to decide whether `codex/demo-smoke-test`'s stricter
   posture should eventually supersede the current carve-out, or be abandoned.
4. **Process gap**: whatever mechanism put commit `cf92a9e` (or its branch) into the live
   deployment's working directory on 07-11 without a corresponding `main` merge should be
   identified — this phase found the symptom, not how the branch got there (no deploy/CI logs
   were available to trace this; VPS shell history was not reviewed in this pass).

## 8. Verification Checklist (for whoever executes the corrective action)

- [ ] Confirm `git -C /home/aungp/session-smc-trading-bot branch --show-current` reads `main`
      immediately before starting the service (guards against a repeat of this exact incident).
- [ ] `sudo systemctl enable smc-demo-runner.service`
- [ ] `sudo systemctl start smc-demo-runner.service`
- [ ] `journalctl -u smc-demo-runner.service -f` — confirm no `PermissionError`/`governance check
      failed` line appears; confirm `MetaAPI connected` and a clean first tick.
- [ ] `systemctl status smc-demo-runner.service` shows `active (running)`, `NRestarts=0` after a
      few minutes (not climbing).
- [ ] Re-run `vps_health_check.sh` manually or wait for the next `vps-health-check.timer` cycle
      (every 15 min) — confirm `runner:tick`/`runner:broker` flip to PASS.
- [ ] Check disk headroom before and after — if `df -h /` approaches 95%+, halt and address disk
      before proceeding to S4.

## 8.5. Addendum — controlled restart executed, new blocker found (2026-07-12, ~19:01-19:04 UTC)

Per operator instruction, the corrective action in §7.1 was executed as a controlled recovery
(S5.5): `config/strategy_portfolio.yaml` backed up to `config/strategy_portfolio.yaml.pre-restart.backup`,
`systemctl enable` + `systemctl start smc-demo-runner.service` from the confirmed `main` checkout
(`206027c`).

**Result: the original root cause (§5's governance gate) is confirmed fixed** — no
`PermissionError`/`governance check failed` line appeared across 3 start attempts. **But a second,
different, genuine crash loop appeared immediately**, at the broker-connection step:

```
ERROR strategy_demo.runner — Connection failed: We were not able to connect to your broker using
credentials provided. Please check that server.dat file you uploaded to your provisioning profile
is correct, your trading account login, password and server name. (...), check error.details for
more information. Request URL: https://mt-provisioning-api-v1.agiliumtrade.agiliumtrade.ai/users/
current/accounts/d6f6eec3-96d5-4001-a802-62b3f4b49817/deploy
```

Restart counter climbed 0→1→2 in under 90 seconds (systemd `Restart=always`/`RestartSec=15`,
matching the exact ~15-20s cadence of the original 07-11 incident, just from a different cause).
Per the operator's own stated exit criteria ("do not proceed if startup fails"), the service was
**stopped and disabled again** (`systemctl stop` + `systemctl disable`) after ~2 minutes rather than
completing the planned 30-minute observation window, to avoid hammering MetaAPI's provisioning API
and growing logs pointlessly on an already 90%-full disk.

**Read-only follow-up check** (`MetaApi.metatrader_account_api.get_account()`, same account ID):
the account exists, `state=UNDEPLOYED`, `connectionStatus=DISCONNECTED`, `type=cloud-g2`,
`login=25657968`, `server=VantageMarkets-Demo`. MetaAPI itself is reachable and the account record
is intact — this is not a MetaAPI outage. The rejection is coming from the **broker's own
provisioning step** (Vantage's MT5 demo server refusing the login/password MetaAPI is presenting on
this account's behalf). This is consistent with a demo account that has expired, been reset, or had
its password changed on Vantage's side since it last successfully connected — demo MT5 accounts
commonly have finite validity windows. This cannot be diagnosed or fixed further from this
environment: no credential-testing tool short of the broker's own MT5 terminal/webtrader (or a
Vantage support channel) can confirm or reset a broker-side demo login.

**This finding revises §5-§9 below**: the governance-gate root cause was real and is now fixed, but
it was masking this second, independent, currently-blocking issue the entire time — the runner
could not have connected successfully even if the governance gate had never been added. Whether
this broker-credential rejection is new (started sometime between 07-04's last confirmed successful
connection and now) or has been present since is not established by this pass; no earlier journal
evidence survives to check (single-boot journal retention, `strategy_demo.log` before 07-11 was not
reviewed for a prior connection-failure signature in this pass).

## 9. Recommendation on whether S4 can begin

**No — updated after §8.5's controlled restart.** The original blocker (governance gate) is fixed
and confirmed. A second, independent blocker — Vantage broker rejecting the demo account's
login/provisioning — is now the active cause, confirmed by a real (brief, deliberately curtailed)
crash loop, not a hypothesis. This is **owner-actionable, not engineering-actionable**: someone with
access to the Vantage demo account (`login=25657968`, `server=VantageMarkets-Demo`) needs to verify
the account is still valid/active on Vantage's side (log in via MT5 terminal/webtrader directly, or
via Vantage support) and, if it has expired or the password has changed, update the credentials
MetaAPI holds for account `d6f6eec3-96d5-4001-a802-62b3f4b49817` (MetaAPI's account-update API, not
this repo's `.env` — MetaAPI stores broker credentials server-side per account, not locally).

Service left **stopped and disabled** at the end of this phase — matching the pre-phase state,
deliberately, so it does not sit crash-looping unattended against a broker that is actively
rejecting it. Do not re-enable until the broker-side credential issue is confirmed resolved.
Disk headroom (§3, §7.2 — now 90%, `docker system df` shows ~14GB in images/build-cache/volumes as
the largest reclaimable-ish surface, not investigated further as a fix in this pass) remains a
separate, still-open precondition for S4 regardless of the broker issue.

## Answers to the Phase S5 success criteria

1. **Why is `smc-demo-runner.service` inactive?** It crash-looped on 2026-07-11 due to an unmerged,
   stricter governance gate (`cf92a9e`) conflicting with `main`'s documented ST-A2 policy, and was
   manually disabled to stop the loop. It has not been re-enabled since.
2. **Is the issue reproducible?** Not on the current `main` checkout. Reproducible only if the
   unmerged branch/commit is reintroduced without reconciling the portfolio config.
3. **What dependencies are affected?** None of PostgreSQL, `.env`, Python imports, or disk/memory
   were the cause. `vps-health-check.service`'s failure is a downstream consequence, not a separate
   root cause. Disk headroom (90%, worsening) is a real, separate, live risk worth addressing before
   S4, not the cause of this outage.
4. **What corrective action is required?** Re-enable and start the service from the current `main`
   checkout (§7.1) — a distinct, approvable action, not performed by this forensics-only phase.
5. **Can a stable 24-hour run begin?** Not yet — only after the service is restarted and §8's
   checklist confirms clean startup, and disk headroom is checked.
