# VPS Cleanup Plan

Date: 2026-07-04
Status: Review
Approval state: **Not approved; no cleanup performed**

## Guardrails

No deletion, package removal, service stop/restart, configuration change, or archive move is authorized by this document. Nothing under `/home`, `/opt`, `/etc`, or `/var/lib` may be removed without explicit approval. Preserve Git worktrees, secrets, databases, datasets, strategy packages, Compose files, trading/audit logs, and broker/MT5 state.

## Safe Immediately — executable only after approval

These are rebuildable or OS-generated, but still await owner approval because several reside in protected paths.

| Candidate | Approx. reclaim | Proposed command class / validation |
|---|---:|---|
| Apt download cache | up to 166 MiB | `apt-get clean`; verify dpkg and services afterward |
| Pip HTTP cache | 35 MiB | `python3 -m pip cache purge`; no environment packages removed |
| Primary repo Python bytecode | up to 177 MiB | Delete only `__pycache__`/`.pyc`; run focused tests and dashboard import check |
| Mypy/pytest/Ruff caches | ~27 MiB | Delete cache directories only; rebuildable |
| `/var/crash` crash reports | 125 MiB | Record filenames first; delete only after confirming no open incident needs them |
| `/tmp` stale ordinary files | negligible | Age/owner/open-file check; skip systemd private directories |

Do **not** clean npm now: active MCP processes execute from npm `_npx` directories.

## Needs Confirmation

| Candidate | Why confirmation is required |
|---|---|
| Old VS Code server generation (`Stable-7e...`) | Likely inactive and potentially hundreds of MiB, but verify no processes and retain current `Stable-4fe...` |
| IDE cached VSIX/extensions and Antigravity server | Rebuildable but owner workflow impact |
| Codex `logs_2.sqlite` (382 MiB) and caches | Active agent/audit history; may contain valuable state |
| npm cache (241 MiB) | Active `_npx` workloads; clean only after sessions end |
| Rotated syslog/auth/btmp | Security and trading audit retention decision required |
| Avahi, multipath/open-iscsi, Wine packages | Service/package dependency decision, not disk-only cleanup |
| Unknown small home projects | Ownership/status not established |
| Disabled custom systemd units | Preserve until linked repos/config/secrets are formally retired |

## Archive First

Create checksummed, access-controlled archives outside the root disk or on approved object storage; test listing/restoration; then request a second deletion approval.

- `/opt/forex-validate` (420 MiB) and its venv.
- `/opt/smc-test` (174 MiB) including backtest results/logs.
- `/opt/benchmark-bot` (109 MiB), preserving Compose/config and its disabled unit.
- `simple-smc-ag-trading-bot` (745 MiB Git repo), preserving `.git`, `.env` separately and service definition.
- `forex-ai-trading-platform` and other unknown/legacy small projects.
- `/home/aungp/backups` only after establishing retention, remote copy, checksum, and restore test.

## Never Delete

- Primary `session-smc-trading-bot` Git repository or its current `.venv` while the dashboard depends on it.
- Any market/trading dataset, DuckDB/SQLite/PostgreSQL data, database backup, journal, evidence, report, strategy artifact/package, or audit log without an approved retention disposition.
- `/home/aungp/.mt5`, `.wine`, `/opt/wine-staging` until broker runtime ownership is explicitly resolved.
- Secrets/configuration (`.env`, `/etc/session-smc-trading-bot`, `/etc/agent-bus`), SSH configuration/keys, systemd definitions, Docker Compose files.
- PostgreSQL data, `/var/lib`, live dashboard assets, or dirty/uncommitted Git content.

## Proposed execution batches

1. **Batch A: rebuildable caches** — inventory filenames/sizes, approve exact list, clean apt/pip/test/Python caches, measure disk, verify dashboard/PostgreSQL/systemd.
2. **Batch B: developer tooling** — end IDE/agent sessions, verify PIDs, remove only confirmed obsolete server/cache generations, reconnect and validate tools.
3. **Batch C: archive legacy projects** — owner classifies each project; archive/checksum/restore-test; separate approval before source removal.
4. **Batch D: retention policy** — define logs, crashes, backups, and datasets by regulatory/research requirements; automate rotation only after approval.

Each destructive command must be timestamped in `CLEANUP_REPORT.md` with target, bytes before/after, return code, approver, and verification result.

## Approval request

No Phase 7 work should begin until the owner approves a specific batch and exact targets. Broad approval such as “clean everything safe” should still be translated into an explicit path list before execution.
