# Log Rotation Audit

Date: 2026-07-06
Status: Audit — proposals only, nothing applied
Authoritative prior document: `docs/vps/LOG_RETENTION_POLICY.md` (2026-07-04) — this
audit does not restate that document's findings in full; it verifies they
still hold and adds what changed since (ADR-0011 mt5linux work).

## Scope

Every component that continuously writes logs on `auto-trade-vps`: dashboard,
strategy runner, PostgreSQL, systemd journal, research logs, replay logs.

## Rotation status by component (verified against current code, 2026-07-06)

| Component | Rotates? | Mechanism | Notes |
|---|---|---|---|
| Strategy runner (`scripts/run_st_a2_demo.py`, `run_strategy_demo.py`) | **Yes** | `monitoring/logging_utils.py`'s `TimedRotatingFileHandler` (daily, gzip) | No enforced maximum age confirmed uniformly across call sites — same finding as `LOG_RETENTION_POLICY.md` §1, still true |
| `scripts/capture_spreads.py` (ADR-0011) | **Yes** | Same `build_gzip_timed_rotating_handler` helper, 7-day `backup_count` | New since the prior audit — capture_spreads.py was migrated from `MetaAPIClient` to `MT5LinuxConnector` in ADR-0011 Phase 1-3; its logging setup is unchanged and already rotates |
| Dashboard (`dashboard/status_server.py`, `live_dashboard_service.py`) | **No** | Ad hoc, no `RotatingFileHandler` found | Same finding as prior audit — files are currently small (`dashboard.log` ~360B) but unbounded |
| PostgreSQL | Indirect | `logging_collector = off`, writes to syslog/journal | Governed by journald/rsyslog policy below, not a PG-specific policy — unchanged |
| systemd journal | Bounded only by journald defaults | No explicit `SystemMaxUse=`/`MaxRetentionSec=` in `journald.conf` | Unchanged — still proposal-only per `LOG_RETENTION_POLICY.md` §4.1 |
| Research/replay logs (`research/*.py`, replay runners) | **Mixed** | Some use the same `logging_utils` helper; ad hoc scripts (e.g. one-off analysis scripts) print to stdout only, not logged to disk | No behavior change since prior audit |
| Append-only JSON/JSONL state (`risk_state.json`, `execution_pipeline_events.jsonl`, `runtime_events.jsonl`, `dashboard_audit.jsonl`) | **No** | Overwritten in place or append-only, no rotation | Unchanged — `execution_pipeline_events.jsonl` is durably mirrored to Postgres `operations.execution_event` (Sprint 2.3), so its growth risk is partially mitigated by that migration, but the flat file itself still has no cap |
| `execution/mt5linux_connector.py` heartbeat/latency log (`logs/latency_timeseries.jsonl`) | **Yes, self-capped** | Hand-rolled retention in `_append_latency_sample()`: keeps the last 1000 lines, rewrites the file each call | New in ADR-0011 — this is the same pattern `execution/mt5_connector.py` already used (copied verbatim for interface parity), so it inherits the existing self-capping behavior, not a new unbounded-growth risk |

## Logs that can grow indefinitely today

Unchanged from `LOG_RETENTION_POLICY.md` §1/§2:
- Dashboard ad hoc logs (currently negligible size, but no cap)
- `execution_pipeline_events.jsonl` / `runtime_events.jsonl` (partially mitigated by the Postgres mirror, but the flat file itself is uncapped)
- systemd journal (bounded only by journald's default 4G/10%-of-filesystem ceiling, not an explicit policy)

## Recommended rotation configuration (proposed, NOT applied)

No changes to this section from `LOG_RETENTION_POLICY.md` §4 — it remains the
correct proposal:
1. `SystemMaxUse=500M`, `MaxRetentionSec=90day` in `/etc/systemd/journald.conf`.
2. A repo-level `logrotate` drop-in for `logs/*.log` (`rotate 12` weekly or
   `maxage 90`, `compress`, `delaycompress`), explicitly excluding the audit
   denylist (`fail2ban.log*`, `auth.log*`, `*_audit.jsonl`,
   `docs/VERDICT_LOG.md`, `data/trade_journal.db` — now also codified in
   `config/storage_policy.yaml`'s `retention.logs.audit_denylist`).
3. Confirm `backupCount` is set consistently across every `TimedRotatingFileHandler`
   call site in `monitoring/logging_utils.py`'s callers, including the new
   `capture_spreads.py` call site added in ADR-0011.
4. Add a `TimedRotatingFileHandler` (or equivalent app-level rotation) to
   `dashboard/status_server.py` and `live_dashboard_service.py`'s logging setup
   — this remains the one component with genuinely no rotation and no
   self-capping mechanism at all.

## Delta since 2026-07-04

- ADR-0011 (mt5linux migration) added one new logger (`strategy_demo.mt5linux_connector`)
  and repointed `capture_spreads.py`'s logging — both already follow the
  existing rotation/self-cap patterns, so no new unbounded-growth risk was
  introduced by that work.
- No rotation configuration has been applied since the 2026-07-04 proposal —
  `LOG_RETENTION_POLICY.md`'s "Explicitly deferred" section still holds.

## Disposition

This audit confirms `LOG_RETENTION_POLICY.md`'s findings are still accurate
and extends coverage to the ADR-0011 additions. No new proposal is needed
beyond what that document already specifies — applying it remains a separate,
explicitly-approved pass, not part of this audit.
