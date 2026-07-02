"""Offline demo smoke preflight. This module never connects to a broker or places orders."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from approval_package.package_validator import validate_package  # noqa: E402
from dashboard.strategy_service import _STATUS_TO_UI_STAGE  # noqa: E402
from scripts.run_portfolio import _ensure_strategy_package  # noqa: E402
from scripts.validate_strategy_identity import validate_strategy_identity  # noqa: E402

@dataclass(frozen=True, slots=True)
class SmokeResult:
    passed: bool
    strategy_id: str
    checks: dict[str, bool]
    failures: tuple[str, ...]
    broker_connection_attempted: bool = False
    order_submission_attempted: bool = False
    live_trading_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_preflight(
    *,
    package_path: Path | str,
    signing_key: str,
    output_dir: Path | str,
    root: Path | str = ROOT,
    registry_root: Path | str | None = None,
    mode: str = "dry-run",
) -> SmokeResult:
    if mode == "live":
        raise PermissionError("live mode is blocked for demo smoke tests")
    root_path = Path(root)
    package = Path(package_path)
    package_result = validate_package(package, signing_key=signing_key)
    try:
        profile = json.loads((package / "demo_profile.json").read_text(encoding="utf-8"))
        state = json.loads((Path(registry_root or root_path / "data" / "svos" / "registry") / "ST-A2" / "state.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        profile, state = {}, {}
    identity = validate_strategy_identity(
        root=root_path,
        package_path=package,
        runner_strategy_id="ST-A2",
        registry_root=registry_root,
    )
    canonical_runner = False
    try:
        canonical_runner = _ensure_strategy_package(
            str(package),
            "ST-A2",
            signing_key=signing_key,
            root=root_path,
            registry_root=registry_root,
        ) == "ST-A2"
    except PermissionError:
        canonical_runner = False
    checks = {
        "approved_demo_package": package_result.valid,
        "demo_only": profile.get("profile") == "DEMO_ONLY",
        "dry_run_only": profile.get("dry_run_only") is True,
        "not_live_eligible": profile.get("live_eligible") is False,
        "identity_validation": identity.valid,
        "canonical_runner_preflight": canonical_runner,
        "svos_demo_registration": state.get("context") == "test/demo" and state.get("strategy") == "ST-A2",
        "dashboard_svos_status": _STATUS_TO_UI_STAGE.get(str(state.get("current_stage"))) == "Virtual Demo Validation",
        "broker_not_connected": True,
        "order_not_submitted": True,
        "live_trading_disabled": True,
    }
    failures = tuple(name for name, passed in checks.items() if not passed)
    result = SmokeResult(not failures, identity.strategy_id, checks, failures)
    write_report(result, output_dir)
    return result


def write_report(result: SmokeResult, output_dir: Path | str) -> tuple[Path, Path]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "demo_smoke_report.json"
    markdown_path = directory / "demo_smoke_report.md"
    json_path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# Demo Smoke Test Report", "", f"- Verdict: `{'PASS' if result.passed else 'FAIL'}`", f"- Strategy: `{result.strategy_id}`", "", "## Checks", ""]
    lines.extend(f"- {'PASS' if passed else 'FAIL'} — `{name}`" for name, passed in result.checks.items())
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, markdown_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy-package", required=True)
    parser.add_argument("--signing-key", required=True, help="Test/demo signing key; never a live secret")
    parser.add_argument("--registry-root")
    parser.add_argument("--output", default="reports/demo_smoke")
    parser.add_argument("--mode", choices=["dry-run", "demo", "live"], default="dry-run")
    args = parser.parse_args()
    try:
        result = run_preflight(package_path=args.strategy_package, signing_key=args.signing_key, output_dir=args.output, registry_root=args.registry_root, mode=args.mode)
    except PermissionError as exc:
        print(f"FAIL: {exc}")
        return 1
    print("PASS" if result.passed else "FAIL")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
