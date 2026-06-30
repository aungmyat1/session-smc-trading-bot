#!/usr/bin/env python3
"""Optimize D2 rules on cached EURUSD/GBPUSD M15 data (named as 5m for filename compat).

This is not a guarantee; it is an in-sample/out-of-sample rule search to make the D2 video rules more mechanical.

Note: data is M15 bars (not true 5m). confirm_bars represent 15-min multiples.
"""
from __future__ import annotations

import itertools
import json
import math
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import pandas as pd

from backtest_d2_daily_bias import (
    OUTDIR as DATA_DIR, add_context, pivot_swings, PIP_SIZE,
    INITIAL_CAPITAL, RISK_PER_TRADE, SL_BUFFER_PIPS, SPREAD_FILTER_MULT,
    prepare_data,
)

OUTDIR = Path('backtest_output_d2_optimized')
OUTDIR.mkdir(exist_ok=True)
SYMBOLS = ['EURUSD','GBPUSD']
TRAIN_END = pd.Timestamp('2026-04-01 00:00:00+00:00') # Dec-Mar train, Apr-May validation

@dataclass(frozen=True)
class Params:
    session_start: int
    session_end: int
    confirm_bars: int
    entry_mode: str          # next_open or fifty_pullback
    entry_wait: int
    rr: float
    target_mode: str         # fixed_rr or liq_or_rr
    max_stop_pips: float
    min_stop_pips: float
    cooldown: int
    trend_filter: str        # none, with_1h, counter_1h


def load_symbol(symbol):
    p = DATA_DIR / f'{symbol}_5m_2025-12-01_2026-05-31.csv'
    df5 = pd.read_csv(p, parse_dates=['timestamp'], index_col='timestamp')
    df = pivot_swings(add_context(df5))
    df['median_spread'] = df['spread'].rolling(24*4*10, min_periods=100).median().bfill()
    return df


def summarize(trades: pd.DataFrame, initial=INITIAL_CAPITAL):
    if trades.empty:
        return dict(trades=0, wins=0, losses=0, win_rate_pct=0, total_R=0, avg_R=0, profit_factor_R=0, max_drawdown_pct=0, final_equity=initial, return_pct=0)
    wins = int((trades.r > 0).sum())
    losses = int((trades.r <= 0).sum())
    gross_win = trades.loc[trades.r > 0, 'r'].sum()
    gross_loss = abs(trades.loc[trades.r < 0, 'r'].sum())
    eq = initial + trades.pnl.cumsum()
    eq2 = pd.concat([pd.Series([initial]), eq], ignore_index=True)
    dd = (eq2 - eq2.cummax()) / eq2.cummax()
    return dict(
        trades=int(len(trades)), wins=wins, losses=losses,
        win_rate_pct=round(wins/len(trades)*100,2),
        total_R=round(float(trades.r.sum()),2), avg_R=round(float(trades.r.mean()),3),
        profit_factor_R=round(float(gross_win/gross_loss),3) if gross_loss else math.inf,
        max_drawdown_pct=round(float(dd.min()*100),2),
        final_equity=round(float(eq.iloc[-1]),2), return_pct=round(float((eq.iloc[-1]/initial-1)*100),2)
    )


