# Verdict Log — Session & SMC Trading Bot

One row per trial. Never delete entries. Every parameter change = new row.
Fee model: VT Markets Standard — spread + 0.6pip commission RT.
Gate: n ≥ 50 AND net PF > 1.0 at BOTH standard AND 2× spread stress.

Reference failures from simple-smc-ag-trading-bot (do not re-run):
- T27: EURUSD session-box sweep only — net PF=0.58 FAIL
- T28: GBPUSD session-box sweep only — net PF=0.95 FAIL (2× stress)
- T29-EUR: EURUSD BOS-retest continuation — gross PF=0.83 FAIL
- T29-GBP: GBPUSD BOS-retest continuation — 2× stress FAIL
- ST-1: Session IB sweep + CHoCH (entry at close, not retest) — FAIL

---

## Results

| Trial | Date | Signal | TF | Pairs | n | Gross PF | Avg fee (pip) | Net PF (std) | Net PF (2×) | Win% | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ST-A | 2026-06-21 | Sweep Reversal: 4H+1H bias → Asian range build → session sweep → 15M displacement (body > 1.2×ATR, strict close_pos) → entry at displacement close. SL = sweep wick − 2pip buffer. TP1=4R(75%)→BE, TP2=5R+. Session close rule. London 06-09 UTC, NY 11-14 UTC (EDT). No min SL filter. | 4H+M15 | EUR+GBP | 181 | 1.327 | EURUSD 1.4pip / GBPUSD 1.8pip RT | 1.126 | 0.965 | 31.5% | **FAIL** — passes std at RR3–5 but 2× stress fails all RR variants. Gap at RR5: 0.035. GBPUSD London (PF_2x=0.701) identified as primary drag. Run: 20260621T060745-f6ac57. See BACKTEST_RESULTS.md |
| ST-A2 | 2026-06-21 | ST-A + min_sl_pips ≥ 5.0 gate. All other parameters unchanged. 12 of 181 ST-A trades removed (sweep wick < 5pip). Production code confirmed: `session_strategy.py` DEFAULT_CONFIG + post-build_signal() reject. | 4H+M15 | EUR+GBP | 169 | 1.299 | EURUSD 1.4pip / GBPUSD 1.8pip RT | 1.151 | 1.025 | 32.0% | **PASS** ✅ — Production run 20260621T100458-183aaa confirms EXP-01 post-hoc exactly. RR4 also passes (PF_2x=1.022). Max DD improved 28.14R→18.72R (−33%). See ST_A2_CONFIRMATION.md |
| ST-B | PENDING | Trend Pullback: same chain, pullback to session midpoint + 15M BOS in trend direction | 4H+1H+15M | EUR+GBP | — | — | — | — | — | — | **PENDING ST-A2 result first** |
| ST-C | PENDING | Range Fade: range session + rejection at session extreme + 15M rejection candle | 4H+1H+15M | EUR+GBP | — | — | — | — | — | — | **PENDING ST-A2 result first** |
