#!/usr/bin/env python3
"""
Phase-0 holdout run for ST-D2-E3-OPT2.

Params locked per ST-D2-E3-OPT2 spec (docs/VERDICT_LOG.md):
  - Session: 08:00–16:00 UTC
  - Entry: fifty_pullback (limit at 50% of MSS candle, wait 3 bars)
  - Target: liq_or_rr — PDL/PDH if reward ≥ 1.2R, else fixed 2R
  - Stop: sweep extreme + 2pip buffer; 2–25pip gate
  - Risk: 0.5% per trade | Max hold: 32 M15 bars (8h) | Cooldown: 3 bars

Data note: M15 bars used as proxy (no 5M data).
  confirm_bars=12 M15 = 3h confirm window (spec: 12×5M = 1h).
"""
from __future__ import annotations
import json
import math
from pathlib import Path
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).parent))

from backtest_d2_daily_bias import (
    OUTDIR as DATA_DIR, add_context, pivot_swings, PIP_SIZE,
    INITIAL_CAPITAL, RISK_PER_TRADE, prepare_data,
)
from optimize_d2_rules import backtest, Params

OUTDIR = Path('backtest_output_d2_holdout')
OUTDIR.mkdir(exist_ok=True)

# ── LOCKED params — ST-D2-E3-OPT2 (do not change) ────────────────────────────
BEST = Params(
    session_start=8, session_end=16,
    confirm_bars=12, entry_mode='fifty_pullback', entry_wait=3,
    rr=2.0, target_mode='liq_or_rr',
    max_stop_pips=25, min_stop_pips=2.0,
    cooldown=3, trend_filter='none',
)

HOLDOUT_START = '2021-06-21'
HOLDOUT_END   = '2025-11-30'
SYMBOLS = ['EURUSD', 'GBPUSD']

COSTS = {
    'EURUSD': {'std': 1.4, 'stress2x': 2.8},
    'GBPUSD': {'std': 1.8, 'stress2x': 3.6},
}


def load_holdout(symbol: str) -> pd.DataFrame:
    p = DATA_DIR / f'{symbol}_5m_{HOLDOUT_START}_{HOLDOUT_END}.csv'
    df = pd.read_csv(p, parse_dates=['timestamp'], index_col='timestamp')
    df = pivot_swings(add_context(df))
    df['median_spread'] = df['spread'].rolling(24*4*10, min_periods=100).median().bfill()
    return df


def net_summary(trades: pd.DataFrame, symbol: str) -> dict:
    if trades.empty:
        return {}
    pip = PIP_SIZE[symbol]
    cost_std = COSTS[symbol]['std']
    cost_2x  = COSTS[symbol]['stress2x']
    trades = trades.copy()
    trades['sl_pips'] = abs(trades['entry'] - trades['stop']) / pip
    trades['fee_r_std'] = cost_std / trades['sl_pips']
    trades['fee_r_2x']  = cost_2x  / trades['sl_pips']
    trades['net_r_std'] = trades['r'] - trades['fee_r_std']
    trades['net_r_2x']  = trades['r'] - trades['fee_r_2x']

    def pf(r_col):
        w = trades.loc[trades[r_col] > 0, r_col].sum()
        l = abs(trades.loc[trades[r_col] <= 0, r_col].sum())
        return round(float(w / l), 3) if l else math.inf

    gross_pf = pf('r')
    return {
        'n': int(len(trades)),
        'wins': int((trades.r > 0).sum()),
        'win_rate_pct': round((trades.r > 0).mean() * 100, 1),
        'gross_pf': gross_pf,
        'net_pf_std': pf('net_r_std'),
        'net_pf_2x':  pf('net_r_2x'),
        'avg_r_gross': round(float(trades.r.mean()), 3),
        'avg_r_net_std': round(float(trades.net_r_std.mean()), 3),
        'total_r_gross': round(float(trades.r.sum()), 2),
        'total_r_net_std': round(float(trades.net_r_std.sum()), 2),
        'avg_sl_pips': round(float(trades.sl_pips.mean()), 1),
        'avg_fee_r': round(float(trades.fee_r_std.mean()), 3),
    }


