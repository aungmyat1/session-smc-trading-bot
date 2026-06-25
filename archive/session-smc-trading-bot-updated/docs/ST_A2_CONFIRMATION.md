# ST_A2_CONFIRMATION.md
# Strategy A2 — Min SL Floor 5 pip — Production Backtest Confirmation
# Run: 20260621T100458-183aaa  |  Date: 2026-06-21

---

## Verdict

### ✅ ST-A2 CONFIRMED

PF_2x = 1.025 > 1.0 at RR5 (gate: > 1.0)
PF_2x = 1.022 > 1.0 at RR4 (gate: > 1.0)

Both RR4 and RR5 pass the Phase-0 gate.
Production code matches EXP-01 post-hoc prediction exactly (n=169, PF_2x=1.025).

---

## Change Applied

| Field | ST-A | ST-A2 |
|---|---|---|
| min_sl_pips | — (no filter) | 5.0 |
| File changed | `DEFAULT_CONFIG` | `session_strategy.py` line 32 |
| Filter location | — | After `build_signal()`, before signal append |
| Trades removed | — | 12 (sweep wicks < 5 pip) |

---

## ST-A vs ST-A2 Comparison (RR5, combined)

| Metric | ST-A | ST-A2 | Δ |
|---|---|---|---|
| Trade Count | 181 | 169 | −12 |
| Win Rate | 31.5% | 32.0% | +0.5pp |
| Gross PF | 1.327 | 1.299 | −0.028 |
| Net PF (std) | 1.126 | 1.151 | +0.025 |
| Net PF (2×) | 0.965 | 1.025 | **+0.060** |
| Max DD | 28.14R | 18.72R | −9.42R |
| Phase-0 Gate | ❌ FAIL | ✅ PASS | — |

Gross PF falls slightly (12 removed trades had higher gross R) but net PF improves
because those trades had spread_cost_R ≥ 1.0R — their gross wins were consumed entirely
by spread cost at 2× stress, making them net-negative contributors.

Max DD improvement (28.14R → 18.72R) is a material risk reduction: −33.5%.

---

## Full Results (ST-A2, both RR variants that pass)

| RR | Trades | Win% | Gross PF | Net PF (std) | Net PF (2×) | Max DD | Gate |
|---|---|---|---|---|---|---|---|
| 2 | 169 | 38.5% | 1.152 | 1.003 | 0.877 | 11.57R | ❌ FAIL |
| 3 | 169 | 34.3% | 1.225 | 1.078 | 0.954 | 11.18R | ❌ FAIL |
| 4 | 169 | 32.5% | 1.299 | 1.149 | 1.022 | 16.72R | ✅ PASS |
| 5 | 169 | 32.0% | 1.299 | 1.151 | 1.025 | 18.72R | ✅ PASS |

**Operating RR: 5** (max PF_2x; matches EXP-01 registered spec)

---

## Per-Symbol (RR5)

| Symbol | Trades | Win% | Net PF (std) | Net PF (2×) | Max DD |
|---|---|---|---|---|---|
| EURUSD | 105 | 29.5% | 1.059 | 0.945 | 14.00R |
| GBPUSD |  64 | 35.9% | 1.313 | 1.168 |  9.70R |
| Combined | 169 | 32.0% | 1.151 | 1.025 | 18.72R |

Note: EURUSD alone still fails 2× stress (0.945). Combined passes due to GBPUSD strength.
This is a known asymmetry — watch EURUSD performance closely in paper trade.

---

## Per-Session (RR5, combined, standard spread)

| Session | Trades | Win% | Net PF (std) |
|---|---|---|---|
| london   | 118 | 28.0% | 0.949 |
| new_york |  51 | 41.2% | 1.731 |

London still below 1.0 at standard spread. NY is the primary edge driver.
This is the known structural pattern (GBPUSD London = 0.701 PF_2x, EXP-04 fallback candidate).

---

## Per-Year (combined, RR5, standard spread)

| Year | Trades | Win% | Net PF | Note |
|---|---|---|---|---|
| 2021 | 15 | 26.7% | 0.830 ⚠ | EURUSD only (GBPUSD data from 2023) |
| 2022 | 25 | 36.0% | 1.416 | |
| 2023 | 48 | 27.1% | 0.878 ⚠ | First GBPUSD year; London-heavy |
| 2024 | 20 | 40.0% | 1.659 | |
| 2025 | 43 | 27.9% | 0.886 ⚠ | Trending regime |
| 2026 | 18 | 44.4% | 2.182 | Partial (Jan–Jun) |

2021, 2023, 2025 are losing years. The 5-yr aggregate still passes the gate.
Paper trade must be monitored for regime sensitivity.

---

## Risk Flags for Paper Trade

1. **EURUSD 2× stress = 0.945** — below gate individually. Combined passes only because GBPUSD
   adds sufficient positive R. Monitor EURUSD drawdown separately in demo.

2. **London win rate = 28.0%** — below 30%. If paper trade London win rate falls below 25%
   over 20+ trades, flag for review.

3. **3 of 6 years negative** — strategy is regime-sensitive. Expect drawdown periods in
   trending/volatile environments (2023, 2025 pattern).

4. **n=169 over 4.9yr** — low frequency: ~34 trades/year, ~3/month. 30-day paper trade
   may capture only 3–5 trades. Statistical validity requires the full 50-trade minimum
   (PHASE_PLAN §1) before proceeding to Phase-2 micro live.

---

## Gate Status

| Gate | Condition | Value | Status |
|---|---|---|---|
| Trade count | ≥ 100 | 169 | ✅ |
| Net PF (std) | > 1.0 | 1.151 | ✅ |
| Net PF (2×) | > 1.0 | 1.025 | ✅ |
| Phase-0 | All three | — | ✅ PASS |

---

## Files

- `strategy/session_liquidity/session_strategy.py` — filter enforced at line 178
- `strategy/session_liquidity/config.yaml` — `min_sl_pips: 5.0` documented
- `research/backtest_runs.csv` — run 20260621T100458-183aaa logged (8 rows)
- `research/trades.csv` — 676 rows added (169 signals × 4 RR variants)
- `docs/BACKTEST_RESULTS.md` — updated with ST-A2 metrics

*Run ID: 20260621T100458-183aaa | Confirmed: 2026-06-21*
