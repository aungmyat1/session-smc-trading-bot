# Log Retention Policy (proposed — not yet applied)

Date: 2026-07-04
Status: Proposal only. No configuration in this document has been applied to the host.
Goal: retain operational logs 30 days, compress older logs, auto-remove logs older than 90 days,
preserve audit logs indefinitely, prevent root filesystem exhaustion (currently 81% used, 7.4 GiB free).

---

## 1. Current state by source

| Source | Mechanism today | Location | Current retention |
|---|---|---|---|
| systemd journal | `journald`, default config (no `SystemMaxUse=` set in `/etc/systemd/journald.conf`) | `/var/log/journal/` | 26.8 MiB used; uncapped by explicit config, bounded only by journald's default 4G/10%-of-filesystem ceiling |
| OS logs (`syslog`, `kern.log`, `auth.log`, `mail.log`, `cron.log`, `user.log`) | `logrotate`, `/etc/logrotate.d/rsyslog` | `/var/log/*` | `rotate 4` weekly + compress + delaycompress = ~4 weeks (~28 days) compressed history |
| `fail2ban.log` | `logrotate`, `/etc/logrotate.d/fail2ban` | `/var/log/fail2ban.log*` | Security-relevant — currently rotated but retention count not verified beyond the default; treat as an audit log (see §3) |
| Docker | N/A — Docker/containerd are inactive on this host (confirmed in `OPERATIONS_BASELINE.md`) | n/a | Not applicable while Docker stays disabled |
| PostgreSQL | `logging_collector = off` — Postgres writes to syslog/journal, not its own rotated file; `/var/log/postgresql/*` (64 KiB) is stale/inactive | `/var/log/postgresql/` | Effectively governed by the journald/syslog policies above, not a separate PG-specific policy |
| Dashboard (`dashboard/status_server.py`, `dashboard/app.py`) | Ad hoc — no `RotatingFileHandler` found in dashboard code; small files (`dashboard.log` 360 B, `dashboard_audit.jsonl` 8 KiB) | `logs/dashboard*.{log,jsonl}` | Unbounded growth today, currently negligible size |
| Trading engine (`scripts/run_st_a2_demo.py` and legacy runners) | `monitoring/logging_utils.py` builds a `TimedRotatingFileHandler` (daily, gzip-compressed backups) — this is the mechanism behind the `bot.log.YYYY-MM-DD.gz` / `d2e3_demo.log.YYYY-MM-DD.gz` pattern already observed in `logs/` | `logs/*.log*` (17 MiB across 39 files today) | App-level daily rotation exists; **no enforced maximum age** — oldest file present is 12 days old (2026-06-22) only because nothing has requested more; `backupCount` is not confirmed set to a fixed cap in all call sites |
| Application JSON/JSONL state and event logs (`risk_state.json`, `execution_pipeline_events.jsonl`, `runtime_events.jsonl`, `dashboard_audit.jsonl`) | No rotation at all — these are either point-in-time snapshots (overwritten in place) or append-only | `logs/*.json`, `logs/*.jsonl` | Append-only files (`execution_pipeline_events.jsonl` especially, now also durably mirrored to Postgres `operations.execution_event` per Sprint 2.3) will grow unbounded without a policy |

## 2. Proposed policy

| Tier | Rule | Applies to |
|---|---|---|
| **Hot (0-30 days)** | Keep uncompressed, no action | Active `logs/*.log`, current journald window, current `syslog`/`kern.log`/etc. |
| **Warm (30-90 days)** | Compress if not already `.gz`; keep in place | Rotated `bot.log.*.gz`, `d2e3_demo.log.*.gz`, rotated OS logs |
| **Cold (>90 days)** | Delete, **except audit logs** (§3) | Anything matching the above patterns aged past 90 days |
| **Append-only event logs** | Cap by size + time: rotate `execution_pipeline_events.jsonl` / `runtime_events.jsonl` daily (same `TimedRotatingFileHandler` pattern already used elsewhere), apply the same 30/90-day compress/delete tiers to the rotated files | `logs/*.jsonl` |
| **Journald** | Set explicit `SystemMaxUse=500M` and `MaxRetentionSec=90day` in `/etc/systemd/journald.conf` (currently unset/uncapped) | `/var/log/journal/` |

## 3. Audit logs — preserved, never auto-deleted

Per this repo's own governance (`CLAUDE.md` §0.4 evidence retention, `ARCHITECTURE_STABILIZATION_ROADMAP.md` principle "Evidence is append-only"), the following are **excluded from the 90-day deletion tier** regardless of age:

- `fail2ban.log*` and `auth.log*` (security audit trail)
- `data/trade_journal.db` (SQLite) and the Postgres `operations.*` schema (migration 004) — not log files, but called out here so no future log-cleanup automation is ever pointed at them
- `dashboard_audit.jsonl` and any file matching `*_audit.jsonl`
- `docs/VERDICT_LOG.md` and any SVOS evidence/report artifacts — not logs, explicitly out of scope for any rotation tooling
- Startup-recovery and recovery-checkpoint records (`operations.recovery_checkpoint` in Postgres, Sprint 2.3) — durable by design, not subject to a log-rotation policy at all

These should be excluded by path pattern in whatever rotation tooling is implemented (an explicit denylist, not an assumption), consistent with this repo's "no `\|\| true`, no silent suppression" quality bar.

## 4. Implementation approach (not applied yet)

1. Add `SystemMaxUse=500M` and `MaxRetentionSec=90day` to `/etc/systemd/journald.conf`, `systemctl restart systemd-journald`. Low risk, reversible, one-line-per-setting change.
2. Add a repo-level `logrotate` drop-in (`/etc/logrotate.d/session-smc-trading-bot`) targeting `logs/*.log` with `rotate 12` (weekly) or a `maxage 90` directive, `compress`, `delaycompress`, explicitly excluding the audit-log denylist in §3 via separate stanza or `logrotate`'s built-in file-matching (do not use a single wildcard that could sweep up `*_audit.jsonl`).
3. Confirm every `TimedRotatingFileHandler` call site in `monitoring/logging_utils.py` and its callers sets `backupCount` consistently with the 90-day cold tier (currently not verified to be uniform across all loggers).
4. Re-verify no policy change touches `data/trade_journal.db`, Postgres data directories, or any SVOS evidence path.

## 5. Explicitly deferred

Applying any of the above is deferred to a separate, explicitly-approved pass per this phase's instructions ("Do not apply configuration yet"). This document is the proposal only.
