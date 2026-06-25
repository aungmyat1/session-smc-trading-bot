# Setup A — Full 11-Phase Replay Report (Dukascopy Parquet)
Symbol: EURUSD | Period: 2024-01-01 → 2024-12-31
Session window: 48 bars (12h00m) | Session range: first 8 bars (2h) | Advance: 12 bars (3h)
D2 context gates: OFF (pure 11-phase baseline)
Generated: 2026-06-25T16:16:17Z

## Core Metrics

| Metric | Gross | Net (std 1.4pip) | Net (2× stress 2.8pip) |
|---|---|---|---|
| Trades (n) | 12 | 12 | 12 |
| Win Rate | 16.7% | 16.7% | 16.7% |
| Profit Factor | 0.481 | 0.315 | 0.218 |
| Avg R | -0.4326 | -0.7724 | -1.1122 |
| Total R | -5.191 | -9.269 | -13.347 |
| Max DD | 5.19R | 9.27R | 13.35R |

**Phase-0 gate (n≥50 AND PF>1.0 std AND 2×): ❌ FAIL**

## Monthly Breakdown (net std)

| Month | n | WR% | PF | Total R |
|---|---|---|---|---|
| 2024-03 | 2 | 0.0% | 0.000 | -2.992R |
| 2024-06 | 2 | 50.0% | 0.477 | -0.694R |
| 2024-08 | 2 | 0.0% | 0.000 | -2.831R |
| 2024-09 | 2 | 50.0% | 2.832 | +2.352R |
| 2024-10 | 2 | 0.0% | 0.000 | -2.583R |
| 2024-11 | 2 | 0.0% | 0.000 | -2.521R |

## Session Breakdown (net std)

| Session | n | WR% | PF | Total R | Max DD |
|---|---|---|---|---|---|
| london | 11 | 9.1% | 0.269 | -9.902R | 9.90R |
| ny | 1 | 100.0% | ∞ | +0.633R | 0.00R |

## Exit Breakdown

| Exit | Count |
|---|---|
| SESSION_END | 1 |
| SL | 10 |
| TP1 | 1 |

## Trade Ledger

| # | Date | Time UTC | Session | Dir | SL pip | Gross R | Net R | Exit |
|---|---|---|---|---|---|---|---|---|
| 1 | 2024-03-05 | 15:30 | london | long | 2.6 | -1.000 | -1.544 | SL |
| 2 | 2024-03-27 | 15:30 | london | short | 3.1 | -1.000 | -1.448 | SL |
| 3 | 2024-06-06 | 12:45 | london | long | 4.3 | -1.000 | -1.327 | SL |
| 4 | 2024-06-12 | 18:30 | ny | short | 8.0 | +0.809 | +0.633 | SESSION_END |
| 5 | 2024-08-19 | 12:15 | london | long | 3.7 | -1.000 | -1.376 | SL |
| 6 | 2024-08-27 | 15:15 | london | long | 3.1 | -1.000 | -1.455 | SL |
| 7 | 2024-09-03 | 14:30 | london | short | 4.9 | -1.000 | -1.284 | SL |
| 8 | 2024-09-11 | 13:00 | london | short | 3.9 | +4.000 | +3.636 | TP1 |
| 9 | 2024-10-04 | 13:00 | london | short | 3.6 | -1.000 | -1.389 | SL |
| 10 | 2024-10-30 | 13:00 | london | short | 7.2 | -1.000 | -1.194 | SL |
| 11 | 2024-11-01 | 13:00 | london | long | 5.1 | -1.000 | -1.276 | SL |
| 12 | 2024-11-08 | 14:00 | london | short | 5.7 | -1.000 | -1.246 | SL |