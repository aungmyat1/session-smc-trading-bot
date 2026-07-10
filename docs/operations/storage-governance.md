# Storage Governance — auto-trade-vps

Date: 2026-07-06
Status: Active — reporting tooling only, no automated cleanup
Owner: Platform Operations
Related: `config/storage_policy.yaml`, `scripts/disk_report.py`, `scripts/cleanup_report.py`,
`docs/vps/DISK_USAGE_REPORT.md` (2026-07-04 manual baseline this formalizes),
`docs/vps/CLEANUP_PLAN.md` (approval workflow for actually acting on findings),
`docs/audit/capacity-plan.md`, `docs/operations/backup-retention.md`

## Why this exists

`docs/vps/DISK_USAGE_REPORT.md` and `docs/vps/CLEANUP_PLAN.md` (2026-07-04) were
one-off manual audits. Disk usage has kept moving since then (82% → 88% → 86%
across three days, per `docs/vps/OPERATIONS_BASELINE.md`, the ADR-0011 Phase 4
cache cleanup, and this pass) — a manual snapshot goes stale immediately. This
introduces a **repeatable, policy-driven reporting system** so "what's using
disk and is it safe to touch" is a script run, not a fresh manual audit each
time. It does not replace the approval workflow in `CLEANUP_PLAN.md` — it feeds it.

## Components

| Component | Purpose |
|---|---|
| `config/storage_policy.yaml` | Single source of truth for thresholds (disk/memory/swap warning+critical), retention rules (logs, archives, journald), and path classification (safe-to-clean / requires-confirmation / never-clean) |
| `scripts/disk_report.py` | Read-only: total/free disk vs. thresholds, largest directories, project log growth, PostgreSQL size (best-effort), archives footprint, MT5/Wine footprint, regenerable-cache footprint |
| `scripts/cleanup_report.py` | Read-only: classifies `storage_policy.yaml`'s cache-cleanup paths into safe / requires-confirmation / never-clean tiers with current sizes and a reclaimable-space estimate |

**Neither script deletes, moves, or modifies anything.** They exist to make
`CLEANUP_PLAN.md`-style approval requests fast to produce with current
numbers, not to auto-execute cleanup. Actual cleanup remains a manually-run,
explicitly-approved action, same as the existing `CLEANUP_PLAN.md` workflow.

## Path classification (from `storage_policy.yaml`)

- **Safe** — regenerable dev-tool caches with no dependency on live process state
  (`~/.cache/pip-tools`, `~/.cache/ms-playwright-go`, `~/.cache/cloud-code`,
  `~/.cache/node-gyp`, `~/.cache/pip-audit`, `~/.cache/pip`, `~/.npm/_cacache`).
  These were the exact paths cleaned in the ADR-0011 Phase 4 pass (~700MB reclaimed,
  zero service impact, verified via health check).
- **Requires confirmation** — regenerable in principle but tied to active tool
  state or unverified dependency: `~/.codex`, `~/.gemini`, `~/.continue`,
  `~/.claude`, `~/.antigravity-ide-server` (see `docs/audit/ai-tooling-storage.md`),
  and `~/.local` (user-installed Python/Node tooling, not audited per-package here).
- **Never clean** — the repo itself, `data/`, `logs/`, `~/.wine`, `~/.mt5`,
  `~/archives` (see `docs/operations/backup-retention.md`), `~/db_backups`,
  PostgreSQL's data directory.

## Thresholds

| Resource | Warning | Critical | Current (2026-07-06) |
|---|---|---|---|
| Disk | 80% | 90% | 86% (5.6G free of 38G) — **WARNING** |
| Memory | 80% | 92% | ~68% used, 1.2-1.4G available — OK |
| Swap | 40% used | — | ~28% (1.1G/4G) — OK, but not zero at idle |

Disk is currently in the WARNING band. This is the same conclusion
`docs/vps/RESOURCE_OPTIMIZATION.md` reached on 2026-07-04 ("treat 85% as an
internal alert threshold, not 90%+") — `storage_policy.yaml` codifies that
threshold instead of leaving it as prose.

## Usage

```
python3 scripts/disk_report.py            # human-readable
python3 scripts/disk_report.py --json      # machine-readable, for future alerting hookup
python3 scripts/cleanup_report.py          # cache classification + reclaim estimate
```

## Explicitly out of scope

- No cron/systemd timer wiring these scripts up to auto-run — that's future
  work once the output format is validated in practice (see
  `docs/operations/production-readiness-infrastructure.md`'s Monitoring row).
- No automatic cleanup execution, ever, from either script.
- No changes to journald, logrotate, or PostgreSQL configuration — those remain
  proposals in `docs/vps/LOG_RETENTION_POLICY.md` / `docs/vps/RESOURCE_OPTIMIZATION.md`
  pending explicit owner approval.
