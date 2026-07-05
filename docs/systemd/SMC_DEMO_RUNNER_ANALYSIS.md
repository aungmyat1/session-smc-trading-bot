# smc-demo-runner.service — Crash-Loop Analysis

Date: 2026-07-04T16:50Z
Status: Investigation only — service NOT modified
Restart count at time of writing: 173+ (climbing, ~1 restart per RestartSec=15)

---

## 1. What is actually failing

Chain of execution: `smc-demo-runner.service` → `deploy/gcp-vm1/run_smc_demo.sh` → `scripts/run_strategy_demo.py` (a thin `runpy.run_path` shim, confirmed via its own source — 12 lines, just re-executes `run_st_a2_demo.py` under `__main__`) → `scripts/run_st_a2_demo.py`'s argparse.

Exact failure, confirmed via `journalctl -u smc-demo-runner.service`:

```
run_st_a2_demo.py: error: argument --strategy: invalid choice: 'SMCOrderBlockFVGSession'
(choose from 'AdaptiveSMC', 'LondonBreakout', 'NYMomentum', 'ST-A2', 'VWAPBreakout', 'VWAPMeanReversion')
```

The process exits with code 2 (argparse's standard usage-error exit code) in under one second, before any market data fetch, broker connection, or lifecycle/governance check ever runs. `systemd` (`Restart=always`, `RestartSec=15`) then restarts it, forever.

## 2. Why: root cause, not drift

`deploy/gcp-vm1/run_smc_demo.sh` hardcodes `--strategy SMCOrderBlockFVGSession`. Git history
(`git log -p -- deploy/gcp-vm1/run_smc_demo.sh`) shows this argument was present in the **first**
commit that introduced the file — there is no prior working value that later "drifted" away. This
is an integration gap from day one, not a regression:

- `strategies/adapters/smc_ob_fvg_session_adapter.py` exists and defines a real
  `SMCOrderBlockFVGSessionAdapter(BaseStrategy)` class — the strategy logic itself was built.
- But `strategies/adapters/__init__.py`'s `ADAPTER_TYPES` registry — the dict `run_st_a2_demo.py`'s
  `--strategy` argparse `choices=` is generated from — was **never updated** to include it. `git log`
  on that file shows three commits, none adding this entry.
- The deployment wrapper and the systemd unit's own `Description=SMC OB+FVG strategy demo runner`
  were written assuming the adapter would be registered and runnable; that registration step was
  never completed.

**No environment variables, file moves, or dependency changes are involved.** `EnvironmentFile=/etc/session-smc-trading-bot/live-dashboard.env` correctly sets `REPO_DIR`, `PYTHON_BIN`; both resolve correctly on this host.

## 3. Does it belong to the current System 2 architecture?

**No — and this is the more consequential finding.** `config/strategy_catalog.yaml` and
`data/svos/registry/SMCOrderBlockFVGSession/state.json` both confirm this strategy's actual
lifecycle state:

```yaml
SMCOrderBlockFVGSession:
  status: draft
  svos_stage: INTAKE
  approved: false
  version: '0.1'
```

`INTAKE` is the **first** stage of this repo's canonical lifecycle (`DRAFT → INTAKE → AUDIT → ...`,
`svos/lifecycle/manager.py`) — this strategy has not even cleared Phase 0 (Strategy Audit), let
alone Historical Replay, Statistical Validation, or Robustness Validation. `CLAUDE.md`'s governing
rule ("Every strategy passes through all phases in order. No skipping.") means this strategy has no
business generating live demo signals at all yet, independent of the crash.

By contrast, `ST-A2` is the tier1 strategy `config/strategy_portfolio.yaml` and `CLAUDE.md` §1/§6
document as **currently approved to run in demo** (`execution_mode: demo`, tier1) — and it is
literally the strategy `run_st_a2_demo.py` was built around (its own module name, its historical
lifecycle evidence at `docs/VERDICT_LOG.md`). This same session's Sprints 1-3 work
(`SYSTEM2_MASTER_PLAN.md`) extensively exercised and tested this exact runner assuming ST-A2 was
the strategy actually running through it. **It has not been** — the deployed unit has been trying
to run a different, unapproved, unregistered strategy since the unit was created.

## 4. Has it already been replaced / does another service supersede it?

No. `run_portfolio.py` (the architecturally "canonical," `CanonicalExecutionPipeline`-based runner
per `SYSTEM2_MASTER_PLAN.md` Phase 2) has no systemd unit at all (confirmed in this session's Sprint
2.2 work — it is explicitly blocked from starting by default). No other process on this host runs
any strategy adapter. **No strategy has been trading in demo through this systemd unit at any point
its git history covers.**

## 5. Recommendation: Replace

**Replace** the wrapper's target: change `deploy/gcp-vm1/run_smc_demo.sh`'s
`--strategy SMCOrderBlockFVGSession` to `--strategy ST-A2`, keep everything else (unit file, mode,
interval, environment file) unchanged.

**Why Replace, not the other three options:**

- **Not Repair** (register `SMCOrderBlockFVGSession` in `ADAPTER_TYPES` so the current invocation
  works as-is): this would launch a `draft`/`INTAKE`/`approved: false` strategy into live demo signal
  generation — a governance violation of this repo's own phase-gate model, not a fix. Separately,
  `tests/core/test_smc_ob_fvg_session_adapter.py::test_generates_long_signal_on_retrace` is a
  pre-existing, currently-failing test against this exact adapter (confirmed via `git stash`
  earlier this session to predate all recent changes) — the adapter's signal generation itself has
  an open, unresolved defect, a second independent reason not to put it into production as-is.
- **Not Disable**: stops the resource drain but leaves the platform's flagship validated strategy
  (ST-A2) not running anywhere in demo, which is the actual, more important gap this crash-loop was
  masking. Disable is the safe fallback if the owner does not want to make a strategy-selection call
  right now, but it does not fix anything.
- **Not Remove**: the unit, wrapper, and environment plumbing are all correctly built and otherwise
  unmodified since creation — there is no reason to delete deployment infrastructure over a one-line
  argument mismatch.

**Evidence supporting Replace over the alternatives:** ST-A2 is (a) the only strategy in
`config/strategy_portfolio.yaml` at tier1 / demo-approved status relevant to this specific runner's
design, (b) the strategy this exact runner and this session's Sprint 1-3 work already assume is
running and have extensively tested (296+ passing tests touching `run_st_a2_demo.py`'s ST-A2 path
this session alone), and (c) immediately available with zero additional registration or governance
work — it is already a valid `--strategy` choice today.

**Not yet done — awaiting approval per this phase's instructions:** the one-line wrapper edit itself,
and the follow-up restart/verification. No file has been changed to produce this analysis.
