"""
SA-01 — Asian Session Builder + Killzone Classifier.

Provides:
  AsianRange        dataclass for daily high/low of Asian session
  build_asian_range build Asian range from M15 candles (no lookahead)
  classify_session  classify UTC datetime into 'london' | 'new_york' | None
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

_EST = ZoneInfo("America/New_York")
_UTC = timezone.utc


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
