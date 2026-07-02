from __future__ import annotations

from pathlib import Path

import yaml

from strategy_input.strategy_spec_schema import StrategySpec


def build_strategy_config(spec: StrategySpec, output: Path | str) -> Path:
    """Write canonical YAML after schema validation."""
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = spec.model_dump(mode="json")
    destination.write_text(yaml.safe_dump(payload, sort_keys=True), encoding="utf-8")
    return destination


def load_strategy_config(path: Path | str) -> StrategySpec:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return StrategySpec.model_validate(payload)
