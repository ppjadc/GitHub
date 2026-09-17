"""PAXG swing/breakout around macro events — cash long only, not a scalp.

Setup
-----
1. Only consider bars that fall inside a documented FOMC / CPI / NFP window.
2. Measure the prior 10 *committed* 4h bars' high/low (about a week of gold).
3. Skip if that range cannot cover round-trip *spot crypto* fees (PAXG is not FX).
4. Buy a close through the lookback high. Stop: lookback low. Target: 1R.
5. Time stop: end of the event window (typically ~1–2 sessions).

This is intentionally selective. Starter-tier PAXG round-trip is 1.60%, so most
quiet days are fee-skipped — which is the point of a $1k–$5k book.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from multi_market_paper.fees import DEFAULT_PAXG_EDGE_MULTIPLE, should_skip_for_fees
from multi_market_paper.instruments import Instrument
from multi_market_paper.macro_calendar import (
    MacroEvent,
    default_events,
    events_covering,
    next_event,
)
from multi_market_paper.public_client import Candle
from multi_market_paper.sizing import SizeRequest, SizeResult, size_cash_long

LOOKBACK_BARS = 10
BREAK_BUFFER_FRAC = 0.05
UTC = timezone.utc


@dataclass(frozen=True)
class PaxgSignal:
    instrument: str
    ts: datetime
    action: str
    side: str
    reason: str
    event_name: str
    lookback_high: float
    lookback_low: float
    range_pct: float
    entry: float
    stop: float
    target: float
    size: SizeResult | None


def evaluate_paxg_swing(
    instrument: Instrument,
    candles: list[Candle],
    as_of: datetime,
    cash_usd: float,
    risk_pct: float,
    max_notional_pct: float,
    edge_multiple: float = DEFAULT_PAXG_EDGE_MULTIPLE,
    events: tuple[MacroEvent, ...] | None = None,
) -> PaxgSignal:
    as_of = as_of if as_of.tzinfo else as_of.replace(tzinfo=UTC)
    as_of = as_of.astimezone(UTC)
    cal = events or default_events()
    base = dict(
        instrument=instrument.symbol,
        ts=as_of,
        side="long",
        event_name="",
        lookback_high=0.0,
        lookback_low=0.0,
        range_pct=0.0,
        entry=0.0,
        stop=0.0,
        target=0.0,
        size=None,
    )
    covering = events_covering(as_of, cal)
    if not covering:
        nxt = next_event(as_of, cal)
        extra = f" next={nxt.name} {nxt.day.isoformat()}" if nxt else " next=none"
        return PaxgSignal(action="SKIP", reason="not_in_macro_window" + extra, **base)

    event = covering[0]
    base["event_name"] = f"{event.name} {event.day.isoformat()}"

    committed = [c for c in candles if c.committed and c.time <= as_of]
    if len(committed) < LOOKBACK_BARS + 1:
        return PaxgSignal(action="SKIP", reason="not_enough_history", **base)

    prior = committed[-(LOOKBACK_BARS + 1) : -1]
    last = committed[-1]
    high = max(c.high for c in prior)
    low = min(c.low for c in prior)
    mid = (high + low) / 2.0
    width = high - low
    if mid <= 0 or width <= 0:
        return PaxgSignal(action="SKIP", reason="zero_lookback_range", **base)
    range_pct = width / mid
    base.update(lookback_high=high, lookback_low=low, range_pct=range_pct)

    skip, fee_reason = should_skip_for_fees(range_pct, instrument.schedule, edge_multiple)
    if skip:
        return PaxgSignal(action="SKIP", reason=fee_reason, **base)

    buffer = width * BREAK_BUFFER_FRAC
    if last.close <= high + buffer:
        if last.close < low - buffer:
            return PaxgSignal(action="SKIP", reason="cash_only_no_short", **base)
        return PaxgSignal(action="SKIP", reason="no_range_breakout_yet", **base)

    entry = last.close
    stop = low
    target = entry + width
    size = size_cash_long(
        SizeRequest(
            cash_usd=cash_usd,
            price=entry,
            stop_distance=max(entry - stop, entry * 0.005),
            risk_pct=risk_pct,
            max_notional_pct=max_notional_pct,
            schedule=instrument.schedule,
            limits=instrument.limits,
        )
    )
    if size.skipped:
        return PaxgSignal(
            action="SKIP",
            reason=f"size_skip {size.reason}",
            entry=entry,
            stop=stop,
            target=target,
            size=size,
            **{k: v for k, v in base.items() if k not in {"entry", "stop", "target", "size"}},
        )
    return PaxgSignal(
        action="PLAN",
        reason="macro_high_break",
        instrument=instrument.symbol,
        ts=last.time,
        side="long",
        event_name=base["event_name"],
        lookback_high=high,
        lookback_low=low,
        range_pct=range_pct,
        entry=entry,
        stop=stop,
        target=target,
        size=size,
    )


def simulate_paxg_path(
    instrument: Instrument,
    candles: list[Candle],
    signal: PaxgSignal,
    hold_bars: int = 12,
) -> dict:
    if signal.action != "PLAN" or signal.size is None:
        return {"pnl_usd": 0.0, "exit": "none", "exit_price": 0.0}
    qty = signal.size.qty
    fee_in = signal.size.fee_usd
    path = [c for c in candles if c.time > signal.ts][:hold_bars]
    exit_price = signal.entry
    exit_why = "time_stop"
    for bar in path:
        if bar.low <= signal.stop:
            exit_price = signal.stop
            exit_why = "stop"
            break
        if bar.high >= signal.target:
            exit_price = signal.target
            exit_why = "target"
            break
        exit_price = bar.close
    notional_out = qty * exit_price
    fee_out = notional_out * instrument.schedule.fill_rate
    pnl = (exit_price - signal.entry) * qty - fee_in - fee_out
    return {"pnl_usd": pnl, "exit": exit_why, "exit_price": exit_price, "fee_out": fee_out}
