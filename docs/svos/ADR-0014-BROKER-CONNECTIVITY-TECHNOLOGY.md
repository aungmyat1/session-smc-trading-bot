# ADR-0014: Broker Connectivity Technology — Wine/MT5 vs. MetaAPI vs. FIX API

Date: 2026-07-07
Status: Proposed — recommendation only, no implementation performed
Version: 1.0
Owner: Lead Architect
Authority: Level 5 — Decision
Related: `ADR-0011-MT5LINUX-BROKER-BRIDGE.md`, `ADR-0012-SYSTEM2-HOSTING-STRATEGY.md`,
`ADR-0013-MT5-EXECUTION-ARCHITECTURE.md` (node-topology question — remains
valid *if* mt5linux is chosen; this ADR reopens the higher-level "which
technology" question at the layer above it), `docs/audit/wine-investigation-report.md`,
`docs/operations/disk-expansion-2026-07-07.md`

## Context

ADR-0011 committed to replacing MetaAPI with mt5linux without FIX API having
been considered — it wasn't known to be an option at the time. Since then:
- The mt5linux path hit a confirmed, unresolved Wine reliability blocker
  (`docs/audit/wine-investigation-report.md`) that a dedicated node (ADR-0013)
  might fix, but this is a hypothesis, not a proven fact — the migration
  plan's own Step 2 treats "does Wine even work on a fresh node" as a gate,
  not a given.
- Research surfaced that Vantage offers a native institutional-grade FIX API
  that bypasses MT4/MT5 entirely — a option that existed before ADR-0011 but
  wasn't evaluated against it.
- The disk-capacity blocker that motivated part of ADR-0012/0013 has since
  been resolved independently (`docs/operations/disk-expansion-2026-07-07.md`
  — 50GB disk, 69% used, 31% free) — this ADR's comparison is not influenced
  by capacity pressure either way.

This ADR compares all three connectivity technologies on their own merits,
since the original ADR-0011 decision was made without FIX API on the table.

## Comparison

| Dimension | Wine/MT5 (mt5linux) | MetaAPI (current, live) | FIX API (Vantage native) |
|---|---|---|---|
| **Currently working** | No — confirmed broken on Node 1, unconfirmed whether a fresh node fixes it | **Yes** — live in production right now (`smc-demo-runner.service`) | Unconfirmed — access/tier not verified for the current account |
| **Runs natively on Linux** | No — requires Wine (a compatibility layer, not native) | Yes — pure Python SDK | Yes — FIX is a wire protocol, engines exist for Linux/Python |
| **Third-party dependency** | None beyond Wine itself, but requires owning/operating a Windows-emulated terminal process | Yes — MetaAPI Cloud (their uptime, pricing, rate limits) | None — direct broker connectivity |
| **Latency** | Low once working (local/network RPC to a terminal) | Higher — extra hop through MetaAPI's cloud infrastructure | Lowest — direct market access, purpose-built for this |
| **Operational burden** | High — supervising a Wine/MT5 terminal process (crash recovery, login persistence), on top of whatever caused the current reliability failure | Low — it's a managed cloud API, already proven stable enough to run today | Medium — a FIX session needs its own connection/heartbeat management, but no OS-level terminal to babysit |
| **Known incidents** | Wine load failure, root cause unconfirmed | 119 MetaAPI RPC subscription-timeout errors observed (`docs/systems/system2/ROADMAP.md` Phase 12) — real but non-fatal, existing reconnect logic handles it | None yet — untested |
| **Engineering effort to adopt** | Already built (ADR-0011 connector code exists), blocked on infra | Zero — already the live implementation | New — requires a FIX engine (e.g. `simplefix`, `quickfixpy`), Vantage-specific message dictionary, session management; no existing code in this repo |
| **Access/approval required** | None beyond infra | None — already have it | **Unconfirmed** — FIX API access is typically a separate account tier; requires contacting Vantage, unknown timeline/requirements |
| **Architectural cleanliness** | Medium — a real terminal you own, but an emulation layer in the path | Medium — clean SDK, but a cloud intermediary between you and the broker | **Highest** — most direct, most "professional trading architecture" path |

## Decision

**Continue running on MetaAPI as the live connectivity path. Investigate FIX
API access with Vantage as the target end-state architecture. Do not
continue the mt5linux/Wine path unless the FIX API investigation concludes
it's unavailable or impractical.**

Reasoning:
- MetaAPI is the only option of the three that is *proven working today*,
  with zero migration risk to stay on it. The original motivation for
  ADR-0011 (owner request to move off MetaAPI) did not identify a specific
  functional deficiency in MetaAPI itself — no incident in this project's
  history shows MetaAPI as unfit for continued use, only a preference to
  reduce third-party dependency.
- FIX API directly addresses that preference (removes MetaAPI as a
  dependency) *without* introducing Wine's unresolved reliability problem —
  it is native Linux, no compatibility-layer risk, and is the most
  professional architecture of the three. It is the better target than
  mt5linux for the same underlying goal.
- mt5linux's core value proposition (own the terminal, no cloud
  intermediary) is achieved *equally well or better* by FIX API, without
  inheriting Wine's confirmed reliability problem. There is no dimension
  in the comparison table where mt5linux wins outright against both
  alternatives simultaneously.
