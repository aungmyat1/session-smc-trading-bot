---
Date: 2026-07-12
Author: PM/Architect audit (Claude)
Authority: Level 8 — informational evidence. Does not supersede
`docs/00_Project/DOC_AUTHORITY.md`.
Scope: Phase 1 of the demo-readiness audit requested 2026-07-12.
---

# Architecture Reality Map

What is actually running, actually tested, and actually missing — as opposed
to what the target architecture docs describe. Facts are cited to file:line;
inferences are labeled.

## 1. Headline fact

**Controlled demo trading is not a future milestone — it is already deployed
and running.** `smc-demo-runner.service` (systemd unit,
`deploy/gcp-vm1/systemd/smc-demo-runner.service`) runs
`scripts/run_st_a2_demo.py`, which connects to a live Vantage MT5 **demo**
account via MetaAPI and places real demo-account orders for strategy ST-A2.
Per `docs/audit/DEMO_TRADING_RISK_ASSESSMENT.md` and
`docs/audit/EXECUTION_LAYER_GAP_ANALYSIS.md` (both 2026-07-05, code-verified,
not just doc claims), the service has been stable (0 restarts) since a
crash-loop bug was fixed on 2026-07-04. `LIVE_TRADING=false` / `DEMO_ONLY=true`
are enforced (§0.1 invariant, not violated by any finding here).

The project's stated objective ("get running in controlled demo trading") is
therefore **~80% already true for ST-A2 specifically**. The real gap is not
deployment — it's that the validation evidence behind that running instance
doesn't meet the current gate, and two other strategies sit in a
"could place live demo orders" config state with zero backtest evidence.
Details below.

## 2. Actual data → execution pipeline (live path only)

```
Historical data (Dukascopy, scripts/fetch_data.py / download_dukascopy.py)
        |
Feature/session build (strategy/session_liquidity/session_builder.py)
        |
Strategy engine — LIVE PATH:
  strategy/session_liquidity/{bias_filter,sweep_detector,displacement_detector,entry_engine}.py
  orchestrated by strategy/session_liquidity/session_strategy.py
  wrapped by strategies/adapters/st_a2_runtime.py -> st_a2_adapter.py
        |
Risk engine: execution/demo_risk_manager.py (0.25%/trade, 4 trades/day,
  2 open positions, 1.5% daily loss limit, 3 consecutive losses)
        |
Execution layer: execution/trade_manager.py (order retry+backoff,
  idempotency key, emergency_close_all) -> execution/mt5_connector.py
        |
Broker: Vantage MT5 demo account via MetaAPI Cloud SDK
```

Entry point: `scripts/run_st_a2_demo.py` (its own docstring names itself the
canonical, deployed entrypoint; corroborated by the systemd unit file).
Per-tick safety: `execution/control_plane.py` `TradingPermissionService`
checked every tick before any order logic runs; on `emergency_stop.active`,
`trade_manager.emergency_close_all()` fires and the tick returns early
(verified against code, per `docs/audit/EXECUTION_LAYER_GAP_ANALYSIS.md` row 5).

## 3. What exists / tested / missing, by layer

| Layer | Exists | Tested | Missing / gap |
|---|---|---|---|
| Historical data | Dukascopy fetch scripts, `data/` store | `scripts/validate_dataset.py`, `verify_data_layers.py` | GBPUSD 2021-2023 data still missing per `docs/WALK_FORWARD_RESEARCH_PLAN.md` — blocks walk-forward |
| Strategy logic (ST-A2) | `strategy/session_liquidity/*` — bias, sweep, displacement, entry/SL/TP, all with inline no-lookahead reasoning | `tests/session_liquidity/*` (6 files), `tests/core/test_st_a2_adapter.py` — substantial unit coverage | No lookahead audit document actually covers this chain — `docs/audit/LOOKAHEAD_AUDIT.md` audits a *different*, unused chain (see §5) |
| Replay/backtest engine | `scripts/backtest_session_liquidity.py` — real bar-by-bar chronological simulation, SL-before-TP same-bar handling | `tests/test_backtest_session_liquidity.py`, `tests/test_historical_replay.py` | Hardcoded gate inside the script itself is the **old** gate (PF>1.0, n≥100), not the current one; no Sharpe computed anywhere in `compute_metrics()` |
| Cost model | `config/costs.json` | n/a | `active_profile: "PLACEHOLDER_vt_markets_assumption"` — explicitly unverified against real Vantage spreads; `vantage_measured` profile exists but is empty |
| Risk engine | `execution/demo_risk_manager.py` (live) + legacy `execution/risk_manager.py` (serves dormant `bot.py` path) | `tests/execution/test_demo_risk_manager.py` | Two risk numbers for ST-A2 not reconciled (portfolio.yaml 0.30% vs demo_risk_manager.py 0.25%) |
| Execution/broker | `execution/mt5_connector.py` (live), `execution/trade_manager.py`, `execution/control_plane.py`, `execution/close_reconciliation.py` | `tests/execution/*` (11 files), `tests/scripts/test_run_st_a2_demo_*` (4 files) | Idempotency key generated fresh per order call, never checked against existing records — no live double-order dedup (P0 per `DEMO_TRADING_RISK_ASSESSMENT.md`) |
| Deployment | systemd units in `deploy/gcp-vm1/systemd/` (runner, reconciliation timer, health-check timer) — real, `Restart=always`, resource-limited | `docs/vps/RUNNING_SERVICES.md`, `VPS_INVENTORY.md` snapshots | None blocking; monitoring is dashboard/log-based, not alerting-based (Telegram alerts configured but not verified wired to every failure mode) |
| Governance/lifecycle | `svos/lifecycle/manager.py` (11-stage state machine, real, not a stub) | — | ST-A2 registry status `DEFERRED_REVALIDATION` in `config/strategy_catalog.yaml`, yet the strategy is placing live demo orders — a tracked gap per CLAUDE.md §6, confirmed still open |

