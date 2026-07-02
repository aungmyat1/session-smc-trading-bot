"""Build the deterministic, test-only ST-A2 demo package fixture."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from approval_package.package_signature import sign_files  # noqa: E402

FIXTURE_ROOT = ROOT / "tests" / "fixtures"
PACKAGE_DIR = FIXTURE_ROOT / "demo_approved_package"
REGISTRY_DIR = FIXTURE_ROOT / "svos_demo_registry" / "ST-A2"
DEMO_FIXTURE_SIGNING_KEY = "TEST-ONLY-DEMO-SMOKE-ST-A2-KEY"


def build_fixture(output_dir: Path = PACKAGE_DIR, registry_dir: Path = REGISTRY_DIR) -> Path:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    files = {
        "strategy_spec.yaml": yaml.safe_dump(
            {
                "strategy_id": "ST-A2",
                "version": "2.1.0",
                "pair": "EURUSD",
                "session": "London",
                "bias": "H4 trend",
                "entry": "M15 liquidity sweep confirmation",
                "risk_pct": 0.1,
                "reward_risk": 2.0,
                "max_trades_per_day": 1,
                "stop_loss_required": True,
            },
            sort_keys=True,
        ),
        "backtest_report.md": "# Fixture Backtest Evidence\n\nDeterministic test evidence; not production approval.\n",
        "replay_report.md": "# Fixture Replay Evidence\n\nDeterministic no-order replay fixture.\n",
        "risk_report.md": "# Fixture Risk Evidence\n\nDry-run risk firewall contract passed.\n",
        "validation_summary.json": json.dumps(
            {"risk_check": "PASS", "validation": "PASS", "fixture": True}, indent=2, sort_keys=True
        ) + "\n",
        "approval_status.json": json.dumps(
            {
                "approval_status": "APPROVED",
                "approved_at": "2026-07-02T00:00:00+00:00",
                "expires_at": "2099-12-31T23:59:59+00:00",
                "strategy_id": "ST-A2",
                "deployment_mode": "DEMO_ONLY",
                "dry_run_only": True,
                "live_eligible": False,
                "fixture": True,
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
        "demo_profile.json": json.dumps(
            {
                "account_type": "demo",
                "broker_connection_allowed": False,
                "dry_run_only": True,
                "live_eligible": False,
                "order_submission_allowed": False,
                "profile": "DEMO_ONLY",
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
    }
    for name, content in files.items():
        (output_dir / name).write_text(content, encoding="utf-8")
    signature = sign_files({name: content.encode() for name, content in files.items()}, DEMO_FIXTURE_SIGNING_KEY)
    (output_dir / "signature.txt").write_text(json.dumps(signature, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    registry_dir.mkdir(parents=True, exist_ok=True)
    (registry_dir / "state.json").write_text(
        json.dumps(
            {
                "context": "test/demo",
                "current_stage": "VIRTUAL_DEMO",
                "current_version_id": "fixture-st-a2-2.1.0",
                "latest_version": "2.1.0",
                "strategy": "ST-A2",
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    (registry_dir / "registration.json").write_text(
        json.dumps(
            {
                "context": "test/demo",
                "package": "tests/fixtures/demo_approved_package",
                "registration_status": "REGISTERED",
                "strategy": "ST-A2",
                "live_eligible": False,
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    return output_dir


if __name__ == "__main__":
    print(build_fixture())
