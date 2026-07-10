# ADR-0012: System 2 Hosting Strategy — Single VPS vs. Dedicated MT5 Execution Node

Date: 2026-07-06
Status: Proposed — recommendation only, no provisioning performed.
**Refined by `ADR-0013-MT5-EXECUTION-ARCHITECTURE.md` (2026-07-07)**, which
evaluates a third option (hybrid gateway architecture) and makes the final
hosting-architecture decision. This ADR's content and evidence updates below
remain the historical record of how that decision was reached — not rewritten.
Version: 1.0
Owner: Lead Architect
Authority: Level 5 — Decision
Related: `ADR-0011-MT5LINUX-BROKER-BRIDGE.md`, `docs/audit/capacity-plan.md`,
`docs/operations/storage-governance.md`, `docs/vps/DEPLOYMENT_TOPOLOGY.md`

**Placement note:** the requesting task specified `docs/adr/ADR-00XX-*.md`.
Per `docs/00_Project/DOC_AUTHORITY.md` §5 ("Decision authority:
`docs/svos/ADR-*.md`"), this ADR is filed under the existing `docs/svos/`
sequence instead, continuing from ADR-0011, to avoid a second competing ADR
location.

## Context

ADR-0011 committed to replacing MetaAPI with mt5linux for Vantage
connectivity. Phase 4 infrastructure validation (see ADR-0011's own
operational-validation appendix) found `auto-trade-vps` has no working MT5
terminal installed — only bare Wine prefixes. `docs/audit/capacity-plan.md`
shows provisioning a real terminal + Wine Python + growing market-data cache
on this host risks crossing the 90% critical disk threshold, on a box that is
**also** the live-demo trading host (`smc-demo-runner.service`), the
dashboard host (`live-dashboard.service`), and the PostgreSQL host, all on a
single 2 vCPU / 3.8G RAM / 38G disk VM.

This ADR evaluates whether mt5linux should be provisioned on this same host
or on a separate, dedicated execution node.

## Option A — Single VPS (status quo host)

Everything stays on `auto-trade-vps`: dashboard, PostgreSQL, the demo runner,
and (if provisioned) Wine + MT5 terminal + mt5linux RPyC server.

| Dimension | Assessment |
|---|---|
| Fault isolation | **Weak** — a Wine/MT5 terminal crash, OOM, or disk-full event shares fate with the dashboard and PostgreSQL on the same 3.8G-RAM host |
| Maintenance | Simple — one host, one deploy target, no cross-host networking |
| Resource contention | **Real** — 2 vCPU already serves dashboard + demo runner + PostgreSQL + IDE/agent tooling; adding a Wine/MT5 terminal (a full Windows-emulation process) competes directly |
| Security | Single blast radius — a Wine/terminal compromise or misconfiguration has direct access to the same host as trading credentials and the dashboard |
| Upgrade path | Awkward — Wine/MT5 terminal updates, restarts, or crashes directly risk the demo runner's uptime |
| Future scaling | Poor — this host is already capacity-constrained (see capacity plan); adding more symbols/strategies competes with the same fixed 38G/3.8G envelope |
| Cost | **Zero incremental** — no new VM |
| Operational complexity | Lowest short-term (nothing new to provision), highest long-term (every future MT5-related incident is entangled with trading/dashboard/DB incidents) |

## Option B — Dedicated MT5 Execution Node

A second, small VM hosts only Wine + MT5 terminal + mt5linux RPyC server.
`auto-trade-vps` connects to it as a remote RPyC endpoint
(`MT5LINUX_HOST`/`MT5LINUX_PORT` already externalized as env vars in
ADR-0011's connector design — no code change needed to point at a different host).

| Dimension | Assessment |
|---|---|
| Fault isolation | **Strong** — a terminal crash or Wine instability cannot take down the dashboard, PostgreSQL, or the demo runner's process; only the broker connection degrades (already handled by the existing reconnect/heartbeat logic) |
| Maintenance | One more host to patch/monitor, but each host's failure domain is independently reasoned about |
| Resource contention | **None** — Wine/MT5's CPU and memory footprint is isolated from trading logic and the dashboard |
| Security | Smaller blast radius per host; the execution node only needs outbound broker connectivity + an internal (Tailscale) RPyC link, no public dashboard exposure |
| Upgrade path | Clean — terminal restarts/updates on the execution node don't risk the demo runner's process uptime |
| Future scaling | Better — a second execution node could serve additional strategies/accounts without re-contesting `auto-trade-vps`'s fixed envelope |
| Cost | **One additional small VM** (a Wine/MT5 terminal doesn't need much CPU/RAM — a shared-core, 1-2G RAM instance is plausible) |
| Operational complexity | Higher short-term (new host to provision, network path to secure), lower long-term (cleaner failure domains) |

## Decision

**Recommend Option B — dedicated MT5 execution node** — conditional on cost
being acceptable to the owner, since this ADR does not have infrastructure
budget authority.

Rationale: `docs/audit/capacity-plan.md` already shows `auto-trade-vps` is
resource-constrained before mt5linux is even provisioned (86-88% disk, disk
threshold already crossed). Provisioning a Windows-emulation stack (Wine +
MT5 terminal), which is qualitatively different from the lightweight Python
processes the host currently runs, onto an already-constrained, single
point-of-failure production host is the higher-risk path for a system that
CLAUDE.md §0 explicitly prioritizes safety and inaction over convenience. The
connector design from ADR-0011 already externalizes the RPyC host/port,
so this is a configuration change, not a rework, whenever the owner approves it.

**If Option B's cost is not acceptable**, Option A remains viable only after
the capacity-plan's reclaim recommendations are executed and disk is brought
back under the 80% warning threshold with the full high-end mt5linux estimate
(2.3G) accounted for — provisioning should not proceed on this host at
today's 86-88% disk usage regardless of which option is chosen.

## Rejected alternatives

- **Provision on `auto-trade-vps` immediately, accept the risk**: rejected —
  the capacity plan shows this could cross the critical disk threshold on
  the live-demo trading host, violating this repo's "safety and inaction
  always wins ties" principle (CLAUDE.md §6 equivalent for the sibling
  controller doc; this repo's own §0 governance mode is equally conservative).
- **Do nothing, keep MetaAPI**: out of scope for this ADR — ADR-0011 already
  made that decision; this ADR is about *where* mt5linux runs, not *whether*.

## Consequences

- No provisioning action is taken by this ADR. It is a recommendation for the
  owner to act on before ADR-0011's Phase 4 provisioning step proceeds.
- If Option B is chosen, ADR-0011's rollout plan gains a new dependency (a
  second VM) before the shadow-verification phase can run against a real
  terminal.

## Phase 5D evidence update — 2026-07-07

A real provisioning attempt was made on Option A (`auto-trade-vps`) since
this ADR was written, per owner decision to proceed despite the flagged
risk. Two independent findings now strengthen the Option B recommendation:

1. **Wine itself is non-functional on this host** — reproducible across 2
   Wine versions, 2 fresh prefixes, varying memory conditions (see
   `docs/audit/wine-investigation-report.md`). Root cause not confirmed
   despite a structured, hypothesis-driven investigation (10 hypotheses
   evaluated; the strongest surviving candidate is a kernel/Wine loader
   incompatibility specific to this host's kernel version). A dedicated
   node, provisioned from a clean base image, would not necessarily inherit
   whatever is causing this — it is a materially lower-risk starting point
   than continuing to debug this specific host.
2. **The disk-capacity problem is now confirmed, not projected** — the
   provisioning attempt itself pushed disk from 86-87% to 90% (critical)
   before being rolled back to 87% via one approved cleanup
   (`docs/audit/capacity-plan.md` Phase 5B update). Separately, the 75%
   target set for this phase is **not achievable through cleanup alone** —
   the gap analysis shows ~15G of the 38G disk is structurally protected
   (repo, research data, `.venv`, Wine/MT5 prefixes), leaving no realistic
   path to 75% without a disk resize or moving research data off-host.

**This does not change the ADR's Decision** (Option B was already the
primary recommendation) — it removes the main practical objection to acting
on it. The original conditional ("if Option B's cost is not acceptable,
Option A remains viable after reclaim") is now weaker: Option A requires
solving both an unresolved Wine incompatibility *and* a disk-capacity
problem that cleanup cannot close, while Option B's clean-base-image
approach plausibly resolves the first at zero additional diagnostic cost
and sidesteps the second by not competing for this host's disk at all.
- `docs/vps/DEPLOYMENT_TOPOLOGY.md` will need an update once a hosting
  decision is executed — not done here, since no provisioning has happened.
