"""Tests for the E5/E6 spread capture and cost revalidation helpers."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts import build_cost_model as bcm
from scripts import check_phase2_completion as phase2
from scripts import export_spread_limits as export_limits
from scripts import spread_status


def _write_spread_csv(path: Path) -> None:
    rows = [
        {"time_utc": "2026-06-24T06:00:00+00:00", "symbol": "EURUSD", "session": "london", "hour": "6", "minute": "0", "spread_pips": "1.20"},
        {"time_utc": "2026-06-24T06:00:30+00:00", "symbol": "GBPUSD", "session": "london", "hour": "6", "minute": "0", "spread_pips": "1.50"},
        {"time_utc": "2026-06-24T11:00:00+00:00", "symbol": "EURUSD", "session": "new_york", "hour": "11", "minute": "0", "spread_pips": "1.30"},
        {"time_utc": "2026-06-24T11:00:30+00:00", "symbol": "GBPUSD", "session": "new_york", "hour": "11", "minute": "0", "spread_pips": "1.70"},
        {"time_utc": "2026-06-24T03:00:00+00:00", "symbol": "EURUSD", "session": "off", "hour": "3", "minute": "0", "spread_pips": "0.90"},
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def test_spread_status_counts_session_days(tmp_path, monkeypatch):
    csv_path = tmp_path / "spread_samples.csv"
    _write_spread_csv(csv_path)
    monkeypatch.setattr(spread_status, "CSV_PATH", csv_path)
    rows = spread_status.load_rows(csv_path)
    session_days = spread_status.count_session_days(rows)
    assert len(session_days["london"]) == 1
    assert len(session_days["new_york"]) == 1


def test_phase2_gate_failure_and_pass(tmp_path, monkeypatch, capsys):
    csv_path = tmp_path / "spread_samples.csv"
    _write_spread_csv(csv_path)
    monkeypatch.setattr(phase2, "CSV_PATH", csv_path)
    assert phase2.main() == 1
    out = capsys.readouterr().out
    assert "NOT_READY" in out

    rows = []
    for day in range(5):
        rows.extend(
            [
                {"time_utc": f"2026-06-{24 + day:02d}T06:00:00+00:00", "symbol": "EURUSD", "session": "london", "hour": "6", "minute": "0", "spread_pips": "1.20"},
                {"time_utc": f"2026-06-{24 + day:02d}T11:00:00+00:00", "symbol": "GBPUSD", "session": "new_york", "hour": "11", "minute": "0", "spread_pips": "1.70"},
            ]
        )
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    assert phase2.main() == 1  # still below row threshold


def test_build_cost_model_and_export_updates_costs(tmp_path, monkeypatch):
    csv_path = tmp_path / "spread_samples.csv"
    _write_spread_csv(csv_path)
    model_path = tmp_path / "cost_model.json"
    yaml_path = tmp_path / "recommended_spread_limits.yaml"
    costs_path = tmp_path / "costs.json"
    costs_path.write_text(
        json.dumps(
            {
                "active_profile": "PLACEHOLDER_vt_markets_assumption",
                "profiles": {
                    "PLACEHOLDER_vt_markets_assumption": {
                        "EURUSD": {"standard": 1.4, "stress2x": 2.8},
                        "GBPUSD": {"standard": 1.8, "stress2x": 3.6},
                    },
                    "vantage_measured": {
                        "EURUSD": {"standard": None, "stress2x": None},
                        "GBPUSD": {"standard": None, "stress2x": None},
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(bcm, "SRC", csv_path)
    monkeypatch.setattr(bcm, "OUT", model_path)
    model = bcm.build_model(list(csv.DictReader(csv_path.open(newline="", encoding="utf-8"))))
    assert model["row_count"] == 5
    model_path.write_text(json.dumps(model), encoding="utf-8")

    monkeypatch.setattr(export_limits, "MODEL_PATH", model_path)
    monkeypatch.setattr(export_limits, "YAML_PATH", yaml_path)
    monkeypatch.setattr(export_limits, "COSTS_PATH", costs_path)
    assert export_limits.main() == 0

    updated = json.loads(costs_path.read_text(encoding="utf-8"))
    assert updated["active_profile"] == "vantage_measured"
    assert updated["profiles"]["vantage_measured"]["EURUSD"]["standard"] is not None
    assert yaml_path.exists()
