# Runtime Resource Optimization Recommendations

Date: 2026-07-04
Status: Mostly recommendations only. **Applied 2026-07-05**: `effective_cache_size` lowered
4GB→2GB (`ALTER SYSTEM` + `pg_reload_conf()`, no restart) — see updated finding below. All other
items in this document remain unapplied.
Baseline: `docs/vps/OPERATIONS_BASELINE.md` (2 vCPU, 3.8 GiB RAM, 81% disk used, load avg 0.38/0.24/0.22)

---

## High Impact

| Area | Finding | Recommendation |
|---|---|---|
| **PostgreSQL `effective_cache_size`** | ~~Set to **4GB**, but total host RAM is **3.8 GiB**~~ **FIXED 2026-07-05**: was 4GB against 3.8 GiB total host RAM — the query planner was tuned assuming more OS page cache than physically exists, which can produce suboptimal query plans (wrongly favoring index scans it thinks will hit cache) | ~~Lower to ~2GB~~ **Applied**: set to `2GB` via `ALTER SYSTEM SET effective_cache_size = '2GB'; SELECT pg_reload_conf();` — took effect immediately, `postgresql@16-main.service` stayed active throughout, no restart needed. |
| **`smc-demo-runner.service` crash-loop** | 173+ restarts and climbing, one exec + one Python interpreter startup + argparse failure every 15 seconds, indefinitely | Resolve per `docs/systemd/SMC_DEMO_RUNNER_ANALYSIS.md` (Replace recommendation) — this is a real, continuous, avoidable CPU/journal-write cost with zero benefit, not just a cleanliness issue. |
| **Disk headroom** | 81% used, 7.4 GiB free, on a host with an actively-growing Postgres database, journald, and application logs | No further cleanup batch needed *immediately*, but see `docs/vps/LOG_RETENTION_POLICY.md` — without a retention cap, disk pressure returns. Treat 85% as an internal alert threshold, not 90%+. |

## Medium Impact

| Area | Finding | Recommendation |
|---|---|---|
| **journald rate limiting** | `RateLimitIntervalSec`/`RateLimitBurst` are commented out (defaults: 30s / 10000 burst) | Fine at current volume, but the crash-loop is a live example of a source that could burst past defaults under a worse failure mode. Once journald caps are added per the log policy (`SystemMaxUse=500M`), also uncomment and confirm sane rate limits so a future crash-loop can't silently drop log lines. |
| **PostgreSQL `max_connections`** | 100, generous for a single-operator, low-concurrency demo platform | Lower to 20-30. Each idle connection has a small fixed memory cost; not urgent at current usage but free headroom on a 3.8 GiB host. |
| **VS Code / IDE tooling overhead** | Top CPU/memory consumers on this host are VS Code server + extension host + Pylance (878 MiB + 448 MiB + 311 MiB RSS) — developer tooling, not production trading load | Not something to "fix" (this is expected on a dev+prod combined box), but worth tracking separately from production resource budgeting — don't let IDE session count influence trading-service resource-limit decisions. |
| **npm cache (241 MiB)** | Still present, still in active use by MCP server processes this session (`mcp-server-circleci`, `pionex-trade-mcp`) | Not safe to clear now (see Phase 5). Revisit after those processes end. |

## Low Impact

| Area | Finding | Recommendation |
|---|---|---|
| **Swap (`vm.swappiness=10`)** | Already lower than Ubuntu's default of 60 — appropriate for a server workload | No change needed; confirmed already tuned. |
| **Docker/containerd** | Both `inactive`, no socket, zero resource usage | No action — nothing to optimize while unused. If Docker is never going to be used on this host, the packages could eventually be purged for a small reclaim, but that's a Phase 5-style cleanup decision, not a runtime optimization. |
| **Network** | `tailscaled` running at low, steady CPU (0.3%); `ufw` active; single `sshd` listener; no unexpected listening ports found in this pass | No findings; healthy as observed. |
| **Background OS services** | `fail2ban` active with one jail (`sshd`) | Reasonable baseline; no change recommended without a broader security review (out of scope here). |
| **Python (application)** | No `run_st_a2_demo.py` process is currently stable long enough to profile (crash-looping) | Revisit CPU/memory profiling of the actual trading runner once Phase 2's fix lands and it runs continuously. |

## Not applicable on this host

Redis and Node.js production services: no Redis installation found (confirmed in the earlier VPS cleanup pass); no project Node.js service is deployed (Node processes present are IDE/MCP tooling only, not a production Node service) — no recommendations to make for either.
