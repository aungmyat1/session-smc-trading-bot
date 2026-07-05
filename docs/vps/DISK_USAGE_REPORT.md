# Disk Usage Report

Date: 2026-07-04
Status: Review
Snapshot: 2026-07-04T11:20Z

## Summary

Root is **82% used** (31 GiB of 38 GiB). Measured file usage is about 29 GiB: `/home` 19 GiB, `/usr` 5.0 GiB, `/opt` 2.4 GiB, and `/var` 1.3 GiB. The immediate capacity risk is real, but most large content is trading data or active tooling and cannot be removed blindly.

## Largest directories

| Path | Size | Assessment |
|---|---:|---|
| `/home/aungp/session-smc-trading-bot` | 9.7 GiB | Active production-facing repo; never delete |
| `.../data` | 7.5 GiB | Trading/research datasets; preserve unless owner approves archival policy |
| `.../.venv` | 1.4 GiB | Used by dashboard service; preserve |
| `/home/aungp/.vscode-server` | 2.8 GiB | Development tooling; old generation may be removable after confirmation |
| `/opt/wine-staging` | 1.7 GiB | Installed Wine runtime; dependency confirmation needed |
| `/home/aungp/.wine` | 1.6 GiB | MT5/Wine state; never delete without broker-runtime migration |
| `/home/aungp/.mt5` | 890 MiB | Trading terminal state; never delete |
| `/home/aungp/.local` | 778 MiB | User packages/tools; dependency review required |
| `simple-smc-ag-trading-bot` | 745 MiB | Git repo referenced by disabled systemd unit |
| `/home/aungp/.cache` | 605 MiB | Mixed cache; portions safe after process checks |
| `/home/aungp/.codex` | 553 MiB | Active agent state/logs; confirmation required |
| `/opt/forex-validate` | 420 MiB | Validation project and 416 MiB venv; archive-first candidate |

## Largest files

| File | Size | Decision |
|---|---:|---|
| XAUUSD normalized ticks Parquet | 2.43 GB | Never delete; trading data |
| GBPUSD normalized ticks Parquet | 837 MB | Never delete; trading data |
| EURUSD normalized ticks Parquet | 802 MB | Never delete; trading data |
| `/home/aungp/.codex/logs_2.sqlite` | 382 MB | Needs confirmation; active tool state |
| Google Cloud CLI seed snap | 358 MB | Package-managed; do not delete manually |
| Feature DuckDB | 283 MB | Never delete; research database |
| Current Codex extension binary | 286 MB | Active tooling |
| Primary Polars runtime | 213 MB | Active venv |
| Processed EURUSD tick Parquet | 209 MB | Preserve; possible duplicate representation only after lineage verification |

## Logs, caches, temporary files

- `/var/log`: 166 MiB. Largest: `syslog.1` 87 MiB, journal 27 MiB, `syslog.3.gz` 13 MiB, current syslog 11 MiB, `btmp.1` 9.6 MiB. These are audit/security records; retention changes need approval.
- Project logs: 17 MiB; `adaptive_shadow.log` 6.1 MiB and `strategy_demo.log` 1.5 MiB. Preserve for trading audit.
- `/var/crash`: 125 MiB. Crash artifacts are the clearest safe-immediate candidate, but `/var` deletion still requires explicit approval under the prompt.
- Apt cache: 166 MiB. Safe to clean after approval; no package removal needed.
- npm cache/tree: 241 MiB; pip cache: 35 MiB; test caches: `.mypy_cache` 27 MiB, pytest 172 KiB, Ruff 244 KiB; repo `__pycache__` total 177 MiB.
- `/tmp` 100 KiB and `/var/tmp` 24 KiB: negligible.
- No material Downloads directory was found.

## Archives, backups, and duplicate repositories

- `/home/aungp/backups`: 112 MiB, including `auto-trade-system-2026-06-12.tar.gz` 69 MiB and `trading-loki-backup-20260618.tar.gz` 48 MiB.
- `/home/aungp/db_backups`: 62 MiB; database backup—never delete without verified retention/recovery policy.
- `/opt/smc-test`: 174 MiB including 101 MiB logs and multiple backtest ZIPs. Archive first.
- Primary repo contains an `archive/` subtree (7.7 MiB) and `session-smc-trading-bot-updated` (36 KiB); too small to matter and must not be assumed disposable.
- Two Git repositories were found: the primary repo and `simple-smc-ag-trading-bot`. IDE history directories also contain Git metadata but are tooling history, not deployable clones.

## Docker and environments

Docker has no daemon/socket and its storage directories are empty (4 KiB each), so Docker cleanup would recover effectively zero. Known venvs are tied to active or historical projects; none is classified safe without project disposition. No Conda environments were found.

## Estimated reclaim bands (no action taken)

| Band | Approximate potential | Conditions |
|---|---:|---|
| Safe-immediate after approval | 0.3–0.5 GiB | apt, pip, Python/test caches and crash dumps; avoid active npm `_npx` |
| Needs confirmation | 0.5–1.5 GiB | Codex/IDE caches and an old VS Code server generation |
| Archive first | 0.7–2.5 GiB | inactive projects/venvs, Wine only if proven unused |
| Protected | 9+ GiB | primary repo, datasets, DBs, logs/evidence, MT5/Wine runtime state |
