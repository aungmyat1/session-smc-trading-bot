# Capacity Plan — auto-trade-vps (System 2)

Date: 2026-07-06
Status: Assessment — no provisioning performed
Related: `docs/vps/DISK_USAGE_REPORT.md`, `docs/svos/ADR-0011-MT5LINUX-BROKER-BRIDGE.md`,
`docs/svos/ADR-0012-SYSTEM2-HOSTING-STRATEGY.md`, `docs/operations/storage-governance.md`

## Current state (2026-07-06)

| Resource | Value |
|---|---|
| Disk total | 38G (Google Persistent Disk) |
| Disk used | 33G (87%) |
| Disk free | 5.6G (after ADR-0011 Phase 4 cache cleanup; was 4.9G before) |
| Memory | 3.8G total, ~1.2-1.4G available, 1.1G/4G swap in use at idle |
| CPU | 2 vCPU (AMD EPYC 7B12, 1 core / 2 threads) |

Largest consumers today: repo `session-smc-trading-bot` 11-12G (of which
`data/` research datasets alone are 8.8G), `~/.vscode-server` 1.7G, `~/.wine`
1.6G, `~/.mt5` 887M (both currently bare/empty prefixes — see
`docs/svos/ADR-0011-MT5LINUX-BROKER-BRIDGE.md` Phase 4A finding), `~/.local`
750M, `~/.antigravity-ide-server` 593M, `~/.codex` 528M, `~/archives` 513M.

## Projected usage — each future component

| Component | Estimated footprint | Basis |
|---|---:|---|
| **MT5 terminal install** (under the existing `~/.mt5` Wine prefix) | +300-600M | Typical MT5 terminal installer + program files; the prefix itself is already 887M as a bare Wine bootstrap, so this is incremental on top of that |
| **Wine-side Python** (required for the mt5linux RPyC server) | +80-150M | A Windows Python 3.x distribution + minimal site-packages, installed inside the Wine prefix |
| **mt5linux client package** (Linux side) | +5M | Already added to `requirements.lock` (ADR-0011) — `mt5linux==0.2.4` + `rpyc==5.2.3`, negligible |
| **MT5 terminal local market-data cache** | +200M-1.5G, growing | MT5 terminals cache tick/candle history locally per symbol; grows with how many symbols/timeframes are watched and how far back history is pulled. Bounded by terminal settings, not by this project's code |
| **Research datasets** (`data/`) | Currently 8.8G, growing | Already the single largest consumer; growth rate depends on how many additional symbols/timeframes get backfilled via `scripts/fetch_data.py` — no current growth-rate telemetry exists (see Monitoring gap in `docs/operations/production-readiness-infrastructure.md`) |
| **Historical replay artifacts** | Variable, currently small | Replay runs produce report/evidence artifacts under `docs/svos`-adjacent report paths; no dedicated large-dataset replay output identified today |
| **Dashboard growth** | +tens of MB/year | JSON/JSONL state files are either overwritten in place or already durably mirrored to Postgres (Sprint 2.3); low risk relative to the above |

**Total incremental footprint to fully provision mt5linux (terminal + Wine
Python + growing market-data cache): roughly 600M-2.3G**, on top of the 2.5G
the bare prefixes already occupy.

## Safe operating margin

`config/storage_policy.yaml` sets disk warning at 80%, critical at 90%.
Current state (87% used, 5.6G free) is **already past the warning threshold**
before any mt5linux provisioning work begins. Provisioning the low end of the
estimate (600M) would land free space around 5.0G (~87-88% used); the high
end (2.3G) would push free space to roughly 3.3G (~91% used) — **into the
critical band**, on a host that also needs headroom for PostgreSQL growth,
research dataset growth, and normal IDE/agent tooling.

## Risk assessment

- **High**: provisioning mt5linux at the high end of the estimate, on this
  host, with no other capacity action taken first, risks crossing the 90%
  critical disk threshold — on a host actively running live-demo trading,
  where an out-of-space condition could affect the dashboard, PostgreSQL
  writes, or log flushing, not just the new component.
- **Medium**: the research dataset (`data/`, 8.8G) has no observed growth-rate
  telemetry — future backfills (`scripts/fetch_data.py`) could add
  gigabytes without warning under the current setup.
- **Low**: the mt5linux client-side package footprint itself (`requirements.lock`
  addition) is negligible; the risk is entirely in the Wine/MT5 terminal side.

