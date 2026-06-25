# HISTORICAL REPLAY FINAL VERDICT
**Date:** 2026-06-25 | Updated bot: session-smc-trading-bot-updated
**Strategy:** ST-A2 — Session Liquidity Sweep + Displacement
**Reviewer:** Claude Code — automated audit (no live trading, no parameters modified)

---

## Phases Completed

| Phase | Description | Verdict |
|-------|-------------|---------|
| A | Lookahead audit: 18 causal checks | ✅ PASS |
| B | Replay engine review: O(n) batch confirmed | ✅ PASS |
| C | Data audit: EURUSD + GBPUSD, zero issues | ✅ PASS |
| D | Historical replay Jan–Jun 2026: 18 trades, PF=1.879 | ✅ PASS |
| E | Signal quality: 18/18 VALID, 0 INVALID, 0 logic bugs | ✅ PASS |
| F | Performance audit: +7.50R net, max DD=5.32R, expectancy +0.417R | ✅ PASS |
| G | Deployment readiness gate | ⚠ CONDITIONAL |
| 0 (5yr) | Phase-0 gate: 169 trades, PF_std=1.151, PF_2x=1.025 | ✅ PASS |

---

## Summary of Evidence

### Statistical Performance (6-month replay)
```
Trades:          18  (EURUSD: 6, GBPUSD: 12)
Win rate:        50.0%
Profit Factor:   1.879  (standard spread)
Est. PF 2×:     ~1.52  (both above 1.0 gate)
Net R:          +7.50R
Expectancy:     +0.417R/trade
Max drawdown:    5.32R  (Jan 19–26 streak; recovered within 2 trades)
Max loss streak: 5      (bot would halt per §4; resumes next day)
```

### 5-Year Phase-0 Gate (pre-existing validated backtest)
```
Trades:          169  (≥ 50 gate: ✅)
PF at standard:  1.151 (> 1.0: ✅)
PF at 2× stress: 1.025 (> 1.0: ✅)
Signal rate:     ~7.5% of sessions — selective, consistent with 6-month replay
```

### Signal Integrity
- All 18 signals structurally valid (correct EST/EDT killzone, confirmed sweep + displacement)
- No lookahead violations (18-check audit, Phase A)
- No logic bugs found
- "Other" session label in Phase D was a UTC mislabeling in reporting — not a strategy issue

### Infrastructure
- 160 files compile cleanly; 22 critical modules import without error
- Risk guards active: daily halt, drawdown kill switch, consecutive loss halt
- Account isolated by magic number (21099 vs production 21001/21002)
- `LIVE_TRADING=False` by default

---

## Condition Applied (Fixed Before Verdict)

**BUG: `bot.py` line 72** — `METAAPI_ACCOUNT_ID` read from wrong env var.

```python
# BEFORE (broken):
METAAPI_ACCOUNT_ID: str = os.getenv("METAAPI_ACCOUNT_ID", "")

# AFTER (fixed — applied 2026-06-25):
METAAPI_ACCOUNT_ID: str = os.getenv("VANTAGE_DEMO_METAAPI_ID", "")
```

This fix has been applied. The condition is resolved.

---

## Remaining Observations (Non-Blocking)

1. **6-month trade count (18) is below the 30-trade sample guideline** for the
   rolling window. The 5yr baseline (169) satisfies the formal Phase-0 gate.
   Demo trading will accumulate the next sample. No remediation required now.

2. **`session_label()` in `replay_runner.py`** uses UTC windows instead of EST/EDT,
   causing reporting mislabels in Phase D. Does not affect signal generation or
   execution. Low-priority cosmetic fix only.

3. **XAUUSD configured in `demo.yaml`** but no historical data exists. EURUSD/GBPUSD
   are unaffected. Remove XAUUSD from `allowed_pairs` before running to avoid a
   potential "no data" error at startup.

---

## VERDICT

---

# CONDITIONAL PASS

---

**Condition met:** `bot.py` line 72 env var bug has been fixed (2026-06-25).
**Next step:** Deploy to VT Markets demo account with `LIVE_TRADING=False`.
Track the next 30 demo trades before assessing Phase-1 paper trade outcome.

**Do not:** Enable live trading, change strategy parameters, or modify risk settings
until 30 demo trades complete and Phase-1 gate is evaluated.

---

## Deployment Checklist

Before starting the bot on VT Markets demo:

- [ ] `.env` populated: `VANTAGE_DEMO_METAAPI_ID`, `METAAPI_TOKEN`, `TELEGRAM_BOT_TOKEN`,
       `TELEGRAM_CHAT_ID`, `LIVE_TRADING=false`
- [ ] `XAUUSD` removed from `config/demo.yaml` `allowed_pairs` (optional but clean)
- [ ] Confirm MetaAPI demo account is active and synchronized
- [ ] Confirm Telegram bot is reachable (send a test message)
- [ ] Start bot and verify the startup Telegram message fires
- [ ] Monitor first London session for signal (expected ~every 3–5 trading days)
- [ ] Log each demo trade in `docs/VERDICT_LOG.md` as it closes
