from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def parse_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = value.strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class ReplayConfig:
    run_id: str
    symbol: str
    timeframe: str
    start_time: datetime
    end_time: datetime
    data_path: Path
    strategy_package_path: Path
    output_dir: Path = Path("artifacts/replay")

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", self.symbol.upper().replace("/", ""))
        object.__setattr__(self, "timeframe", self.timeframe.upper())
        object.__setattr__(self, "start_time", parse_timestamp(self.start_time))
        object.__setattr__(self, "end_time", parse_timestamp(self.end_time))
        object.__setattr__(self, "data_path", Path(self.data_path))
        object.__setattr__(self, "strategy_package_path", Path(self.strategy_package_path))
        object.__setattr__(self, "output_dir", Path(self.output_dir))
        if not self.run_id or any(char in self.run_id for char in "/\\"):
            raise ValueError("run_id must be non-empty and must not contain path separators")
        if self.end_time < self.start_time:
            raise ValueError("end_time must not precede start_time")
        if not self.data_path.is_file():
            raise ValueError(f"historical data file does not exist: {self.data_path}")
        if not self.strategy_package_path.is_file():
            raise ValueError(f"strategy package provenance file does not exist: {self.strategy_package_path}")

    @property
    def run_dir(self) -> Path:
        return self.output_dir / self.run_id
