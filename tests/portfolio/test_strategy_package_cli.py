from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from approval_package.package_builder import build_approval_package


def _approved_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    key = "portfolio-test-key"
    monkeypatch.setenv("STRATEGY_PACKAGE_SIGNING_KEY", key)
    evidence: dict[str, Path] = {}
    content = {
        "strategy_spec.yaml": "strategy_id: ST-A2\n",
        "backtest_report.md": "pass\n",
        "replay_report.md": "pass\n",
        "risk_report.md": "pass\n",
    }
    for name, text in content.items():
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        evidence[name] = path
    return build_approval_package(
        tmp_path / "approved",
        evidence=evidence,
        validation_summary={"validation": "PASS", "risk_check": "PASS"},
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        signing_key=key,
    )


def _run_main(*args: str) -> None:
    from scripts import run_portfolio

    def close_coroutine(coro):
        coro.close()

    with patch("sys.argv", ["run_portfolio.py", *args]), patch.object(run_portfolio.asyncio, "run", side_effect=close_coroutine):
        run_portfolio.main()


def test_rejects_missing_strategy_package(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APPROVED_STRATEGY_PACKAGE", raising=False)
    with pytest.raises(SystemExit) as exc:
        _run_main("--mode", "demo")
    assert exc.value.code == 1


def test_rejects_invalid_package_path(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        _run_main("--mode", "demo", "--strategy-package", str(tmp_path / "missing"))
    assert exc.value.code == 1


def test_rejects_unapproved_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package = _approved_package(tmp_path, monkeypatch)
    status_path = package / "approval_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["approval_status"] = "REJECTED"
    status_path.write_text(json.dumps(status), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        _run_main("--mode", "demo", "--strategy-package", str(package))
    assert exc.value.code == 1


def test_rejects_unsigned_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package = _approved_package(tmp_path, monkeypatch)
    (package / "signature.txt").unlink()
    with pytest.raises(SystemExit) as exc:
        _run_main("--mode", "demo", "--strategy-package", str(package))
    assert exc.value.code == 1


@pytest.mark.parametrize("mode_args", [("--mode", "demo"), ("--dry-run",)])
def test_accepts_valid_package_without_live_trading(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode_args: tuple[str, ...]) -> None:
    package = _approved_package(tmp_path, monkeypatch)
    monkeypatch.setenv("LIVE_TRADING", "false")
    _run_main(*mode_args, "--strategy-package", str(package), "--strategy-id", "ST-A2")
    assert os.environ["LIVE_TRADING"] == "false"


def test_live_mode_is_blocked_even_with_valid_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package = _approved_package(tmp_path, monkeypatch)
    with pytest.raises(SystemExit) as exc:
        _run_main("--mode", "live", "--strategy-package", str(package))
    assert exc.value.code == 1


def test_approved_package_scopes_runtime_to_its_strategy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package = _approved_package(tmp_path, monkeypatch)
    from scripts import run_portfolio

    captured = []

    def close_coroutine(coro):
        captured.append(coro.cr_frame.f_locals["strategy_id"])
        coro.close()

    with (
        patch("sys.argv", ["run_portfolio.py", "--mode", "demo", "--strategy-package", str(package)]),
        patch.object(run_portfolio.asyncio, "run", side_effect=close_coroutine),
    ):
        run_portfolio.main()
    assert captured == ["ST-A2"]
