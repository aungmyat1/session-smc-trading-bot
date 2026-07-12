---
Date: 2026-07-12
Author: Lead Architect / Quant (Claude)
Authority: Level 8 — informational evidence. Does not supersede `docs/00_Project/DOC_AUTHORITY.md`.
Scope: Phase 4 of the System2 Completion Mission. BLOCKED — documented per the
mission's explicit instruction: "stop at that point, document exactly what
is blocked, what evidence is missing, and what the owner must do next. Never
fabricate results or mark a blocked task as complete."
---

# Phase 4 — Measured Cost Model: Blocked

## Executive Summary

Live spread capture cannot be performed from this session. `config/cost_profile_vantage_v1.json`
was created with the exact structure `scripts/capture_spreads.py` (the
existing, unmodified tool) already produces — every numeric field is `null`.
**No spread numbers were fabricated or estimated.** This task is explicitly
**not** marked complete; it is blocked pending owner action.

## Current State

- `config/costs.json`'s `active_profile` remains `"PLACEHOLDER_vt_markets_assumption"`
  — unchanged by this phase.
- `scripts/capture_spreads.py` exists, is unmodified, and is the correct,
  already-built tool for this task (per the mission's own instruction: "use
  existing spread capture tools").

## Evidence — why this is blocked, not merely inconvenient

1. **No credentials available.** `scripts/capture_spreads.py` requires
   `METAAPI_TOKEN` and `METAAPI_ACCOUNT_ID` (checked directly in its `main()`,
   exits with code 2 if either is missing). This session has:
   - No `.env` file (`ls .env` → No such file or directory).
   - No `METAAPI_TOKEN`/`METAAPI_ACCOUNT_ID`/`VANTAGE_*` environment variables
     set (checked directly).
2. **Even with credentials, this cannot run to completion in an automated
   session.** The tool's own docstring: *"leave running across several
   London and NY sessions"* — it polls live market data at a fixed interval
   (default 30s) and only produces meaningful killzone-hour averages after
   **hours to days** of continuous real-time operation against a live
   broker connection. This is fundamentally an operational task that belongs
   on the deployed VPS (`auto-trade-vps`), not something a single sandboxed
   session invocation can produce, regardless of credential availability.
3. **Symbol/session taxonomy note** (not a blocker, but a correction to the
   mission's own wording): the tool classifies samples as `london` /
   `new_york` / `off` (`classify_session()`), not a four-way
   Asian/London/NewYork/Overlap split. `config/cost_profile_vantage_v1.json`
   matches what the tool actually produces. Its default `--pairs` list is
   `EURUSD GBPUSD USDJPY AUDUSD` — **XAUUSD is not included by default** and
   must be passed explicitly (`--pairs EURUSD GBPUSD XAUUSD`) when this is
   actually run, to match this mission's Phase 4 symbol list.

## Risk

None from this phase itself (no code changed, no fabricated data). The risk
this phase exists to prevent — treating the placeholder cost model as if it
were real — remains open until the owner completes the steps below; that
risk is unchanged by this phase, not introduced by it.

## Recommendation — what the owner must do next

1. On the VPS (or any environment with real `METAAPI_TOKEN`/`METAAPI_ACCOUNT_ID`
   and sustained network access to MetaAPI), run:
   ```bash
   export METAAPI_TOKEN=...
   export METAAPI_ACCOUNT_ID=...
   python3 scripts/capture_spreads.py --pairs EURUSD GBPUSD XAUUSD --interval 30
   ```
   left running across at least one full London session and one full New
   York session (per the tool's own documented recommendation).
2. Take the tool's reported killzone-hour median/average/p90/p95 per symbol
   and populate `config/cost_profile_vantage_v1.json`'s `null` fields (or
   feed directly into `config/costs.json`'s `vantage_measured` profile,
   whichever this project's revalidation step consumes — see
   `docs/audit/STA2_REVALIDATION_PLAN.md` task 1-2 from the prior sprint).
3. Only then set `config/costs.json`'s `active_profile` to `"vantage_measured"`.

## Priority

High (blocks Phase 6's revalidation trial from producing trustworthy
evidence) but not owner-actionable by an agent — this phase's own output is
complete once the blocker is documented; the remaining work belongs to the
owner.

## Estimated effort

Owner time: a few minutes to start the capture script, running unattended
for the duration of one London + one New York session (real wall-clock time,
not engineering effort). Populating the JSON afterward: <30 minutes.

## Rollback

N/A — no code changed. `config/cost_profile_vantage_v1.json` is a new,
inert file (not referenced by any code path) until explicitly wired in by a
future step; deleting it has zero runtime effect.

## Dependencies

None for this phase. Phase 6 (ST-A2 revalidation) depends on this phase's
output being real, not placeholder, data.

## Acceptance criteria

- [x] Attempted the existing tool, confirmed the exact missing precondition (credentials)
- [x] Identified the additional blocker even credentials wouldn't resolve (multi-session real-time requirement)
- [x] No numbers fabricated — every field in `cost_profile_vantage_v1.json` is `null`, clearly marked as not captured
- [x] Exact next action documented for the owner
- [x] Task NOT marked complete — explicitly blocked