## Recommendation

1. **Reclaim before provisioning.** `~/archives` (513M, checksummed backups)
   and `~/.local` (750M, unaudited user packages) are the two largest
   candidates that don't require touching AI tooling or trading data — see
   `docs/operations/backup-retention.md` for the archives disposition and
   `docs/audit/ai-tooling-storage.md` for the tooling-cache side. Reclaiming
   even 1G here materially changes the safety margin before any MT5
   provisioning.
2. **Do not provision mt5linux on this host until disk is back under the 80%
   warning threshold with the full high-end estimate (2.3G) accounted for.**
   At today's 5.6G free, that means reclaiming at least ~1.5-2G first, or
   choosing the dedicated-node option in `ADR-0012-SYSTEM2-HOSTING-STRATEGY.md`.
3. **Add growth telemetry** for `data/` and the eventual MT5 terminal cache
   before relying on a one-time capacity estimate — `scripts/disk_report.py`
   gives a point-in-time view; it does not yet track growth rate over time
   (see the Monitoring gap noted in the production-readiness checklist).

## Phase 5B update — 2026-07-07: gap-to-target analysis

**Current state after Phase 5A cleanup:** 87% used, 5.0G free (was 90%/4.1G
after the Phase 4/5 Wine provisioning attempts consumed the earlier
reclaimed headroom — see ADR-0011's provisioning appendix; `~/.mt5-terminal`,
a 912M failed-provisioning artifact, was deleted with explicit approval this
phase, recovering most of that loss).

**Target: disk usage below 75%** (Objective 2). Gap: 87% → 75% requires
reclaiming approximately **4.6G** (12 percentage points of a 38G disk).

**This target is not achievable through cleanup alone**, based on evidence
from this and the prior audit:

| Item | Size | Status |
|---|---:|---|
| `data/` (research datasets) | 8.9G | Protected — never delete |
| `session-smc-trading-bot` repo (incl. `data/`, `.venv`) | 12G | Protected |
| `.venv` | 1.3G | Protected — active dependency of both production services |
| `~/.wine` | 1.6G | Protected — original MT5 prefix, preserved per hard constraint even though non-functional (see ADR-0011 Wine investigation) |
| `~/.mt5` | 890M | Protected — same reason |
| `~/archives` | 514M | Protected by retention policy — checksummed backups, only 3 days old, not eligible for deletion under `config/storage_policy.yaml` (90-day minimum) |
| `~/.local` | 778M | Owner declined to clean this phase, despite evidence that its Python packages duplicate `.venv` and aren't used by production (verified: both systemd services' launch scripts use `.venv/bin/python` explicitly) |
| `~/.gemini` | 273M | Owner confirmed still in active use (prior phase) — protected |

Between data that's structurally protected (repo/data/venv/wine/mt5: ~15G,
untouchable) and data that's protected by explicit owner decision this phase
(archives, `.local`, `.gemini`: ~1.6G), there is no remaining safe reclaim
candidate large enough to close a 4.6G gap. The `~/.mt5-terminal` deletion
(900M) executed this phase was the last readily-available safe candidate.

**Actual paths to the 75% target** (none executed — all require a decision
beyond "cleanup"):
1. **Resize the GCE persistent disk** (e.g., 38G → 50G+). This is an
   infrastructure change with a small recurring cost, not a cleanup action —
   requires cloud console/API access and owner budget approval.
2. **Move `data/` (8.9G) to attached/network storage** or object storage,
   loading it on demand rather than keeping it resident. A real architecture
   change to the research data pipeline, out of scope for a cleanup phase.
3. **Revisit the `~/archives` retention window** once the 90-day minimum
   passes (2026-10-02) and the source projects are confirmed retired — see
   `docs/operations/backup-retention.md`. Would reclaim up to ~377M of the
   514M (excluding the still-useful `home-backups`/`rotated-logs` tarballs).
4. **Revisit `~/.local` and `~/.gemini`** if circumstances change — combined
   ~1G, currently protected by explicit owner decision, not a technical
   blocker.

**Recommendation:** treat 75% as a target that requires a real infrastructure
or architecture decision (disk resize being the simplest), not something
Phase 5A-style cleanup can reach. Recommend the owner decide on disk resize
vs. data-offload vs. accepting a higher operating threshold, independent of
the MT5/Wine question.
