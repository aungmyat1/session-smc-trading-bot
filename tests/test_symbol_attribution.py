from __future__ import annotations

from research.failure_decomposition import symbol_attribution


def test_symbol_attribution_ranks_best_and_worst(sample_decomposition_rows) -> None:
    report = symbol_attribution(sample_decomposition_rows)

    assert report["rankings"]["best_symbol"] == "GBPUSD"
    assert report["rankings"]["worst_symbol"] == "XAUUSD"
    assert "GBPUSD" in report["questions"]["profit_contributors"]
    assert "XAUUSD" in report["questions"]["performance_destroyers"]