- This does not waste the ADR-0011/0012/0013 work: the connector design
  (`BrokerInterface` abstraction, externalized connection config) is
  reusable for a FIX adapter, and the node-topology reasoning in ADR-0013
  remains valid *if* the FIX investigation fails and mt5linux is
  reconsidered.

## System1 / System2 boundary check

All three options are purely within **System 2 (Production Execution)**'s
scope — broker connectivity is an execution-layer concern. None of the three
require SVOS (System 1 / research) to gain broker access, place orders, or
otherwise cross the "research never trades" boundary (CLAUDE.md §1). This
decision does not touch that boundary in any option.

## Execution adapter design (interface-level only — no implementation)

**CORRECTED 2026-07-07 (Phase 5B independent verification) — the original
claim below was wrong. Left visible, struck through, rather than deleted, so
the correction is traceable:**

~~The existing `core/broker_interface.py` `BrokerInterface` ABC (`get_account`,
`get_price`, `send_order`, `modify_order`, `close_order`, `get_positions`)
is already the seam every connectivity technology plugs into —
`execution/metaapi_client.py` (`MetaAPIClient`) implements it today. A future
FIX adapter (e.g. `execution/fix_client.py`, working name) would implement
the same interface, meaning `execution/order_manager.py`,
`execution/trade_manager.py`, and `execution/vantage_demo_executor.py` need
no redesign to eventually support it — the adapter boundary already exists
and is proven (it's how MetaAPI and the mt5linux connector both slot in
today). **No new abstraction needs to be built; the existing one is
sufficient and is not being changed by this ADR.**~~

**Corrected finding**: `BrokerInterface`'s 6 methods are real, and
`MetaAPIClient` does implement them, but as thin wrappers around a much
larger surface (`check_spread`, `get_open_positions(magic=...)`, a
keyword-argument `place_order`, etc.) that `execution/order_manager.py`
actually calls — `order_manager.py` type-hints against `MetaAPIClient`
directly, not `BrokerInterface`, and depends on methods/signatures the ABC
doesn't have. Separately, `execution/trade_manager.py` (the class behind the
*live* ST-A2 demo path) depends on `execution/vantage_demo_executor.py`,
which doesn't implement `BrokerInterface` at all and returns yet a third,
differently-shaped dict contract (`lots` instead of `volume`, `id` instead
of `position_id`, etc.).

**Consequence for this ADR's decision**: none — staying on MetaAPI now and
investigating FIX API next is unaffected, since neither depended on this
claim. **Consequence for future work**: a future FIX adapter cannot be
added by "just implementing `BrokerInterface`" as originally stated — it
would additionally require either (a) rewriting `order_manager.py` and
`trade_manager.py`/`vantage_demo_executor.py` to call through the ABC's
actual method names, or (b) growing the ABC to match what callers actually
use, or (c) a shim/adapter layer translating between the ABC and each
caller's specific surface. This is real, previously-uncounted engineering
cost that lowers FIX API's already-low "Development speed" score in the
weighted framework below further in practice (the 1/5 already given was
the floor of the scale, so the number is unchanged, but the reason is now
more serious than "just write a FIX engine").

