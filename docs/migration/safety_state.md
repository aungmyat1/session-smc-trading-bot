# Architecture Migration Safety State

Date: 2026-07-01
Status: Observed
Version: 1.0
Owner: Operations
Authority: Level 7 — Migration Evidence
Related: baseline.md, current_test_status.md, ../svos/DEPLOYMENT_TOPOLOGY.md

## Trading Safety

Locally observed process environment and runtime state:

| Control | State |
|---|---|
| Host | `auto-trade-vps` |
| Account mode | demo |
| Runner mode | demo |
| `LIVE_TRADING` | `false` |
| `DEMO_ONLY` | `true` |
| Live capital submission | disabled |
| Broker state file | connected at snapshot time |
| Execution state | idle; last decision `no_signals` |
| Emergency/circuit halt | no active control-state snapshot was present; authoritative source is `reports/control_state.json` |

The active runner and dashboard use `dashboard.control_state` and
`reports/control_state.json` for emergency-stop authority. `logs/bot_state.json`
belongs to the legacy risk-manager path and must not be used to determine the
active emergency-stop state during cutover or incident response.

The runtime does contact MetaAPI for market/broker data and logged recurring
subscription timeouts. `LIVE_TRADING=false` and `DEMO_ONLY=true` prevent order
submission through the guarded paths. No safety setting was changed.

## Active Runtime Strategy

`SMCOrderBlockFVGSession` version `0.1` is running as a demo service on
`auto-trade-vps`, scanning EURUSD, GBPUSD, and XAUUSD. Its runtime state reports
`active`, but its canonical catalog state is `draft`, `approved: false`, and
`current: false`.

This is a governance/runtime mismatch. Runtime activity must not be interpreted
as strategy approval.

## Canonical Strategy Catalog

`current_strategy` is `null`. No catalog entry is approved or current.

| Strategy | Version | Catalog status | Approved/current |
|---|---:|---|---|
| ST-A2 | 2.1 | `DEFERRED_REVALIDATION` | no/no |
| LondonBreakout | 0.3 | research | no/no |
| NYMomentum | 0.3 | replay | no/no |
| VWAPBreakout | 0.3 | shadow | no/no |
| VWAPMeanReversion | 0.1 | shadow | no/no |
| AdaptiveSMC | 0.1 | research | no/no |
| SMCOrderBlockFVGSession | 0.1 | draft | no/no |
| D2E3 | 0.1 | research | no/no |

No strategy has a valid Production Approval package in the observed catalog.

## Current Risk Settings

The active demo risk manager defines:

- risk per trade: `0.25%` of balance;
- maximum trades per day: `4`;
- maximum open positions: `2`;
- daily loss limit: `1.5%`;
- maximum consecutive losses: `3`;
- maximum lot size: `0.5`.

Repository-level `config/risk.yaml` separately specifies `0.5%` risk per trade,
and `config/demo.yaml` specifies other portfolio-level limits. Multiple risk
configurations therefore exist and must be mapped to their actual consumers in
Phase 1. They were not reconciled or changed here.

## Emergency Stop Procedure

The active status service exposes:

- `POST /api/emergency-stop` with exact confirmation token
  `CONFIRM-EMERGENCY-STOP`;
- scopes `block_only` or `close_positions`;
- `POST /api/emergency-stop/clear` with exact token
  `CONFIRM-CLEAR-EMERGENCY-STOP` after operator review.

Activating the stop writes shared control state. The runner checks this state;
the `close_positions` scope requests managed-position closure. In an incident,
the operator should:

1. activate the emergency stop through the authenticated dashboard/control API;
2. select `close_positions` only when immediate managed-position closure is
   intended;
3. verify `GET /api/control/state`, broker positions, and service logs;
4. stop `smc-demo-runner.service` if the control plane or runner is unreliable;
5. clear the stop only after reconciliation and explicit operator review.

Phase 0 did not invoke, test, or clear the emergency stop because that would
mutate live operational state.

## Safety Verdict

Live trading remains disabled and the guarded demo configuration is intact.
The system is not production-approved: no strategy is approved/current, the
active demo runner conflicts with catalog state, and recurring MetaAPI errors
remain. The migration must fail closed and preserve these guards throughout.
