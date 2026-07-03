"""Architecture gates for the Stage 2 boundary packages."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOTS = {
    "shared": ROOT / "shared",
    "application": ROOT / "application",
    "production": ROOT / "production",
}

FORBIDDEN_PREFIXES = {
    "shared": ("agtrade", "application", "dashboard", "db", "execution", "production", "research", "svos"),
    "production": ("agtrade", "dashboard", "research", "strategy_audit", "strategy_validation", "svos"),
}

SVOS_FORBIDDEN_LIVE_MODULES = (
    "execution.metaapi_client",
    "execution.mt5_connector",
    "execution.mt5_executor",
    "execution.order_manager",
    "execution.trade_manager",
    "production",
)


def _module_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.module:
        return [node.module]
    return []


def _python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def test_stage2_package_roots_exist() -> None:
    missing = [name for name, path in PACKAGE_ROOTS.items() if not path.is_dir()]
    assert not missing, f"Expected Stage 2 package roots are missing: {missing}"


def test_agtrade_cli_depends_on_application_layer() -> None:
    cli_path = ROOT / "agtrade" / "cli.py"
    tree = ast.parse(cli_path.read_text(encoding="utf-8"), filename=str(cli_path))
    imports = {name for node in ast.walk(tree) for name in _module_names(node)}
    assert "application" in imports or any(name.startswith("application.") for name in imports), (
        "agtrade.cli should depend on the application layer during the migration"
    )


def test_boundary_packages_respect_import_rules() -> None:
    violations: list[str] = []
    for package, forbidden_prefixes in FORBIDDEN_PREFIXES.items():
        for path in _python_files(PACKAGE_ROOTS[package]):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path.relative_to(ROOT)))
            for node in ast.walk(tree):
                for module in _module_names(node):
                    for prefix in forbidden_prefixes:
                        if module == prefix or module.startswith(f"{prefix}."):
                            violations.append(f"{path.relative_to(ROOT)} imports {module}")
    assert not violations, "Boundary package import violations:\n" + "\n".join(violations)


def test_svos_does_not_import_live_execution_modules() -> None:
    violations: list[str] = []
    for path in _python_files(ROOT / "svos"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path.relative_to(ROOT)))
        for node in ast.walk(tree):
            for module in _module_names(node):
                if any(module == prefix or module.startswith(f"{prefix}.") for prefix in SVOS_FORBIDDEN_LIVE_MODULES):
                    violations.append(f"{path.relative_to(ROOT)} imports {module}")
    assert not violations, "SVOS must not import live execution modules:\n" + "\n".join(violations)


def test_legacy_signal_module_is_a_shared_reexport() -> None:
    tree = ast.parse((ROOT / "core" / "signal.py").read_text(encoding="utf-8"), filename="core/signal.py")
    imports = {name for node in ast.walk(tree) for name in _module_names(node)}
    assert "shared.strategy_api.signal" in imports


def test_legacy_svos_shared_modules_reexport_shared_packages() -> None:
    expected = {
        "svos/shared/models.py": "shared.models.records",
        "svos/shared/support.py": "shared.serialization.json_files",
    }
    for relative, target in expected.items():
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"), filename=relative)
        imports = {name for node in ast.walk(tree) for name in _module_names(node)}
        assert target in imports, f"{relative} should re-export from {target}"


def test_active_code_avoids_legacy_shared_import_paths() -> None:
    scan_roots = [
        ROOT / "application",
        ROOT / "core",
        ROOT / "execution",
        ROOT / "production",
        ROOT / "strategies",
        ROOT / "svos",
    ]
    allowed_files = {
        ROOT / "core" / "signal.py",
        ROOT / "svos" / "shared" / "__init__.py",
        ROOT / "svos" / "shared" / "models.py",
        ROOT / "svos" / "shared" / "support.py",
    }
    forbidden = ("core.signal", "svos.shared.models", "svos.shared.support")
    violations: list[str] = []

    for root in scan_roots:
        for path in _python_files(root):
            if path in allowed_files:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path.relative_to(ROOT)))
            for node in ast.walk(tree):
                for module in _module_names(node):
                    if module in forbidden:
                        violations.append(f"{path.relative_to(ROOT)} imports {module}")

    assert not violations, "Active code should import shared.* directly:\n" + "\n".join(violations)


def test_production_engine_facade_import_policy() -> None:
    facade_dir = ROOT / "production" / "engine"
    allowed_prefixes = ("execution", "production", "__future__")
    allowed_stdlib = {"asyncio", "collections", "dataclasses", "enum", "json", "os", "pathlib", "typing", "uuid"}
    violations: list[str] = []
    for path in _python_files(facade_dir):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path.relative_to(ROOT)))
        for node in ast.walk(tree):
            for module in _module_names(node):
                if module.startswith("shared."):
                    continue
                if module == "shared":
                    continue
                if module.split(".", 1)[0] in allowed_stdlib:
                    continue
                if not any(module == prefix or module.startswith(f"{prefix}.") for prefix in allowed_prefixes):
                    violations.append(f"{path.relative_to(ROOT)} imports {module}")
    assert not violations, "Production engine facade should stay narrowly scoped:\n" + "\n".join(violations)


def test_active_code_uses_production_engine_for_runtime_services() -> None:
    scan_roots = [
        ROOT / "application",
        ROOT / "dashboard",
        ROOT / "production",
        ROOT / "scripts",
        ROOT / "svos",
    ]
    allowed_files = {
        ROOT / "execution" / "control_plane.py",
        ROOT / "execution" / "execution_state.py",
        ROOT / "execution" / "governance_guard.py",
        ROOT / "execution" / "trade_manager.py",
        ROOT / "production" / "engine" / "services.py",
    }
    forbidden = (
        "execution.control_plane",
        "execution.execution_state",
        "execution.governance_guard",
        "execution.trade_manager",
    )
    violations: list[str] = []

    for root in scan_roots:
        for path in _python_files(root):
            if path in allowed_files:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path.relative_to(ROOT)))
            for node in ast.walk(tree):
                for module in _module_names(node):
                    if module in forbidden:
                        violations.append(f"{path.relative_to(ROOT)} imports {module}")

    assert not violations, (
        "Runtime service consumers should import through production.engine:\n" + "\n".join(violations)
    )
