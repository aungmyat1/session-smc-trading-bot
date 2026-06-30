"""
V2 session helpers for the replay snapshot.

This module keeps the legacy Asian-range helper for compatibility, but adds a
UTC session-box model and overlapping session classification that match the
fully-auto V2 runbook more closely.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Mapping, Any
from zoneinfo import ZoneInfo

_EST = ZoneInfo("America/New_York")
_UTC = timezone.utc

SESSION_WINDOWS_V2 = {
    "asian": {
        "start_h": 0,
        "end_h": 8,
        "label": "Asian",
        "range_thr": 0.50,
        "trend_thr": 0.70,
    },
    "london": {
        "start_h": 7,
        "end_h": 12,
        "label": "London",
        "range_thr": 0.55,
        "trend_thr": 0.75,
    },
    "overlap": {
        "start_h": 12,
        "end_h": 15,
        "label": "Overlap",
        "range_thr": 0.60,
        "trend_thr": 0.80,
    },
    "newyork": {
        "start_h": 12,
        "end_h": 17,
        "label": "NewYork",
        "range_thr": 0.55,
        "trend_thr": 0.75,
    },
}

_SESSION_PRIORITY = ("overlap", "newyork", "london", "asian")


@dataclass
class AsianRange:
    trade_date: date  # EST calendar date this range feeds into
    high: float
    low: float

    @property
    def range_points(self) -> float:
        """Raw range size in price units."""
        return round(self.high - self.low, 6)

    def range_pips_for_symbol(self, symbol: str = "") -> float:
        """Range in pips/points. USDJPY: 1 pip = 0.01. Others: 1 pip = 0.0001."""
        pip = 0.01 if "JPY" in symbol.upper() else 0.0001
        return round((self.high - self.low) / pip, 1)


def _parse_utc(t: Any) -> datetime:
    """Parse ISO string or datetime to UTC-aware datetime."""
    if isinstance(t, datetime):
        return t if t.tzinfo else t.replace(tzinfo=_UTC)
    return datetime.fromisoformat(str(t).replace("Z", "+00:00"))


def _to_est(dt_utc: datetime) -> datetime:
    return dt_utc.astimezone(_EST)


def _as_records(data: Any) -> list[dict]:
    """Normalize DataFrame-like or list-like candle containers into dicts."""
    if data is None:
        return []
    if hasattr(data, "to_dict"):
        try:
            return list(data.to_dict(orient="records"))
        except Exception:
            pass
    if isinstance(data, list):
        return [dict(row) for row in data]
    return [dict(row) for row in data]


def _hour_of(row: Mapping[str, Any]) -> int:
    return _parse_utc(row["time"]).hour


def _atr(records: list[dict], period: int = 14) -> float:
    """Simple Wilder-style ATR approximation over the provided records."""
    if len(records) < 2:
        return 0.0
    trs: list[float] = []
    prev_close: float | None = None
    for row in records:
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        if prev_close is None:
            tr = high - low
        else:
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
        prev_close = close
    if not trs:
        return 0.0
    if len(trs) <= period:
        return round(sum(trs) / len(trs), 6)
    seed = sum(trs[:period]) / period
    atr = seed
    for tr in trs[period:]:
        atr = ((atr * (period - 1)) + tr) / period
    return round(atr, 6)


def active_sessions(
    dt_utc: datetime, session_windows: dict[str, dict] | None = None
) -> list[str]:
    """Return all V2 sessions active at the given UTC datetime."""
    windows = session_windows or SESSION_WINDOWS_V2
    hour = _parse_utc(dt_utc).hour
    active: list[str] = []
    for name, cfg in windows.items():
        start = int(cfg["start_h"])
        end = int(cfg["end_h"])
        if start <= hour < end:
            active.append(name)
    return active


def classify_session(
    dt_utc: datetime, session_windows: dict[str, dict] | None = None
) -> "str | None":
    """
    Classify a UTC datetime into a V2 session label.

    Because the V2 windows overlap, the function returns the highest-priority
    active session. Use `active_sessions()` when you need the full overlap set.
    """
    windows = session_windows or SESSION_WINDOWS_V2
    active = set(active_sessions(dt_utc, windows))
    for name in _SESSION_PRIORITY:
        if name in active and name in windows:
            return name
    return None


def build_session_box(df_1h: Any, start_h: int, end_h: int) -> dict:
    """
    Build a UTC session box from 1H candles.

    The box uses candles whose UTC hour is in [start_h, end_h). The returned
    dict includes range size, ATR(14), candle count, and a basic quality ratio.
    """
    records = _as_records(df_1h)
    session_rows = [row for row in records if start_h <= _hour_of(row) < end_h]
    if len(session_rows) < 3:
        raise ValueError("session not yet complete")

    box_high = max(float(row["high"]) for row in session_rows)
    box_low = min(float(row["low"]) for row in session_rows)
    box_range = box_high - box_low
    atr = _atr(records, period=14)
    ratio = round(box_range / atr, 4) if atr else None

    name = next(
        (
            n
            for n, cfg in SESSION_WINDOWS_V2.items()
            if cfg["start_h"] == start_h and cfg["end_h"] == end_h
        ),
        "custom",
    )
    return {
        "session_name": name,
        "start_h": start_h,
        "end_h": end_h,
        "box_high": round(box_high, 6),
        "box_low": round(box_low, 6),
        "box_mid": round((box_high + box_low) / 2, 6),
        "box_range": round(box_range, 6),
        "atr": round(atr, 6),
        "range_to_atr": ratio,
        "candle_count": len(session_rows),
    }


def build_asian_range(candles_m15: list[dict], trade_date: date) -> "AsianRange | None":
    """
    Legacy compatibility helper for the old EST-based Asian range.

    Asian session: 18:00 EST on (trade_date - 1) through 01:45 EST on trade_date.
    """
    prev_day = trade_date - timedelta(days=1)
    highs: list[float] = []
    lows: list[float] = []

    for c in candles_m15:
        t_est = _to_est(_parse_utc(c["time"]))
        c_date = t_est.date()
        c_hour = t_est.hour
        in_prev = c_date == prev_day and c_hour >= 18
        in_curr = c_date == trade_date and c_hour < 2
        if in_prev or in_curr:
            highs.append(float(c["high"]))
            lows.append(float(c["low"]))

    if len(highs) < 4:
        return None

    return AsianRange(trade_date=trade_date, high=max(highs), low=min(lows))
