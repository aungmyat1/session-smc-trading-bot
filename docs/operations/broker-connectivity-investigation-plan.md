# Broker Connectivity Investigation Plan (ADR-0014 follow-up)

Date: 2026-07-07
Status: Plan only — no code, no infrastructure, no broker contact made yet.
Requires owner action for several steps (Vantage is a business relationship,
not something an agent can initiate).
Related: `docs/svos/ADR-0014-BROKER-CONNECTIVITY-TECHNOLOGY.md`

## Objective

Determine whether Vantage's FIX API is a viable replacement for MetaAPI on
the current (or an upgraded) account, before committing further engineering
effort to either FIX or continuing the paused mt5linux path.

## Steps

### 1. Access confirmation (owner action required)
- Contact Vantage (via the API Solutions / Vantage Connect channel found in
  ADR-0014's research) to ask directly:
  - Is FIX API available on the current demo account, or does it require a
    different account tier/application?
  - What are the minimum requirements (account size, approval process,
    fees) for a live account, and is there a **FIX demo/UAT environment**
    to test against safely (matching this project's `DEMO_ONLY` posture)?
  - What FIX version/dialect do they use, and do they provide a message
    dictionary / specification document?
- **This step cannot be completed by an agent** — it requires a business
  relationship with Vantage. Everything below is blocked on its outcome.

### 2. Technical feasibility review (once access/spec is known)
- Evaluate Python FIX engine options against Vantage's actual spec:
  `simplefix` (lightweight, manual session handling) vs. `quickfixpy`
  (fuller-featured, more moving parts) — decision depends on what Vantage's
  FIX dialect actually requires, not knowable in the abstract.
- Confirm whether Vantage's FIX API provides market data (quotes/candles) or
  only order execution — if data-only-via-FIX isn't offered, a separate
  market-data source might still be needed alongside it.

### 3. Prototype (isolated, read-only first)
- Build a minimal FIX session (logon/heartbeat/logout) against Vantage's
  demo/UAT FIX endpoint, if one exists — read-only market data subscription
  first, no order messages, mirroring this project's existing pattern of
  proving connectivity before writing an execution path (same shape as
  ADR-0011's shadow-verification approach).
- Only after read-only parity is demonstrated: design the `BrokerInterface`
  implementation (`get_account`, `get_price`, `send_order`, `modify_order`,
  `close_order`, `get_positions`) per the existing seam described in
  ADR-0014 — no new abstraction, just a new implementation of the existing one.

### 4. Shadow verification (same governance pattern as ADR-0011)
- Run the FIX adapter alongside the live MetaAPI connection, read-only,
  diffing prices/account state/positions — no order placement — for an
  agreed period before considering cutover.
- `DEMO_ONLY=true` / `LIVE_TRADING=false` unchanged throughout, per this
  project's standing governance (CLAUDE.md §0.1).

### 5. Decision point
- **If FIX API access is granted and the prototype/shadow phase succeeds**:
  propose a follow-up ADR to formally adopt FIX as the primary connectivity
  path, with a cutover plan modeled on ADR-0011's.
- **If FIX API is unavailable, impractical, or the prototype reveals
  blocking issues**: fall back to `ADR-0013`'s mt5linux/Node 2 plan, starting
  from its Step 2 Wine-validation gate on a fresh node.

## What does NOT happen until Step 1 resolves

No FIX engine library is added to `requirements.in`, no code is written, no
Vantage account changes are requested by an agent, and the mt5linux/Node 2
migration plan is not resumed. This plan's only immediately-actionable item
is Step 1, and it belongs to the owner.

## Acceptance criteria for closing this investigation

- Step 1 answer documented (available / not available / conditional).
- If available: Steps 2-4 evidence produced before any cutover recommendation.
- If not available: explicit handoff back to `ADR-0013`'s plan, with this
  document updated to record why FIX API was ruled out.
