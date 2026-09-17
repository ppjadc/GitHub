"""UTC session clocks for FX. Times are exchange-agnostic civil hours in UTC.

London cash FX: 07:00–16:00 UTC
New York cash FX: 12:00–21:00 UTC
London/NY overlap: 12:00–16:00 UTC
Asian range used as the breakout base: 00:00–07:00 UTC

This is a session/swing filter, not a scalp clock. Weekend FX is closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc

LONDON_OPEN = time(7, 0)
LONDON_CLOSE = time(16, 0)
NY_OPEN = time(12, 0)
NY_CLOSE = time(21, 0)
ASIAN_OPEN = time(0, 0)
ASIAN_CLOSE = time(7, 0)


@dataclass(frozen=True)
class SessionWindow:
    name: str
    start: time
    end: time


LONDON = SessionWindow("london", LONDON_OPEN, LONDON_CLOSE)
NEW_YORK = SessionWindow("new_york", NY_OPEN, NY_CLOSE)
OVERLAP = SessionWindow("london_ny_overlap", NY_OPEN, LONDON_CLOSE)
ASIAN_RANGE = SessionWindow("asian_range", ASIAN_OPEN, ASIAN_CLOSE)
# Trade the London break into the overlap; flatten before NY afternoon.
FX_ENTRY = SessionWindow("fx_entry", LONDON_OPEN, LONDON_CLOSE)


def ensure_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC)


def is_fx_weekday(ts: datetime) -> bool:
    """FX trades Sunday 21:00 UTC through Friday 21:00 UTC.

    For this research lane we only take weekday London sessions (Mon–Fri UTC).
    """
    day = ensure_utc(ts).weekday()  # Mon=0
    return day <= 4


def _on_clock(ts: datetime, window: SessionWindow) -> bool:
    clock = ensure_utc(ts).timetz().replace(tzinfo=None)
    return window.start <= clock < window.end


def in_session(ts: datetime, window: SessionWindow) -> bool:
    ts = ensure_utc(ts)
    if window.name.startswith("fx") or window in {LONDON, NEW_YORK, OVERLAP, ASIAN_RANGE, FX_ENTRY}:
        if not is_fx_weekday(ts):
            return False
    return _on_clock(ts, window)


def in_london(ts: datetime) -> bool:
    return in_session(ts, LONDON)


def in_new_york(ts: datetime) -> bool:
    return in_session(ts, NEW_YORK)


def in_overlap(ts: datetime) -> bool:
    return in_session(ts, OVERLAP)


def in_fx_entry_window(ts: datetime) -> bool:
    return in_session(ts, FX_ENTRY)


def in_asian_range(ts: datetime) -> bool:
    return in_session(ts, ASIAN_RANGE)


def session_date_utc(ts: datetime):
    return ensure_utc(ts).date()


def asian_range_bounds(ts: datetime) -> tuple[datetime, datetime]:
    """Return [start, end) of the Asian range for the London session of `ts`."""
    ts = ensure_utc(ts)
    start = datetime.combine(ts.date(), ASIAN_OPEN, tzinfo=UTC)
    end = datetime.combine(ts.date(), ASIAN_CLOSE, tzinfo=UTC)
    return start, end


def fx_entry_bounds(ts: datetime) -> tuple[datetime, datetime]:
    ts = ensure_utc(ts)
    start = datetime.combine(ts.date(), LONDON_OPEN, tzinfo=UTC)
    end = datetime.combine(ts.date(), LONDON_CLOSE, tzinfo=UTC)
    return start, end


def next_fx_session_open(ts: datetime) -> datetime:
    """Next Monday–Friday 07:00 UTC (today if still before London open)."""
    ts = ensure_utc(ts)
    candidate = datetime.combine(ts.date(), LONDON_OPEN, tzinfo=UTC)
    if ts < candidate and is_fx_weekday(candidate):
        return candidate
    day = ts.date() + timedelta(days=1)
    while True:
        candidate = datetime.combine(day, LONDON_OPEN, tzinfo=UTC)
        if is_fx_weekday(candidate):
            return candidate
        day += timedelta(days=1)


def ny_wall_clock(ts: datetime) -> datetime:
    """Helper for documenting US macro prints (ET)."""
    return ensure_utc(ts).astimezone(ZoneInfo("America/New_York"))