def backtest(df: pd.DataFrame, symbol: str, p: Params, start=None, end=None) -> pd.DataFrame:
    if start is not None or end is not None:
        dfx = df.loc[start:end]
    else:
        dfx = df
    if len(dfx) < 300:
        return pd.DataFrame()

    # Pre-extract numpy arrays — avoids ~200µs pandas iloc overhead per iteration
    idx         = dfx.index
    opens       = dfx['open'].values.astype('f8')
    highs       = dfx['high'].values.astype('f8')
    lows        = dfx['low'].values.astype('f8')
    closes      = dfx['close'].values.astype('f8')
    spreads     = dfx['spread'].values.astype('f8')
    pdh_arr     = dfx['pdh'].values.astype('f8')
    pdl_arr     = dfx['pdl'].values.astype('f8')
    phl_arr     = dfx['pivot_high_level'].values.astype('f8')
    pll_arr     = dfx['pivot_low_level'].values.astype('f8')
    med_sp_arr  = dfx['median_spread'].values.astype('f8')
    htf_arr     = dfx['htf_trend'].values          # object/str array
    hours_arr   = np.array(idx.hour, dtype='i4')

    pip = PIP_SIZE[symbol]
    sl_buffer = SL_BUFFER_PIPS[symbol] * pip
    equity = INITIAL_CAPITAL
    trades = []
    open_trade = None
    pending = None
    cooldown_until = -1

    for i in range(200, len(dfx)-1):
        h = highs[i]
        lo = lows[i]
        c = closes[i]

        # Manage open trade
        if open_trade:
            bars_held = i - open_trade['entry_i']
            exit_price = None
            reason = None
            if open_trade['direction'] == 'long':
                if lo <= open_trade['stop']:
                    exit_price = open_trade['stop']
                    reason = 'SL'
                elif h >= open_trade['target']:
                    exit_price = open_trade['target']
                    reason = 'TP'
            else:
                if h >= open_trade['stop']:
                    exit_price = open_trade['stop']
                    reason = 'SL'
                elif lo <= open_trade['target']:
                    exit_price = open_trade['target']
                    reason = 'TP'
            if exit_price is None and bars_held >= 32:
                exit_price = c
                reason = 'TIME'
            if exit_price is not None:
                risk_dist = abs(open_trade['entry'] - open_trade['stop'])
                if open_trade['direction'] == 'long':
                    r = (exit_price - open_trade['entry']) / risk_dist
                else:
                    r = (open_trade['entry'] - exit_price) / risk_dist
                pnl = equity * RISK_PER_TRADE * r
                equity += pnl
                trades.append({
                    'symbol': open_trade['symbol'], 'entry_time': open_trade['entry_time'],
                    'direction': open_trade['direction'], 'model': open_trade['model'],
                    'entry': open_trade['entry'], 'stop': open_trade['stop'],
                    'target': open_trade['target'],
                    'exit_time': str(idx[i]), 'exit': float(exit_price),
                    'r': float(r), 'pnl': float(pnl), 'reason': reason,
                })
                open_trade = None
                pending = None
                cooldown_until = i + p.cooldown
            continue

        # Pending setup
        if pending:
            age = i - pending['sweep_i']
            if age > p.confirm_bars + p.entry_wait + 2:
                pending = None
            else:
                if not pending.get('confirmed'):
                    if age <= p.confirm_bars:
                        pll_prev = pll_arr[i-1]
                        phl_prev = phl_arr[i-1]
                        if pending['direction'] == 'short':
                            mss = (c < pll_prev) if not np.isnan(pll_prev) else False
                        else:
                            mss = (c > phl_prev) if not np.isnan(phl_prev) else False
                        if mss:
                            pending['confirmed'] = True
                            if p.entry_mode == 'next_open':
                                entry = float(opens[i+1])
                                fill_i = i+1
                                pending['entry'] = entry
                                pending['fill_deadline'] = i + p.entry_wait
                                open_trade = _make_trade_arr(symbol, idx, pending, p, fill_i, entry, sl_buffer, pip, pdh_arr, pdl_arr, highs, lows)
                                if open_trade is None:
                                    pending = None
                                continue
                            else:
                                entry = float((h + lo) / 2.0)
                                pending['entry'] = entry
                                pending['fill_deadline'] = i + p.entry_wait
                    else:
                        pending = None
                else:
                    if p.entry_mode == 'fifty_pullback':
                        if i <= pending['fill_deadline']:
                            entry = pending['entry']
                            filled = (h >= entry) if pending['direction']=='short' else (lo <= entry)
                            if filled:
                                open_trade = _make_trade_arr(symbol, idx, pending, p, i, entry, sl_buffer, pip, pdh_arr, pdl_arr, highs, lows)
                                if open_trade is None:
                                    pending = None
                                continue
                        else:
                            pending = None
            continue

        if i < cooldown_until:
            continue
        if not (p.session_start <= hours_arr[i] < p.session_end):
            continue
        pdh = pdh_arr[i]
        pdl = pdl_arr[i]
        if np.isnan(pdh) or np.isnan(pdl) or np.isnan(phl_arr[i]) or np.isnan(pll_arr[i]):
            continue
        if spreads[i] > med_sp_arr[i] * SPREAD_FILTER_MULT:
            continue

        swept_pdh = h > pdh and c < pdh
        swept_pdl = lo < pdl and c > pdl
        if swept_pdh:
            direction = 'short'
            extreme = h
        elif swept_pdl:
            direction = 'long'
            extreme = lo
        else:
            continue

        htf = htf_arr[i]
        if p.trend_filter == 'with_1h':
            if direction == 'short' and htf != 'bearish':
                continue
            if direction == 'long' and htf != 'bullish':
                continue
        elif p.trend_filter == 'counter_1h':
            if direction == 'short' and htf != 'bullish':
                continue
            if direction == 'long' and htf != 'bearish':
                continue

        pending = {'symbol': symbol, 'direction': direction, 'sweep_i': i,
                   'sweep_time': idx[i], 'sweep_high': h, 'sweep_low': lo,
                   'pdh': pdh, 'pdl': pdl, 'extreme': extreme, 'confirmed': False}

    return pd.DataFrame(trades)