## 4. What's declared vs. what's actually executing (important distinction)

`config/strategy_portfolio.yaml` declares **five** strategies `enabled: true`:
ST-A2 (`execution_mode: demo`), LondonBreakout (`demo`), NYMomentum (`demo`),
AdaptiveSMC (`shadow`), VWAPMeanReversion (`shadow`).

**Only ST-A2 is actually executing anywhere.** The deployed systemd runner
(`scripts/run_st_a2_demo.py`) is hardcoded to `--strategy ST-A2`
(`SYSTEM2_MASTER_PLAN.md:527-543`). `scripts/run_portfolio.py` is the only
entrypoint that could run all five, but it has **no systemd unit** and is
gated by an explicit `RUN_PORTFOLIO_ALLOW_START` guard preventing accidental
start.

This means `strategy_portfolio.yaml`'s `execution_mode: demo` for
LondonBreakout and NYMomentum is currently a **latent config landmine, not an
active fact**: per `config/strategy_catalog.yaml`, both strategies have
`replay: pending` / `backtest: pending` (zero completed evidence), yet the
config file already authorizes real demo-account order placement
(`execution_mode: demo` header explicitly means "live demo orders," per
`strategy_portfolio.yaml:2`) the moment anything runs `run_portfolio.py` or
the single-strategy guard is relaxed. This is a bigger, currently-latent
version of the ST-A2 governance gap that CLAUDE.md §1/§6 already documents by
name — CLAUDE.md does not currently call out LondonBreakout/NYMomentum for it.

## 5. Duplication inventory (fact-checked against imports, not just directory names)

| Area | Active (imported by live path) | Dormant/duplicate | Recommendation |
|---|---|---|---|
| Strategy definitions | `strategy/session_liquidity/` (ST-A2), `adaptive/` (London/NY/AdaptiveSMC engines, reached via `strategies/adapters/`) | `session_smc/` — contains what look like two nested full repo copies, not a normal package; no confirmed live import found. **Not fully verified** — flagged for a follow-up check, not yet safe to delete. | Do not touch now; verify import resolution before any decision |
| Broker/execution client | `execution/mt5_connector.py` (used by `run_st_a2_demo.py`) | `execution/metaapi_client.py` (597 lines, used by dormant `bot.py`/`order_manager.py`), `execution/mt5_executor.py` (182 lines, unused) | Three parallel broker-client stacks is a real maintenance/confusion risk (already flagged in `EXECUTION_LAYER_GAP_ANALYSIS.md`) — consolidation is a `LATER` item, not blocking |
| Lookahead audit | strategy's own inline no-lookahead comments (bias_filter.py, sweep_detector.py, displacement_detector.py) | `docs/audit/LOOKAHEAD_AUDIT.md` audits `session_smc/`'s CHoCH+BOS+FVG chain — a different, unused-in-production strategy variant | The deployed chain has no standalone lookahead audit document — worth producing later, not blocking (unit tests + inline reasoning provide partial coverage now) |
| Dashboard | `dashboard/` (Python/Flask, `dashboard/app.py`, wired to `make dashboard`) | `"New Dashborad"/` — a separate Vite/React/TS frontend prototype, not wired to any Python backend, no code imports it | Disconnected prototype, zero risk to demo readiness, ignore |
| SVOS orchestration | `svos/lifecycle/`, `svos/registry/`, etc. (newer backend package) | `research/svos/engine.py` (older script-driven orchestrator, still active per `CURRENT_STATE.md`) | Known dual-orchestrator debt (already tracked in `docs/svos/CURRENT_STATE.md`); does not block the ST-A2 demo runner, which does not depend on either orchestrator |
| `archive/` | — | Confirmed genuinely inert: excluded from `pyproject.toml`, `pytest.ini`, lint configs; no active import found anywhere in the repo | No action needed |

## 6. Bottom line

The runtime architecture for **ST-A2 demo execution** is real, largely
complete, and already live — this is the strongest part of the project. The
architecture risk is concentrated in three places: (1) the config layer
authorizing more than what's evidenced (LondonBreakout/NYMomentum), (2) an
unresolved freeze-status question between SVOS-governance docs and System-2
execution work, and (3) duplicate/dormant code paths that don't block today
but will confuse the next change if not eventually consolidated. None of
these require an architecture rewrite — they require targeted config changes,
one governance decision, and a scoped code fix (idempotency dedup). See
`FASTEST_PATH_TO_DEMO.md` for sequencing.
