from __future__ import annotations

import json
from pathlib import Path

from historical_replay.replay_engine import ReplayResult


def write_replay_report(result: ReplayResult, output_dir: Path | str) -> tuple[Path, Path]:
    directory = Path(output_dir) / result.run_id
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "replay_report.json"
    md_path = directory / "replay_report.md"
    json_path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(
        "\n".join(["# Historical Replay Report", "", f"- Run ID: `{result.run_id}`", f"- Pair: `{result.pair}`", f"- Candles: `{result.candles_processed}`", f"- Signals: `{len(result.events)}`", f"- Missing M1 candles: `{result.missing_m1_candles}`"]) + "\n",
        encoding="utf-8",
    )
    return json_path, md_path
