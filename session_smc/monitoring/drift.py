"""
Drift detector — slippage drift, spread anomaly, performance drift.

Monitors for conditions that indicate the execution environment has changed
relative to the backtest cost model.

Usage::
    detector = DriftDetector(strategy_id="ST-A2")
    detector.record_fill(symbol="EURUSD", actual_spread_pip=1.5,
                         expected_spread_pip=1.0, slippage_pip=0.2)
    report = detector.get_drift_report()
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)
_UTC = timezone.utc

# Thresholds
SPREAD_ANOMALY_MULTIPLIER = 2.5   # actual spread > 2.5× expected → anomaly
SLIPPAGE_DRIFT_PIP = 0.5          # cumulative slippage above this per trade → alert
PERFORMANCE_DRIFT_WIN_RATE = 0.15 # win rate drop below this vs backtest → alert


@dataclass
class FillRecord:
    symbol: str
    timestamp: str
    actual_spread_pip: float
    expected_spread_pip: float
    slippage_pip: float
    win: Optional[bool] = None


@dataclass
class DriftReport:
    strategy_id: str
    timestamp: str
    n_fills: int
    spread_anomaly_count: int
    avg_slippage_pip: float
    slippage_drift_alert: bool
    win_rate: Optional[float]
    performance_drift_alert: bool
    notes: list[str] = field(default_factory=list)

    @property
    def drift_detected(self) -> bool:
        return self.spread_anomaly_count > 0 or self.slippage_drift_alert or self.performance_drift_alert

    def to_dict(self) -> dict:
        return {
            "strategy_id": self.strategy_id,
            "timestamp": self.timestamp,
            "n_fills": self.n_fills,
            "spread_anomaly_count": self.spread_anomaly_count,
            "avg_slippage_pip": self.avg_slippage_pip,
            "slippage_drift_alert": self.slippage_drift_alert,
            "win_rate": self.win_rate,
            "performance_drift_alert": self.performance_drift_alert,
            "drift_detected": self.drift_detected,
            "notes": self.notes,
        }


class DriftDetector:
    """Tracks execution quality and detects drift from backtest baselines."""

    def __init__(self, strategy_id: str = "unknown") -> None:
        self.strategy_id = strategy_id
        self._fills: list[FillRecord] = []

    def record_fill(
        self,
        symbol: str,
        actual_spread_pip: float,
        expected_spread_pip: float,
        slippage_pip: float,
        win: Optional[bool] = None,
    ) -> None:
        self._fills.append(FillRecord(
            symbol=symbol,
            timestamp=datetime.now(_UTC).isoformat(),
            actual_spread_pip=actual_spread_pip,
            expected_spread_pip=expected_spread_pip,
            slippage_pip=slippage_pip,
            win=win,
        ))

    def get_drift_report(self) -> DriftReport:
        fills = self._fills
        if not fills:
            return DriftReport(
                strategy_id=self.strategy_id,
                timestamp=datetime.now(_UTC).isoformat(),
                n_fills=0,
                spread_anomaly_count=0,
                avg_slippage_pip=0.0,
                slippage_drift_alert=False,
                win_rate=None,
                performance_drift_alert=False,
                notes=["No fills recorded yet."],
            )

        anomaly_count = sum(
            1 for f in fills
            if f.actual_spread_pip > f.expected_spread_pip * SPREAD_ANOMALY_MULTIPLIER
        )

        slippages = [f.slippage_pip for f in fills]
        avg_slip = statistics.mean(slippages)
        slip_alert = avg_slip > SLIPPAGE_DRIFT_PIP

        closed = [f for f in fills if f.win is not None]
        win_rate: Optional[float] = None
        perf_alert = False
        if closed:
            win_rate = sum(1 for f in closed if f.win) / len(closed)
            perf_alert = win_rate < PERFORMANCE_DRIFT_WIN_RATE

        notes = []
        if anomaly_count:
            notes.append(f"Spread anomalies: {anomaly_count}/{len(fills)} fills")
        if slip_alert:
            notes.append(f"Slippage drift: avg={avg_slip:.3f}pip > {SLIPPAGE_DRIFT_PIP}")
        if perf_alert:
            notes.append(f"Performance drift: win_rate={win_rate:.1%} below {PERFORMANCE_DRIFT_WIN_RATE:.1%}")

        return DriftReport(
            strategy_id=self.strategy_id,
            timestamp=datetime.now(_UTC).isoformat(),
            n_fills=len(fills),
            spread_anomaly_count=anomaly_count,
            avg_slippage_pip=avg_slip,
            slippage_drift_alert=slip_alert,
            win_rate=win_rate,
            performance_drift_alert=perf_alert,
            notes=notes,
        )
