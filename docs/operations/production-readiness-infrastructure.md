# Production Readiness Checklist — Infrastructure (auto-trade-vps)

Date: 2026-07-06
Status: Assessment
Scope note: this checklist covers **infrastructure** readiness only (storage,
logging, monitoring, backups, recovery, capacity, security, service health,
future MT5 readiness). For platform-level readiness (architecture, deployment
pipeline, SVOS lifecycle gates), see the existing
`docs/operations/production_readiness_report.md` (2026-07-02) — this document
does not duplicate or supersede it.

| Area | Status | Evidence |
|---|---|---|
| **Storage** | 🟢 PASS (resolved 2026-07-07) | Boot disk resized live 40G→50G (`docs/operations/disk-expansion-2026-07-07.md`) — **69% used, 31% free**, past both the 80% warning threshold and the 75% target. Zero downtime; demo runner process PID unchanged throughout. Reporting tooling exists; automated alerting still not wired up (tracked separately). |
| **Logging** | 🟡 PARTIAL | Strategy runner and `capture_spreads.py` rotate correctly (daily, gzip, `TimedRotatingFileHandler`). Dashboard has no rotation at all. journald has no explicit cap (`docs/audit/log-rotation-audit.md`). Proposal exists (`docs/vps/LOG_RETENTION_POLICY.md`), not applied. |
| **Monitoring** | 🔴 FAIL | No cron/systemd timer runs `disk_report.py`/`cleanup_report.py` or any equivalent automatically. No alerting on disk/memory/swap thresholds exists today — crossing 90% critical would currently go unnoticed until someone looks. `docs/vps/PERFORMANCE_RECOMMENDATIONS.md` flagged this same gap on 2026-07-04; still open. |
| **Backups** | 🟢 PASS | `~/archives` holds six checksummed, recent (2 days old) backup tarballs (`docs/operations/backup-retention.md`). `~/db_backups` (62M) exists separately for database backups. No automated backup schedule confirmed (`docs/vps/OPERATIONS_BASELINE.md` §4: "backups remain manual-only") — that's the gap within an otherwise-passing area. |
| **Recovery** | 🟡 PARTIAL | Checksummed backups exist and are restorable in principle; no restore has actually been tested per this audit or prior ones. `TradeManager`/connector-level reconnect logic is well-tested (existing test suite), but host-level disaster recovery (VM loss, disk corruption) has no documented runbook beyond the backups' existence. |
| **Capacity** | 🟡 PARTIAL | `docs/audit/capacity-plan.md` now exists with concrete projections; current state is already past the warning threshold before any new MT5 provisioning is added. Recommendation (reclaim before provisioning, or use a dedicated node per ADR-0012) is documented but not yet acted on. |
| **Security** | 🟢 PASS (infra baseline only) | `fail2ban`, `tailscaled`, unattended-upgrades, chrony all active per service health below. No credentials found in logs/diagnostics during this audit. Full security posture (IAM, secret rotation) is out of scope here — see `docs/operations/production_readiness_report.md`'s Security dimension (7/10) for the platform-level score. |
| **Service health** | 🟢 PASS | `smc-demo-runner.service`, `live-dashboard.service`, `postgresql@16-main.service`, `tailscaled.service`, `ssh.service`, `fail2ban.service` all verified `active` post-cleanup (2026-07-06). Dashboard HTTP endpoint returns 200. PostgreSQL accepting connections. Demo runner process confirmed alive throughout this entire task. |
| **Future MT5 readiness** | 🔴 FAIL (confirmed, 2026-07-07) | Beyond the empty-prefix finding (Phase 4A), an actual provisioning attempt now shows **Wine itself cannot execute any Windows binary on this host** — reproducible across two Wine versions (11.11, 11.12) and two prefixes (original + freshly created), not a one-off. Root cause unconfirmed (kernel/Wine incompatibility suspected). No MT5 terminal was installed. See ADR-0011's provisioning appendix. |

## Evidence sources

- Storage/Capacity: `docs/operations/storage-governance.md`, `docs/audit/capacity-plan.md`, live `scripts/disk_report.py` output (86-87% disk, 5.6G free)
- Logging: `docs/audit/log-rotation-audit.md`, `docs/vps/LOG_RETENTION_POLICY.md`
- Backups: `docs/operations/backup-retention.md`
- Service health: direct `systemctl is-active` + HTTP + `pg_isready` checks run 2026-07-06 during ADR-0011 Phase 4
- Future MT5 readiness: `docs/svos/ADR-0011-MT5LINUX-BROKER-BRIDGE.md` Phase 4A findings, `docs/svos/ADR-0012-SYSTEM2-HOSTING-STRATEGY.md`

## Overall infrastructure readiness

🟡 **Ready with conditions** for continued System 2 demo operation as-is — all
6 checked services verified `active` throughout Phases 4-5 (2026-07-06 and
2026-07-07), zero interruption at any point across two full provisioning
attempts and a cleanup pass. 🔴 **Not ready** for MT5/mt5linux provisioning
on this host: disk is back to 87% (still above target) and Wine itself is
confirmed non-functional after a structured investigation
(`docs/audit/wine-investigation-report.md`), independent of disk. Recommend
`ADR-0012`'s dedicated-node option as the primary path forward — see that
ADR's 2026-07-07 evidence update. No condition here blocks current ST-A2
demo operation — this checklist is about the *next* infrastructure step, not
the current one.
