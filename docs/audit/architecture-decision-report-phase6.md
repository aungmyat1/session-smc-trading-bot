# Architecture Decision Report — Phase 6: MT5 Hosting Architecture

Date: 2026-07-07
Status: Analysis supporting `docs/svos/ADR-0013-MT5-EXECUTION-ARCHITECTURE.md`
Related: `docs/svos/ADR-0011-MT5LINUX-BROKER-BRIDGE.md`,
`docs/svos/ADR-0012-SYSTEM2-HOSTING-STRATEGY.md`,
`docs/audit/capacity-plan.md`, `docs/audit/wine-investigation-report.md`

**Evidence note:** the disk (90%→87%), backup-integrity, and Wine-investigation
(8/10 hypotheses eliminated) figures below are independently verified in this
session's own prior work. The test-count figures cited in the Phase 6 prompt
(284 governance tests, 41/41 risk-portfolio, 116/116 dashboard) are taken as
given context from the prompt, not independently re-run in this pass — flagged
here per the "distinguish verified facts from assumptions" rule, since this
report doesn't re-execute those suites.

## Current problem

Two independent blockers prevent MT5 execution from being safely built on
`auto-trade-vps` as-is:
1. **Capacity**: disk cannot reach a comfortable operating margin via cleanup
   alone — ~15G of the 38G disk is structurally required (repo, datasets,
   `.venv`, Wine/MT5 artifacts, operational data).
2. **Reliability**: Wine itself does not reliably execute Windows binaries on
   this host. Root cause unconfirmed after a structured investigation.

Both point the same direction: MT5 execution should not share a failure
domain with the trading system's dashboard, database, and strategy engine.
The open question is not *whether* to separate them, but *how much*
architecture to build around that separation.

## Options evaluated

### Option A — Keep current VPS, resize/improve

Single node running strategy engine, dashboard, database, monitoring, and
MT5 execution together. Requires disk resize, a resolved Wine root cause,
MT5 stability proof, added monitoring, and a documented rollback before it
could be approved at all.

**This option does not resolve either blocker on its own** — a disk resize
addresses capacity, but the Wine investigation found no confirmed fix, and
"resize the disk and hope Wine starts working" is not evidence-based.
Approving Option A today would mean approving MT5 provisioning against an
unresolved reliability blocker, which the Phase 5 gates already found
disqualifying.

### Option B — Dedicated MT5 execution node

Two nodes: the existing trading-system VPS (strategy engine, dashboard, DB,
analytics, monitoring) and a new node dedicated to Wine + MT5 terminal +
the execution bridge. `execution/mt5linux_connector.py` (ADR-0011) already
externalizes `MT5LINUX_HOST`/`MT5LINUX_PORT`, so the connector code needs no
rework to point at a remote node — this is a topology change, not a rewrite.

Directly resolves both blockers: a fresh node sidesteps whatever this
specific host's Wine incompatibility is, and moving Wine/MT5 off
`auto-trade-vps` removes the single largest capacity risk from the capacity
plan's own findings.

### Option C — Hybrid architecture (execution gateway with a defined interface)

Same physical two-node split as B, but the boundary between "System2 Core"
(strategy/risk/portfolio/dashboard/DB) and the "MT5 Gateway" (terminal,
broker adapter, order execution, market data bridge) is a designed,
documented interface (API or message queue) rather than the trading system
simply pointing its existing connector at a remote RPyC endpoint. Framed
explicitly around supporting multiple future execution providers/brokers.

## Scoring (1-5, 5 = best)

| Criterion | Option A | Option B | Option C |
|---|---:|---:|---:|
| Reliability | 2 | 4 | 4 |
| Security | 2 | 3 | 4 |
| Operational simplicity | 5 | 3 | 2 |
| Scalability | 2 | 4 | 5 |
| Recovery capability | 2 | 4 | 4 |
| Cost | 5 | 3 | 3 |
| Maintenance burden | 3 | 3 | 2 |
| Trading safety | 2 | 4 | 4 |
| Future broker expansion | 2 | 3 | 5 |
| **Total (/45)** | **25** | **31** | **33** |

Reasoning for the closer calls:
- **Security**: B scores lower than C because a generic second VM with a
  direct connector link still needs secrets/comms secured, but doesn't force
  a narrow, purpose-built boundary the way an explicit gateway interface does.
- **Operational simplicity / Maintenance burden**: C scores lowest here —
  a designed interface (API/message queue, its own monitoring, its own
  contract to maintain) is real, ongoing engineering cost that B doesn't
  carry. This is the honest cost of C's benefits, not a rounding error.
- **Future broker expansion**: C scores highest by design intent — but this
  criterion's weight should be judged against actual near-term need (see
  Reasoning below), not just architectural elegance.

## Reasoning — why the recommendation is not a simple "C wins on points"

C scores highest (33 vs. 31 for B), but the margin is modest, and it's
concentrated in one criterion (future broker expansion) that reflects a
capability the project does not have a concrete near-term need for today:
**there is exactly one broker (Vantage) and one execution path in scope**
(replacing MetaAPI with mt5linux for that same broker, per ADR-0011). This
repo's own engineering principle — stated in this project's guidance and
consistently applied throughout the ADR-0011/0012 work — is to not build
generality for hypothetical future requirements ("three similar lines is
better than a premature abstraction"). Building a full message-queue-based,
multi-provider execution gateway today, before a second broker or execution
provider is actually on the roadmap, risks exactly that kind of premature
abstraction: real design/build/maintenance cost paid now for a capability
not yet needed.

**Recommendation: adopt Option C's separation principle, implemented via
Option B's simpler topology first.** Concretely:
- Stand up the two-node split now (Option B's physical architecture) —
  this alone resolves both the capacity and Wine-reliability blockers.
- Design the connector boundary so it does not foreclose C — the existing
  `BrokerInterface` abstraction (`execution/metaapi_client.py`) and
  `mt5linux_connector.py`'s externalized host/port config are already close
  to what a future formalized gateway interface would need. Keep that
  abstraction clean rather than hard-coding node-specific assumptions.
- Defer the full message-queue/multi-provider gateway design (Option C's
  distinguishing feature) until a second broker or execution provider is
  actually planned — at which point the two-node split already in place
  makes that a natural evolution, not a rebuild.

This is a deliberately more conservative recommendation than "build C now" —
it gets the safety benefit immediately (both blockers resolved) without
committing to generality the project doesn't yet need, consistent with this
repo's own stated engineering values.
