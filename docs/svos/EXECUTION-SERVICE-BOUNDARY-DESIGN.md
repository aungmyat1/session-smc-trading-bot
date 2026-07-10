# ExecutionService Boundary — Design Proposal (not implemented)

Date: 2026-07-07
Status: Proposal only — no code written, no migration performed
Related: `docs/svos/ADR-0014-BROKER-CONNECTIVITY-TECHNOLOGY.md` (corrected),
`docs/audit/execution-contract-audit.md`, `core/broker_interface.py`

## Why

`docs/audit/execution-contract-audit.md` found three incompatible calling
conventions in production execution code. This document proposes what a
single real seam would look like — a normalized contract that
`order_manager.py`, `trade_manager.py`, and `vantage_demo_executor.py` could
all eventually call through, and that MetaAPI, FIX, and (if ever revived)
mt5linux could all implement underneath. **This is a proposal to review, not
a design to build yet** — no broker technology decision requires this to
exist first (MetaAPI keeps working exactly as it does today regardless).

## Target shape

```
System2 (order_manager.py, trade_manager.py, strategy runners)
        |
        |  (single normalized contract)
        v
   ExecutionService
        |
        |  (adapter interface — this IS core/broker_interface.py,
        |   corrected to match what callers actually need)
        v
  Broker Adapter Layer
   +---- MetaAPI Adapter   (execution/metaapi_client.py, adapted)
   +---- FIX Adapter        (future, per ADR-0014's investigation)
   +---- MT5 Adapter        (execution/mt5linux_connector.py, paused per ADR-0014)
```

`ExecutionService` is the thing `order_manager.py`/`trade_manager.py` would
call; each adapter underneath implements the same normalized methods against
its specific broker technology. This is the layer that doesn't exist today —
what exists today is three consumers each hard-wired to one specific
adapter's exact method names and return shapes.

## Order Request (normalized)

| Field | Type | Notes |
|---|---|---|
| `symbol` | str | e.g. `"EURUSD"` |
| `side` | enum | `"buy"` \| `"sell"` — normalizes `direction` (executor) vs. implicit method choice (`create_market_buy_order` vs `_sell_order` in MetaAPI) |
| `quantity` | float | replaces `volume` (MetaAPIClient) / `lots` (VantageDemoExecutor) — one name |
| `order_type` | enum | `"market"` for now (matches both current paths); reserved for `"limit"` since `MetaAPIClient.place_limit_order` already exists but isn't used by either live consumer today |
| `stop_loss` | float \| None | |
| `take_profit` | float \| None | |
| `strategy_id` | str | new field — neither current path tags orders with a strategy identifier in the request itself; `magic` numbers currently serve an overlapping but broker-specific purpose (see Error/metadata note below) |

## Order Response (normalized)

| Field | Type | Notes |
|---|---|---|
| `order_id` | str | unifies `order_id` (executor dict) and MetaAPI's `orderId` |
| `status` | enum | `"filled"` \| `"rejected"` \| `"pending"` \| `"simulated"` (preserves `vantage_demo_executor.py`'s `DEMO_ONLY` simulated-order semantics — this must not be lost in normalization, since it's a live safety mechanism) |
| `fill_price` | float \| None | |
| `timestamp` | str (ISO 8601) | |
| `broker_metadata` | dict | escape hatch for broker-specific fields (magic number, comment, raw retcode) that don't need to be first-class but shouldn't be discarded either — avoids over-normalizing away information a future debugging session might need |

## Position Model (normalized)

| Field | Type | Notes |
|---|---|---|
| `symbol` | str | |
| `quantity` | float | unifies `volume`/`lots` |
| `direction` | enum | `"long"` \| `"short"` — unifies MetaAPI's `POSITION_TYPE_BUY`/`SELL` string and the executor's already-normalized `"buy"`/`"sell"` |
| `average_price` | float | unifies `openPrice`/`entry` |
| `unrealized_pnl` | float | unifies `profit` |
| `strategy_id` | str \| None | derived from `magic` today — see note below |

**Open question, not resolved by this proposal**: today, `magic` numbers
double as both a broker-required order-tagging mechanism and this project's
de facto strategy identifier (`config/demo.yaml`'s magic-number-per-strategy
convention, per CLAUDE.md §5). Whether `strategy_id` becomes a first-class
field with `magic` demoted to `broker_metadata`, or whether `magic` stays
primary, is a design decision for whoever implements this — flagged here,
not decided.

## Error Contract (normalized)

| Category | Meaning | Maps from |
|---|---|---|
| `rejected` | Broker actively refused the order (bad price, invalid volume, etc.) | MetaAPI order result with a non-success retcode |
| `timeout` | No response within the expected window — **ambiguous**, may or may not have executed | `execution/trade_manager.py`'s existing timeout→ambiguous classification (already exists, already correct — preserve as-is, don't regress it) |
| `broker_unavailable` | Connection down, reconnect in progress | Both `MT5Connector`/`MT5LinuxConnector`'s and `MetaAPIClient`'s existing reconnect/heartbeat states |
| `invalid_request` | Caller-side validation failure (bad symbol, non-positive quantity) | New category — neither current path has a clean pre-flight validation error class today; requests currently fail deep inside broker-specific code instead |

## What this proposal deliberately does NOT do

- Does not specify *how* migration happens (that's a separate migration
  roadmap, not drafted here — Task 4 asked for the contract shapes, not the
  migration mechanics).
- Does not choose between "rewrite `order_manager.py`/`trade_manager.py` to
  call `ExecutionService`" vs. "build `ExecutionService` as a shim behind
  the existing call sites" — both are viable, and the choice affects risk/
  effort differently; a follow-up decision, not assumed here.
- Does not touch risk engine code — `execution/risk_manager.py`/
  `demo_risk_manager.py` were confirmed already broker-agnostic
  (`docs/audit/execution-contract-audit.md`), so nothing here changes their
  interface.
- Does not build a FIX adapter or resume MT5/Wine — both remain gated by
  `ADR-0014`'s existing decision.
