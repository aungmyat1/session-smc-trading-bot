# Project Audit

Date: 2026-07-04
Status: Review

## Method

Project candidates were discovered under `/home`, `/opt`, `/srv`, and `/root` using Git metadata, Python/Node manifests, Compose files, top-level directory inspection, process working directories, systemd definitions, cron, and script references. “Safe to delete” is deliberately conservative: no Git repo, database, trading data, configuration, or unknown project is approved for deletion.

## Classification

| Project/location | Size / modified | Class | Running / references | Archive? | Delete? |
|---|---|---|---|---|---|
| `/home/aungp/session-smc-trading-bot` | 9.7 GiB / Jul 4 | **Production** (demo/shadow, not approved live) | Dashboard running; demo runner restart-looping; two enabled systemd units; developer processes; many scripts | No | **Never** |
| `/home/aungp/simple-smc-ag-trading-bot` | 745 MiB / Jun 19 | Archived/legacy | Not running; disabled `smc-bot.service` references it | Yes, after unit/secret backup | No without explicit approval |
| `/opt/forex-bot` | 260 KiB / Jun 18 | Archived/legacy demo | Not running; disabled `forex-bot.service` references it and its `.env` | Yes, after unit/config backup | No |
| `/opt/benchmark-bot` | 109 MiB / Jun 4 | Experimental | Not running; disabled Compose systemd unit; Docker inactive | Yes | No until owner confirms retirement |
| `/opt/smc-test` | 174 MiB / Jun 11 | Experimental | Not running; test data/logs/backtests; no enabled startup reference found | Yes | No until evidence retention checked |
| `/opt/forex-validate` | 420 MiB / Jun 18 | Experimental/validation | Not running; no startup reference found; 416 MiB venv | Yes | Venv only after archive/rebuild proof |
| `/home/aungp/forex-ai-trading-platform` | 644 KiB / Jun 19 | Experimental | Not running; no systemd/cron reference found | Yes | Needs confirmation |
| `/home/aungp/ag-simple-smc-bot` | 48 KiB / Jun 15 | Unknown/legacy | Not running; no startup reference found | Yes | Needs confirmation |
| `/home/aungp/smc-bot` | 64 KiB / Jun 12 | Unknown/legacy | Not running; no startup reference found | Yes | Needs confirmation |
| `/home/aungp/gcp-infra` | 100 KiB / Jun 26 | Active development/infrastructure | Not running; infrastructure material may describe this VPS | Only with backup | Never delete casually |
| `/home/aungp/vm-backup-restore` | 208 KiB / Jun 4 | Operations | Not running; recovery archive present | No | Never until recovery plan supersedes it |
| `/home/aungp/vps_cleanup_audit` | 196 KiB / Jul 2 | Active audit | Not running; recent audit evidence | Archive after reconciliation | Needs confirmation |
| `/home/aungp/session-smc-trading-bot-updated` | 36 KiB / Jun 25 | Unknown | Not running; no startup reference found | Yes | Needs confirmation |
| `/home/aungp/backups` | 112 MiB / Jun 18 | Archive | Backup payloads, not runtime | Already archive | Retention approval required |
| `/home/aungp/db_backups` | 62 MiB / Jun 9 | Archive/DB recovery | Database backups | Already archive | **Never without retention approval** |
| `/home/aungp/vectorbt_data` and `/home/aungp/data` | 7.2 MiB combined | Research data | No process/startup reference found | Yes after lineage check | No |
| `/home/aungp/.wine`, `.mt5`, `/opt/wine-staging` | 4.2 GiB combined | Production-capable runtime state | No process at snapshot, but broker/MT5 relevance is high | No until architecture decision | **Never delete without explicit owner approval** |

## Important qualifications

- The primary repository is a dirty, active Git worktree with many modified and untracked files. It must not be archived, reset, cleaned, or deduplicated.
- No user cron references were found. Custom startup ownership is systemd-centric.
- Docker currently references no running resources because the daemon is inactive; Compose files on disk still count as project configuration and are protected.
- Last-modified time is weak evidence. “Unknown” means more owner context is required, not that deletion is safe.
