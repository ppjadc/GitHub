"""Offline-capable backtest over public OHLC (max ~720 candles from Kraken)."""

from __future__ import annotations

from datetime import timedelta

from multi_market_paper.instruments import FX_UNIVERSE, PAXGUSD
from multi_market_paper.paper import Book
from multi_market_paper.public_client import Candle, PublicClient
from multi_market_paper.sessions import fx_entry_bounds, is_fx_weekday
from multi_market_paper.strategies.fx_session_breakout import (
    evaluate_fx_breakout,
    simulate_fx_path,
)
from multi_market_paper.strategies.paxg_macro_swing import (
    evaluate_paxg_swing,
    simulate_paxg_path,
)


def _cutoff(candles: list[Candle], days: int) -> list[Candle]:
    if not candles:
        return []
    end = candles[-1].time
    start = end - timedelta(days=days)
    return [c for c in candles if c.time >= start]


def backtest_fx(candles: list[Candle], instrument, book: Book, days: int) -> dict:
    window = _cutoff(candles, days)
    trades = []
    seen_days: set = set()
    for bar in window:
        if not is_fx_weekday(bar.time):
            continue
        day = bar.time.date()
        if day in seen_days:
            continue
        # Evaluate at London close so the full entry window is visible.
        as_of = fx_entry_bounds(bar.time)[1] - timedelta(minutes=1)
        sig = evaluate_fx_breakout(
            instrument, window, as_of, book.cash_usd, book.risk_pct, book.max_notional_pct
        )
        seen_days.add(day)
        if sig.action != "PLAN":
            trades.append(
                {
                    "day": day.isoformat(),
                    "action": "SKIP",
                    "reason": sig.reason,
                    "pnl_usd": 0.0,
                }
            )
            continue
        sim = simulate_fx_path(instrument, window, sig)
        trades.append(
            {
                "day": day.isoformat(),
                "action": "PLAN",
                "reason": sig.reason,
                "entry": sig.entry,
                "qty": sig.size.qty if sig.size else 0.0,
                **sim,
            }
        )
    planned = [t for t in trades if t["action"] == "PLAN"]
    pnl = sum(t.get("pnl_usd", 0.0) for t in planned)
    return {
        "instrument": instrument.symbol,
        "strategy": "fx_london_ny_breakout",
        "days": days,
        "signals": len(trades),
        "taken": len(planned),
        "skipped": len(trades) - len(planned),
        "pnl_usd": pnl,
        "trades": trades,
    }


def backtest_paxg(candles: list[Candle], book: Book, days: int) -> dict:
    window = _cutoff(candles, days)
    trades = []
    seen_days: set = set()
    for i, bar in enumerate(window):
        if not bar.committed:
            continue
        day = bar.time.date()
        if day in seen_days:
            continue
        # Evaluate at the last committed bar of this UTC day.
        day_end_idx = i
        for j in range(i, len(window)):
            if window[j].time.date() != day:
                break
            if window[j].committed:
                day_end_idx = j
        seen_days.add(day)
        bar = window[day_end_idx]
        sig = evaluate_paxg_swing(
            PAXGUSD,
            window[: day_end_idx + 1],
            bar.time,
            book.cash_usd,
            book.risk_pct,
            book.max_notional_pct,
        )
        if sig.action != "PLAN":
            trades.append(
                {
                    "day": day.isoformat(),
                    "action": "SKIP",
                    "reason": sig.reason,
                    "event": sig.event_name,
                    "pnl_usd": 0.0,
                }
            )
            continue
        sim = simulate_paxg_path(PAXGUSD, window[day_end_idx + 1 :], sig)
        trades.append(
            {
                "day": day.isoformat(),
                "action": "PLAN",
                "reason": sig.reason,
                "event": sig.event_name,
                "entry": sig.entry,
                "qty": sig.size.qty if sig.size else 0.0,
                **sim,
            }
        )
    planned = [t for t in trades if t["action"] == "PLAN"]
    pnl = sum(t.get("pnl_usd", 0.0) for t in planned)
    return {
        "instrument": PAXGUSD.symbol,
        "strategy": "paxg_macro_swing",
        "days": days,
        "taken": len(planned),
        "skipped": len(trades) - len(planned),
        "pnl_usd": pnl,
        "trades": trades,
    }


def run_backtest(
    client: PublicClient,
    book: Book,
    days: int,
    strategy: str = "all",
) -> dict:
    if days < 1:
        raise ValueError("--days must be >= 1")
    reports = []
    if strategy in {"all", "fx"}:
        for inst in FX_UNIVERSE:
            candles = client.ohlc(inst.pair, inst.interval_backtest, inst.asset_class)
            reports.append(backtest_fx(candles, inst, book, days))
    if strategy in {"all", "paxg"}:
        candles = client.ohlc(PAXGUSD.pair, PAXGUSD.interval_backtest, PAXGUSD.asset_class)
        reports.append(backtest_paxg(candles, book, days))
    return {
        "lane": "multi_market_paper",
        "mode": "backtest",
        "live_orders": False,
        "days": days,
        "book_usd": book.cash_usd,
        "reports": reports,
    }