def main():
    prepare_data(start=HOLDOUT_START, end=HOLDOUT_END)

    all_trades = []
    per_symbol = {}

    for sym in SYMBOLS:
        print(f'Loading {sym} holdout …')
        df = load_holdout(sym)
        tr = backtest(df, sym, BEST)
        tr.to_csv(OUTDIR / f'{sym}_holdout_trades.csv', index=False)
        stats = net_summary(tr, sym)
        per_symbol[sym] = stats
        all_trades.append(tr)
        gbpusd_start = '2023-03-13'
        print(f'  {sym}: n={stats.get("n",0)}  gross_pf={stats.get("gross_pf")}  net_std={stats.get("net_pf_std")}  net_2x={stats.get("net_pf_2x")}  wr={stats.get("win_rate_pct")}%')

    # Portfolio (combine both symbols)
    merged = pd.concat(all_trades, ignore_index=True).sort_values('entry_time') if all_trades else pd.DataFrame()
    merged.to_csv(OUTDIR / 'all_holdout_trades.csv', index=False)

    # Combined net PF (merge R streams, apply per-symbol fee)
    pip = PIP_SIZE['EURUSD']
    if not merged.empty:
        merged['pip'] = merged.symbol.map(PIP_SIZE)
        merged['sl_pips'] = abs(merged.entry - merged.stop) / merged.pip
        merged['fee_std'] = merged.symbol.map({s: COSTS[s]['std'] for s in SYMBOLS})
        merged['fee_2x']  = merged.symbol.map({s: COSTS[s]['stress2x'] for s in SYMBOLS})
        merged['net_r_std'] = merged.r - merged.fee_std / merged.sl_pips
        merged['net_r_2x']  = merged.r - merged.fee_2x  / merged.sl_pips
        def pf_col(col):
            w = merged.loc[merged[col]>0, col].sum()
            l = abs(merged.loc[merged[col]<=0, col].sum())
            return round(float(w/l), 3) if l else math.inf
        eq = INITIAL_CAPITAL + (merged.r * INITIAL_CAPITAL * RISK_PER_TRADE).cumsum()
        eq2 = pd.concat([pd.Series([INITIAL_CAPITAL]), eq], ignore_index=True)
        dd = ((eq2 - eq2.cummax()) / eq2.cummax()).min()
        portfolio = {
            'n': int(len(merged)),
            'wins': int((merged.r > 0).sum()),
            'win_rate_pct': round((merged.r > 0).mean() * 100, 1),
            'gross_pf': pf_col('r'),
            'net_pf_std': pf_col('net_r_std'),
            'net_pf_2x':  pf_col('net_r_2x'),
            'avg_r_gross': round(float(merged.r.mean()), 3),
            'avg_r_net_std': round(float(merged.net_r_std.mean()), 3),
            'max_drawdown_pct': round(float(dd * 100), 2),
        }
    else:
        portfolio = {}

    result = {
        'trial': 'ST-D2-E3-OPT2',
        'holdout': f'{HOLDOUT_START} → {HOLDOUT_END}',
        'params': BEST.__dict__,
        'per_symbol': per_symbol,
        'portfolio': portfolio,
        'gate': {
            'n_pass': portfolio.get('n', 0) >= 50,
            'net_pf_std_pass': portfolio.get('net_pf_std', 0) > 1.0,
            'net_pf_2x_pass':  portfolio.get('net_pf_2x', 0) > 1.0,
        },
    }
    result['gate']['PASS'] = all(result['gate'].values())

    json.dump(result, open(OUTDIR / 'holdout_result.json', 'w'), indent=2)

    print('\n=== HOLDOUT RESULT ===')
    print(json.dumps(result, indent=2))
    print()
    if result['gate']['PASS']:
        print('✅ Phase-0 PASS — all three gates met.')
    else:
        fails = [k for k, v in result['gate'].items() if k != 'PASS' and not v]
        print(f'❌ Phase-0 FAIL — gates failed: {fails}')


if __name__ == '__main__':
    main()
