from __future__ import annotations

from research.experiments.st_a2_candidate_robustness import _candidate_rows, _gate, _metrics


def test_candidate_rows_excludes_configured_symbol() -> None:
    rows = [{"symbol": "EURUSD"}, {"symbol": "XAUUSD"}, {"symbol": "GBPUSD"}]
    config = {"selection_rule": {"type": "exclude_symbol", "symbol": "XAUUSD"}}

    assert [row["symbol"] for row in _candidate_rows(rows, config)] == ["EURUSD", "GBPUSD"]


def test_metrics_uses_cost_multiplier() -> None:
    rows = [
        {"gross_pnl": 3.0, "spread_cost": 0.25, "commission_cost": 0.25, "slippage_cost": 0.0},
        {"gross_pnl": -1.0, "spread_cost": 0.25, "commission_cost": 0.25, "slippage_cost": 0.0},
    ]

    metrics = _metrics(rows, cost_multiplier=2.0)

    assert metrics["trade_count"] == 2
    assert metrics["net_r"] == 0.0
    assert metrics["profit_factor"] == 1.0


def test_gate_requires_standard_and_2x_metrics() -> None:
    gate = {
        "min_trades": 200,
        "min_pf_standard": 1.25,
        "min_pf_2x": 1.25,
        "min_sharpe_standard": 1.2,
        "min_sharpe_2x": 1.2,
        "max_drawdown_r": 15.0,
    }
    std = {"trade_count": 250, "profit_factor": 1.4, "sharpe": 1.3, "max_drawdown_r": 10.0}
    stress = {"trade_count": 250, "profit_factor": 1.1, "sharpe": 1.3, "max_drawdown_r": 10.0}

    result = _gate(std, stress, gate)

    assert result["status"] == "FAIL"
    assert result["checks"]["pf_2x"] is False
