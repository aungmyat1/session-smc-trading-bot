# Project Objective And Fastest Path To Live Trading

## Objective

Deploy ST-A2 (Session Liquidity Sweep Reversal) as a live automated forex
trading bot on EURUSD and GBPUSD via Vantage MT5, generating consistent
risk-adjusted returns at 0.25% to 1.0% risk per trade with automated circuit
breakers, Telegram alerts, and a two-VPS architecture separating execution from
research.

Current phase: Phase-1 demo validation.

ST-A2 has passed Phase-0 backtest (`n=169`, `PF_2x=1.025`, run
`20260621T100458-183aaa`). The execution layer is deployed and the bot is
running (`LIVE_TRADING=false`). The remaining blockers before live execution are
cost validation (E5+E6) and a 7-day execution gate (E1-E4).

Strategy registry state: `walk_forward` - `last_svos_verification_ready: true`
(see `config/strategy_catalog.yaml`).

For authoritative strategy state and lifecycle position, use:

- `config/strategy_catalog.yaml`
- `docs/SYSTEM_ARCHITECTURE.md`
- `docs/SVOS_LIFECYCLE_WORKFLOW.md`
- `docs/OPS02_REVISED_GATE.md`
- `docs/PROJECT_LIVE_STATUS_TIMELINE.md`

Current operational validation pipeline in this repo:

```text
Strategy Intake
  ↓
Strategy Audit
  ↓
Strategy Enhancement
  ↓
Historical Replay
  ↓
Backtest
  ↓
Robustness
  ↓
Verification Ready
  ↓
Virtual Demo Trading
  ↓
Production Approval
```

This is the current implemented workflow. It is different from the older
"target architecture" phrasing because audit failures now feed into a concrete
enhancement stage before replay and backtest.

## Fastest Path to Live

The revised demo gate (`docs/OPS02_REVISED_GATE.md`, owner-approved 2026-06-24)
replaces the original 30-day/50-trade requirement. The correct sequence is:

### Gate E5 - Spread Capture (IN PROGRESS)

- VPS 1. Running since 2026-06-24 06:01 UTC (`tmux spreads`).
- Pass condition: at least 5 London sessions and 5 New York sessions captured.
  Output: `research/spread_samples.csv`
- Monitor: `python3 scripts/spread_status.py`
- Projected gate: ~2026-06-30.
- Preliminary (1 session): EURUSD 1.35pip, GBPUSD 1.56pip - both below
  placeholder costs. Projected `PF_2x` ~1.035.

### Gate E6 - Cost Revalidation (BLOCKED on E5)

- VPS 2. Run immediately when `python3 scripts/check_phase2_completion.py`
  exits 0. Package is ready: `bash scripts/run_e6_revalidation.sh`.
- Pass condition: `PF_2x >= 1.00` at real Vantage costs.
- Decision table (from `docs/OPS02_REVISED_GATE.md`):
  - `PF_2x > 1.05` -> continue to E1-E4
  - `PF_2x 1.00-1.05` -> demo only; no micro-live until confirmed
  - `PF_2x < 1.00` -> stop. No demo. No live. Prepare ST-A3 recovery options.

### Gates E1-E4 - 7-Day Execution Gate (BLOCKED on E5+E6)

All four run concurrently inside a single 7-day window (`LIVE_TRADING=true`).

- E1: 7-day runtime - 0 crashes, heartbeat gaps < 600s, health checks clean.
- E2: at least 1 `SIGNAL_CREATED` event in `logs/trades.jsonl` with correct fields.
- E3: at least 1 complete order lifecycle (fill or valid broker rejection).
- E4: manual restart test on Day 2-3; state intact, no spurious orders.

OPS-01 stability prerequisite: 7-day run in progress, expires 2026-06-28.

### Micro-Live (Owner Decision - BLOCKED on E1-E4)

Owner-stated parameters (from `docs/OPS02_REVISED_GATE.md`):

- $1,000 Vantage live account
- 0.25% risk per trade
- 1 max open position
- 3R daily loss limit, 10% account drawdown kill switch
- first 20 trades = validation period before any size increase

Fastest path to micro-live: ~14-21 days from spread capture start.

## VPS Split

- VPS 1: execution, demo/live bot, spread capture
- VPS 2: backtesting, holdout evaluation, research queue, E6 revalidation

## Notes

- Strategy audit validates whether the specification is complete,
  measurable, and replay-ready before any data is consumed.
- Strategy enhancement converts audit failures into concrete fixes,
  clarifying questions, and proposed specification revisions.
- Historical replay validates execution logic and signal timing after the
  strategy has cleared audit and enhancement.
- Backtest validates profitability and cost sensitivity; ST-A2 has passed
  this gate (`docs/VERDICT_LOG.md`, run `20260621T100458-183aaa`).
- The original 30-day/50-trade demo requirement is replaced by the owner-
  approved E5+E6+E1-E4 gate sequence. Demo validates execution correctness,
  not profitability (which is Phase-0's job).
