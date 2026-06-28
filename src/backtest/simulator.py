from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1

import pandas as pd


@dataclass(frozen=True)
class TradeSimulationConfig:
    initial_capital: float = 10_000.0
    risk_per_trade: float = 0.005
    rr_multiple: float = 2.0
    stop_lookback: int = 5
    stop_buffer_pips: float = 1.0
    spread_pips: float = 1.5
    commission_pips: float = 0.6
    slippage_pips: float = 0.2
    execution_delay_bars: int = 1
    max_hold_bars: int = 48


_PIP = {"EURUSD": 0.0001, "GBPUSD": 0.0001, "XAUUSD": 0.1, "USDJPY": 0.01}


class TradeSimulator:
    """Bar-close simulator with simple costs and R-based exits."""

    def __init__(self, config: TradeSimulationConfig | None = None) -> None:
        self.config = config or TradeSimulationConfig()

    def simulate(self, candles: pd.DataFrame, signals: pd.DataFrame) -> pd.DataFrame:
        if signals.empty:
            return pd.DataFrame(columns=[
                "trade_id", "signal_id", "pair", "strategy_name", "entry_time", "exit_time",
                "entry_price", "exit_price", "stop_loss", "take_profit", "result_r", "result_money",
            ])

        candles = candles.copy().reset_index(drop=True)
        candles["timestamp"] = pd.to_datetime(candles["timestamp"], utc=True)
        rows: list[dict] = []

        for _, sig in signals.iterrows():
            pair = sig["pair"]
            pip = _PIP.get(pair, 0.0001)
            sig_ts = pd.to_datetime(sig["timestamp"], utc=True)
            try:
                sig_pos = candles.index[candles["timestamp"] >= sig_ts][0]
            except IndexError:
                continue

            entry_pos = min(sig_pos + self.config.execution_delay_bars, len(candles) - 1)
            window_start = max(0, entry_pos - self.config.stop_lookback)
            window = candles.iloc[window_start:entry_pos + 1]
            entry_bar = candles.iloc[entry_pos]
            is_long = str(sig["direction"]).upper() == "LONG"
            if is_long:
                stop_loss = float(window["low"].min() - self.config.stop_buffer_pips * pip)
                entry_price = float(entry_bar["open"] + (self.config.spread_pips + self.config.slippage_pips) * pip)
            else:
                stop_loss = float(window["high"].max() + self.config.stop_buffer_pips * pip)
                entry_price = float(entry_bar["open"] - (self.config.spread_pips + self.config.slippage_pips) * pip)

            risk = abs(entry_price - stop_loss)
            if risk <= 0:
                continue
            take_profit = float(entry_price + self.config.rr_multiple * risk) if is_long else float(entry_price - self.config.rr_multiple * risk)

            exit_price = float(candles.iloc[-1]["close"])
            exit_time = candles.iloc[-1]["timestamp"]
            result_r = 0.0
            exit_limit = min(len(candles), entry_pos + max(1, self.config.max_hold_bars) + 1)
            for i in range(entry_pos, exit_limit):
                bar = candles.iloc[i]
                exit_time = bar["timestamp"]
                if is_long:
                    if bar["low"] <= stop_loss:
                        exit_price = stop_loss
                        result_r = -1.0
                        break
                    if bar["high"] >= take_profit:
                        exit_price = take_profit
                        result_r = self.config.rr_multiple
                        break
                else:
                    if bar["high"] >= stop_loss:
                        exit_price = stop_loss
                        result_r = -1.0
                        break
                    if bar["low"] <= take_profit:
                        exit_price = take_profit
                        result_r = self.config.rr_multiple
                        break
            if result_r == 0.0:
                if is_long:
                    result_r = (exit_price - entry_price) / risk
                else:
                    result_r = (entry_price - exit_price) / risk

            cost_r = (self.config.spread_pips + self.config.commission_pips + self.config.slippage_pips) * pip / risk
            net_r = result_r - cost_r
            risk_money = self.config.initial_capital * self.config.risk_per_trade
            rows.append({
                "trade_id": sha1(f"{sig['signal_id']}-{sig_ts.isoformat()}".encode()).hexdigest()[:16],
                "signal_id": sig["signal_id"],
                "pair": pair,
                "strategy_name": sig.get("strategy_name", "ST-A2"),
                "entry_time": candles.iloc[entry_pos]["timestamp"],
                "exit_time": exit_time,
                "entry_price": round(entry_price, 6),
                "exit_price": round(exit_price, 6),
                "stop_loss": round(stop_loss, 6),
                "take_profit": round(take_profit, 6),
                "result_r": round(net_r, 3),
                "result_money": round(net_r * risk_money, 2),
            })

        return pd.DataFrame.from_records(rows)
