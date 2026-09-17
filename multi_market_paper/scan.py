"""Public-data scan: tickers, spreads, session state, xStocks catalog (no orders)."""

from __future__ import annotations

from datetime import datetime, timezone

from multi_market_paper.instruments import (
    FX_UNIVERSE,
    PAXGUSD,
    XSTOCK_RESEARCH,
    XSTOCKS_GEO_NOTES,
    XSTOCKS_PUBLIC_ENDPOINT,
    XSTOCKS_SUPPORT,
    Instrument,
)
from multi_market_paper.macro_calendar import events_covering, next_event
from multi_market_paper.public_client import PublicAPIError, PublicClient
from multi_market_paper.sessions import (
    in_fx_entry_window,
    in_london,
    in_new_york,
    in_overlap,
    next_fx_session_open,
)

UTC = timezone.utc


def _snapshot(client: PublicClient, inst: Instrument) -> dict:
    ticker = client.ticker(inst.pair, inst.asset_class)
    row = {
        "symbol": inst.symbol,
        "display": inst.display,
        "kind": inst.kind,
        "tradable_in_this_lane": inst.tradable_in_this_lane,
        "bid": ticker.bid,
        "ask": ticker.ask,
        "last": ticker.last,
        "spread_pct": ticker.spread_pct,
        "volume": ticker.volume,
        "fee_taker": inst.schedule.taker_rate,
        "round_trip": inst.schedule.round_trip_rate,
        "notes": inst.notes,
    }
    return row


def scan_market(client: PublicClient, as_of: datetime | None = None) -> dict:
    as_of = as_of or datetime.now(tz=UTC)
    fx_rows = [_snapshot(client, inst) for inst in FX_UNIVERSE]
    gold = _snapshot(client, PAXGUSD)
    xstocks = []
    xstock_error = None
    for inst in XSTOCK_RESEARCH:
        try:
            xstocks.append(_snapshot(client, inst))
        except PublicAPIError as exc:
            xstock_error = str(exc)
            xstocks.append(
                {
                    "symbol": inst.symbol,
                    "display": inst.display,
                    "kind": inst.kind,
                    "tradable_in_this_lane": False,
                    "error": str(exc),
                    "notes": inst.notes,
                }
            )
    covering = events_covering(as_of)
    nxt = next_event(as_of)
    return {
        "lane": "multi_market_paper",
        "mode": "scan",
        "live_orders": False,
        "as_of": as_of.isoformat(),
        "sessions": {
            "london": in_london(as_of),
            "new_york": in_new_york(as_of),
            "overlap": in_overlap(as_of),
            "fx_entry_window": in_fx_entry_window(as_of),
            "next_london_open_utc": next_fx_session_open(as_of).isoformat(),
        },
        "fx": fx_rows,
        "gold": gold,
        "xstocks_research": xstocks,
        "xstocks_meta": {
            "tradable_in_this_lane": False,
            "geo": XSTOCKS_GEO_NOTES,
            "pairs_endpoint": XSTOCKS_PUBLIC_ENDPOINT,
            "support": XSTOCKS_SUPPORT,
            "error": xstock_error,
        },
        "active_macro_events": [
            {"name": e.name, "day": e.day.isoformat(), "kind": e.kind} for e in covering
        ],
        "next_macro_event": (
            {"name": nxt.name, "day": nxt.day.isoformat(), "kind": nxt.kind} if nxt else None
        ),
    }
