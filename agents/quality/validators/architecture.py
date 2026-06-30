"""Architecture validator — enforces module boundary rules via AST import analysis."""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from agents.quality.agent import Status, StageResult

logger = logging.getLogger(__name__)

_DEFAULT_RULES_PATH = "quality/architecture_rules.yaml"


@dataclass
class Violation:
    source_file: str
    source_layer: str
    imported_module: str
    target_layer: str
    rule: str
    reason: str


@dataclass
class LayerDef:
    name: str
    patterns: list[re.Pattern[str]] = field(default_factory=list)


class ArchitectureValidator:
    """Validates that module imports obey the configured layer boundary rules."""

    def __init__(self, root: Path, config: dict[str, Any]) -> None:
        self._root = root
        self._rules_path: Path = root / config.get(
            "architecture_rules", _DEFAULT_RULES_PATH
        )
        self._min_score: float = float(config.get("minimum_architecture_score", 90.0))
        self._max_violations: int = int(config.get("max_architecture_violations", 0))

    def validate(self) -> StageResult:
        rules = self._load_rules()
        if not rules:
            return StageResult(
                name="architecture",
                status=Status.SKIP,
                score=100.0,
                details={"reason": f"rules file not found: {self._rules_path}"},
            )

        layers = self._build_layers(rules.get("layers", {}))
        forbidden = rules.get("forbidden", [])
        py_files = [f for f in self._root.rglob("*.py") if not self._is_excluded(f)]

        violations: list[Violation] = []
        files_checked = 0
        for py_file in py_files:
            files_checked += 1
            source_layer = self._classify_file(py_file, layers)
            if source_layer is None:
                continue
            imports = self._extract_imports(py_file)
            for imp in imports:
                target_layer = self._classify_module(imp, layers)
                if target_layer is None or target_layer == source_layer:
                    continue
                for rule in forbidden:
                    if (
                        rule.get("from") == source_layer
                        and rule.get("to") == target_layer
                    ):
                        violations.append(
                            Violation(
                                source_file=str(py_file.relative_to(self._root)),
                                source_layer=source_layer,
                                imported_module=imp,
                                target_layer=target_layer,
                                rule=f"{source_layer}→{target_layer}",
                                reason=rule.get("reason", "forbidden dependency"),
                            )
                        )

        score = max(0.0, round(100.0 - len(violations) * 10.0, 1))
        errors = [
            f"ARCH {v.rule} in {v.source_file}: imports {v.imported_module} ({v.reason})"
            for v in violations
        ]
        failed = len(violations) > self._max_violations or score < self._min_score

        return StageResult(
            name="architecture",
            status=Status.FAIL if failed else Status.PASS,
            score=score,
            details={
                "files_checked": files_checked,
                "violations": len(violations),
                "violation_list": [
                    {"file": v.source_file, "rule": v.rule, "import": v.imported_module}
                    for v in violations[:50]
                ],
            },
            errors=errors[:30],
        )

    # -------------------------------------------------------------------------

    def _load_rules(self) -> dict[str, Any] | None:
        if not self._rules_path.exists():
            logger.warning("Architecture rules not found at %s", self._rules_path)
            return None
        try:
            return yaml.safe_load(self._rules_path.read_text()) or {}
        except yaml.YAMLError as exc:
            logger.error("Cannot parse architecture rules: %s", exc)
            return None

    @staticmethod
    def _build_layers(layers_cfg: dict[str, Any]) -> dict[str, LayerDef]:
        layers: dict[str, LayerDef] = {}
        for name, cfg in layers_cfg.items():
            if isinstance(cfg, dict):
                patterns = cfg.get("patterns", [cfg.get("pattern", "")])
            else:
                patterns = [str(cfg)]
            compiled = [re.compile(p) for p in patterns if p]
            layers[name] = LayerDef(name=name, patterns=compiled)
        return layers

    def _classify_file(self, path: Path, layers: dict[str, LayerDef]) -> str | None:
        rel = str(path.relative_to(self._root)).replace("\\", "/")
        return self._match_layers(rel, layers)

    def _classify_module(self, module: str, layers: dict[str, LayerDef]) -> str | None:
        mod_path = module.replace(".", "/")
        return self._match_layers(mod_path, layers)

    @staticmethod
    def _match_layers(path: str, layers: dict[str, LayerDef]) -> str | None:
        for name, layer in layers.items():
            for pat in layer.patterns:
                if pat.search(path):
                    return name
        return None

    @staticmethod
    def _extract_imports(path: Path) -> list[str]:
        try:
            tree = ast.parse(path.read_text(errors="replace"))
        except SyntaxError:
            return []
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return imports

    def _is_excluded(self, path: Path) -> bool:
        excluded_parts = {
            ".git",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "archive",
            "data",
            "logs",
            "reports",
            "node_modules",
        }
        return bool(excluded_parts.intersection(path.parts))
