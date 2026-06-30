from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1

import pandas as pd
import numpy as np


@dataclass(frozen=True)
class SignalConfig:
    lookback_sweeps: int = 3
    lookback_structure: int = 3
    lookback_fvg: int = 5
    lookback_ob: int = 5
    max_signals_per_day: int = 3
    min_confluence: int = 1
    strategy_name: str = "ST-A2"
    allowed_sessions: tuple[str, ...] = ("asian", "london", "new_york")


class SignalGenerator:
    """Convert engineered features into searchable trade opportunities."""

    def __init__(self, config: SignalConfig | None = None) -> None:
        self.config = config or SignalConfig()

    def generate(
        self,
        candles: pd.DataFrame,
        sessions: pd.DataFrame,
        structure: pd.DataFrame,
        liquidity: pd.DataFrame,
        fvg: pd.DataFrame,
        order_blocks: pd.DataFrame,
    ) -> pd.DataFrame:
        candles = candles.copy()
        candles["timestamp"] = pd.to_datetime(candles["timestamp"], utc=True)
        sessions = sessions.copy()
        structure = structure.copy()
        liquidity = liquidity.copy()
        fvg = fvg.copy()
        order_blocks = order_blocks.copy()
        for df in [sessions, structure, liquidity, fvg]:
            if not df.empty:
                df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        if not order_blocks.empty:
            order_blocks["time"] = pd.to_datetime(order_blocks["time"], utc=True)

        candles = candles.sort_values("timestamp").reset_index(drop=True)
        base = candles[["timestamp"]].copy()
        base["pair"] = candles["pair"] if "pair" in candles.columns else ""
        if "pair" in candles.columns:
            pair_value = candles["pair"].iloc[0]
        else:
            pair_value = ""

        session_df = (
            sessions[["timestamp", "session"]].sort_values("timestamp")
            if not sessions.empty
            else pd.DataFrame(columns=["timestamp", "session"])
        )
        merged = base.merge(session_df, on="timestamp", how="left")
        merged["session"] = merged["session"].fillna("asian")

        def _merge_latest(
            frame: pd.DataFrame, ts_col: str, keep_cols: list[str]
        ) -> pd.DataFrame:
            if frame.empty:
                out = merged[["timestamp"]].copy()
                for col in keep_cols:
                    out[col] = pd.NA
                out[f"{ts_col}_event_ts"] = pd.NaT
                return out
            tmp = frame[keep_cols].copy()
            tmp = tmp.rename(columns={ts_col: f"{ts_col}_event_ts"})
            tmp = tmp.sort_values(f"{ts_col}_event_ts")
            return pd.merge_asof(
                merged[["timestamp"]].sort_values("timestamp"),
                tmp,
                left_on="timestamp",
                right_on=f"{ts_col}_event_ts",
                direction="backward",
            )

        liq_latest = (
            _merge_latest(
                liquidity.rename(columns={"timestamp": "timestamp"}),
                "timestamp",
                ["timestamp", "sweep_type"],
            )
            if not liquidity.empty
            else pd.DataFrame(
                {
                    "timestamp": merged["timestamp"],
                    "timestamp_event_ts": pd.NaT,
                    "sweep_type": pd.NA,
                }
            )
        )
        struct_latest = (
            _merge_latest(
                structure.rename(columns={"timestamp": "timestamp"}),
                "timestamp",
                ["timestamp", "structure", "direction"],
            )
            if not structure.empty
            else pd.DataFrame(
                {
                    "timestamp": merged["timestamp"],
                    "timestamp_event_ts": pd.NaT,
                    "structure": pd.NA,
                    "direction": pd.NA,
                }
            )
        )
        fvg_latest = (
            _merge_latest(
                fvg.rename(columns={"timestamp": "timestamp"}),
                "timestamp",
                ["timestamp", "direction"],
            )
            if not fvg.empty
            else pd.DataFrame(
                {
                    "timestamp": merged["timestamp"],
                    "timestamp_event_ts": pd.NaT,
                    "direction": pd.NA,
                }
            )
        )
        ob_frame = (
            order_blocks.rename(columns={"time": "timestamp"})
            if not order_blocks.empty
            else pd.DataFrame(columns=["timestamp", "direction"])
        )
        ob_latest = (
            _merge_latest(ob_frame, "timestamp", ["timestamp", "direction"])
            if not ob_frame.empty
            else pd.DataFrame(
                {
                    "timestamp": merged["timestamp"],
                    "timestamp_event_ts": pd.NaT,
                    "direction": pd.NA,
                }
            )
        )

        candles = candles.sort_values("timestamp").reset_index(drop=True)
        freq_delta = (
            candles["timestamp"].diff().dropna().median()
            if len(candles) > 1
            else pd.Timedelta("1min")
        )
        freq_delta = (
            pd.Timedelta(freq_delta) if pd.notna(freq_delta) else pd.Timedelta("1min")
        )

        timestamps = candles["timestamp"].reset_index(drop=True)
        sessions_series = merged["session"].reset_index(drop=True)
        allowed_sessions = set(self.config.allowed_sessions)

        liq_event_ts = pd.to_datetime(
            liq_latest["timestamp_event_ts"], utc=True, errors="coerce"
        )
        struct_event_ts = pd.to_datetime(
            struct_latest["timestamp_event_ts"], utc=True, errors="coerce"
        )
        fvg_event_ts = pd.to_datetime(
            fvg_latest["timestamp_event_ts"], utc=True, errors="coerce"
        )
        ob_event_ts = pd.to_datetime(
            ob_latest["timestamp_event_ts"], utc=True, errors="coerce"
        )

        recent_liq = liq_event_ts.notna() & (
            (timestamps - liq_event_ts) <= freq_delta * self.config.lookback_sweeps
        )
        recent_struct = struct_event_ts.notna() & (
            (timestamps - struct_event_ts)
            <= freq_delta * self.config.lookback_structure
        )
        recent_fvg = fvg_event_ts.notna() & (
            (timestamps - fvg_event_ts) <= freq_delta * self.config.lookback_fvg
        )
        recent_ob = ob_event_ts.notna() & (
            (timestamps - ob_event_ts) <= freq_delta * self.config.lookback_ob
        )

        sweep = recent_liq.to_numpy()
        bos = (
            recent_struct & (struct_latest["structure"].astype(str) == "BOS")
        ).to_numpy()
        choch = (
            recent_struct & (struct_latest["structure"].astype(str) == "CHOCH")
        ).to_numpy()
        gap = recent_fvg.to_numpy()
        ob = recent_ob.to_numpy()

        votes = (
            np.where(
                recent_liq & (liq_latest["sweep_type"].astype(str) == "bullish"),
                1,
                np.where(
                    recent_liq & (liq_latest["sweep_type"].astype(str) == "bearish"),
                    -1,
                    0,
                ),
            )
            + np.where(
                recent_struct & (struct_latest["direction"].astype(str) == "bullish"),
                1,
                np.where(
                    recent_struct
                    & (struct_latest["direction"].astype(str) == "bearish"),
                    -1,
                    0,
                ),
            )
            + np.where(
                recent_fvg & (fvg_latest["direction"].astype(str) == "bullish"),
                1,
                np.where(
                    recent_fvg & (fvg_latest["direction"].astype(str) == "bearish"),
                    -1,
                    0,
                ),
            )
            + np.where(
                recent_ob & (ob_latest["direction"].astype(str) == "bullish"),
                1,
                np.where(
                    recent_ob & (ob_latest["direction"].astype(str) == "bearish"), -1, 0
                ),
            )
        )
        confluence = (
            sweep.astype(int)
            + bos.astype(int)
            + choch.astype(int)
            + gap.astype(int)
            + ob.astype(int)
        )
        session_mask = sessions_series.isin(allowed_sessions).to_numpy()
        direction_mask = votes != 0
        selection = (
            session_mask & direction_mask & (confluence >= self.config.min_confluence)
        )

        selected = candles.loc[selection, ["timestamp", "close"]].copy()
        if selected.empty:
            return pd.DataFrame(
                columns=[
                    "signal_id",
                    "timestamp",
                    "pair",
                    "session",
                    "direction",
                    "strategy_name",
                    "sweep",
                    "bos",
                    "choch",
                    "fvg",
                    "order_block",
                    "entry_price",
                    "confluence",
                ]
            )

        selected["pair"] = pair_value
        selected["session"] = sessions_series.loc[selection].to_numpy()
        selected["direction"] = np.where(votes[selection] > 0, "LONG", "SHORT")
        selected["strategy_name"] = self.config.strategy_name
        selected["sweep"] = sweep[selection]
        selected["bos"] = bos[selection]
        selected["choch"] = choch[selection]
        selected["fvg"] = gap[selection]
        selected["order_block"] = ob[selection]
        selected["entry_price"] = selected["close"].astype(float)
        selected["confluence"] = confluence[selection]
        selected["signal_id"] = [
            sha1(
                f"{self.config.strategy_name}-{pair_value}-{ts.isoformat()}-{direction}".encode()
            ).hexdigest()[:16]
            for ts, direction in zip(
                selected["timestamp"], selected["direction"], strict=False
            )
        ]
        rows = selected.drop(columns=["close"]).to_dict("records")

        frame = pd.DataFrame.from_records(
            rows,
            columns=[
                "signal_id",
                "timestamp",
                "pair",
                "session",
                "direction",
                "strategy_name",
                "sweep",
                "bos",
                "choch",
                "fvg",
                "order_block",
                "entry_price",
                "confluence",
            ],
        )
        if frame.empty or self.config.max_signals_per_day <= 0:
            return frame

        frame["date"] = frame["timestamp"].dt.floor("D")
        frame = frame.sort_values(["pair", "date", "timestamp"]).reset_index(drop=True)
        frame = frame.groupby(["pair", "date"], group_keys=False).head(
            self.config.max_signals_per_day
        )
        return frame.drop(columns=["date"]).reset_index(drop=True)
