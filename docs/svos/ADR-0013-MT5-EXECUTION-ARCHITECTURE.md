# ADR-0013: MT5 Execution Architecture — Phased Two-Node Split

Date: 2026-07-07
Status: Proposed — recommendation only, no provisioning performed.
**Deprioritized by `ADR-0014-BROKER-CONNECTIVITY-TECHNOLOGY.md` (2026-07-07)**,
which reopened the higher-level question of *which* broker connectivity
technology to use (Wine/MT5 vs. MetaAPI vs. FIX API) and recommends
investigating Vantage's native FIX API before continuing this mt5linux path.
This ADR's node-topology plan remains the fallback if that investigation
concludes FIX API is unavailable — not discarded, not currently active.
Version: 1.0
Owner: Lead Architect
Authority: Level 5 — Decision
Related: `ADR-0011-MT5LINUX-BROKER-BRIDGE.md`, `ADR-0012-SYSTEM2-HOSTING-STRATEGY.md`
(refined by this ADR — ADR-0012's own historical content and evidence updates
remain intact; this ADR resolves the specific hosting-architecture question
with a three-option comparison ADR-0012 didn't originally consider),
`docs/audit/architecture-decision-report-phase6.md` (full scoring detail),
`docs/audit/capacity-plan.md`, `docs/audit/wine-investigation-report.md`

## Context

ADR-0012 recommended a dedicated MT5 execution node (its "Option B") over
keeping everything on `auto-trade-vps`, conditional on cost being acceptable.
A provisioning attempt was subsequently made on `auto-trade-vps` anyway (owner
decision, documented in ADR-0011/0012's evidence appendices), which produced
two confirmed findings: Wine cannot execute Windows binaries on this host
(root cause unconfirmed after a 10-hypothesis investigation), and the disk
capacity problem cannot be resolved by cleanup alone (~15G is structurally
required). Both blockers independently point toward separating MT5 execution
from the trading system's current host.

This ADR evaluates three options (single-VPS, dedicated node, hybrid gateway
architecture) with explicit scoring, superseding ADR-0012's simpler two-option
framing now that a third, more architecturally deliberate option is on the
table.

## Decision

**Stand up a dedicated MT5 execution node (two physical nodes), designed so
that a future formalized execution-gateway interface (multiple
brokers/providers) is a natural evolution rather than a rebuild — but do not
build that full gateway interface now.**

This adopts the separation principle behind the "hybrid" option (isolating
execution from strategy/dashboard/database) using the simpler two-node
topology, deferring the heavier message-queue/multi-provider interface design
until there is an actual second broker or execution provider on the roadmap.
See `docs/audit/architecture-decision-report-phase6.md` for the full 9-criterion
scoring table (Option A: 25/45, Option B: 31/45, Option C: 33/45) and the
reasoning for recommending B's topology over committing to C's full interface
today.

## Node responsibilities

**Node 1 — Trading System (existing `auto-trade-vps`):**
- Strategy engine (`scripts/run_st_a2_demo.py` / `run_strategy_demo.py`)
- Live dashboard (`dashboard/status_server.py`, `live-dashboard.service`)
- PostgreSQL (`postgresql@16-main.service`)
- Research/analytics, monitoring
- Unchanged by this ADR — no migration of these components

**Node 2 — MT5 Execution Node (new):**
- Wine + MT5 terminal (the component that does not work on Node 1 today)
- mt5linux RPyC server
- No dashboard, no database, no strategy logic — purely a broker-connectivity
  endpoint reachable over Tailscale

## Interface (boundary between the two nodes)

`execution/mt5linux_connector.py`'s `MT5LINUX_HOST`/`MT5LINUX_PORT` env vars
(already externalized per ADR-0011) become the actual boundary — Node 1's
connector talks to Node 2's RPyC server over the existing Tailscale mesh
(already used by `auto-trade-vps`, per `docs/vps/VPS_INVENTORY.md`). No new
network technology is introduced. The existing `BrokerInterface` abstraction
(`execution/metaapi_client.py`) is preserved as the seam a future
multi-provider gateway would extend — not rebuilt, not bypassed.

## Rejected alternatives

- **Option A (resize current VPS, keep MT5 on it)**: rejected — does not
  resolve the confirmed Wine reliability blocker; a disk resize alone cannot
  fix an unconfirmed root-cause software incompatibility. Approving this
  would mean provisioning MT5 against a blocker the Wine investigation
  explicitly left unresolved.
- **Option C in full (message-queue-based multi-provider gateway) now**:
  rejected for the *current* phase — scores highest on paper (33/45) but the
  margin over Option B is concentrated in "future broker expansion," a
  capability with no concrete near-term requirement (exactly one broker,
  Vantage, is in scope). Building the full interface now would be the kind
  of premature abstraction this project's own engineering principles
  caution against. Revisit when a second broker/execution provider is
  actually planned — Node 2's existence by then makes this an addition, not
  a migration.

## Rollback

If Node 2 proves unstable or the connection to it is unreliable: point
`MT5LINUX_HOST`/`MT5LINUX_PORT` back to `localhost`/unset, which reverts to
attempting local Wine on Node 1 (known broken) — meaning the true rollback
for MT5 specifically is the existing ADR-0011 rollback: keep MetaAPI as the
live connection on Node 1, and treat Node 2 as inert/decommissionable without
affecting Node 1's trading, dashboard, or database services at all, since
none of those move.

## Consequences

- Requires provisioning one new VM (Node 2) — cost and access decision for
  the owner, not executed by this ADR.
- `docs/vps/DEPLOYMENT_TOPOLOGY.md` needs an update once Node 2 exists —
  not done here, since no provisioning has happened.
- The full multi-provider gateway interface (Option C) remains a documented,
  intentional deferral, not a rejected idea — tracked as future work should
  a second broker be planned.
