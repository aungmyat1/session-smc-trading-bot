# Pipeline Consolidation Plan

Date: 2026-07-04
Status: Plan — reflects what this pass will and will not attempt, and why
Inputs: `EXECUTION_PIPELINE_INVENTORY.md`, `CANONICAL_EXECUTION_PIPELINE.md`

---

## Migration sequence, by risk level

### Tier 1 — Low risk, safe this pass

| Item | Why low risk | Action |
|---|---|---|
| "Production Platform v2" cluster: `production/engine/{orders,positions,risk}.py` + `production/{recovery,operations,reporting,api}.py` (411 lines) | Zero callers outside its own dedicated test files; never imported by either real runner; introduced already-disabled by its own commit message | **Remove**, together with its dedicated test file. This is dead code, not a live duplicate execution path — removing it doesn't touch anything safety-critical, since nothing safety-critical calls it. |

### Tier 2 — Medium risk, deferred, tracked

| Item | Why deferred | Current disposition |
|---|---|---|
| `run_portfolio.py` full retirement | Its `main()`/package-validation CLI path is real, tested coverage (WS1 canonical-package handoff, `tests/portfolio/test_strategy_package_cli.py`, `tests/integration/test_canonical_package_handoff.py`) that has no equivalent elsewhere. Deleting the file would delete that coverage with nothing to replace it. | Stays blocked-from-starting (Sprint 2.2), not deleted. Revisit only alongside a WS1 canonical-package-handoff decision, which is a separate, larger workstream than this task's scope. |
| `run_portfolio.py`'s missing `startup_recovery` wiring | Adding it would be new investment in a runner intentionally kept non-canonical | Not fixed — consistent with prior sprints' reasoning ("fixing code slated for retirement is wasted effort") |

### Tier 3 — High risk / requires an owner product decision, not attempted this pass

| Item | Why this needs a decision, not a mechanical merge |
|---|---|
| `bot.py` stack (`OrderManager`, `MetaAPIClient`, `RiskManager`) | Not dead code in the same sense as Tier 1 — it has its own real, passing test suite (`tests/test_ops01_safety.py`, `tests/test_order_manager.py`, `tests/test_metaapi_client.py`, `tests/test_bug01_rpc_timeout.py`) exercising real behavior, just not deployed. Removing it means deleting that coverage; consolidating it means porting behavior into the canonical runner — either is a real scope decision, not a dedup. |
| `adaptive/run_shadow.py` stack (`mt5_executor.py`, `adaptive/engine/risk_manager.py`) | Same reasoning — a real, distinct shadow/paper-trading capability for adaptive strategies, not currently deployed, not equivalent to anything in the canonical pipeline (the canonical runner is single-strategy) |
| Legacy `deploy/gcp-vm1/systemd/*.service` files never installed (`d2e3.*`, `reconcile-positions.*`, `agtrade-deployment-agent.*`) | Zero functional risk either way (never active), but removing deployment artifacts from the repo without confirming they're not a rollback/reference target for a future D2/D3 redeployment is a documentation-hygiene call, not a safety one — flagged, not actioned |

## Dependency notes

- Tier 1 removal has **no dependency on Tier 2 or 3** — it can proceed independently and immediately.
- Tier 2's resolution depends on a WS1 (canonical strategy package) decision that is out of this
  task's scope (`ARCHITECTURE_STABILIZATION_ROADMAP.md` WS1, still open).
- Tier 3 items depend on an explicit product decision this task is not authorized to make
  ("do not implement new trading strategies" / "prefer consolidation over expansion" — neither
  authorizes unilaterally deleting a working, tested, if-dormant capability).

## What this pass will do (Phase 4/5)

Remove the Tier 1 cluster only: `production/engine/{orders,positions,risk}.py`,
`production/{recovery,operations,reporting,api}.py`, and their dedicated test files
(`tests/production/test_system2_platform.py`; `tests/production/test_system2_demo_readiness.py`'s
`ProductionReadAPI` import needs updating or removing, checked individually — it uses fakes, not the
real repository classes, so its *test intent* may be portable even if the import needs to move).

Full test suite runs before and after; startup/broker/recovery/risk of the **actual production
runner** (`run_st_a2_demo.py`, already live) is re-verified after, per Phase 4's own rule of
validating after every migration step — even though this specific removal has zero code-path
overlap with it, this is the safety-critical system in question and gets the same scrutiny
regardless of whether the change was "supposed" to touch it.

## What this pass will NOT do

Merge, delete, or otherwise touch the `bot.py` stack or `adaptive/run_shadow.py` stack. Both remain
exactly as they are, fully documented in the inventory, flagged for an explicit future owner
decision. This is "prefer consolidation over expansion" read correctly: there is no live duplicate
execution path today competing with the canonical runner for traffic or resources — the risk of a
forced merge (breaking dormant-but-real test coverage, or silently dropping a capability someone
may still want) outweighs the cosmetic benefit of a smaller `git ls-files` count.
