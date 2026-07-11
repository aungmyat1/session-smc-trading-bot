from __future__ import annotations

from research.failure_decomposition import cost_attribution, hypotheses, regime_attribution, root_causes, session_attribution, symbol_attribution, failure_breakdown


def test_hypothesis_generation_is_evidence_based(sample_decomposition_rows) -> None:
    breakdown = failure_breakdown(sample_decomposition_rows)
    symbols = symbol_attribution(sample_decomposition_rows)
    regimes = regime_attribution(sample_decomposition_rows)
    sessions = session_attribution(sample_decomposition_rows)
    costs = cost_attribution(sample_decomposition_rows)
    causes = root_causes(breakdown, symbols, regimes, sessions, costs)

    report = hypotheses(causes, regimes, sessions, symbols, costs)

    assert report["hypotheses"]
    assert all(item["evidence"] for item in report["hypotheses"])
    assert all(item["single_change"] for item in report["hypotheses"])
