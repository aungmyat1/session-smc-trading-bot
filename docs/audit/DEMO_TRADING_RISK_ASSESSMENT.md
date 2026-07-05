---
Date: 2026-07-05
Status: Assessment — informational, does not authorize any trading milestone
Scope: Risk assessment for proceeding toward demo trading, post-PR #22
Owner: Repository governance
Related: docs/audit/EXECUTION_LAYER_GAP_ANALYSIS.md, docs/audit/STABILIZATION_ROADMAP.md, CLAUDE.md §0/§9
---

# Risk Assessment — Proceeding Toward Demo Trading

Scope note: this assesses readiness for **demo** trading only (the deployed runner already trades demo capital against a live broker connection today, per `docs/systems/system2/STATUS.md`). It does not touch live-trading readiness — that remains gated behind `LIVE_TRADING=false`/`DEMO_ONLY=true`, a full Production Approval package, and explicit owner authorization, none of which this pass evaluates or unlocks (CLAUDE.md §0.1).

## Already-running demo state (context, not a finding)

`smc-demo-runner.service` runs ST-A2 against a live (demo) broker connection, verified stable (0 restarts) since 2026-07-04, with broker-truth reconciliation, per-tick emergency-stop enforcement, and crash-recovery all confirmed real (see gap analysis). Demo trading is not a future state to reach — it is the current state. This assessment is about the *risk profile* of that ongoing demo trading and what should change before treating it as a stable, trustworthy signal source for eventual live-readiness evidence.

## Risk register

| Risk | Severity | Likelihood | Basis | Mitigation status |
|---|---|---|---|---|
| Duplicate order from a double-call during normal operation (not just crash-recovery) | **High** | Low | `idempotency_key` includes a random suffix never checked against existing records — dedup exists only at crash-recovery time (§ Execution Layer Gap Analysis #2) | **Unmitigated** — P0 item in the roadmap |
| `run_portfolio.py` activated without emergency-stop wiring | **High** | Low (currently blocked) | No per-tick control-state check exists in that script at all; only mitigation is a start-time env-var gate | **Partially mitigated** (blocked from starting), but the underlying gap is real if that gate is ever removed without also adding the check |
| Broker connectivity relies on the wrong/dormant client during a future refactor | Medium | Low | Three parallel broker-client implementations exist; only one is live, distinguishable only by reading code, not by structure | **Unmitigated**, but currently inert — the dormant stacks aren't running |
| A transient broker read failure (`get_positions`/`get_account_info`) goes unretried and is silently swallowed | Medium | Medium | No retry/backoff on read calls, unlike order placement | **Unmitigated** |
| Reconciliation drift between the per-tick check and the 5-minute timer | Low-Medium | Low | Three reconciliation mechanisms at different cadences, not one unified loop | **Partially mitigated** — both directions are covered, just not on the same clock |
| Monitoring shows stale data as current | Low | Medium | `/api/v1/production/health` heartbat file never written by the canonical runner | **Unmitigated**, but low blast radius (observability only, doesn't affect trading behavior) |
| A regression in `tests/core/*` or dashboard status-server tests ships undetected | Medium | Medium | Neither test path is in `main`'s required CI matrix | **Unmitigated** |
| Dependency bumps merged against unreadable CI signal | Low | Low (nothing currently open) | `develop`'s CI is a different, broken pipeline generation from `main`'s | **Unmitigated**, but no immediate exposure since no PRs are open |

## What would most increase confidence before treating this demo runner as evidence toward the next lifecycle stage

In order:
1. Close the idempotency gap (P0.1) — this is the one finding in this pass with genuine capital-safety implications even in demo mode (duplicate demo orders corrupt the P&L/risk-state evidence trail this platform depends on for eventual qualification).
2. Add the missing CI coverage for `tests/core/*` / `test_status_server.py` — a silent regression in dashboard auth or trade-journal logic (both areas this session found real bugs in) would currently ship undetected.
3. Resolve the broker-client duplication before it becomes load-bearing in a future change.

## What this assessment does NOT find

No evidence of anything that should **pause** the currently-running demo trading — the per-tick emergency stop, broker-truth reconciliation, and crash-recovery are all real and were independently verified against actual code, not just the docs' own claims. The risks above are about hardening an already-functioning demo path and about not letting known gaps become load-bearing later, not about an active, ongoing safety failure.

## Explicit non-scope reminder

This document does not evaluate, and should not be read as progress toward, Production Approval or live-trading enablement. Those require: a strategy holding current Production Approval (none do — see `docs/VERDICT_LOG.md`), a 30+ day stable *online* demo with n≥50 trades and zero critical execution failures (separate from this Phase-5 offline virtual demo track), and explicit owner authorization to flip `LIVE_TRADING`. Nothing in this stabilization pass changes any of those facts.
