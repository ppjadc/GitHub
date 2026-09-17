"""Historical walk-forward of locked A+ rules on public 15m OHLC. No live orders."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from kraken_paper.breakout import evaluate_breakout
from kraken_paper.constants import (
    CHASE_MAX_PCT,
    FEE_RT,
    LIVE_DAILY_LOSS_STOP,
    MAX_CLIPS_PER_DAY,
    PAPER_DAILY_LOSS_STOP,
    SCRATCH_BARS,
    SESSION_TZ,
    T1_SCALE_FRAC,
    TIME_STOP_BARS,
    UNIVERSE,
)
from kraken_paper.fees import one_way_fee
from kraken_paper.models import Candle, Fill, Setup, Trade
from kraken_paper.sizing import book_defaults, size_long

ET = ZoneInfo(SESSION_TZ)


def et_date_str(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=ET).strftime("%Y-%m-%d")


def _fill(time: int, price: float, qty: float, side: str, reason: str, fee_rt: float) -> Fill:
    notional = abs(qty) * price
    return Fill(time=time, price=price, qty=qty, side=side, reason=reason, fee=one_way_fee(notional, fee_rt))


@dataclass
class OpenPos:
    pair: str
    setup: Setup
    qty: float
    remaining: float
    notional: float
    entry: float
    stop: float
    orig_stop: float
    t1: float
    t2: float
    trigger: float
    entry_time: int
    entry_index: int
    bars_held: int = 0
    t1_done: bool = False
    fills: list[Fill] = field(default_factory=list)
    realized_gross: float = 0.0
    realized_fees: float = 0.0
    entry_date: str = ""


@dataclass
class BacktestResult:
    book: str
    days: int
    fee_rt: float
    trades: list[Trade]
    skipped_signals: int
    daily_stop_hits: int
    clips_capped: int
    notes: list[str]

    def summary(self) -> dict[str, Any]:
        nets = [t.net_pnl for t in self.trades]
        wins = [t for t in self.trades if t.net_pnl > 0]
        losses = [t for t in self.trades if t.net_pnl < 0]
        scratches = [t for t in self.trades if t.exit_reason.startswith("scratch")]
        return {
            "book": self.book,
            "days": self.days,
            "trades": len(self.trades),
            "wins": len(wins),
            "losses": len(losses),
            "scratches": len(scratches),
            "gross_pnl": round(sum(t.gross_pnl for t in self.trades), 4),
            "fees": round(sum(t.fees for t in self.trades), 4),
            "net_pnl": round(sum(nets), 4),
            "avg_net": round(sum(nets) / len(nets), 4) if nets else 0.0,
            "skipped_signals": self.skipped_signals,
            "daily_stop_hits": self.daily_stop_hits,
            "clips_capped": self.clips_capped,
            "exit_reasons": _count([t.exit_reason for t in self.trades]),
        }


def _count(items: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for x in items:
        out[x] = out.get(x, 0) + 1
    return out


def _close_pos(pos: OpenPos, time: int, price: float, reason: str, fee_rt: float) -> Trade:
    qty = pos.remaining
    fill = _fill(time, price, -qty, "sell", reason, fee_rt)
    pos.fills.append(fill)
    gross = qty * (price - pos.entry)
    pos.realized_gross += gross
    pos.realized_fees += fill.fee
    pos.remaining = 0.0
    total_risk_px = (pos.entry - pos.orig_stop) * pos.qty
    r_mult = pos.realized_gross / total_risk_px if total_risk_px else 0.0
    return Trade(
        pair=pos.pair,
        entry_time=pos.entry_time,
        exit_time=time,
        entry=pos.entry,
        stop=pos.stop,
        t1=pos.t1,
        t2=pos.t2,
        trigger=pos.trigger,
        qty=pos.qty,
        notional=pos.notional,
        exit_reason=reason,
        gross_pnl=pos.realized_gross,
        fees=pos.realized_fees,
        net_pnl=pos.realized_gross - pos.realized_fees,
        r_multiple=r_mult,
        clips_date=pos.entry_date,
        fills=list(pos.fills),
    )


def _scale_t1(pos: OpenPos, time: int, fee_rt: float) -> None:
    qty = pos.remaining * T1_SCALE_FRAC
    if qty <= 0:
        return
    fill = _fill(time, pos.t1, -qty, "sell", "t1", fee_rt)
    pos.fills.append(fill)
    pos.realized_gross += qty * (pos.t1 - pos.entry)
    pos.realized_fees += fill.fee
    pos.remaining -= qty
    pos.t1_done = True
    pos.stop = pos.entry  # remainder: stop to breakeven (does not widen risk)


def run_backtest(
    candles_by_pair: dict[str, list[Candle]],
    *,
    book: str = "live",
    days: int = 7,
    fee_rt: float = FEE_RT,
    pair_meta: dict[str, Any] | None = None,
    max_clips: int = MAX_CLIPS_PER_DAY,
) -> BacktestResult:
    defaults = book_defaults(book)
    daily_loss_stop = LIVE_DAILY_LOSS_STOP if book == "live" else PAPER_DAILY_LOSS_STOP
    notes = [
        f"{book} book ${defaults['equity']:.0f}; risk ${defaults['risk_min']:.0f}–${defaults['risk_max']:.0f} "
        f"incl. {fee_rt:.2%} RT fees; cash only; A+ only; max {max_clips} clips/day ET; "
        f"daily loss stop −${daily_loss_stop:.0f}.",
        "Fills at stop/target prices (no slippage). Same-day flatten = last 15m bar of the ET date.",
    ]

    # Align by timestamp. Each pair may start at a slightly different first bar.
    times: dict[int, dict[str, Candle]] = defaultdict(dict)
    for pair, candles in candles_by_pair.items():
        for c in candles:
            times[c.time][pair] = c
    timeline = sorted(times)
    history: dict[str, list[Candle]] = {p: [] for p in candles_by_pair}

    open_pos: OpenPos | None = None
    trades: list[Trade] = []
    clips_today: dict[str, int] = defaultdict(int)
    pnl_today: dict[str, float] = defaultdict(float)
    halted: set[str] = set()
    skipped_signals = 0
    daily_stop_hits = 0
    clips_capped = 0

    def flatten(reason: str, ts: int, price: float) -> None:
        nonlocal open_pos
        if open_pos is None or open_pos.remaining <= 0:
            open_pos = None
            return
        trade = _close_pos(open_pos, ts, price, reason, fee_rt)
        trades.append(trade)
        pnl_today[trade.clips_date] += trade.net_pnl
        open_pos = None

    for ts in timeline:
        bar_map = times[ts]
        # 1) manage open trade on its pair's new bar
        if open_pos is not None and open_pos.pair in bar_map:
            bar = bar_map[open_pos.pair]
            open_pos.bars_held += 1
            day = et_date_str(bar.time)
            # Same-day flatten: new ET date → close at this open (overnight gap)
            if day != open_pos.entry_date:
                flatten("session_flatten", bar.time, bar.open)
            else:
                # Intrabar: original stop vs targets. If structural stop and a
                # target print in the same bar, assume stop first (do not loosen).
                hit_stop = bar.low <= open_pos.stop
                hit_t1 = (not open_pos.t1_done) and bar.high >= open_pos.t1
                hit_t2 = bar.high >= open_pos.t2
                if hit_stop:
                    flatten("stop", bar.time, open_pos.stop)
                else:
                    if hit_t1:
                        _scale_t1(open_pos, bar.time, fee_rt)
                    if open_pos is not None and hit_t2:
                        flatten("t2", bar.time, open_pos.t2)
                    elif open_pos is not None and open_pos.t1_done and bar.low <= open_pos.stop:
                        flatten("be_stop", bar.time, open_pos.stop)
                    elif open_pos is not None:
                        # scratch: close back below trigger within 2 bars
                        if open_pos.bars_held <= SCRATCH_BARS and bar.close < open_pos.trigger:
                            flatten("scratch_below_trigger", bar.time, bar.close)
                        elif open_pos.bars_held >= TIME_STOP_BARS and not open_pos.t1_done:
                            flatten("time_stop", bar.time, bar.close)

        # 2) append history then look for a new A+ (one risk unit)
        setups: list[Setup] = []
        for pair, bar in bar_map.items():
            history[pair].append(bar)
            if open_pos is not None:
                continue
            if len(history[pair]) < 100:
                continue
            st = evaluate_breakout(history[pair], len(history[pair]) - 1, pair=pair)
            if st.tradable:
                setups.append(st)
            elif st.grade in {"A", "B"}:
                skipped_signals += 1

        if open_pos is not None or not setups:
            continue

        day = et_date_str(ts)
        if day in halted:
            skipped_signals += len(setups)
            continue
        if pnl_today[day] <= -daily_loss_stop:
            halted.add(day)
            daily_stop_hits += 1
            skipped_signals += len(setups)
            continue
        if clips_today[day] >= max_clips:
            clips_capped += 1
            skipped_signals += len(setups)
            continue

        setups.sort(key=lambda s: (s.net_rr or 0, s.atr_pct or 0), reverse=True)
        chosen = setups[0]
        skipped_signals += len(setups) - 1

        # Enter next-bar style: this close is the signal; fill at this close
        # (memo: close or next open). Chase already enforced on close.
        if chosen.entry is None or chosen.stop is None or chosen.trigger is None:
            continue
        chase_now = (chosen.entry - chosen.trigger) / chosen.trigger
        if chase_now > CHASE_MAX_PCT:
            skipped_signals += 1
            continue
        meta = (pair_meta or {}).get(chosen.pair)
        try:
            plan = size_long(
                chosen.entry,
                chosen.stop,
                book=book,
                fee_rt=fee_rt,
                pair_decimals=getattr(meta, "pair_decimals", 2),
                lot_decimals=getattr(meta, "lot_decimals", 8),
                ordermin=getattr(meta, "ordermin", 0.0),
                t1=chosen.t1,
                t2=chosen.t2,
            )
        except ValueError:
            skipped_signals += 1
            continue

        entry_fill = _fill(ts, plan.entry, plan.qty, "buy", "breakout_close", fee_rt)
        open_pos = OpenPos(
            pair=chosen.pair,
            setup=chosen,
            qty=plan.qty,
            remaining=plan.qty,
            notional=plan.notional,
            entry=plan.entry,
            stop=plan.stop,
            orig_stop=plan.stop,
            t1=plan.t1,
            t2=plan.t2,
            trigger=chosen.trigger,
            entry_time=ts,
            entry_index=len(history[chosen.pair]) - 1,
            fills=[entry_fill],
            realized_fees=entry_fill.fee,
            entry_date=day,
        )
        clips_today[day] += 1

    if open_pos is not None:
        # flatten leftover on last available close
        last_pair_bars = candles_by_pair[open_pos.pair]
        last = last_pair_bars[-1]
        flatten("eod_open_flatten", last.time, last.close)

    return BacktestResult(
        book=book,
        days=days,
        fee_rt=fee_rt,
        trades=trades,
        skipped_signals=skipped_signals,
        daily_stop_hits=daily_stop_hits,
        clips_capped=clips_capped,
        notes=notes,
    )


def result_as_dict(result: BacktestResult) -> dict[str, Any]:
    return {
        "summary": result.summary(),
        "notes": result.notes,
        "trades": [asdict(t) for t in result.trades],
    }
