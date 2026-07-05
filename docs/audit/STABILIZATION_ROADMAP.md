---
Date: 2026-07-05
Status: Proposed — awaiting owner prioritization confirmation
Scope: Prioritized implementation roadmap following the 2026-07-05 repository stabilization pass
Owner: Repository governance
Related: docs/audit/CI_CD_HEALTH_REPORT.md, docs/audit/EXECUTION_LAYER_GAP_ANALYSIS.md, docs/audit/DEPENDENCY_UPDATE_PLAN.md, docs/audit/DEMO_TRADING_RISK_ASSESSMENT.md
---

# Prioritized Implementation Roadmap

Ordered by risk-reduction per unit of effort, not by document section. Nothing here authorizes live trading — see the risk assessment for that gate explicitly.

## P0 — safety-relevant, small, do first

1. **Idempotency guard on live order placement** (`execution/trade_manager.py::open_position()`). Currently only crash-recovery prevents a duplicate order; nothing stops an accidental double-call during normal operation. Add a dedup check against the generated `idempotency_key` before submission, not just a random-suffixed key that's never looked up.
2. **`run_portfolio.py` has no emergency-stop check.** Either wire in the same per-tick `control_state` check `run_st_a2_demo.py` has, or make the `RUN_PORTFOLIO_ALLOW_START` block a permanent architectural decision (retire the script) rather than a temporary gate — leaving it half-wired is the riskier middle state.
3. **`develop`'s CI**: add the missing `pyyaml` install step (trivial) and resolve the `smartmoneyconcepts`/`fastapi` lock-file gaps (regenerate lock, or scope pytest paths like `main` does). Blocks reading any signal from that branch's CI and blocks re-verifying Dependabot bumps cleanly.
4. **`/api/v1/production/health` heartbeat is never written** by the canonical runner — a monitoring consumer would see stale data as if it were current, not an honest unknown. Wire the runner to write it, or remove the endpoint until it's real.

## P1 — reliability, moderate effort

5. **Consolidate broker-client implementations.** Three exist (`mt5_connector.py` live, `metaapi_client.py` used by a separate dormant stack, `mt5_executor.py` unused). Decide: retire the two dormant ones, or document explicitly why each still exists and who owns them. This is a repeat of a known duplication-debt pattern in this repo (already flagged for SVOS orchestrators and dashboard backends) — don't let it become a third instance of the same unresolved problem.
6. **Add retry-with-backoff to broker read calls** (`get_positions()`, `get_account_info()`) — currently a transient failure raises once and is swallowed by a bare `except`, with no retry. Order placement already has this pattern (`_place_order_with_retry`); extend it.
7. **Unify reconciliation cadence.** Three separate mechanisms (per-tick, 5-minute timer, startup-only) cover both directions of drift but at different intervals — document the coverage gap explicitly or converge on one loop, whichever is cheaper.
8. **`tests/core/*` and `tests/test_status_server.py` are not run by `main`'s CI at all.** Add them to the `unit` or `integration` matrix in `ci.yml` — right now a regression in either is invisible to the required check.
9. **Coverage threshold (`--cov-fail-under=67`) is configured but bypassed** by CI's own `-o addopts=''`. Either enforce it in CI deliberately or remove the config to stop implying a gate that doesn't run.

## P2 — hygiene, low urgency

10. **Merge the 5 Dependabot PRs once reopened**, after P0.3 above — see `docs/audit/DEPENDENCY_UPDATE_PLAN.md` for the per-PR process.
11. **Sync or formally diverge `develop` from `main`.** Right now it's neither current nor deliberately a separate pipeline — pick one.
12. **CircleCI GitHub App**: revoke repo access or remove the CircleCI project (needs admin access outside `gh`'s reach) — purely cosmetic cleanup, not blocking anything.
13. **Recovery-path test fixtures use synthetic broker-position dicts**, never a real MetaAPI response shape — worth a test using recorded real API responses if/when this path becomes higher-stakes.

## Explicitly out of scope for this roadmap

New trading strategies, live-trading enablement, and anything beyond repository/execution stability — per this stabilization pass's own constraint. See `docs/audit/DEMO_TRADING_RISK_ASSESSMENT.md` for what actually gates progression toward demo/live trading; this roadmap only closes engineering gaps, it doesn't itself authorize any trading-readiness milestone.
