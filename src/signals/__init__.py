"""Signal generation from engineered features."""

from .generator import SignalConfig, SignalGenerator
from .london_breakout import (LondonBreakoutConfig,
                              generate_london_breakout_signals)
from .ny_momentum import NYMomentumConfig, generate_ny_momentum_signals
from .vwap_mean_reversion import (VWAPMeanReversionConfig,
                                  generate_vwap_mean_reversion_signals)

__all__ = [
    "SignalConfig",
    "SignalGenerator",
    "LondonBreakoutConfig",
    "generate_london_breakout_signals",
    "NYMomentumConfig",
    "generate_ny_momentum_signals",
    "VWAPMeanReversionConfig",
    "generate_vwap_mean_reversion_signals",
]
