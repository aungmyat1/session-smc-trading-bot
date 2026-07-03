from pathlib import Path

import pytest


@pytest.fixture
def sample_candles(tmp_path: Path) -> Path:
    path = tmp_path / "candles.csv"
    path.write_text(
        "symbol,timestamp,open,high,low,close,volume,timeframe,source\n"
        "EURUSD,2024-01-01T00:01:00Z,1.1,1.2,1.0,1.15,11,M1,test\n"
        "EURUSD,2024-01-01T00:00:00Z,1.0,1.1,0.9,1.05,10,M1,test\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def strategy_package(tmp_path: Path) -> Path:
    path = tmp_path / "example.package.json"
    path.write_text('{"strategy":"provenance-only"}\n', encoding="utf-8")
    return path
