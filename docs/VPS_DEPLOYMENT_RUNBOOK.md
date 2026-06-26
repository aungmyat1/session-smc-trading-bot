# VPS Deployment Runbook

This runbook matches the current repository entry points and keeps the execution
path safe:

- VPS 1 is for ST-A2 demo/shadow trading.
- VPS 2 is for research, validation, replay, and backtesting.
- `LIVE_TRADING` remains owner-only and must stay `false` in automation.

## VPS 1 - Demo And Shadow Trading

### One-Time Setup

```bash
git clone https://github.com/aungmyat1/session-smc-trading-bot.git
cd session-smc-trading-bot
pip install -r requirements.txt

cp .env.example .env
nano .env
```

Fill these values in `.env` on VPS 1:

```env
METAAPI_TOKEN=<your MetaAPI token>
METAAPI_ACCOUNT_ID=<your MetaAPI account UUID>
VANTAGE_DEMO_METAAPI_ID=<Vantage MT5 demo account UUID>
TELEGRAM_BOT_TOKEN=<your bot token>
TELEGRAM_CHAT_ID=<your chat ID>
DEMO_ONLY=true
LIVE_TRADING=false
```

### Shadow Mode

Shadow mode logs signals and execution decisions without sending broker orders.

```bash
TRADING_MODE=shadow python3 scripts/run_st_a2_demo.py
```

### Demo Mode

Demo mode connects to the demo account and can place demo orders once the repo
checks pass and `DEMO_ONLY=false` is set manually.

```bash
TRADING_MODE=demo python3 scripts/run_st_a2_demo.py
TRADING_MODE=demo python3 scripts/run_st_a2_demo.py --mode demo --interval 60
```

### Health And Status

```bash
python3 scripts/demo_health_check.py
python3 scripts/demo_status.py
```

### Run In Background

`nohup` and `screen` both work. Use one of these:

```bash
TRADING_MODE=demo nohup python3 scripts/run_st_a2_demo.py --mode demo --interval 60 \
  > logs/demo_run.log 2>&1 &
echo $! > logs/bot.pid
```

```bash
screen -S trading-bot
TRADING_MODE=demo python3 scripts/run_st_a2_demo.py --mode demo --interval 60
# Ctrl+A then D to detach
# screen -r trading-bot to reattach
```

### Docker

```bash
docker build -t smc-bot .
docker run -d \
  --name smc-bot \
  --restart unless-stopped \
  --env-file .env \
  -e TRADING_MODE=demo \
  -v $(pwd)/logs:/app/logs \
  smc-bot
docker logs -f smc-bot
```

## VPS 2 - Strategy Validation And Research

### One-Time Setup

```bash
git clone https://github.com/aungmyat1/session-smc-trading-bot.git
cd session-smc-trading-bot
pip install -r requirements.txt

cp .env.example .env
nano .env
```

VPS 2 does not need broker credentials for backtesting and validation.

### Download Historical Data

Run this once per symbol range:

```bash
python3 scripts/download_dukascopy.py --symbols EURUSD GBPUSD --start 2021-01 --end 2026-06
```

### Spread Capture And Gate Monitoring

```bash
python3 scripts/capture_spreads.py --commission-pips 0.0 --interval 30
python3 scripts/spread_status.py
python3 scripts/check_phase2_completion.py
```

### Build Timeframes

```bash
python3 scripts/build_timeframes.py --symbols EURUSD GBPUSD --timeframes M15 H1 H4
```

### Validate Dataset

```bash
python3 scripts/validate_dataset.py --symbols EURUSD GBPUSD --timeframes M15 H1 H4
```

### Phase-0 Backtest

```bash
python3 scripts/backtest_session_liquidity.py \
  --symbols EURUSD GBPUSD \
  --start 2021-01-01 --end 2026-01-01 \
  --json-out reports/backtest/ST-A2_backtest.json
```

### Pending D2E3 Holdout

```bash
python3 scripts/backtest_d2_holdout.py
```

### Historical Replay Audit

Replay is the execution-logic check. It does not replace the backtest gate.

```bash
python3 scripts/historical_replay.py \
  --symbol EURUSD \
  --start 2021-01-01 \
  --end 2026-01-01 \
  --json-out reports/HISTORICAL_REPLAY_AUDIT.json
```

### Validation Gate

```bash
python3 scripts/run_validation_gate.py \
  --strategy ST-A2 \
  --mode backtest \
  --backtest-json reports/backtest/ST-A2_backtest.json \
  --latest-json reports/backtest/ST-A2_backtest.json \
  --stage backtest \
  --outdir reports/validation
```

### E6 Revalidation Pipeline

```bash
bash scripts/run_e6_revalidation.sh
```

### Research Queue

```bash
python3 scripts/run_research_queue.py
```

### Strategy Stats

```bash
python3 scripts/strategy_stats.py
```

## Live Trading Gate

Live trading is not automated. It remains owner-only.

Only after a clean demo period and an explicit owner approval should the live
configuration be changed manually.

```env
LIVE_TRADING=true
DEMO_ONLY=false
METAAPI_ACCOUNT_ID=<live account UUID>
```

After that, restart the already-installed service or process manager manually.
