# Optimized D2 Strategy Rules

Source: D2 video E3 model — price sweeps PDH/PDL liquidity → M15 MSS confirmation → enter on reversal.
Data: M15 bars (Dec 2025 – May 2026). confirm_bars = M15 intervals after sweep.

## Selected parameters
```json
{
  "session_start": 12,
  "session_end": 17,
  "confirm_bars": 12,
  "entry_mode": "fifty_pullback",
  "entry_wait": 3,
  "rr": 2.0,
  "target_mode": "fixed_rr",
  "max_stop_pips": 25,
  "min_stop_pips": 2.0,
  "cooldown": 3,
  "trend_filter": "none"
}
```

## Walk-forward split
- Train: 2025-12-01 to 2026-03-31
- Validation: 2026-04-01 to 2026-05-31

### Train
```json
{
  "trades": 20,
  "wins": 11,
  "losses": 9,
  "win_rate_pct": 55.0,
  "total_R": 6.08,
  "avg_R": 0.304,
  "profit_factor_R": 1.776,
  "max_drawdown_pct": -3.78,
  "final_equity": 10605.45,
  "return_pct": 6.05
}
```

### Validation
```json
{
  "trades": 10,
  "wins": 5,
  "losses": 5,
  "win_rate_pct": 50.0,
  "total_R": 4.06,
  "avg_R": 0.406,
  "profit_factor_R": 2.32,
  "max_drawdown_pct": -1.98,
  "final_equity": 10403.42,
  "return_pct": 4.03
}
```

## Full 6-month result with selected rules
| Symbol | Trades | Win rate | Total R | Avg R | PF | Max DD | Return |
|---|---:|---:|---:|---:|---:|---:|---:|
| EURUSD | 16 | 43.75% | 2.0 | 0.125 | 1.338 | -3.78% | 1.92% |
| GBPUSD | 15 | 60.0% | 8.02 | 0.535 | 2.565 | -3.09% | 8.19% |

### Portfolio proxy
```json
{
  "trades": 31,
  "wins": 16,
  "losses": 15,
  "win_rate_pct": 51.61,
  "total_R": 10.02,
  "avg_R": 0.323,
  "profit_factor_R": 1.908,
  "max_drawdown_pct": -3.59,
  "final_equity": 11011.82,
  "return_pct": 10.12
}
```

## Optimized rules for code agent
1. Trade only during **12:00–17:00 UTC**.
2. Mark previous day high/low as primary D2 liquidity targets.
3. After PDH/PDL sweep, wait up to **12** M15 bars (180 min) for MSS (close beyond recent swing).
4. Entry mode: **fifty_pullback**. If `fifty_pullback`, place limit at 50% of MSS candle and wait **3** bars (45 min).
5. Stop: between **2.0 and 25 pips**; SL beyond sweep extreme + 2.0pip buffer.
6. Target mode: **fixed_rr**, RR = **2.0**.
7. H1 trend filter: **none** (none = trade both directions; with_1h = align; counter_1h = fade).
8. Cooldown: 3 M15 bars after a closed trade before seeking the next setup.

## Warning
Optimized on 6 months of M15 data — small sample, overfitting risk is high.
Treat best parameters as a starting hypothesis only. Run forward demo ≥ 30 days before live.