def _make_trade_arr(symbol, idx, pending, p, fill_i, entry, sl_buffer, pip, pdh_arr, pdl_arr, highs, lows):
    direction = pending['direction']
    if direction == 'short':
        stop = pending['sweep_high'] + sl_buffer
        risk = stop - entry
        if risk <= 0:
            return None
        risk_pips = risk / pip
        if risk_pips < p.min_stop_pips or risk_pips > p.max_stop_pips:
            return None
        liq = pending['pdl']
        target = liq if (p.target_mode == 'liq_or_rr' and liq < entry and (entry-liq)/risk >= 1.2) else entry - p.rr * risk
        model = f'D2_E3_opt_short_{p.entry_mode}'
    else:
        stop = pending['sweep_low'] - sl_buffer
        risk = entry - stop
        if risk <= 0:
            return None
        risk_pips = risk / pip
        if risk_pips < p.min_stop_pips or risk_pips > p.max_stop_pips:
            return None
        liq = pending['pdh']
        target = liq if (p.target_mode == 'liq_or_rr' and liq > entry and (liq-entry)/risk >= 1.2) else entry + p.rr * risk
        model = f'D2_E3_opt_long_{p.entry_mode}'
    return {'symbol': symbol, 'entry_time': str(idx[fill_i]), 'direction': direction,
            'model': model, 'entry_i': fill_i, 'entry': float(entry),
            'stop': float(stop), 'target': float(target)}


def make_trade(symbol, dfx, pending, p: Params, fill_i, entry, sl_buffer, pip):
    direction = pending['direction']
    if direction == 'short':
        stop = pending['sweep_high'] + sl_buffer
        risk = stop - entry
        if risk <= 0:
            return None
        risk_pips = risk / pip
        if risk_pips < p.min_stop_pips or risk_pips > p.max_stop_pips:
            return None
        fixed_target = entry - p.rr * risk
        liq_target = pending['pdl']
        if p.target_mode == 'liq_or_rr' and liq_target < entry and (entry-liq_target)/risk >= 1.2:
            target = liq_target
        else:
            target = fixed_target
        model = f'D2_E3_opt_short_{p.entry_mode}'
    else:
        stop = pending['sweep_low'] - sl_buffer
        risk = entry - stop
        if risk <= 0:
            return None
        risk_pips = risk / pip
        if risk_pips < p.min_stop_pips or risk_pips > p.max_stop_pips:
            return None
        fixed_target = entry + p.rr * risk
        liq_target = pending['pdh']
        if p.target_mode == 'liq_or_rr' and liq_target > entry and (liq_target-entry)/risk >= 1.2:
            target = liq_target
        else:
            target = fixed_target
        model = f'D2_E3_opt_long_{p.entry_mode}'
    return {'symbol':symbol, 'entry_time':str(dfx.index[fill_i]), 'direction':direction, 'model':model, 'entry_i':fill_i, 'entry':float(entry), 'stop':float(stop), 'target':float(target)}


def param_grid():
    sessions=[(7,17),(8,16),(7,12),(12,17),(13,17)]
    confirm=[1,3,6,12]
    modes=['next_open','fifty_pullback']
    waits=[1,3,6]
    rrs=[2.0,3.0,4.0]
    targets=['fixed_rr','liq_or_rr']
    maxstops=[6,10,15,25]
    trends=['none','with_1h','counter_1h']
    for (ss,se),cb,mode,wait,rr,tgt,ms,tr in itertools.product(sessions,confirm,modes,waits,rrs,targets,maxstops,trends):
        if mode == 'next_open' and wait != 1:
            continue
        yield Params(ss,se,cb,mode,wait,rr,tgt,ms,2.0,3,tr)


