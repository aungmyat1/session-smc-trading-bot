---
Date: 2026-07-12
Author: PM Agent (Claude) — System 2 Completion and Execution Platform Hardening, Phase S5.6
Authority: Level 8 — informational evidence. Does not supersede `docs/00_Project/DOC_AUTHORITY.md`.
Scope: Broker connectivity recovery. No code changed. No trading logic touched. No credentials
fabricated or guessed. Owner-only verification steps (Vantage portal/MT5 terminal/support) were
NOT performed by this agent — no access to those systems exists in this environment. This report
documents what could be verified from this environment and hands off the remainder explicitly.
---

# System 2 — Broker Connectivity Recovery Report

## Status: BLOCKED — awaiting owner action. S4 cannot start.

## 1. Original Failure

`smc-demo-runner.service` was disabled and stopped since 2026-07-11 (see
`docs/audit/SYSTEM2_RUNTIME_OUTAGE_RCA.md` for the full timeline). A controlled restart was
performed this session (Phase S5.5) after confirming its original crash cause — an unmerged,
stricter startup governance gate (`cf92a9e`, branch `codex/demo-smoke-test`) — was absent from the
current `main` checkout (`206027c`).

## 2. Root Cause (this incident)

The governance gate is confirmed fixed: across 3 start attempts during the S5.5 restart, no
`PermissionError`/governance-block log line appeared. **A second, independent failure surfaced
immediately after**, at the broker-connection step, before any strategy/execution code runs:

```
ERROR strategy_demo.runner — Connection failed: We were not able to connect to your broker using
credentials provided. Please check that server.dat file you uploaded to your provisioning profile
is correct, your trading account login, password and server name. (...), check error.details for
more information. Request URL: https://mt-provisioning-api-v1.agiliumtrade.agiliumtrade.ai/users/
current/accounts/d6f6eec3-96d5-4001-a802-62b3f4b49817/deploy
```

Restart counter climbed 0→1→2 in under 90 seconds (systemd `Restart=always`, `RestartSec=15`) — a
real, reproducing loop, not a one-off. The service was deliberately stopped and disabled again
after ~2 minutes (not the full planned 30-minute window) to avoid repeatedly hitting MetaAPI's
provisioning endpoint and growing logs on an already 90%-full disk, per the operator's own stated
exit criterion ("do not proceed if startup fails").

**This is a broker-side rejection, not a code or MetaAPI-platform defect**: MetaAPI's own account
record is intact and reachable (see §3). The rejection is coming from Vantage's MT5 demo server
refusing the login/password MetaAPI is presenting on this account's behalf.

## 3. MetaAPI Status (verified this session, read-only)

| Field | Value |
|---|---|
| Account ID | `d6f6eec3-96d5-4001-a802-62b3f4b49817` |
| MetaAPI account state | `UNDEPLOYED` |
| Connection status | `DISCONNECTED` |
| Login | `25657968` |
| Server | `VantageMarkets-Demo` |
| Account name (MetaAPI label) | `aung.pro1@gmail.com` |
| Created at | `2026-06-23 06:00:00 UTC` (~19 days old at time of this report) |

Re-verified immediately before writing this report — no change from the state observed during the
S5.5 restart attempt. `state=UNDEPLOYED` reflects that MetaAPI's own deploy attempt failed and it
gave up, not that deploy was never tried — 3 deploy attempts were made and rejected during S5.5.

## 4. Corrective Action

**Not performed by this agent.** The five-step owner checklist below requires access this
environment does not have: no Vantage client-portal session, no MT5 desktop terminal, no ability to
open a Vantage support channel, and — correctly, per this repo's CLAUDE.md §0.4 rule that
`pionex_python`/broker SDKs are the only sanctioned auth path and per the standing instruction not
to fabricate or guess credentials — no willingness to guess at login/password combinations against
a live broker endpoint.

| Step | Description | Status |
|---|---|---|
| 1. Verify Vantage demo account | MT5 login works, password valid, server name correct, not expired/deleted, trading permission enabled | **Owner action required** — needs MT5 terminal, Vantage client portal, or Vantage support |
| 2. Confirm MT5 credentials | Login/password/server match what MetaAPI has on file | **Owner action required** — this repo's `.env` does not store the MT5 account password (only `METAAPI_TOKEN`/`METAAPI_ACCOUNT_ID`; MetaAPI holds the broker password server-side, entered once at account provisioning, not re-readable via the SDK) |
| 3. Check demo expiration | Active, no forced reset, no server migration | **Owner action required** |
| 4. Update MetaAPI account | If credentials changed, update via MetaAPI's account-update API (not this repo's code) | **Owner action required** — and explicitly out of this agent's scope even if it had the new credentials, per "only update broker connection credentials, do not modify strategy/execution/risk/broker adapter code" |
| 5. Re-test connection | Confirm `state=CONNECTED`, then re-enable + start the service | **Not yet reached** — blocked on Steps 1-4 |

## 5. Runtime Verification

Not performed for this incident — there is nothing to verify yet. The service remains stopped and
disabled, matching its state before this session's recovery attempt began. No new
`systemctl status`/`journalctl`/`NRestarts` evidence beyond what's already in §2 above is available
until Steps 1-4 complete and a re-test (Step 5) is actually run.

## 6. Decision: Can S4 begin?

**No.** Two independent conditions must both hold before S4's 24-hour clock starts, and neither
does yet:

1. Broker connectivity restored and verified stable (this report — blocked on owner action).
2. Disk headroom addressed — 90% used, `docker system df` shows ~14GB across images/build-cache/
   volumes as the largest reclaimable-ish surface (noted in the RCA's addendum, not remediated in
   this pass).

**Do-not-do list, followed in this pass and to be followed by whoever executes Steps 1-5**:
no new strategy created, no execution/risk/broker-adapter code changed, no broker check disabled or
bypassed, no fake or placeholder credentials used, no fabricated "CONNECTED" status — the account
genuinely remains `UNDEPLOYED`/`DISCONNECTED` as of this report.

## 7. Handoff — what the owner needs to do next

1. Open the Vantage client portal or MT5 desktop terminal and confirm demo account `25657968` on
   server `VantageMarkets-Demo` is still active and its password is known/unchanged.
2. If the password changed or the account needs re-provisioning, update it through MetaAPI's own
   account management (dashboard at `app.metaapi.cloud`, or the SDK's account-update call) — not
   through this repository.
3. Once MetaAPI reports `state=CONNECTED` for `d6f6eec3-96d5-4001-a802-62b3f4b49817` (verifiable via
   the same read-only `get_account()` check used in this report), ask for this workstream to resume
   at Step 5 (re-enable + start `smc-demo-runner.service`) and the S5.5 30-minute observation window.
4. Separately, decide whether to address disk usage (§6, item 2) before or in parallel with the
   broker fix — it does not block Steps 1-4 but does block S4 regardless of broker status.

## 8. Acceptance criteria for this report

- [x] Original failure and root cause documented, cross-referenced to `SYSTEM2_RUNTIME_OUTAGE_RCA.md`
- [x] MetaAPI status captured (read-only, re-verified at report time)
- [x] Corrective-action checklist reproduced with explicit status per step — no step marked done
      that wasn't actually done
- [x] No credentials fabricated, guessed, or assumed
- [x] No trading/strategy/execution code touched
- [x] Explicit S4 go/no-go decision: **no-go**, with the two specific blocking conditions named
- [x] Runtime verification section present, explicitly states nothing new to report until Steps 1-4
      complete (not fabricated)
