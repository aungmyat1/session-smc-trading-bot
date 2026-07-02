from __future__ import annotations

from pathlib import Path

from strategy_input.strategy_validator import StrategyValidationResult


def write_strategy_input_report(result: StrategyValidationResult, output: Path | str) -> Path:
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Strategy Input Report", "", f"- Validation: `{'PASS' if result.valid else 'FAIL'}`"]
    if result.spec:
        lines.extend([f"- Strategy: `{result.spec.strategy_id}`", f"- Pair: `{result.spec.pair}`", f"- Session: `{result.spec.session}`"])
    if result.errors:
        lines.extend(["", "## Findings", "", *[f"- {error}" for error in result.errors]])
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return destination
