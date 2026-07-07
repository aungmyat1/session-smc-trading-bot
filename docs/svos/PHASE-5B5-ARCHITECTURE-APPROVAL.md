# Phase 5B.5 — Architecture Approval & Implementation Readiness

Date: 2026-07-07
Status: Governance artifact — architecture approval only. No production code
changed, no ExecutionService implemented, no MetaAPI integration modified.
Owner: PM Agent (this document), inputs from Architecture/System2/Documentation/
QA review of existing repository evidence.
Related: `docs/svos/ADR-0013-MT5-EXECUTION-ARCHITECTURE.md`,
`docs/svos/ADR-0014-BROKER-CONNECTIVITY-TECHNOLOGY.md`,
`docs/audit/execution-contract-audit.md`,
`docs/svos/EXECUTION-SERVICE-BOUNDARY-DESIGN.md`,
`docs/operations/risk-register.md`, `docs/systems/system2/ROADMAP.md`,
`docs/systems/system2/STATUS.md`, `SYSTEM2_MASTER_PLAN.md`.

CLAUDE.md scope check: this document is System 2 (Production Execution)
governance work. It records and cross-checks existing findings; it does not
touch broker connectivity, execution code, or trading logic (§0.1, §9 of
`CLAUDE.md`, and this phase's own constraints).

---

## 1. Executive Summary

Five documents (ADR-0013, ADR-0014, execution-contract-audit.md,
EXECUTION-SERVICE-BOUNDARY-DESIGN.md, risk-register.md) were produced on
2026-07-07 and are internally consistent: they tell one continuous story —
broker-technology choice (ADR-0014, superseding ADR-0013) → a self-correction
inside ADR-0014 about the true execution seam → an audit that formalizes the
correction (execution-contract-audit.md) → a boundary design that responds to
the audit's finding (EXECUTION-SERVICE-BOUNDARY-DESIGN.md) → a risk register
that tracks all of it (risk-register.md). No contradictions found between
them. One live cross-reference gap was found (§3 below) and is non-blocking.

**Bottom line:** the architecture is sound enough to *specify* against (this
phase's actual deliverable), but not ready to *implement* against yet, because
the highest-leverage precondition — FIX API access confirmation with Vantage —
is still an open, unstarted investigation (risk #9). Recommendation: **GO WITH
CONDITIONS** on Phase 5C (MetaAPI Demo Validation, which does not depend on
ExecutionService or FIX API), and **HOLD** on any ExecutionService
implementation start until risk #9 resolves. See §7 for full reasoning — these
are two different gates and this document deliberately does not conflate them.

---

## 2. Objective 1 — Architecture Review Board: Approval Report

### 2.1 Documents reviewed

| Doc | Date | Status | Role in the chain |
|---|---|---|---|
| ADR-0013 | 2026-07-07 | Proposed, deprioritized by ADR-0014 | Two-node MT5 topology (fallback only) |
| ADR-0014 | 2026-07-07 | Proposed, current primary path | Broker technology decision: stay on MetaAPI, investigate FIX API |
| `execution-contract-audit.md` | 2026-07-07 | Audit — findings only | Formalizes ADR-0014's self-correction into a structured table |
| `EXECUTION-SERVICE-BOUNDARY-DESIGN.md` | 2026-07-07 | Proposal only | Normalized contract responding to the audit |
| `docs/operations/risk-register.md` | 2026-07-07 (Phase 6) | Living document | Tracks all of the above as risks #1–#12 |

### 2.2 Approved findings (evidence-consistent, no contradiction found)

1. **MetaAPI is the live, working connectivity path today** — confirmed by
   ADR-0014's comparison table and independently by `scripts/run_st_a2_demo.py`
   (`TradeManager(executor, ...)` at line 849, `executor` = `VantageDemoExecutor`,
   which itself wraps `MT5Connector`/`MT5LinuxConnector` — **note**: this is a
   naming nuance, see §3.1, not a contradiction of the decision itself).
2. **Wine/mt5linux is confirmed broken on the current host**, root cause
   unconfirmed after a 10-hypothesis investigation (`wine-investigation-report.md`,
   cited consistently by ADR-0013, ADR-0014, and the risk register).
3. **`BrokerInterface` (`core/broker_interface.py`) has zero live callers** —
   this is the audit's central, verified finding, and it correctly caused
   ADR-0014 to strike through and correct its own earlier claim rather than
   silently edit it. That correction-in-place (visible strikethrough, not a
   deletion) is good practice and was verified against the actual file: the ABC
   is a 6-method, `async` interface (`get_account`, `get_price`, `send_order`,
   `modify_order`, `close_order`, `get_positions`) implemented only by
   intent, not by any consumer's actual call pattern.
4. **Three incompatible execution contracts exist in production code**,
   verified directly against source:
   - `execution/order_manager.py` imports `MetaAPIClient` directly
     (`execution/order_manager.py:28`), not `BrokerInterface`.
   - `execution/trade_manager.py` imports `VantageDemoExecutor` directly
     (`execution/trade_manager.py:23`) — the actual live class behind the
     deployed ST-A2 demo runner.
   - `execution/vantage_demo_executor.py` wraps `MT5Connector`/
     `MT5LinuxConnector` via raw RPC calls (`execution/vantage_demo_executor.py:29-30`),
     declares no `BrokerInterface` inheritance.
   This matches the audit's table exactly — independently re-verified, not
   just re-quoted.
5. **The risk engine is already broker-agnostic** — `execution/risk_manager.py`
   and `execution/demo_risk_manager.py` contain no broker-specific method
   calls; `order_manager.py` only calls `self._risk.check_circuit_breakers(...)`
   and reads `self._risk.risk_pct`. This bounds the blast radius of any future
   ExecutionService migration to exactly three files — confirmed, not a
   projection.
6. **Risk register items #1–#12 are internally consistent** with the
   ADR-0014 decision: items #1, #4–#6 are correctly marked deprioritized
   (mt5linux-path-specific), item #7 was correctly revised upward in cost
   after the audit, and items #11–#12 correctly trace back to the audit and
   boundary design as their mitigation path.

### 2.3 Rejected / unsupported assumptions

- **None of the five documents contain an assumption the evidence
  contradicts.** The one prior assumption that *was* wrong (BrokerInterface as
  the live seam) was already self-corrected in ADR-0014 before this review,
  which is the process working as intended, not a finding for this board to
  raise fresh.
- **Reject as premature**: any implicit read of ADR-0013 as "the plan" for
  execution isolation. ADR-0014 explicitly deprioritizes it and this review
  agrees that pursuing dedicated-node infrastructure work now, ahead of the
  FIX API investigation, would be scope creep against the current decision
  chain.

### 2.4 Unresolved issues (explicit, carried forward)

| # | Issue | Owner action needed |
|---|---|---|
| A | FIX API access/tier with Vantage is unconfirmed (risk #9) | Contact Vantage — `docs/operations/broker-connectivity-investigation-plan.md` is the tracked next step |
| B | Whether `strategy_id` becomes first-class or `magic` stays primary in the normalized Position Model | Deferred to whoever implements ExecutionService (boundary design §"Open question") — not a blocker to freezing the spec |
| C | No automated disk/capacity alerting on Node 1 exists yet (risk #3) | Independent of broker-connectivity work; recommend scheduling `scripts/disk_report.py` regardless of FIX API outcome |
| D | Naming inconsistency: `VantageDemoExecutor` vs. the "MetaAPI" label used in ADR-0014's comparison table | See §3.1 — documentation clarity issue, not an architecture defect |

### 2.5 Implementation prerequisites (must hold before ExecutionService work starts)

1. Risk #9 (FIX API access) resolves — either confirms availability or rules
   it out, per ADR-0014's rollback/fallback chain step 2 or 3.
2. A migration-strategy decision is made (Objective 4, §5 below) — shim-first
   vs. direct rewrite — since the boundary design explicitly does not choose.
3. Objective 2's `ExecutionService v1` specification (§4 below) is reviewed
   and frozen by the owner, since this document is the first freeze pass,
   not a substitute for owner sign-off.

---

## 3. Cross-Document Consistency Findings

### 3.1 Terminology drift (non-blocking, flag only)

ADR-0014's comparison table labels the current live path "**MetaAPI (current,
live)**" throughout. Direct source verification shows the actual deployed
runner (`scripts/run_st_a2_demo.py`) instantiates `TradeManager(executor)`
where `executor` is a `VantageDemoExecutor` (`execution/vantage_demo_executor.py`),
which talks to MT5 via `MT5Connector`/`MT5LinuxConnector` RPC — not
`execution/metaapi_client.py`'s `MetaAPIClient` class directly. `order_manager.py`
is the component that actually imports `MetaAPIClient`, but `order_manager.py`
does not appear in the live ST-A2 demo runner's construction path shown above.

This does not contradict ADR-0014's decision (both `MetaAPIClient` and
`VantageDemoExecutor`'s MT5Connector path are pre-FIX, non-Wine-only-path
options, and the decision to "stay on MetaAPI" reads correctly as "stay off
the confirmed-broken Wine/mt5linux path" in substance). But the ADR's table
should say precisely which class is live, since the audit and boundary design
depend on this precision for correct migration scoping. **Flagged as
implementation prerequisite B-adjacent** — recommend a one-line correction to
ADR-0014 clarifying `VantageDemoExecutor` vs. `MetaAPIClient` as the two
distinct non-Wine paths currently in use by different callers, not a single
"MetaAPI" path. This is a documentation-precision finding, not an
architecture defect — raised for Documentation Agent follow-up, not a
blocker to this phase's GO decision.

### 3.2 No other contradictions found

Scoring tables (ADR-0013's 9-criterion table, ADR-0014's 5-criterion weighted
table) use different criteria for different questions (node topology vs.
broker technology) — this is appropriate, not inconsistent, since they answer
different questions at different layers, exactly as ADR-0014 states.

---

## 4. Objective 2 — ExecutionService v1 Specification (Frozen)

Source: `docs/svos/EXECUTION-SERVICE-BOUNDARY-DESIGN.md`, reviewed against
the audit's confirmed findings and adopted here as the frozen v1 contract.
No broker-specific logic included, per constraint.

### 4.1 OrderRequest

| Field | Type | Required | Validation rule |
|---|---|---|---|
| `symbol` | str | Yes | Must be a known tradeable symbol (existing pair whitelist, e.g. `config/demo.yaml`) |
| `side` | enum(`buy`,`sell`) | Yes | Normalizes `direction` (executor) / implicit method choice (MetaAPI) |
| `quantity` | float | Yes | > 0; replaces `volume`/`lots` |
| `order_type` | enum(`market`,`limit`) | Yes, default `market` | `limit` reserved — no live consumer uses it today |
| `stop_loss` | float \| None | No | Must be on the correct side of entry per `side` if present |
| `take_profit` | float \| None | No | Must be on the correct side of entry per `side` if present |
| `strategy_id` | str | Yes | New field — neither current path tags orders with this in the request itself (open question §2.4-B on its relationship to `magic`) |

### 4.2 OrderResponse

| Field | Type | Notes |
|---|---|---|
| `order_id` | str | Unifies `order_id` (executor dict) / `orderId` (MetaAPI) |
| `status` | enum(`filled`,`rejected`,`pending`,`simulated`) | `simulated` preserves `VantageDemoExecutor`'s `DEMO_ONLY` safety semantics — **must not be lost**, per CLAUDE.md §0.1 |
| `fill_price` | float \| None | |
| `timestamps` | dict | `submitted_at`, `filled_at` (ISO 8601) — expanded from the boundary design's single `timestamp` to preserve both submission and fill instants, since the error contract (§4.5) distinguishes timeout-before-fill from confirmed fill |
| `fill_info` | dict \| None | `filled_quantity`, `average_fill_price` — for partial fills (see §4.5) |
| `metadata` | dict | Escape hatch for broker-specific fields (magic number, comment, raw retcode) |

### 4.3 Position Model

| Field | Type | Notes |
|---|---|---|
| `symbol` | str | |
| `direction` | enum(`long`,`short`) | Unifies `POSITION_TYPE_BUY`/`SELL` and executor's `buy`/`sell` |
| `quantity` | float | Unifies `volume`/`lots` |
| `average_price` | float | Unifies `openPrice`/`entry` |
| `unrealized_pnl` | float | Unifies `profit` |
| `strategy_id` | str \| None | Derived from `magic` today — resolution deferred, §2.4-B |

### 4.4 Account Model

| Field | Type | Notes |
|---|---|---|
| `balance` | float | |
| `equity` | float | |
| `margin_used` | float | |
| `free_margin` | float | |
| `leverage` | float | Not currently used by a spot-only pair set per CLAUDE.md §5, but MT5/Vantage forex accounts always expose it — included for completeness, not because it's used |

### 4.5 Error Contract

| Category | Meaning | Maps from |
|---|---|---|
| `rejected` | Broker actively refused the order | MetaAPI non-success retcode |
| `timeout` | No response within expected window — ambiguous, may or may not have executed | `trade_manager.py`'s existing timeout→ambiguous classification (preserve as-is) |
| `broker_unavailable` | Connection down, reconnect in progress | Existing reconnect/heartbeat states in both MT5Connector-family and MetaAPIClient |
| `invalid_request` | Caller-side pre-flight validation failure | New category — neither current path has clean pre-flight validation |
| `partial_fill` | Order filled for less than requested quantity | New category, not explicitly in the original boundary design — added here because `OrderResponse.fill_info` (§4.2) needs a matching error/status path; flagged for owner review since it wasn't in the source proposal |

**Retry behavior**: not specified by the source design and not invented here.
Flagged as an open spec gap — retry policy (`execution/execution_state.py`'s
`RetryPolicy`, already used by `TradeManager`) should be reused rather than
redesigned, but this document does not assume that decision on the owner's
behalf.

---

## 5. Objective 3 — System2 Dependency Map

| Module | Purpose | Public interface (as actually called) | Dependencies | Broker coupling | Migration priority |
|---|---|---|---|---|---|
| Strategy Engine (`scripts/run_st_a2_demo.py`, `core/signal_router.py`) | Generates and routes trading signals | `SignalRouter`, constructs `TradeManager` | `TradeManager`, `CircuitBreaker`, `PortfolioManager` | None direct — calls through TradeManager | Low — already broker-agnostic by construction |
| Risk Manager (`execution/risk_manager.py`, `execution/demo_risk_manager.py`) | Position sizing, circuit breakers, loss halts | `check_circuit_breakers()`, `risk_pct` | None on broker classes (confirmed, zero grep matches) | **None — already meets target** | None needed (§2.2 finding 5) |
| Order Manager (`execution/order_manager.py`) | Places orders via MetaAPI-specific surface | `place_order(...)` (kwarg-based) | `MetaAPIClient` (direct, `:28`), `RiskManager`, `TradeLogger` | **High** — type-hints `MetaAPIClient` directly, calls MetaAPI-only methods (`check_spread`, `get_open_positions(magic=)`) | **High** — one of the 3 files needing ExecutionService convergence |
| Trade Manager (`execution/trade_manager.py`) | Opens/manages positions for the *live deployed* ST-A2 demo path | `open_position(signal)` | `VantageDemoExecutor` (direct, `:23`), `ExecutionStateStore`, `TelegramAlerter` | **High** — the actual live-path coupling (see §3.1 terminology note) | **Highest** — this is the production hot path |
| Execution Layer / Broker Adapter (`execution/vantage_demo_executor.py`) | MT5-family broker calls | `place_order(**kwargs)` returns dict (`order_id`, `lots`, `id`) | `MT5Connector`/`MT5LinuxConnector` via raw `self._rpc()` | **High** — no `BrokerInterface` inheritance at all | **High** |
| MetaAPI integration (`execution/metaapi_client.py`) | Implements `BrokerInterface` correctly | 6 ABC methods | `BrokerInterface` (correctly inherited) | Low — this is the one component already shaped correctly, it just has no caller | Low — already correct, orphaned rather than broken |
| `BrokerInterface` ABC (`core/broker_interface.py`) | Intended broker seam | 6 async methods | None | N/A | Becomes real once ExecutionService exists, or retire (audit's own framing) |
| Future FIX integration | Not yet built | N/A | Would sit under ExecutionService per boundary design | N/A — no code exists | Blocked on risk #9 |

**Architecture bottleneck identified**: the bottleneck is not any single
module — it is that **three call sites (`order_manager.py`, `trade_manager.py`,
`vantage_demo_executor.py`) each hard-wire to one specific adapter's exact
method names and return shapes**, with `trade_manager.py` carrying the
highest migration priority because it is the only one of the three currently
in the live production path. `order_manager.py`'s live-path status is
unconfirmed by this review (§3.1) — recommend the Documentation Agent
resolve this before the dependency map is treated as final for migration
sequencing.

---

## 6. Objective 4 — Migration Strategy Assessment

| Criterion | Option A: Shim-first | Option B: Direct Rewrite |
|---|---|---|
| Implementation effort | Lower — wrap existing classes behind the new contract without changing call sites immediately | Higher — rewrite `order_manager.py`, `trade_manager.py`, `vantage_demo_executor.py` call sites in one pass |
| Operational risk | Lower — `TradeManager` (the live hot path) is untouched until the shim is proven | Higher — directly modifies the file behind the currently-running `smc-demo-runner.service` |
| Testing impact | Incremental — each adapter can be shadow-verified independently, same pattern as ADR-0011's shadow-verification gate | Requires full regression pass across all 3 call sites simultaneously |
| Rollback complexity | Low — shim is additive, remove it to revert | Higher — reverting a rewritten call site means reverting production code that has since accumulated other changes |
| Demo stability | Preserved — ST-A2 demo runner (currently the only thing actually trading, per `docs/systems/system2/STATUS.md`) is not touched until cutover | At risk during the rewrite window |
| Future broker support | Same end-state either way — both converge on the same `ExecutionService` contract | Same end-state |

**Recommendation: Option A (Shim-first).** This is not a preference call —
it follows directly from evidence already in this repo: (1) this project's
own governing pattern for broker-technology changes is shadow-verification
before cutover (ADR-0011's precedent, reaffirmed by ADR-0014 §"Rollback /
fallback chain" step 4 — "no connectivity technology is ever switched without
a proven parity period first"); (2) `trade_manager.py` is the live production
hot path (confirmed §5) and CLAUDE.md §0.1 forbids anything that risks live
trading stability without an explicit gate; (3) the temporary duplication cost
of shimming is bounded to exactly 3 files (confirmed by the audit, not a
project-wide estimate).

**Criteria for revisiting this recommendation**: if a second broker/execution
provider becomes concretely planned (matching ADR-0013's own deferred-Option-C
reasoning), or if the shim layer itself becomes a maintenance burden after
FIX API integration proves stable — reassess toward direct rewrite once
duplication cost is measured against real migration experience, not
projected.

---

## 7. Objective 5 — Phase Readiness Assessment

**Two separate gates exist and must not be conflated:**

### 7.1 Phase 5C (MetaAPI Demo Validation)

| Check | Status | Evidence |
|---|---|---|
| Infrastructure ready | Yes | Disk resolved 50G/69% used (`docs/operations/disk-expansion-2026-07-07.md`); `auto-trade-vps` stable |
| Architecture documented | Yes | ADR-0013/0014, audit, boundary design, risk register all current and consistent (§2, §3) |
| Risks accepted | Yes, with tracking | Risk register items #9, #11, #12 open but explicitly accepted-and-tracked, not blocking demo continuation (risk #10: "this is the safest available state") |
| Execution path stable | Conditionally yes | `smc-demo-runner.service` verified stable, 0 restarts, but 0 trades executed yet and 58 unexplained non-terminal `ExecutionRecord`s remain un-root-caused (`docs/systems/system2/STATUS.md` "Extended Demo Validation") |
| Monitoring available | Yes | `GET /api/system2/monitoring` landed 2026-07-06 |
| Rollback documented | Yes | ADR-0014 §"Rollback / fallback chain", ADR-0011's original shadow-verification precedent |

**Decision: GO WITH CONDITIONS.**
Conditions: (1) the 58 unexplained non-terminal `ExecutionRecord`s should be
root-caused before treating any extended demo run as clean evidence — this is
already flagged in `STATUS.md`, this review does not add a new requirement,
only reaffirms it as a precondition to trusting demo results; (2) continued
demo validation must not be read as license to start ExecutionService
implementation in parallel (see §7.2) — these are independent workstreams
that happen to share a codebase.

### 7.2 ExecutionService v1 Implementation Start

| Check | Status |
|---|---|
| Specification frozen | Yes, this document (§4) — pending owner sign-off |
| Migration strategy decided | Recommended here (§6), pending owner approval |
| FIX API access confirmed | **No — risk #9 still open, investigation not yet started per the register** |
| Owner approval to proceed | Not sought — out of scope for this phase per its own constraints |

**Decision: HOLD.**
Building ExecutionService now, before FIX API access is confirmed, risks
designing an adapter interface around a broker technology that may not be
reachable — the boundary design itself explicitly does not require this to
exist before FIX investigation proceeds ("no broker technology decision
requires this to exist first"). Recommend holding implementation start until
risk #9 resolves, consistent with this project's own sequencing logic.

---

## 8. Updated Risk Assessment

No new risks found beyond the 12 already tracked in `docs/operations/risk-register.md`.
One clarification added by this review:

| # | Risk | Status | Note added by this review |
|---|---|---|---|
| 13 (new) | ADR-0014's comparison table labels the live path "MetaAPI" without distinguishing `VantageDemoExecutor`'s MT5Connector route from `MetaAPIClient`'s direct route | Open — documentation precision only | See §3.1. Does not change ADR-0014's decision or risk #9's priority; recommend a one-line ADR-0014 correction |

All other risk register entries (#1–#12) reviewed and found consistent with
current evidence — no status changes recommended.

---

## 9. Recommended Agent Assignments

| Workstream | Agent |
|---|---|
| Correct ADR-0014's live-path terminology (§3.1, risk #13) | Documentation Agent |
| Confirm risk #9 (FIX API access) — contact Vantage per `docs/operations/broker-connectivity-investigation-plan.md` | Owner (external action, not delegable to an agent) |
| Root-cause the 58 unexplained `ExecutionRecord`s (Phase 5C condition) | execution-agent |
| Review this document's ExecutionService v1 spec for completeness before freeze | Architecture Agent / owner |
| Track Phase 5C extended demo validation | System2 Agent |

---

## 10. Next Phase Roadmap

1. Owner reviews and signs off on this Architecture Approval Report and the
   frozen ExecutionService v1 spec (§4) — or returns findings for revision.
2. Owner or delegated action: initiate FIX API access investigation with
   Vantage (risk #9) — the single highest-leverage unblock for
   ExecutionService work.
3. Continue Phase 5C (MetaAPI Demo Validation) under the GO WITH CONDITIONS
   decision (§7.1) — root-cause the 58 unexplained `ExecutionRecord`s in
   parallel, not sequentially blocking.
4. Do not begin ExecutionService implementation, FIX adapter work, or
   `order_manager.py`/`trade_manager.py`/`vantage_demo_executor.py`
   modification until risk #9 resolves and a migration strategy is formally
   approved (§6).
5. Correct ADR-0014's terminology gap (§3.1) as a low-effort documentation
   follow-up, independent of the above sequencing.

No production behavior changed by this document. No ExecutionService code
written. No MetaAPI integration modified.
