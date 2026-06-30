"""
SA-01 — Asian Session Builder + Killzone Classifier.

Legacy ST-A2 behavior remains the default for compatibility, but the module now
also exposes V2-style session helpers for overlapping session windows.

Provides:
  AsianRange         dataclass for daily high/low of Asian session
  build_asian_range  build Asian range from M15 candles (no lookahead)
  classify_session   legacy UTC datetime classifier → 'london' | 'new_york' | None
  active_sessions    V2 UTC session windows → list[str]
  classify_session_v2 V2 priority classifier for overlapping windows
  build_session_box  V2 UTC session box helper
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
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
    def range_pips(self) -> float:
        """Range in pips (5-decimal pair: 1 pip = 0.0001)."""
        return round((self.high - self.low) / 0.0001, 1)


# ── Internal helpers ──────────────────────────────────────────────────────────


def _parse_utc(t) -> datetime:
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


def _atr(records: list[dict], period: int = 14) -> float:
    """Small ATR helper for V2 session-box gating."""
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
    atr = sum(trs[:period]) / period
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
        if int(cfg["start_h"]) <= hour < int(cfg["end_h"]):
            active.append(name)
    return active


def classify_session_v2(
    dt_utc: datetime, session_windows: dict[str, dict] | None = None
) -> str | None:
    """
    V2 priority classifier for overlapping windows.

    Returns the highest-priority active session.
    """
    windows = session_windows or SESSION_WINDOWS_V2
    active = set(active_sessions(dt_utc, windows))
    for name in _SESSION_PRIORITY:
        if name in active and name in windows:
            return name
    return None


# ── Public API ────────────────────────────────────────────────────────────────


def build_asian_range(candles_m15: list[dict], trade_date: date) -> "AsianRange | None":
    """
    Build the Asian session range for trade_date (an EST calendar date).

    Asian session: 18:00 EST on (trade_date - 1) through 01:45 EST on trade_date.
    The 02:00 EST bar is the London open — it is excluded here.

    Uses completed candles only. The candle 'time' field is the bar's open time;
    a bar is closed when the next bar opens, so all bars in the input list are treated
    as completed (callers must not pass the currently-forming bar).

    Returns None if fewer than 4 Asian bars are found (holiday, data gap, or
    insufficient history at the start of the dataset).

    Lookahead: safe to call with candles_m15[:i] — no future data accessed.
    """
    prev_day = trade_date - timedelta(days=1)
    highs: list[float] = []
    lows: list[float] = []

    for c in candles_m15:
        t_est = _to_est(_parse_utc(c["time"]))
        c_date = t_est.date()
        c_hour = t_est.hour

        # Asian window:
        #   prev_day  18:00–23:59 EST  (hour >= 18)
        #   trade_date 00:00–01:59 EST  (hour < 2)
        in_prev = c_date == prev_day and c_hour >= 18
        in_curr = c_date == trade_date and c_hour < 2
        if in_prev or in_curr:
            highs.append(c["high"])
            lows.append(c["low"])

    if len(highs) < 4:
        return None

    return AsianRange(trade_date=trade_date, high=max(highs), low=min(lows))


def classify_session(dt_utc: datetime) -> "str | None":
    """
    Classify a UTC datetime into a trading killzone by EST/EDT hour.

    London:   02:00–04:59 EST/EDT  → 'london'
    New York: 07:00–09:59 EST/EDT  → 'new_york'
    Other:    None

    DST transitions are handled automatically via zoneinfo.
    In summer (EDT = UTC-4), London starts at 06:00 UTC instead of 07:00 UTC.
    """
    h = _to_est(_parse_utc(dt_utc)).hour
    if 2 <= h < 5:
        return "london"
    if 7 <= h < 10:
        return "new_york"
    return None


def build_session_box(df_1h: Any, start_h: int, end_h: int) -> dict:
    """
    Build a UTC session box from 1H candles.

    Returns box_high, box_low, box_range, ATR(14), and the candle count.
    """
    records = _as_records(df_1h)
    session_rows = [
        row for row in records if start_h <= _parse_utc(row["time"]).hour < end_h
    ]
    if len(session_rows) < 3:
        raise ValueError("session not yet complete")

    box_high = max(float(row["high"]) for row in session_rows)
    box_low = min(float(row["low"]) for row in session_rows)
    box_range = box_high - box_low
    atr = _atr(records, period=14)
    ratio = round(box_range / atr, 4) if atr else None

    session_name = next(
        (
            name
            for name, cfg in SESSION_WINDOWS_V2.items()
            if cfg["start_h"] == start_h and cfg["end_h"] == end_h
        ),
        "custom",
    )
    return {
        "session_name": session_name,
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
