from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def _dataset_timestamp_column(frame: pd.DataFrame) -> str:
    for candidate in ("timestamp", "time", "entry_time", "timestamp_utc"):
        if candidate in frame.columns:
            return candidate
    raise ValueError("dataset frame is missing a supported timestamp column")


def _normalize_time_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for column in out.columns:
        if column in {"date", "timeframe"}:
            continue
        if "time" in column or "timestamp" in column:
            out[column] = pd.to_datetime(out[column], utc=True, errors="coerce")
    return out


def _strategy_dirname(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", name.strip())
    return cleaned.strip("_") or "default"


@dataclass
class LayeredResearchStore:
    root: Path

    def save_partitioned(
        self,
        frame: pd.DataFrame,
        *parts: str,
        timestamp_col: str | None = None,
    ) -> list[Path]:
        if frame.empty:
            return []

        ts_col = timestamp_col or _dataset_timestamp_column(frame)
        out = _normalize_time_columns(frame)
        out[ts_col] = pd.to_datetime(out[ts_col], utc=True)
        out = out.dropna(subset=[ts_col]).sort_values(ts_col).reset_index(drop=True)
        out["year"] = out[ts_col].dt.year.astype(int)
        out["month"] = out[ts_col].dt.month.astype(int)

        saved: list[Path] = []
        for (year, month), partition in out.groupby(["year", "month"], sort=True):
            dest = self.root.joinpath(*parts).joinpath(
                f"year={int(year):04d}", f"month={int(month):02d}", "part-000.parquet"
            )
            dest.parent.mkdir(parents=True, exist_ok=True)
            partition.drop(columns=["year", "month"]).to_parquet(dest, index=False)
            saved.append(dest)
        return saved

    def write_outputs(
        self, outputs: dict[str, pd.DataFrame], symbol: str, timeframe: str
    ) -> dict[str, list[Path]]:
        timeframe_key = timeframe.lower()
        saved: dict[str, list[Path]] = {}

        candles = outputs["candles"].copy()
        sessions = outputs["sessions"].copy()
        if not sessions.empty:
            sessions["timestamp"] = pd.to_datetime(
                sessions["timestamp"], utc=True, errors="coerce"
            )
            candles = candles.merge(
                sessions[["timestamp", "session"]], on="timestamp", how="left"
            )
        candles["symbol"] = symbol
        candles["timeframe"] = timeframe.upper()
        candles["timestamp_utc"] = pd.to_datetime(
            candles["timestamp"], utc=True, errors="coerce"
        )
        candles["tick_volume"] = candles["volume"]
        candles["real_volume"] = candles["volume"]
        candles["spread_mean"] = (
            candles["spread"] if "spread" in candles.columns else 0.0
        )
        candles["spread_max"] = (
            candles["spread"] if "spread" in candles.columns else 0.0
        )
        saved["market"] = self.save_partitioned(
            candles, "market", timeframe_key, symbol
        )

        sessions["symbol"] = symbol
        session_paths: list[Path] = []
        if not sessions.empty and "session" in sessions.columns:
            for session_name, partition in sessions.groupby("session", sort=True):
                session_paths.extend(
                    self.save_partitioned(
                        partition, "sessions", str(session_name), symbol
                    )
                )
        saved["sessions"] = session_paths

        swings = outputs["swings"].copy()
        if not swings.empty:
            swings["symbol"] = symbol
        saved["swings"] = self.save_partitioned(swings, "structure", "swings", symbol)

        structure = outputs["structure"].copy()
        if not structure.empty:
            structure["symbol"] = symbol
        saved["structure"] = self.save_partitioned(
            structure, "structure", "trend", symbol
        )
        saved["bos"] = self.save_partitioned(
            (
                structure[structure["structure"] == "BOS"].copy()
                if not structure.empty
                else structure
            ),
            "structure",
            "bos",
            symbol,
        )
        saved["choch"] = self.save_partitioned(
            (
                structure[structure["structure"] == "CHOCH"].copy()
                if not structure.empty
                else structure
            ),
            "structure",
            "choch",
            symbol,
        )

        liquidity = outputs["liquidity"].copy()
        if not liquidity.empty:
            liquidity["symbol"] = symbol
        saved["liquidity"] = self.save_partitioned(
            liquidity, "liquidity", "liquidity_sweeps", symbol
        )

        fvg = outputs["fvg"].copy()
        if not fvg.empty:
            fvg["symbol"] = symbol
        saved["fvg"] = self.save_partitioned(fvg, "imbalances", "fvg", symbol)

        order_blocks = outputs["order_blocks"].copy()
        if not order_blocks.empty:
            order_blocks["symbol"] = symbol
        saved["order_blocks"] = self.save_partitioned(
            order_blocks, "orderflow", "order_blocks", symbol
        )

        signals = outputs["signals"].copy()
        strategy_paths: list[Path] = []
        if not signals.empty:
            signals["symbol"] = symbol
            for strategy_name, partition in signals.groupby("strategy_name", sort=True):
                strategy_paths.extend(
                    self.save_partitioned(
                        partition,
                        "features",
                        "strategy_specific",
                        _strategy_dirname(str(strategy_name)),
                        symbol,
                    )
                )
        saved["signals"] = strategy_paths

        trades = outputs["trades"].copy()
        if not trades.empty:
            trades["symbol"] = symbol
        saved["trades"] = self.save_partitioned(
            trades, "labels", "trades", symbol, timestamp_col="entry_time"
        )

        self.write_manifest(symbol, timeframe, saved)
        return saved

    def write_manifest(
        self, symbol: str, timeframe: str, saved: dict[str, list[Path]]
    ) -> Path:
        manifest_path = self.root / "metadata" / "layers_manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "timeframe": timeframe.upper(),
            "layers": [
                {
                    "name": name,
                    "paths": [str(path.relative_to(self.root)) for path in paths],
                }
                for name, paths in sorted(saved.items())
            ],
        }
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return manifest_path
