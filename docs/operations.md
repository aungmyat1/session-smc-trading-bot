# Operations Manual

**Document:** Day-to-day operational procedures
**Last updated:** 2026-06-30

---

## Daily Checklist

- [ ] Verify no open positions at session start (00:00 UTC)
- [ ] Check Telegram alerts for overnight errors or incidents
- [ ] Confirm monitoring status is HEALTHY (not ALERT or WATCH)
- [ ] Review daily P&L and drawdown against daily loss limit
- [ ] Verify dataset freshness (no gap > 4 hours in latest data)

---

## Weekly Tasks

- [ ] Review weekly drawdown vs 5% limit
- [ ] Check walk-forward metrics against Phase 4 thresholds
- [ ] Archive weekly P&L report to `reports/weekly/`
- [ ] Update `docs/VERDICT_LOG.md` if any trial completed

---

## Monitoring

### Log Files

| Log | Location | Purpose |
|-----|----------|---------|
| Bot | `logs/bot.log` | Order placement, fills, errors |
| Strategy | `logs/strategy_demo.log` | Signal generation |
| ST-A2 demo | `logs/st_a2_demo.log` | Historical demo logs |

### Incident Classification

| Level | Trigger | Action |
|-------|---------|--------|
| HEALTHY | No anomalies | Continue |
| WATCH | WARN/ERROR in logs (benign pattern) | Review at day end |
| ALERT | FAIL in health check OR DISCONNECTED | Immediate investigation |

### Benign Error Patterns

The following log lines are classified as benign and do not trigger WATCH:
- `engineio.client packet queue is empty, aborting` — normal MetaAPI keep-alive noise

---

## Trial Registration Procedure

Every parameter change or new strategy attempt MUST be registered before running. Never run a backtest without a registered trial ID.

1. Draft the strategy spec change
2. Add a new row to `docs/VERDICT_LOG.md` with status `PENDING`
3. Run the backtest with the registered trial ID
4. Update verdict to `PASS` or `FAIL` with evidence

---

## Revalidation Triggers

A strategy in production must re-enter the qualification pipeline if:

- 6 months of live/demo results show PF < 1.0 on rolling 50-trade window
- Market regime change detected (new volatility floor, spread change)
- Broker updates their spread schedule
- Any code change to the signal generator or risk module

---

## Adding a New Strategy

1. Write the strategy specification following `docs/strategy_specification.md`
2. Add to `config/strategy_catalog.yaml` with `status: draft`
3. Run Phase 0 audit: `python -m svos.application.audit --strategy STRATEGY_NAME`
4. Register the trial in `docs/VERDICT_LOG.md`
5. Fix any Phase 0 FAIL findings and re-audit
6. Proceed through phases in order — no skipping

---

## Known Failure Modes

| Failure | Observed In | Do Not Repeat |
|---------|-------------|---------------|
| Sweep-only entry (no LTF confirmation) | T27, T28 | No edge without confirmation |
| BOS retest continuation without spread buffer | T29-EUR, T29-GBP | Marginal at standard, fails 2× |
| Entry at candle close (too late) | ST-1 | SL too wide by the time of entry |
| Mid-trial parameter tuning | EXP05 | Destroys statistical integrity |

---

## Contact & Escalation

- **Owner:** platform-owner (configure in `.env` or Telegram bot)
- **Telegram bot:** Configured via `TELEGRAM_BOT_TOKEN` in `.env`
- **Incident log:** `docs/INCIDENT_RESPONSE.md`
- **Verdict log:** `docs/VERDICT_LOG.md`
