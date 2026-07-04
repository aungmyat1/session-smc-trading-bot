# Production Readiness Ratings

Date: 2026-07-04
Status: Read-only audit finding
Companion: `IMPLEMENTATION_MATRIX.md` (source detail per subsystem)

Scale: **Research Ready** (correct for offline research use) → **Demo Ready** (safe to run against
a demo broker account, no real capital) → **Production Ready** (safe for real capital, single
operator) → **Enterprise Ready** (safe for a small team, defense-in-depth) → **Institutional Ready**
(audited, regulator-grade, multi-operator, full DR/observability).

**No component in this repository is rated above Demo Ready.** `LIVE_TRADING=false` /
`DEMO_ONLY=true` are correctly enforced platform-wide, and this is the right rating even before
considering feature completeness — the objective itself (`CLAUDE.md` §0.1) forbids Production
Ready status until a strategy holds Production Approval, and none does.

---

## By subsystem

| Subsystem | Rating | Why |
|---|---|---|
| Broker Integration | **Demo Ready** | Real MetaAPI/Vantage connectivity, live-verified data; live-mode paths exist but aren't default-denied at every layer (WS3 open) |
| Logging | **Demo Ready / Production Ready (single-host)** | Real rotation, gzip, dual-layer (app + logrotate); no aggregation, so caps out below Enterprise |
| Authentication | **Demo Ready**, borderline **Production Ready** for an internal tool | Real HMAC/CSRF, role-based permissions; static shared-secret tokens, no MFA — fine for one operator, not a team |
| Postgres / control plane | **Demo Ready** | Real schema, migrations, tested backup/restore; not node-separated, no least-privilege roles yet |
| Strategy Registry / Lifecycle | **Demo Ready**, close to **Production Ready** for the mechanism itself | Immutable, append-only, correctly gates forward promotion; catalog/registry reconciliation gap keeps it from full trust |
| Strategy Packaging / Signing | **Demo Ready (repo-only)** | Real deterministic packaging + 3 signing schemes incl. GCP KMS; zero real-infra rehearsal |
| CI/CD | **Demo Ready** | Real, enforced gates; only ~28% of tests actually run in CI, so "CI green" understates real risk |
| Security scanning | **Demo Ready** | Real bandit/pip_audit/secret-scan; doesn't cover the actual live execution path (`execution/`, `dashboard/`, `bot.py`) |
| Live Trading Engine | **Demo Ready** | Runs correctly in demo; canonical entrypoint lacks recovery/governance wiring the legacy one has |
| Execution Engine | **Demo Ready** | Functionally correct order pipeline exists; a second, unused idempotency layer adds confusion without adding safety |
| **Risk Management** | **Research Ready only** — below Demo Ready for its core promise | Loss-limit halts cannot fire from real P&L (`record_result`/`record_close` uncalled) — a bot on a real losing streak will not stop via this mechanism today |
| Order/Position Management | **Demo Ready** | Retry/state-machine logic real; restart-recovery and position-release both have live gaps |
| Data Pipeline / Research DB | **Research Ready** | Correct and usable for research; no orchestration, and DB not on its target node |
| Historical Replay / Backtesting | **Research Ready** | Correct gate logic; fragmented across 5+ metrics implementations and 2 orchestrators |
| Dashboards (all 3 variants) | **Demo Ready**, explicitly flagged **not reliable for live-money decisions** even in demo | Stale-data bugs (wrong log file, wrong trades file) found in a prior live audit; 3 unconsolidated backends |
| Documentation | **Research Ready** | Governance mechanism (`DOC_AUTHORITY.md`) is sound; existing corpus is not yet compliant with it, and root-level sprawl sits outside governance entirely |
| Multi-Agent/LLM adapter | **Research Ready (experimental)** | Well-isolated, safety-conscious design (disabled by default, human-acceptance gate); not wired into the pipeline, untested |
| Disaster Recovery / Backup | **Demo Ready (code)**, below Demo Ready operationally | Restore code is real and tested; no evidence of an executed rehearsal or a scheduled backup job |

---

## Platform-level verdict

- **Research Ready**: Yes, broadly — the data pipeline, research database, replay, and backtest
  gate are all real and usable for research purposes today.
- **Demo Ready**: Yes, with named caveats — the platform runs a real demo-mode strategy against a
  real broker, with real logging/alerting, but the risk-halt mechanism does not actually protect
  the demo account from a real losing streak, and the dashboard cannot be trusted for freshness
  without independent log verification.
- **Production Ready**: **No.** Blocked by policy (`CLAUDE.md` §0.1 — no strategy holds Production
  Approval) and independently blocked by the risk-feedback gap even if that policy gate were
  lifted — halts that cannot fire are a correctness defect, not just a missing feature.
- **Enterprise Ready**: **No.** No node separation, no centralized log aggregation, no
  multi-operator auth model, dashboard consolidation unresolved, CI covers under a third of tests.
- **Institutional Ready**: **No.** Would additionally require a rehearsed DR drill, regulator-grade
  audit trails beyond append-only JSONL, full-suite CI enforcement, and real-infra-verified
  package signing — none of which exist today even as designs beyond the packaging/signing code
  itself.
