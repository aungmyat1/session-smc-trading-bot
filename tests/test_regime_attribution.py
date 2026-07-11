from __future__ import annotations

from research.failure_decomposition import regime_attribution


def test_regime_attribution_identifies_destructive_regime(sample_decomposition_rows) -> None:
    report = regime_attribution(sample_decomposition_rows)

    assert "RANGE_LOW_VOL" in report["destructive_regimes"]
    assert "TREND_HIGH_VOL" in report["regimes"]
    assert "edge_score" in report["regimes"]["RANGE_LOW_VOL"]
