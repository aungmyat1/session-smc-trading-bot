from __future__ import annotations

from scripts.validate_runtime_config import validate_runtime


def test_validate_runtime_passes_when_required_paths_exist(tmp_path, monkeypatch):
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "strategy_catalog.yaml").write_text("current_strategy: null\nstrategies: {}\n", encoding="utf-8")
    (tmp_path / "deploy" / "gcp-vm1" / "systemd").mkdir(parents=True, exist_ok=True)
    (tmp_path / "deploy" / "gcp-vm1" / "systemd" / "smc-demo-runner.service").write_text("[Unit]\n", encoding="utf-8")
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "scripts" / "reconcile_positions.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    monkeypatch.setenv("TRADING_MODE", "shadow")
    monkeypatch.setenv("DEMO_ONLY", "true")
    monkeypatch.setenv("LIVE_TRADING", "false")

    assert validate_runtime(tmp_path) == []


def test_validate_runtime_rejects_live_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("TRADING_MODE", "live")
    monkeypatch.setenv("LIVE_TRADING", "true")

    issues = validate_runtime(tmp_path)

    assert any("TRADING_MODE=live" in issue for issue in issues)
