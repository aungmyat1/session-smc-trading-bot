from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from research import research_validation as rv


def _write_bars(path: Path, rows: int = 8) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        {
            "timestamp_utc": pd.date_range("2026-01-01", periods=rows, freq="5min", tz="UTC"),
            "open": [1.0 + i * 0.001 for i in range(rows)],
            "high": [1.001 + i * 0.001 for i in range(rows)],
            "low": [0.999 + i * 0.001 for i in range(rows)],
            "close": [1.0005 + i * 0.001 for i in range(rows)],
            "ask_open": [1.0001 + i * 0.001 for i in range(rows)],
            "bid_open": [0.9999 + i * 0.001 for i in range(rows)],
            "spread_avg": [0.0002] * rows,
            "spread_max": [0.0003] * rows,
        }
    )
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), path, compression="snappy")


def _config(tmp_path: Path) -> Path:
    processed = tmp_path / "processed"
    for tf in ["M5", "M15", "H1", "H4"]:
        _write_bars(processed / "EURUSD" / f"{tf}.parquet")
    checksums = tmp_path / "checksums.json"
    checksums.write_text(json.dumps({"dataset_hash": "abc123"}), encoding="utf-8")
    config = {
        "dataset": {
            "version": "professional_3y_4symbol_v2",
            "checksums_path": str(checksums),
            "processed_root": str(processed),
        },
        "symbols": ["EURUSD"],
        "timeframes": ["M5", "M15", "H1", "H4"],
        "acceptance_gates": {
            "trades_min": 2,
            "profit_factor_min": 1.25,
            "sharpe_min": 0.1,
            "max_drawdown_pct_max": 15.0,
            "expectancy_min": 0.0,
        },
        "cost_model": {
            "commission_model": "commission.yaml",
            "slippage_model": "slippage.yaml",
        },
    }
    path = tmp_path / "benchmark.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return path


def test_dataset_research_audit_writes_expected_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(rv, "ROOT", tmp_path)
    outdir = tmp_path / "artifacts"

    result = rv.run_dataset_research_audit(_config(tmp_path), outdir)

    assert result["dataset_research_audit"]["status"] == "PASS"
    assert (outdir / "dataset_research_audit.json").exists()
    assert (outdir / "return_distribution_report.json").exists()
    assert (outdir / "spread_validation_report.json").exists()


def test_st_a2_validation_blocks_without_trade_ledger(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(rv, "ROOT", tmp_path)

    report = rv.st_a2_validation_report(None, _config(tmp_path))

    assert report["status"] == "BLOCKED"
    assert "dataset_hash" in report


def test_robustness_report_includes_optimization_diagnostics(tmp_path: Path, monkeypatch) -> None:
    diagnostics = tmp_path / "diagnostics.yaml"
    diagnostics.write_text(
        yaml.safe_dump(
            {
                "diagnostics": [
                    {
                        "failure": "Few trades",
                        "meaning": "Strategy is over-filtered.",
                        "fix_direction": "Relax rules.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(rv, "ROOT", tmp_path)
    monkeypatch.setattr(rv, "OPTIMIZATION_DIAGNOSTICS", diagnostics)

    report = rv.robustness_report(None, _config(tmp_path))

    assert report["optimization_diagnostics"][0]["failure"] == "Few trades"


def test_trade_ledger_metrics_require_execution_cost_fields(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(rv, "ROOT", tmp_path)
    trades = tmp_path / "trades.json"
    trades.write_text(
        json.dumps(
            [
                {
                    "entry_time": "2026-01-01T00:00:00Z",
                    "entry_price": 1.0,
                    "exit_price": 1.1,
                    "spread_cost": 0.1,
                    "commission": 0.1,
                    "slippage": 0.0,
                    "gross_pnl": 1.0,
                    "net_pnl": 0.8,
                },
                {
                    "entry_time": "2026-02-01T00:00:00Z",
                    "entry_price": 1.1,
                    "exit_price": 1.0,
                    "spread_cost": 0.1,
                    "commission": 0.1,
                    "slippage": 0.0,
                    "gross_pnl": -0.2,
                    "net_pnl": -0.4,
                },
                {
                    "entry_time": "2026-03-01T00:00:00Z",
                    "entry_price": 1.0,
                    "exit_price": 1.2,
                    "spread_cost": 0.1,
                    "commission": 0.1,
                    "slippage": 0.0,
                    "gross_pnl": 1.0,
                    "net_pnl": 0.8,
                },
            ]
        ),
        encoding="utf-8",
    )

    report = rv.st_a2_validation_report(trades, _config(tmp_path))

    assert report["missing_required_trade_fields"] == []
    assert report["metrics"]["trades"] == 3
    assert report["metrics"]["profit_factor_after_cost"] == 4.0
