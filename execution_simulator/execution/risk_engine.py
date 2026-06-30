from __future__ import annotations

from dataclasses import dataclass

from execution_simulator.replay_engine.event_stream import MarketEvent


@dataclass(frozen=True, slots=True)
class RiskResult:
    allowed: bool
    reason: str = ""
    spread_pips: float = 0.0
    required_margin: float = 0.0


class RiskEngine:
    """Broker-style execution checks before a virtual fill is allowed."""

    def __init__(
        self,
        max_spread_pips: dict[str, float] | None = None,
        min_lot: float = 0.01,
        max_lot: float = 10.0,
        min_stop_distance_points: int = 50,
        leverage: int = 100,
        contract_size_by_symbol: dict[str, float] | None = None,
        point_size_by_symbol: dict[str, float] | None = None,
    ) -> None:
        self.max_spread_pips = max_spread_pips or {
            "EURUSD": 3.0,
            "GBPUSD": 4.0,
            "XAUUSD": 5.0,
        }
        self.min_lot = min_lot
        self.max_lot = max_lot
        self.min_stop_distance_points = min_stop_distance_points
        self.leverage = leverage
        self.contract_size_by_symbol = contract_size_by_symbol or {
            "EURUSD": 100_000.0,
            "GBPUSD": 100_000.0,
            "XAUUSD": 100.0,
        }
        self.point_size_by_symbol = point_size_by_symbol or {
            "EURUSD": 0.0001,
            "GBPUSD": 0.0001,
            "XAUUSD": 0.01,
        }

    def validate_order(
        self,
        symbol: str,
        direction: str,
        volume: float,
        stop_loss: float,
        take_profit: float,
        market_event: MarketEvent,
        open_positions: int = 0,
        same_symbol_positions: int = 0,
        account_balance: float = 0.0,
    ) -> RiskResult:
        if symbol != market_event.symbol:
            return RiskResult(False, f"UNKNOWN_SYMBOL:{symbol}", 0.0)

        point = self.point_size_by_symbol.get(symbol, 0.0001)
        spread_pips = round((market_event.ask - market_event.bid) / point, 2)
        max_spread = self.max_spread_pips.get(symbol, 5.0)
        if spread_pips > max_spread:
            return RiskResult(
                False,
                f"SPREAD_TOO_WIDE:{spread_pips:.2f}>{max_spread:.2f}",
                spread_pips,
            )

        if volume < self.min_lot:
            return RiskResult(
                False, f"LOT_TOO_SMALL:{volume:.2f}<{self.min_lot:.2f}", spread_pips
            )
        if volume > self.max_lot:
            return RiskResult(
                False, f"LOT_TOO_LARGE:{volume:.2f}>{self.max_lot:.2f}", spread_pips
            )

        entry = (
            market_event.ask
            if direction.lower() in {"long", "buy"}
            else market_event.bid
        )
        stop_distance_points = abs(entry - stop_loss) / point
        if stop_distance_points < self.min_stop_distance_points:
            return RiskResult(
                False,
                f"STOP_TOO_CLOSE:{stop_distance_points:.1f}<{self.min_stop_distance_points}",
                spread_pips,
            )

        if same_symbol_positions > 0:
            return RiskResult(False, f"MAX_PAIR_EXPOSURE:{symbol}", spread_pips)
        if open_positions > 0:
            return RiskResult(False, f"MAX_OPEN_TRADES:{open_positions}", spread_pips)

        contract_size = self.contract_size_by_symbol.get(symbol, 100_000.0)
        required_margin = (volume * contract_size) / max(self.leverage, 1)
        if account_balance and required_margin > account_balance:
            return RiskResult(
                False,
                f"MARGIN_INSUFFICIENT:{required_margin:.2f}>{account_balance:.2f}",
                spread_pips,
                required_margin,
            )

        return RiskResult(True, "", spread_pips, required_margin)
