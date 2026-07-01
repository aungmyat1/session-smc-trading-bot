# Module Responsibility Boundary Audit

Date: 2026-07-01
Status: Read-only audit finding
Scope: Phase 3 of the deployment-topology validation audit

## Classification

| Component | Production | SVOS | Shared |
|---|---|---|---|
| Broker connector (`execution/vantage_demo_executor.py`, `execution/mt5_executor.py`) | ✅ | | |
| Order execution (`execution/trade_manager.py`, `bot.py`'s order manager) | ✅ | | |
| Risk engine (`execution/risk_manager.py` — legacy; `execution/demo_risk_manager.py` — current) | ✅ | | |
| Replay engine (`pipeline/`, `execution_simulator/`, `simulator/`) | | ✅ | |
| Optimizer (`src/analytics/sweep.py`, `research_sweep/`) | | ✅ | |
| Validation (`strategy_audit/`, `strategy_validation/`, `execution_validation/`) | | ✅ | |
| SMC indicators (`session_smc/`, `adaptive/`) | | ✅ | |
| Strategy API / signal contract (`core/` — `Signal`, `BaseStrategy`, registry) | | | ✅ (by design — both sides implement the same contract) |
| Governance / lifecycle (`svos/lifecycle/manager.py`, `svos/orchestration/`, `svos/governance/`) | | ✅ (authority) | consumed by production via `execution/governance_guard.py` |
| Dashboard (`dashboard/`, `New Dashborad/`) | ✅ | | reads SVOS operational API for control-panel views |

## Correctly separated modules

- **Broker/order/risk execution vs. replay/simulation**: `execution/` (live) and
  `execution_simulator/` (simulated) are cleanly split — the simulator implements the same
  `BrokerInterface` but never touches MetaAPI/MT5. `bot.py` uses the simulator only under
  `DRY_RUN` mode (`bot.py:93`), which is a legitimate, intentional use, not a leak.
- **Validation vs. execution**: `execution_validation/` and `execution_gate.py` consume
  execution_simulator's replay output, not live broker state — they audit signal/order
  matching offline.
- **SMC feature detection**: `session_smc/` is a standalone detector library with no execution
  dependency in either direction.

## Intentionally coupled modules (by design, not a defect)

- **`execution/governance_guard.py`** imports `GovernanceService` and
  `StrategyRegistryService` from `svos/`. Per `docs/CORE_ARCHITECTURE.md` (§39, per the
  research agent that reviewed it), this is deliberate: production is meant to consult SVOS's
  governance/registry before a strategy is allowed to run, so production *cannot* deploy
  without the SVOS lifecycle/governance module being importable. This is a real coupling, but
  it is the documented design, not an accident — production depending on governance state is
  the whole point of the lifecycle gate.
- **`dashboard/app.py`** imports `SVOSOperationalAPI` for its control-panel view — same
  rationale: the dashboard is meant to surface SVOS state to the operator.

## Incorrectly coupled / worth flagging

- **`adaptive/run_shadow.py`** (a research/shadow-trading script) imports `execution.mt5_executor`
  and the `metaapi_cloud_sdk` package directly, to open a live market-data feed for shadow
  (no-order) trading. This is not a live-order risk (no `place_order`/`open_position` calls
  found in this file), but it does mean a "research" script has a hard runtime dependency on
  the broker SDK and the production `execution/` package — if `execution/` is ever split into
  a separate deployable unit from research code, this script breaks. Recommended action (not
  performed by this audit): extract a thin market-data-feed interface that both live execution
  and shadow/research code depend on, instead of research importing `execution.mt5_executor`
  directly.

## Migration risk this creates

Because `execution/governance_guard.py` and `dashboard/app.py` import SVOS packages, and
`adaptive/run_shadow.py` imports execution packages, **production and SVOS cannot currently be
split into two independently-deployable codebases without either (a) shipping SVOS's
governance/registry code alongside production, or (b) formalizing the governance-guard call as
a network/API boundary instead of an in-process import.** This matches the two-node topology
in `docs/svos/DEPLOYMENT_TOPOLOGY.md`, which assumes both nodes run from a checked-out copy of
the same repository rather than from independently-packaged artifacts — so today's coupling is
consistent with the documented plan, not a violation of it. It would become a real blocker only
if a future goal is separate deployable packages/containers per node; see
`architecture_gap_report.md` §3–4 for how this bears on migration priority.
