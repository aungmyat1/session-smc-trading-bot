"""Strategy adapter exports and lightweight factory helpers."""

from __future__ import annotations

from core.base_strategy import BaseStrategy
from strategies.adapters.adaptive_smc_adapter import AdaptiveSMCAdapter
from strategies.adapters.london_breakout_adapter import LondonBreakoutAdapter
from strategies.adapters.ny_momentum_adapter import NYMomentumAdapter
from strategies.adapters.smc_ob_fvg_session_adapter import SMCOrderBlockFVGSessionAdapter
from strategies.adapters.st_a2_adapter import ST2Adapter
from strategies.adapters.vwap_adapter import VWAPBreakoutAdapter, VWAPMeanReversionAdapter

ADAPTER_TYPES: dict[str, type[BaseStrategy]] = {
    "AdaptiveSMC": AdaptiveSMCAdapter,
    "LondonBreakout": LondonBreakoutAdapter,
    "NYMomentum": NYMomentumAdapter,
    "SMCOrderBlockFVGSession": SMCOrderBlockFVGSessionAdapter,
    "ST-A2": ST2Adapter,
    "VWAPBreakout": VWAPBreakoutAdapter,
    "VWAPMeanReversion": VWAPMeanReversionAdapter,
}


def build_strategy(name: str) -> BaseStrategy:
    try:
        return ADAPTER_TYPES[name]()
    except KeyError as exc:
        available = ", ".join(sorted(ADAPTER_TYPES))
        raise KeyError(f"Unknown strategy {name!r}. Available: {available}") from exc


__all__ = [
    "ADAPTER_TYPES",
    "AdaptiveSMCAdapter",
    "LondonBreakoutAdapter",
    "NYMomentumAdapter",
    "SMCOrderBlockFVGSessionAdapter",
    "ST2Adapter",
    "VWAPBreakoutAdapter",
    "VWAPMeanReversionAdapter",
    "build_strategy",
]