def main():
    # Ensure data files exist
    prepare_data()

    data={s:load_symbol(s) for s in SYMBOLS}
    results=[]
    params=list(param_grid())
    print(f'Grid size: {len(params)}')
    for n,p in enumerate(params,1):
        train_tr = []
        val_tr = []
        for sym,df in data.items():
            t=backtest(df,sym,p,end=TRAIN_END-pd.Timedelta(minutes=15))
            v=backtest(df,sym,p,start=TRAIN_END)
            if not t.empty:
                train_tr.append(t)
            if not v.empty:
                val_tr.append(v)
        train=pd.concat(train_tr,ignore_index=True) if train_tr else pd.DataFrame()
        val=pd.concat(val_tr,ignore_index=True) if val_tr else pd.DataFrame()
        st = summarize(train)
        sv = summarize(val)
        if st['trades'] >= 20:  # avoid tiny sample winners
            score = st['profit_factor_R'] * min(1, st['trades']/50) + st['avg_R']
            results.append({'params':p.__dict__,'score':score,'train':st,'validation':sv})
        if n % 500 == 0:
            print(f'{n}/{len(params)}')
    results=sorted(results, key=lambda x:(x['validation']['profit_factor_R'], x['validation']['total_R'], x['train']['profit_factor_R']), reverse=True)
    # Also sort by train to inspect overfit
    by_train=sorted(results, key=lambda x:(x['train']['profit_factor_R'], x['train']['total_R']), reverse=True)
    json.dump({'best_by_validation':results[:20], 'best_by_train':by_train[:20]}, open(OUTDIR/'optimization_results.json','w'), indent=2)
    if not results:
        print('No param sets reached 20 trades on train. Check data and sweep detection logic.')
        return
    best=results[0]
    p=Params(**best['params'])
    print('BEST', json.dumps(best,indent=2))
    # full-period trades for best
    all_tr = []
    per = []
    for sym,df in data.items():
        tr=backtest(df,sym,p)
        tr.to_csv(OUTDIR/f'{sym}_optimized_trades.csv',index=False)
        all_tr.append(tr)
        st = summarize(tr)
        st['symbol'] = sym
        per.append(st)
    merged=pd.concat(all_tr,ignore_index=True).sort_values('entry_time') if all_tr else pd.DataFrame()
    merged.to_csv(OUTDIR/'all_optimized_trades.csv',index=False)
    port=summarize(merged)
    summary={'selected_params':best['params'],'train':best['train'],'validation':best['validation'],'full_period_per_symbol':per,'full_period_portfolio':port}
    json.dump(summary, open(OUTDIR/'summary.json','w'), indent=2)
    # report
    md=['# Optimized D2 Strategy Rules', '',
        'Source: D2 video E3 model — price sweeps PDH/PDL liquidity → M15 MSS confirmation → enter on reversal.',
        'Data: M15 bars (Dec 2025 – May 2026). confirm_bars = M15 intervals after sweep.',
        '', '## Selected parameters', '```json', json.dumps(best['params'],indent=2), '```', '',
        '## Walk-forward split', '- Train: 2025-12-01 to 2026-03-31', '- Validation: 2026-04-01 to 2026-05-31', '',
        '### Train', '```json', json.dumps(best['train'],indent=2), '```', '',
        '### Validation', '```json', json.dumps(best['validation'],indent=2), '```', '',
        '## Full 6-month result with selected rules',
        '| Symbol | Trades | Win rate | Total R | Avg R | PF | Max DD | Return |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for s in per:
        md.append(f"| {s['symbol']} | {s['trades']} | {s['win_rate_pct']}% | {s['total_R']} | {s['avg_R']} | {s['profit_factor_R']} | {s['max_drawdown_pct']}% | {s['return_pct']}% |")
    md += ['', '### Portfolio proxy', '```json', json.dumps(port,indent=2), '```', '',
        '## Optimized rules for code agent',
        f"1. Trade only during **{p.session_start}:00–{p.session_end}:00 UTC**.",
        '2. Mark previous day high/low as primary D2 liquidity targets.',
        f"3. After PDH/PDL sweep, wait up to **{p.confirm_bars}** M15 bars ({p.confirm_bars*15} min) for MSS (close beyond recent swing).",
        f"4. Entry mode: **{p.entry_mode}**. If `fifty_pullback`, place limit at 50% of MSS candle and wait **{p.entry_wait}** bars ({p.entry_wait*15} min).",
        f"5. Stop: between **{p.min_stop_pips} and {p.max_stop_pips} pips**; SL beyond sweep extreme + {SL_BUFFER_PIPS['EURUSD']}pip buffer.",
        f"6. Target mode: **{p.target_mode}**, RR = **{p.rr}**.",
        f"7. H1 trend filter: **{p.trend_filter}** (none = trade both directions; with_1h = align; counter_1h = fade).",
        '8. Cooldown: 3 M15 bars after a closed trade before seeking the next setup.',
        '', '## Warning',
        'Optimized on 6 months of M15 data — small sample, overfitting risk is high.',
        'Treat best parameters as a starting hypothesis only. Run forward demo ≥ 30 days before live.']
    (OUTDIR/'REPORT.md').write_text('\n'.join(md))
    print(f'\nReport written to {OUTDIR}/REPORT.md')

if __name__=='__main__':
    main()
