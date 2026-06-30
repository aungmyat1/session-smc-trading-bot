"""Tests for the SMC order-block plus FVG session adapter."""

from __future__ import annotations

from strategies.adapters.smc_ob_fvg_session_adapter import \
    SMCOrderBlockFVGSessionAdapter


def _ts(hour: int, minute: int) -> str:
    return f"2026-06-24T{hour:02d}:{minute:02d}:00+00:00"


def _candle(
    hour: int, minute: int, open_: float, high: float, low: float, close: float
) -> dict:
    return {
        "time": _ts(hour, minute),
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": 1000,
    }


def _setup_bars() -> list[dict]:
    bars: list[dict] = []
    base = 1.0998
    for idx in range(28):
        hour = idx // 4
        minute = (idx % 4) * 15
        shift = 0.0001 if idx % 2 == 0 else -0.0001
        bars.append(
            _candle(
                hour,
                minute,
                base,
                base + 0.0002 + shift,
                base - 0.0002,
                base + shift / 2,
            )
        )

    bars.extend(
        [
            _candle(7, 0, 1.1001, 1.1002, 1.0994, 1.0995),
            _candle(7, 15, 1.0996, 1.1014, 1.0995, 1.1013),
            _candle(7, 30, 1.1013, 1.1016, 1.10035, 1.1014),
            _candle(7, 45, 1.1010, 1.1011, 1.1001, 1.10025),
        ]
    )
    return bars


class TestSMCOrderBlockFVGSessionAdapter:
    def test_generates_long_signal_on_retrace(self):
        adapter = SMCOrderBlockFVGSessionAdapter()
        signal = adapter.generate_signal(
            {
                "symbol": "EURUSD",
                "m15": _setup_bars(),
                "spread_pips": 0.8,
                "config": {
                    "atr_period": 5,
                    "ob_lookback": 20,
                    "bos_lookback": 4,
                    "stop_buffer_pips": 2.0,
                },
            }
        )

        assert signal is not None
        assert signal.strategy_name == "SMCOrderBlockFVGSession"
        assert signal.action == "BUY"
        assert signal.stop_loss < signal.entry_price < signal.take_profit
        assert signal.metadata["reason"] == "order_block_fvg_bos_confluence"
        assert signal.metadata["rr"] == 3.0

    def test_rejects_outside_kill_zone(self):
        adapter = SMCOrderBlockFVGSessionAdapter()
        bars = _setup_bars()
        bars[-1]["time"] = _ts(18, 0)

        signal = adapter.generate_signal(
            {
                "symbol": "EURUSD",
                "m15": bars,
                "config": {"atr_period": 5, "ob_lookback": 20, "bos_lookback": 4},
            }
        )

        assert signal is None

    def test_rejects_when_spread_is_too_wide(self):
        adapter = SMCOrderBlockFVGSessionAdapter()
        signal = adapter.generate_signal(
            {
                "symbol": "EURUSD",
                "m15": _setup_bars(),
                "spread_pips": 4.5,
                "config": {"atr_period": 5, "ob_lookback": 20, "bos_lookback": 4},
            }
        )
        assert signal is None
