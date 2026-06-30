"""
replay/ — Historical Replay Infrastructure

Modules:
    engine.py   — walk-forward simulation engine (all 5 strategies)
    metrics.py  — profit factor, win rate, drawdown, gate evaluation
    exporter.py — CSV trade log + Markdown report writer

Entry point:
    python3 scripts/run_replay.py
"""

from replay.engine import ReplayEngine, ReplayConfig, ReplayTrade, ReplayResult
from replay.metrics import compute_metrics, gate_check, print_summary, GateResult
from replay.exporter import export_csv, export_report, export_smoke_test

__all__ = [
    "ReplayEngine",
    "ReplayConfig",
    "ReplayTrade",
    "ReplayResult",
    "compute_metrics",
    "gate_check",
    "print_summary",
    "GateResult",
    "export_csv",
    "export_report",
    "export_smoke_test",
]
