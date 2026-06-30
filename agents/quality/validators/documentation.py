"""Documentation validator — checks docstring and type-hint coverage."""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agents.quality.agent import Status, StageResult

logger = logging.getLogger(__name__)

_SOURCE_DIRS = ["svos", "agents", "db"]
_EXCLUDED = {
    ".git",
    "__pycache__",
    "archive",
    "data",
    "logs",
    "reports",
    ".pytest_cache",
}


@dataclass
class DocStats:
    functions: int = 0
    functions_with_docstring: int = 0
    functions_with_return_type: int = 0
    classes: int = 0
    classes_with_docstring: int = 0
    modules: int = 0
    modules_with_docstring: int = 0


class DocumentationValidator:
    """Measures docstring coverage and type-hint adoption across source directories."""

    def __init__(self, root: Path, config: dict[str, Any]) -> None:
        self._root = root
        self._min_score: float = float(config.get("minimum_documentation_score", 70.0))
        self._min_docstring_pct: float = float(
            config.get("minimum_docstring_pct", 60.0)
        )
        self._min_typehint_pct: float = float(config.get("minimum_typehint_pct", 60.0))

    def validate(self) -> StageResult:
        stats = DocStats()
        missing_docstrings: list[str] = []

        for src in _SOURCE_DIRS:
            d = self._root / src
            if not d.exists():
                continue
            for py_file in d.rglob("*.py"):
                if self._is_excluded(py_file):
                    continue
                self._analyze_file(py_file, stats, missing_docstrings)

        # Module docstring coverage
        mod_pct = (
            (stats.modules_with_docstring / stats.modules * 100.0)
            if stats.modules > 0
            else 100.0
        )
        # Function docstring coverage
        fn_doc_pct = (
            (stats.functions_with_docstring / stats.functions * 100.0)
            if stats.functions > 0
            else 100.0
        )
        # Return type hint coverage
        fn_type_pct = (
            (stats.functions_with_return_type / stats.functions * 100.0)
            if stats.functions > 0
            else 100.0
        )
        # Class docstring coverage
        cls_pct = (
            (stats.classes_with_docstring / stats.classes * 100.0)
            if stats.classes > 0
            else 100.0
        )

        # Composite documentation score
        score = round(
            fn_doc_pct * 0.35 + fn_type_pct * 0.30 + cls_pct * 0.20 + mod_pct * 0.15, 1
        )

        errors: list[str] = []
        warnings: list[str] = []
        if fn_doc_pct < self._min_docstring_pct:
            errors.append(
                f"Function docstring coverage {fn_doc_pct:.1f}% < required {self._min_docstring_pct}%"
            )
        if fn_type_pct < self._min_typehint_pct:
            warnings.append(
                f"Return type-hint coverage {fn_type_pct:.1f}% < target {self._min_typehint_pct}%"
            )
        if score < self._min_score:
            errors.append(f"Documentation score {score} < required {self._min_score}")

        # Surface first N undocumented items as warnings.
        for item in missing_docstrings[:10]:
            warnings.append(f"Missing docstring: {item}")

        return StageResult(
            name="documentation",
            status=Status.FAIL if errors else Status.PASS,
            score=score,
            details={
                "modules": stats.modules,
                "module_docstring_pct": round(mod_pct, 1),
                "functions": stats.functions,
                "function_docstring_pct": round(fn_doc_pct, 1),
                "function_typehint_pct": round(fn_type_pct, 1),
                "classes": stats.classes,
                "class_docstring_pct": round(cls_pct, 1),
            },
            errors=errors,
            warnings=warnings,
        )

    # -------------------------------------------------------------------------

    def _analyze_file(self, path: Path, stats: DocStats, missing: list[str]) -> None:
        try:
            source = path.read_text(errors="replace")
            tree = ast.parse(source)
        except (SyntaxError, OSError):
            return

        rel = str(path.relative_to(self._root))
        stats.modules += 1
        if ast.get_docstring(tree):
            stats.modules_with_docstring += 1

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if (
                    node.name.startswith("__")
                    and node.name.endswith("__")
                    and node.name not in ("__init__",)
                ):
                    continue  # skip dunder methods
                stats.functions += 1
                if ast.get_docstring(node):
                    stats.functions_with_docstring += 1
                else:
                    missing.append(f"{rel}:{node.lineno} def {node.name}()")
                if node.returns is not None:
                    stats.functions_with_return_type += 1

            elif isinstance(node, ast.ClassDef):
                stats.classes += 1
                if ast.get_docstring(node):
                    stats.classes_with_docstring += 1

    def _is_excluded(self, path: Path) -> bool:
        return bool(_EXCLUDED.intersection(path.parts))
