"""FX London/NY session breakout — cash long only, not a scalp.

Setup
-----
1. Measure the Asian range (00:00–07:00 UTC) on 60-minute candles.
2. Skip weekends, skip if the range is too small to cover round-trip FX fees.
3. Between London open and London close (07:00–16:00 UTC), buy if a *committed*
   candle closes above the Asian high by a small buffer.
4. Stop: Asian low. Target: entry + 1.0 × Asian range. Time stop: 16:00 UTC.

A USD cash book cannot short EUR/GBP without already holding the base, so
downside breaks are recorded as `cash_only_no_short` and skipped.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from multi_market_paper.fees import DEFAULT_FX_EDGE_MULTIPLE, should_skip_for_fees
from multi_market_paper.instruments import Instrument
from multi_market_paper.public_client import Candle
from multi_market_paper.sessions import (
    UTC,
    asian_range_bounds,
    fx_entry_bounds,
    in_fx_entry_window,
    is_fx_weekday,
)
from multi_market_paper.sizing import SizeRequest, SizeResult, size_cash_long

BREAK_BUFFER_FRAC = 0.10  # require 10% of range beyond the high
TARGET_R = 1.0


@dataclass(frozen=True)
class FxSignal:
    instrument: str
    ts: datetime
    action: str  # PLAN | SKIP
    side: str
    reason: str
    asian_high: float
    asian_low: float
    range_pct: float
    entry: float
    stop: float
    target: float
    size: SizeResult | None


def _candles_in(candles: list[Candle], start: datetime, end: datetime) -> list[Candle]:
    return [c for c in candles if start <= c.time < end]


def asian_range(candles: list[Candle], day_ts: datetime) -> tuple[float, float] | None:
    start, end = asian_range_bounds(day_ts)
    window = _candles_in(candles, start, end)
    if len(window) < 3:
        return None
    return max(c.high for c in window), min(c.low for c in window)


def evaluate_fx_breakout(
    instrument: Instrument,
    candles: list[Candle],
    as_of: datetime,
    cash_usd: float,
    risk_pct: float,
    max_notional_pct: float,
    edge_multiple: float = DEFAULT_FX_EDGE_MULTIPLE,
) -> FxSignal:
    as_of = as_of if as_of.tzinfo else as_of.replace(tzinfo=UTC)
    as_of = as_of.astimezone(UTC)
    empty_size = None
    base = dict(
        instrument=instrument.symbol,
        ts=as_of,
        side="long",
        asian_high=0.0,
        asian_low=0.0,
        range_pct=0.0,
        entry=0.0,
        stop=0.0,
        target=0.0,
        size=empty_size,
    )
    if not is_fx_weekday(as_of):
        return FxSignal(action="SKIP", reason="weekend_fx_closed", **base)

    rng = asian_range(candles, as_of)
    if rng is None:
        return FxSignal(action="SKIP", reason="incomplete_asian_range", **base)
    high, low = rng
    mid = (high + low) / 2.0
    width = high - low
    if mid <= 0 or width <= 0:
        return FxSignal(action="SKIP", reason="zero_asian_range", **base)
    range_pct = width / mid
    base.update(asian_high=high, asian_low=low, range_pct=range_pct)

    skip, fee_reason = should_skip_for_fees(range_pct, instrument.schedule, edge_multiple)
    if skip:
        return FxSignal(action="SKIP", reason=fee_reason, **base)

    if not in_fx_entry_window(as_of):
        start, end = fx_entry_bounds(as_of)
        if as_of < start:
            return FxSignal(action="SKIP", reason="before_london_open", **base)
        return FxSignal(action="SKIP", reason="after_london_close", **base)

    entry_start, entry_end = fx_entry_bounds(as_of)
    entry_bars = [c for c in _candles_in(candles, entry_start, min(as_of, entry_end)) if c.committed]
    if not entry_bars:
        return FxSignal(action="SKIP", reason="waiting_for_london_close_bar", **base)

    buffer = width * BREAK_BUFFER_FRAC
    break_level = high + buffer
    trigger = next((c for c in entry_bars if c.close > break_level), None)
    if trigger is None:
        # Record a cash-only note if price instead broke down.
        down = next((c for c in entry_bars if c.close < low - buffer), None)
        if down is not None:
            return FxSignal(action="SKIP", reason="cash_only_no_short", **base)
        return FxSignal(action="SKIP", reason="no_london_breakout_yet", **base)

    entry = trigger.close
    stop = low
    target = entry + TARGET_R * width
    size = size_cash_long(
        SizeRequest(
            cash_usd=cash_usd,
            price=entry,
            stop_distance=entry - stop,
            risk_pct=risk_pct,
            max_notional_pct=max_notional_pct,
            schedule=instrument.schedule,
            limits=instrument.limits,
        )
    )
    if size.skipped:
        return FxSignal(action="SKIP", reason=f"size_skip {size.reason}", entry=entry, stop=stop, target=target, size=size, **{k: v for k, v in base.items() if k not in {"entry", "stop", "target", "size"}})
    return FxSignal(
        action="PLAN",
        reason="london_high_break",
        instrument=instrument.symbol,
        ts=trigger.time,
        side="long",
        asian_high=high,
        asian_low=low,
        range_pct=range_pct,
        entry=entry,
        stop=stop,
        target=target,
        size=size,
    )


def simulate_fx_path(
    instrument: Instrument,
    candles: list[Candle],
    signal: FxSignal,
) -> dict:
    """Walk forward from entry to London close for paper P&L (fees in, no slippage)."""
    if signal.action != "PLAN" or signal.size is None:
        return {"pnl_usd": 0.0, "exit": "none", "exit_price": 0.0}
    qty = signal.size.qty
    fee_in = signal.size.fee_usd
    entry_end = fx_entry_bounds(signal.ts)[1]
    path = [c for c in candles if c.time > signal.ts and c.time < entry_end + timedelta(hours=1)]
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
