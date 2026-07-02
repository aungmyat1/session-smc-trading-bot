"""Validate one canonical strategy identity before demo runtime starts."""

from __future__ import annotations

import argparse
import json
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


def _canonical(value: object) -> str:
    return re.sub(r"[^A-Z0-9]+", "-", str(value).strip().upper()).strip("-")


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return payload if isinstance(payload, dict) else {}


def package_strategy_id(package_path: Path | str) -> str:
    directory = Path(package_path)
    spec = _load_yaml(directory / "strategy_spec.yaml")
    try:
        status = json.loads((directory / "approval_status.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        status = {}
    for source in (status, spec):
        for key in ("strategy_id", "strategy", "name"):
            value = source.get(key)
            if value:
                return str(value).strip()
    return ""


@dataclass(frozen=True, slots=True)
class IdentityValidationResult:
    valid: bool
    strategy_id: str
    identities: dict[str, str]
    mismatches: tuple[str, ...]
    recommended_fix: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def require_valid(self) -> None:
        if not self.valid:
            raise PermissionError("strategy identity rejected: " + "; ".join(self.mismatches))


def validate_strategy_identity(
    *,
    root: Path | str,
    package_path: Path | str,
    runner_strategy_id: str,
    catalog_path: Path | str | None = None,
    portfolio_path: Path | str | None = None,
    registry_root: Path | str | None = None,
) -> IdentityValidationResult:
    root_path = Path(root)
    catalog = _load_yaml(Path(catalog_path) if catalog_path else root_path / "config" / "strategy_catalog.yaml")
    portfolio = _load_yaml(Path(portfolio_path) if portfolio_path else root_path / "config" / "strategy_portfolio.yaml")
    package_id = package_strategy_id(package_path)
    runner_id = runner_strategy_id.strip()
    target = _canonical(runner_id or package_id)

    catalog_names = [str(name) for name in catalog.get("strategies", {})]
    portfolio_names = [str(name) for name in portfolio.get("strategies", {})]
    catalog_id = next((name for name in catalog_names if _canonical(name) == target), "")
    portfolio_id = next((name for name in portfolio_names if _canonical(name) == target), "")

    registry_base = Path(registry_root) if registry_root else root_path / "data" / "svos" / "registry"
    registry_id = ""
    if catalog_id:
        try:
            state = json.loads((registry_base / catalog_id / "state.json").read_text(encoding="utf-8"))
            registry_id = str(state.get("strategy", "")).strip()
        except (OSError, json.JSONDecodeError):
            registry_id = ""

    identities = {
        "catalog": catalog_id,
        "portfolio": portfolio_id,
        "approved_package": package_id,
        "svos_registry": registry_id,
        "runner": runner_id,
    }
    mismatches: list[str] = []
    if not target:
        mismatches.append("runner and package strategy identity are missing")
    for source, identity in identities.items():
        if not identity:
            mismatches.append(f"{source} identity is missing")
        elif target and _canonical(identity) != target:
            mismatches.append(f"{source} identity {identity!r} does not match runner {runner_id!r}")
    recommendation = (
        "No change required."
        if not mismatches
        else f"Use one canonical ID ({runner_id or package_id or '<strategy-id>'}) in the catalog key, portfolio key, package strategy_id, SVOS state.strategy, and --strategy-id."
    )
    canonical_id = catalog_id or portfolio_id or registry_id or runner_id or package_id
    return IdentityValidationResult(not mismatches, canonical_id, identities, tuple(mismatches), recommendation)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy-package")
    parser.add_argument("--strategy-id")
    parser.add_argument("--root", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return _self_test()
    if not args.strategy_package or not args.strategy_id:
        parser.error("--strategy-package and --strategy-id are required unless --self-test is used")
    result = validate_strategy_identity(root=args.root, package_path=args.strategy_package, runner_strategy_id=args.strategy_id)
    print("PASS" if result.valid else "FAIL")
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0 if result.valid else 1


def _self_test() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        config = root / "config"
        config.mkdir()
        (config / "strategy_catalog.yaml").write_text("strategies:\n  SELF-TEST: {}\n", encoding="utf-8")
        (config / "strategy_portfolio.yaml").write_text("strategies:\n  SELF-TEST:\n    enabled: true\n", encoding="utf-8")
        state = root / "data" / "svos" / "registry" / "SELF-TEST" / "state.json"
        state.parent.mkdir(parents=True)
        state.write_text(json.dumps({"strategy": "SELF-TEST"}), encoding="utf-8")
        package = root / "package"
        package.mkdir()
        (package / "strategy_spec.yaml").write_text("strategy_id: SELF-TEST\n", encoding="utf-8")
        (package / "approval_status.json").write_text(json.dumps({"approval_status": "APPROVED"}), encoding="utf-8")
        passed = validate_strategy_identity(root=root, package_path=package, runner_strategy_id="SELF-TEST")
        mismatch = validate_strategy_identity(root=root, package_path=package, runner_strategy_id="OTHER")
        if not passed.valid or mismatch.valid:
            print("FAIL")
            return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
