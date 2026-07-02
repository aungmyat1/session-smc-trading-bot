# Dependency Boundary Report

Date: 2026-07-01
Status: Read-only audit finding
Scope: Phase 4 of the deployment-topology validation audit — import-level analysis
complementing the responsibility classification in `module_boundary_analysis.md`.

Method: `grep` of `^import|^from` across production-side files (`execution/`, `dashboard/`,
`monitoring/`, `scripts/run_st_a2_demo.py`, `bot.py`, `core/`) for references to
svos/research/replay/optimization/validation/experiments modules, and a reverse grep of
SVOS/research packages for broker/order-execution symbols (`MetaApi`, `place_order`,
`open_position`, `trade_manager`, etc.). `archive/` and `tests/` excluded — not live coupling.

## Production → SVOS/research imports found

| File:line | Imports | Direction | Severity | Notes |
|---|---|---|---|---|
| `execution/governance_guard.py:8-10` | `GovernanceService`, `StrategyRegistryService` (svos) | Production → SVOS | MEDIUM | Documented, intentional design (lifecycle gate) — see `module_boundary_analysis.md`. Real coupling: production cannot run without SVOS's governance module being importable. |
| `dashboard/app.py:66` | `SVOSOperationalAPI` (svos) | Production → SVOS | MEDIUM | Same rationale — dashboard surfaces SVOS state to operators. |
| `bot.py:93` | `VirtualBroker` (execution_simulator) | Production → simulation infra | LOW | Only active under `DRY_RUN`; simulator has no live-broker dependency of its own, so this doesn't chain into a real coupling. |
| `execution_gate.py:7` | execution_simulator symbols | Production/shared → simulation infra | LOW | Validation-oriented gate module, not the hot execution path. |

## SVOS/research → production (broker/order) imports found

| File:line | Imports | Direction | Severity | Notes |
|---|---|---|---|---|
| `adaptive/run_shadow.py:80,82,94` | `execution.mt5_executor`, `metaapi_cloud_sdk` | Research → Production/broker SDK | HIGH | Shadow/paper-trading script; no `place_order`/`open_position` calls found, so it does not place real orders, but it directly imports the live broker executor module and the MetaAPI SDK. This is the one finding in either direction that would block clean separation of research code from the production package and the broker SDK dependency. |

No other file under `svos/`, `research/`, `research_db/`, `research_engine/`, `research_sweep/`,
`strategy_validation/`, or `pipeline/` imports MetaAPI, MT5, `place_order`, `open_position`,
`trade_manager`, or `order_manager`. `research/svos/payload_builder.py` and `.../engine.py`
import from `execution_validation/` (the offline validation framework), which is expected and
not a broker-coupling concern.

`svos/lifecycle/manager.py` and `db/control_plane.py` are imported by
`execution/governance_guard.py` (confirmed above) but not by `scripts/run_st_a2_demo.py`
directly — the live tick loop consults governance only through the guard module, not the raw
lifecycle manager.

## Violations summary

| Severity | Count | Recommended action |
|---|---|---|
| HIGH | 1 (`adaptive/run_shadow.py`) | Extract a thin market-data-feed interface for shadow/research scripts instead of importing `execution.mt5_executor` and the MetaAPI SDK directly. Not performed by this audit. |
| MEDIUM | 2 (`execution/governance_guard.py`, `dashboard/app.py`) | No code change recommended — this is the documented lifecycle-gate design. If independent packaging (separate containers/artifacts per node) ever becomes a goal, this pair would need to become a network call instead of an in-process import. |
| LOW | 2 (`bot.py`, `execution_gate.py`) | No action needed — confined to dry-run/validation paths. |

## Bottom line

The dependency boundary is **mostly clean in the risk-relevant direction**: no SVOS/research
pipeline code can place real orders or touch live broker state, except for the shadow-trading
script noted above, which reads live market data but does not trade. The reverse direction
(production depending on SVOS governance) is coupling by design, matching the two-node
topology's assumption that both nodes run from the same repository rather than from separately
packaged artifacts (see `deployment_topology_validation.md`).
