"""
Session filter — determines if the current UTC time falls within an active
trading session (London or New York).

All times are UTC. Weekends are always blocked.
"""

from datetime import datetime, time, timezone
from typing import Optional

SESSIONS = {
    "london": (time(7, 0), time(10, 0)),
    "newyork": (time(13, 0), time(16, 0)),
}


def get_active_session(dt: Optional[datetime] = None) -> Optional[str]:
    """
    Return 'london', 'newyork', or None.

    Weekdays only (Mon=0 … Fri=4). Saturday/Sunday always return None.
    """
    dt = dt or datetime.now(timezone.utc)
    if dt.weekday() >= 5:
        return None

    t = dt.time().replace(tzinfo=None)
    for session_name, (start, end) in SESSIONS.items():
        if start <= t < end:
            return session_name
    return None


def is_trading_allowed(dt: Optional[datetime] = None) -> bool:
    """True if inside an active session window."""
    return get_active_session(dt) is not None


def seconds_to_next_session(dt: Optional[datetime] = None) -> int:
    """Return seconds until the next session opens. 0 if currently in session."""
    dt = dt or datetime.now(timezone.utc)
    if is_trading_allowed(dt):
        return 0

    # Collect all session open times (today + tomorrow) and find the nearest future one
    from datetime import timedelta

    upcoming = []
    for day_offset in range(7):
        candidate_day = dt + timedelta(days=day_offset)
        if candidate_day.weekday() >= 5:
            continue
        for session_name, (start, _end) in SESSIONS.items():
            session_open = candidate_day.replace(
                hour=start.hour,
                minute=start.minute,
                second=0,
                microsecond=0,
                tzinfo=timezone.utc,
            )
            if session_open > dt:
                upcoming.append(session_open)

    if not upcoming:
        return 24 * 3600
    nearest = min(upcoming)
    return int((nearest - dt).total_seconds())


def session_label(dt: Optional[datetime] = None) -> str:
    """Human-readable label for the current time slot."""
    session = get_active_session(dt)
    return session.upper() if session else "OFF_HOURS"
