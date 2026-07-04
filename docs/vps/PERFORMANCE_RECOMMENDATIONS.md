# VPS Performance Recommendations

Date: 2026-07-04
Status: Review

## Priority order

1. **Resolve the `smc-demo-runner` restart loop.** It is an availability defect and creates needless process/log churn. Fix the strategy/config mismatch through the normal code/config review path; retain demo-only invariants.
2. **Increase disk headroom.** At 82%, establish alerts at 80/90%, perform approved cache cleanup, and move cold archives/datasets to a separate persistent disk or versioned object storage after integrity verification.
3. **Separate production from development workloads.** VS Code extension host plus Pylance consumed about 1.35 GiB RSS on a 3.8 GiB host; Next.js/Codex/MCP add more. Use a separate development VM or stop interactive tooling outside maintenance windows.

## Component recommendations

### Docker

Docker is inactive and empty. If the production architecture does not require it, leave it disabled and document that decision; uninstall only after explicit approval and confirmation that benchmark workloads are retired. If adopted, set daemon log rotation, resource limits, health checks, read-only mounts where possible, and never expose the socket.

### Python

Pin dependencies with hashes, keep one immutable deployment environment per service release, and build/test it off-host. Apply systemd memory/CPU limits after measuring steady state. Keep bytecode/test caches out of release artifacts. The active 1.4 GiB venv is large; dependency trimming should be performed in a new venv, never in place.

### PostgreSQL

The database is small and healthy. Keep it loopback-only, add authenticated logical/physical backups with restore tests, monitor connections/WAL/autovacuum, and set conservative memory for a 4 GiB host (avoid large `shared_buffers`/`work_mem` multiplication). Do not tune without baseline query/IO metrics.

### Redis

Redis is absent. Do not install it unless the application has a measured need; another daemon would consume memory and operational attention.

### Memory and swap

The 2 GiB swapfile is unused and provides reasonable OOM protection. Retain it. Monitor PSI, major faults, swap activity, and OOM logs. Prefer removing development load over aggressive swappiness changes. Define `MemoryHigh`/`MemoryMax` for noncritical development services before constraining trading/database services.

### Filesystem and storage

Keep ext4 discard/fstrim monitoring. Put high-volume immutable market data on a separate disk with snapshots and checksums. Avoid hand-deleting package-managed files. Track inode use as well as bytes. Set a capacity SLO with automated alerts and forecast growth of tick Parquet files.

### Logging and journal

Retain audit-grade trading decisions separately from operational logs. Configure bounded journald/rsyslog retention only after legal/research retention is defined. Add rate limiting to restart-loop logs, but treat rate limiting as containment, not the fix. Rotate project logs with copy/truncate semantics appropriate to open file handles and verify ingestion before compression/removal.

### CPU and background services

Two vCPUs are adequate only if interactive analysis is excluded. Move Pylance/Next.js/agent workloads away from production. Review Avahi, multipath, open-iscsi, and unused cloud/desktop-adjacent services one by one; disable only with dependency evidence and a rollback plan.

### Network and security

- Confirm UFW policy as root; allow only SSH/Tailscale and intentionally published dashboard access.
- Bind dashboard and development servers to loopback or Tailscale unless public exposure is explicitly required. Port 54112 should not be wildcard-bound on production.
- Put dashboard behind authenticated TLS/reverse proxy; add a real health endpoint and service watchdog.
- Preserve Fail2ban, unattended security updates, Chrony, SSH hardening, and Tailscale. Review SSH users/keys and disable password/root login if not already enforced.
- Store broker and application secrets only in protected environment files/secret storage; never surface values in diagnostics.

### Reliability and observability

Add alerts for restart counts, service active state, dashboard endpoint, PostgreSQL readiness, disk, memory, load, clock drift, backup age, and demo-only safety invariants. A zero result from `systemctl --failed` is insufficient—alert on units stuck in `activating/auto-restart`. Run cleanup and package maintenance only in a documented window with before/after verification.
