# Execution Contract Audit

Date: 2026-07-07
Status: Audit — findings only, no code changed
Related: `docs/svos/ADR-0014-BROKER-CONNECTIVITY-TECHNOLOGY.md` (correction
this audit formalizes), `core/broker_interface.py`

**Placement note**: filed under `docs/audit/` (this project's established
location for audit-type documents — `wine-investigation-report.md`,
`capacity-plan.md`, `architecture-decision-report-phase6.md` all live here)
rather than a new `docs/architecture/` directory, to avoid fragmenting audit
documentation across two locations.

## Method

Independent code verification (delegated to `execution-agent`, 2026-07-07)
of the claim that `BrokerInterface` is the live execution seam. Confirmed
false. This audit formalizes that finding into a structured table and adds
one additional check (risk manager coupling) this round.

## Findings

| Component | Current dependency | Problem | Target |
|---|---|---|---|
| `execution/order_manager.py` | `MetaAPIClient` (type-hinted directly, `:28,49` — not `BrokerInterface`) | Calls MetaAPI-specific surface not on the ABC: `check_spread(symbol)` (`:108`), `get_open_positions(magic=magic)` (`:118`), keyword-argument `place_order(symbol=, direction=, volume=, sl=, tp=, magic=, comment=)` (`:161-169`) | `ExecutionService` (see Task 4 design below) |
| `execution/trade_manager.py` | `VantageDemoExecutor` (`:36`) — a class with no `BrokerInterface` inheritance at all | Different contract entirely: `place_order(**kwargs)` returns `dict` with `order_id` key (`:147-148`), `modify_position(position_id, sl, tp)` (`:120`), `get_positions()` returns `list[dict]` filtered by `p.get("magic")` (`:122-124`) — a third, incompatible shape vs. both `MetaAPIClient`'s dataclasses and the ABC | `ExecutionService` |
| `execution/vantage_demo_executor.py` | `MT5Connector` / `MT5LinuxConnector` via raw `self._rpc()` (`:70-71,82,94,104,131,161-165`) | No `BrokerInterface` inheritance declared (`:49`); dict keys differ again (`lots` not `volume`, `current_price`, `id` not `position_id`) — broker-agnostic *between MT5-family backends only*, not against the ABC | `ExecutionService`, or an adapter implementing it |
| `core/broker_interface.py` (`BrokerInterface`) | N/A — the ABC itself | Exists, is implemented by `MetaAPIClient`, but **no consumer actually calls through it** — it's a correct-looking abstraction with zero live callers depending on only its 6 methods | Becomes the real interface once `ExecutionService` is built, or is retired if `ExecutionService` introduces its own contract |
| Risk manager (`execution/risk_manager.py`, `execution/demo_risk_manager.py`) | Neither file references any broker-specific method (`MetaAPI`, `place_order`, `get_positions`, `check_spread` — zero matches on direct grep) | **None found** — risk logic is already independent of broker calls; `order_manager.py` calls `self._risk.check_circuit_breakers(now)` and reads `self._risk.risk_pct` (`:100,137,156`), both broker-agnostic | Already meets the target — no migration needed here |

## Summary

3 of 4 execution-layer components need work to converge on a single real
seam; the risk engine already is independent and requires no change. This
confirms the corrected ADR-0014 finding and narrows the actual scope of
future work: the problem is contained to `order_manager.py`,
`trade_manager.py`, and `vantage_demo_executor.py` — not a project-wide
refactor, and not something that touches risk logic at all.