This also surfaces a standing architecture debt independent of the
broker-technology decision: **three mutually-incompatible calling
conventions currently coexist in production code** (`MetaAPIClient`'s
extended surface via `order_manager.py`, `VantageDemoExecutor`'s dict
surface via `trade_manager.py`, and the unused `BrokerInterface` ABC).
Tracked as risk #11 in `docs/operations/risk-register.md`.

## Phase 5B addendum — weighted decision framework (2026-07-07)

A second scoring pass was run using an explicit weighted framework (Reliability
40%, Recovery-after-restart 20%, Monitoring 15%, Development speed 15%, Cost
10%) to check whether a different weighting scheme changes the conclusion
above. Scores (1-5):

| Criterion | Weight | Wine/MT5 | MetaAPI | FIX API |
|---|---:|---:|---:|---:|
| Reliability | 40% | 1 — confirmed broken | 4 — proven live | 3 — architecturally sound but wholly unproven here |
| Recovery after restart | 20% | 2 — unproven terminal restart-recovery | 4 — existing reconnect/heartbeat logic proven | 3 — well-understood industry pattern, not yet built |
| Monitoring | 15% | 2 — no terminal-process monitoring built | 4 — `health_check.py`/`demo_health_check.py` already cover it | 2 — nothing built |
| Development speed | 15% | 3 — connector built, blocked on infra | 5 — zero effort, already live | 1 — unbuilt, access unconfirmed |
| Cost | 10% | 3 — modest node cost | 3 — known ongoing MetaAPI fee | 4 — likely no SaaS fee, unconfirmed |
| **Weighted total (/5)** | | **1.85** | **4.05** | **2.65** |

This reinforces rather than overturns the Decision above: under a framework
that weights proven reliability most heavily, MetaAPI is unambiguously the
best available choice *today*. FIX API's low score is a reflection of it
being **unproven for this project**, not evidence it's architecturally
inferior — its Reliability/Recovery scores would need to rise materially
(via the investigation plan's prototype/shadow phases) before it could
overtake MetaAPI on this same framework. Wine/MT5 remains the weakest option
regardless of weighting, consistent with every prior analysis.

## Rejected alternatives

- **Proceed with mt5linux/Node 2 as planned (ADR-0013)**: rejected for now —
  not because the plan was wrong, but because FIX API is a better fit for
  the same underlying motivation (reduce third-party dependency) without
  inheriting Wine's unresolved reliability risk. ADR-0013's plan is not
  discarded — it remains the fallback if FIX API access proves unavailable.
- **Do nothing, close the investigation**: rejected — MetaAPI works today,
  but the owner's original request to move off it was a real signal worth
  honoring with a better-fitting option, not ignoring.

## Rollback / fallback chain

1. **Primary**: stay on MetaAPI while investigating FIX API access.
2. **If FIX API is confirmed available and access is granted**: build a FIX
   adapter implementing `BrokerInterface`, shadow-verify it against MetaAPI
   (same pattern as ADR-0011's shadow-verification gate), cut over only
   after parity holds.
3. **If FIX API is unavailable or impractical** (no access, prohibitive
   account requirements, excessive engineering cost): reconsider mt5linux
   per ADR-0013's plan, starting with its Step 2 Wine-validation gate on a
   fresh node.
4. **At every stage**: MetaAPI remains the live connection until a
   replacement is shadow-verified — no connectivity technology is ever
   switched without a proven parity period first, consistent with
   ADR-0011's original governance pattern.

## Consequences

- No code is written or infrastructure provisioned by this ADR.
- The mt5linux connector code, ADR-0011/0012/0013, and the (not-yet-executed)
  Node 2 migration plan are preserved as a fallback path, not deleted.
- Next concrete action is an investigation (contacting Vantage about FIX API
  access), not an engineering task — see the implementation plan.
