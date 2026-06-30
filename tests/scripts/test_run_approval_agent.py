from __future__ import annotations

from pathlib import Path

import pytest

import scripts.run_approval_agent as run_approval_agent


def test_refresh_upstream_reports_raises_when_testing_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(run_approval_agent, "run_testing", lambda argv: 1)
    monkeypatch.setattr(run_approval_agent, "run_quality", lambda argv: 0)

    with pytest.raises(RuntimeError, match=r"testing=1, quality=0"):
        run_approval_agent._refresh_upstream_reports(tmp_path, tmp_path / "reports", "INFO")


def test_refresh_upstream_reports_raises_when_quality_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(run_approval_agent, "run_testing", lambda argv: 0)
    monkeypatch.setattr(run_approval_agent, "run_quality", lambda argv: 2)

    with pytest.raises(RuntimeError, match=r"testing=0, quality=2"):
        run_approval_agent._refresh_upstream_reports(tmp_path, tmp_path / "reports", "INFO")

