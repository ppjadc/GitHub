"""Static macro calendar used by the PAXG swing/breakout research strategy.

This is not a live news feed. Dates are official Fed/BLS 2026 remaining prints
plus a first-Friday NFP helper for tests. Widen the event *day* (not the
minute of the print) so the strategy stays a swing, not a scalp.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

UTC = timezone.utc


@dataclass(frozen=True)
class MacroEvent:
    name: str
    day: date
    kind: str  # fomc | cpi | nfp
    notes: str = ""


# Remaining 2026 FOMC *decision* days (2:00 p.m. ET = 18:00 UTC / 19:00 UTC DST).
FOMC_DECISION_DAYS_2026 = (
    date(2026, 9, 16),
    date(2026, 10, 28),
    date(2026, 12, 9),
)

# Remaining 2026 CPI release dates (8:30 a.m. ET).
CPI_DAYS_2026 = (
    date(2026, 10, 14),
    date(2026, 11, 10),
    date(2026, 12, 10),
)

# Remaining 2026 Employment Situation (NFP) dates from BLS.
NFP_DAYS_2026 = (
    date(2026, 10, 2),
    date(2026, 11, 6),
    date(2026, 12, 4),
)


def default_events() -> tuple[MacroEvent, ...]:
    events = []
    for d in FOMC_DECISION_DAYS_2026:
        events.append(MacroEvent("FOMC", d, "fomc", "decision + press conference"))
    for d in CPI_DAYS_2026:
        events.append(MacroEvent("CPI", d, "cpi", "08:30 ET print"))
    for d in NFP_DAYS_2026:
        events.append(MacroEvent("NFP", d, "nfp", "Employment Situation 08:30 ET"))
    return tuple(sorted(events, key=lambda e: e.day))


def event_window(event: MacroEvent) -> tuple[datetime, datetime]:
    """Inclusive swing window: session before print through next weekday close.

    Gold often trends for 1–2 sessions around a print. We do not enter in the
    minute of the release; we allow a breakout anytime inside this window.
    """
    start = datetime(event.day.year, event.day.month, event.day.day, tzinfo=UTC) - timedelta(hours=12)
    end = datetime(event.day.year, event.day.month, event.day.day, 21, 0, tzinfo=UTC) + timedelta(days=1)
    return start, end


def events_covering(ts: datetime, events: tuple[MacroEvent, ...] | None = None) -> list[MacroEvent]:
    ts = ts if ts.tzinfo else ts.replace(tzinfo=UTC)
    ts = ts.astimezone(UTC)
    hits = []
    for event in events or default_events():
        start, end = event_window(event)
        if start <= ts < end:
            hits.append(event)
    return hits


def in_macro_window(ts: datetime, events: tuple[MacroEvent, ...] | None = None) -> bool:
    return bool(events_covering(ts, events))


def next_event(ts: datetime, events: tuple[MacroEvent, ...] | None = None) -> MacroEvent | None:
    """First event whose swing window has not started yet (strictly upcoming)."""
    ts = ts if ts.tzinfo else ts.replace(tzinfo=UTC)
    ts = ts.astimezone(UTC)
    upcoming = [e for e in (events or default_events()) if event_window(e)[0] > ts]
    if not upcoming:
        return None
    return min(upcoming, key=lambda e: e.day)
