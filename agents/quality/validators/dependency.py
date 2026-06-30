"""Dependency validator — detects circular imports and forbidden module coupling."""

from __future__ import annotations

import ast
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from agents.quality.agent import StageResult, Status

logger = logging.getLogger(__name__)

_DEFAULT_IMPORT_RULES = "quality/import_rules.yaml"
_EXCLUDED = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "archive",
    "data",
    "logs",
    "reports",
    ".mypy_cache",
    ".ruff_cache",
}
# Only scan these top-level packages to keep the graph small and fast.
_SOURCE_PACKAGES = ["svos", "agents", "db", "dashboard", "strategies", "strategy"]


class DependencyValidator:
    """Builds a module import graph and detects cycles and forbidden couplings."""

    def __init__(self, root: Path, config: dict[str, Any]) -> None:
        self._root = root
        self._rules_path = root / config.get("import_rules", _DEFAULT_IMPORT_RULES)

    def validate(self) -> StageResult:
        import_rules = self._load_import_rules()
        graph = self._build_graph()

        cycles = self._find_cycles(graph)
        forbidden_violations = self._check_forbidden(
            graph, import_rules.get("forbidden_imports", [])
        )

        errors: list[str] = []
        warnings: list[str] = []

        for cycle in cycles[:20]:
            errors.append(f"CYCLE: {' → '.join(cycle)}")
        for v in forbidden_violations[:20]:
            errors.append(
                f"FORBIDDEN_IMPORT: {v['from']} imports {v['to']} ({v.get('reason', '')})"
            )

        score = max(
            0.0, round(100.0 - len(cycles) * 15.0 - len(forbidden_violations) * 5.0, 1)
        )
        details: dict[str, Any] = {
            "modules_scanned": len(graph),
            "cycles_found": len(cycles),
            "forbidden_violations": len(forbidden_violations),
            "cycle_list": [" → ".join(c) for c in cycles[:10]],
        }

        return StageResult(
            name="dependency",
            status=Status.FAIL if cycles or forbidden_violations else Status.PASS,
            score=score,
            details=details,
            errors=errors,
            warnings=warnings,
        )

    # -------------------------------------------------------------------------

    def _build_graph(self) -> dict[str, set[str]]:
        """Map module → set of modules it imports (project-internal, scoped packages)."""
        graph: dict[str, set[str]] = defaultdict(set)
        py_files: list[Path] = []
        for pkg in _SOURCE_PACKAGES:
            d = self._root / pkg
            if d.exists():
                py_files.extend(f for f in d.rglob("*.py") if not self._is_excluded(f))

        for py_file in py_files:
            module_id = self._path_to_module(py_file)
            imports = self._extract_imports(py_file)
            for imp in imports:
                if not self._is_project_module(imp):
                    continue
                target = self._path_to_module_from_import(imp)
                if target and target != module_id:  # skip self-loops
                    graph[module_id].add(target)

        return dict(graph)

    def _path_to_module_from_import(self, imp: str) -> str:
        """Normalise an import string to a canonical module-id form."""
        return imp.rstrip(".")

    def _path_to_module(self, path: Path) -> str:
        try:
            rel = path.relative_to(self._root)
            parts = list(rel.with_suffix("").parts)
            if parts and parts[-1] == "__init__":
                parts = parts[:-1]
            return ".".join(parts)
        except ValueError:
            return str(path.stem)

    def _is_project_module(self, module: str) -> bool:
        top = module.split(".")[0]
        return (self._root / top).exists() or (self._root / top).with_suffix(
            ".py"
        ).exists()

    @staticmethod
    def _extract_imports(path: Path) -> list[str]:
        """Extract only module-level imports (not inside functions/classes).

        Function-level imports cannot cause circular-import errors at load time,
        so they are excluded to avoid false-positive cycle reports.
        """
        try:
            tree = ast.parse(path.read_text(errors="replace"))
        except SyntaxError:
            return []
        imports: list[str] = []
        # Only walk the top-level body — skip inside FunctionDef / AsyncFunctionDef.
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
            # Also check class bodies (module-level classes may have class-level imports).
            elif isinstance(node, ast.ClassDef):
                for child in node.body:
                    if isinstance(child, ast.Import):
                        for alias in child.names:
                            imports.append(alias.name)
                    elif isinstance(child, ast.ImportFrom) and child.module:
                        imports.append(child.module)
        return imports

    def _find_cycles(self, graph: dict[str, set[str]]) -> list[list[str]]:
        """Detect all simple cycles in the directed graph using DFS."""
        visited: set[str] = set()
        rec_stack: set[str] = set()
        cycles: list[list[str]] = []

        def dfs(node: str, path: list[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            for neighbour in graph.get(node, set()):
                if neighbour not in visited:
                    dfs(neighbour, path + [neighbour])
                elif neighbour in rec_stack:
                    cycle_start = path.index(neighbour) if neighbour in path else 0
                    cycles.append(path[cycle_start:] + [neighbour])

            rec_stack.discard(node)

        for node in list(graph):
            if node not in visited:
                dfs(node, [node])

        return cycles

    @staticmethod
    def _check_forbidden(
        graph: dict[str, set[str]],
        forbidden: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        violations: list[dict[str, str]] = []
        for rule in forbidden:
            from_mod = rule.get("from", "")
            to_mod = rule.get("to", "")
            for source, targets in graph.items():
                if from_mod and from_mod not in source:
                    continue
                for target in targets:
                    if to_mod and to_mod in target:
                        violations.append(
                            {
                                "from": source,
                                "to": target,
                                "reason": rule.get("reason", ""),
                            }
                        )
        return violations

    def _load_import_rules(self) -> dict[str, Any]:
        if self._rules_path.exists():
            try:
                return yaml.safe_load(self._rules_path.read_text()) or {}
            except yaml.YAMLError:
                pass
        return {}

    def _is_excluded(self, path: Path) -> bool:
        return bool(_EXCLUDED.intersection(path.parts))
