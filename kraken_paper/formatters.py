"""Human-readable tables for Jose — results in plain English."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from kraken_paper.constants import SESSION_TZ
from kraken_paper.models import Setup, SizePlan, Ticker
from kraken_paper.backtest import BacktestResult

ET = ZoneInfo(SESSION_TZ)


def ts_et(ts: int | None) -> str:
    if not ts:
        return "—"
    return datetime.fromtimestamp(ts, tz=ET).strftime("%Y-%m-%d %H:%M ET")


def pct(x: float | None, digits: int = 2) -> str:
    if x is None:
        return "—"
    return f"{x * 100:.{digits}f}%"


def px(x: float | None) -> str:
    if x is None:
        return "—"
    if x >= 1000:
        return f"{x:,.1f}"
    return f"{x:,.2f}"


def usd(x: float | None, digits: int = 2) -> str:
    if x is None:
        return "—"
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x):,.{digits}f}"


def format_scan(setups: list[Setup], tickers: dict[str, Ticker]) -> str:
    lines = [
        "Kraken 15m momentum-breakout scan (PUBLIC REST, no orders).",
        "A+ only is tradable on the locked $1,000 live book. Wicks do not count.",
        "",
        f"{'Pair':<8} {'Last':>12} {'24h range':>24} {'Dist high':>10} {'ATR15':>8} {'ATR/fee':>8} {'Grade':>6}",
        "-" * 90,
    ]
    for s in setups:
        t = tickers.get(s.pair)
        last = t.last if t else s.last_price
        rng = f"{px(t.low_24h)}–{px(t.high_24h)}" if t else "—"
        atr_fee = (s.atr_pct / 0.0026) if s.atr_pct else None
        last_s = px(last)
        atr_s = "—" if atr_fee is None else f"{atr_fee:.1f}×"
        lines.append(
            f"{s.pair:<8} {last_s:>12} {rng:>24} {pct(s.dist_to_24h_high_pct):>10} "
            f"{pct(s.atr_pct):>8} {atr_s:>8} {s.grade:>6}"
        )
    lines.append("")
    for s in setups:
        lines.append(f"## {s.pair} — {s.grade}{' (tradable)' if s.tradable else ''}")
        lines.append(f"   15m bar: {ts_et(s.bar_time)}")
        if s.trigger is not None:
            lines.append(f"   Trigger (range top): {s.trigger:.6g}  entry close: {s.entry:.6g}")
        if s.stop is not None:
            extra = f"  T1 {s.t1:.6g}  T2 {s.t2:.6g}"
            if s.net_rr is not None:
                extra += f"  net R after fees {s.net_rr:.2f}"
            lines.append(f"   Stop {s.stop:.6g} ({pct(s.stop_pct)}){extra}")
        for r in s.reasons:
            lines.append(f"   - {r}")
        lines.append("")
    lines.append(
        "How to read this: Grade SKIP means do nothing. B/A printed a close above the "
        "high but failed compression or another A+ preference — still no clip on this book. "
        "If every pair is SKIP, that is a valid day (patience is part of the edge)."
    )
    return "\n".join(lines)


def format_size_plan(live: SizePlan, paper: SizePlan, setup: Setup) -> str:
    lines = [
        f"Paper plan for {setup.pair} ({setup.grade}) — NOT a live order.",
        f"Signal bar {ts_et(setup.bar_time)}",
        "",
        "Entry / risk (same prices on live and paper):",
        f"  Trigger {setup.trigger:.6g}",
        f"  Entry   {live.entry:.6g}  (15m close; limit preferred if spread is tight)",
        f"  Stop    {live.stop:.6g}  ({pct(live.stop_pct)} below entry; hard band 0.50%–1.00%)",
        f"  T1      {live.t1:.6g}  (2R gross — take ≥50% off)",
        f"  T2      {live.t2:.6g}  (3R gross or trail; flatten same ET day)",
        f"  Net R:R after 0.26% RT fees (50/50 T1/T2): {setup.net_rr:.2f}" if setup.net_rr else "",
        "",
        "LIVE $1,000 cash book (no leverage):",
        f"  Qty {live.qty:.8g}   notional {usd(live.notional)}   /  equity {usd(live.equity)}",
        f"  Price risk {usd(live.price_risk)}  +  RT fees {usd(live.fee_rt_usd)}  =  total risk {usd(live.total_risk)}",
        f"  Band ${live.risk_min:.0f}–${live.risk_max:.0f}  "
        f"{'INSIDE' if live.within_risk_band else 'OUTSIDE (cash-capped or reduced)'}",
        "",
        "PAPER jose-main $10,000 (10× live notionals):",
        f"  Qty {paper.qty:.8g}   notional {usd(paper.notional)}",
        f"  Total risk {usd(paper.total_risk)}  (band ${paper.risk_min:.0f}–${paper.risk_max:.0f})",
        "",
        "Rules still in force after send: 1 open risk unit, 1–2 clips/day, flatten same day, "
        "scratch on a 15m close back below trigger within 2 bars, 3h time stop if T1 never prints.",
        "",
        "Notes:",
    ]
    for n in live.notes + paper.notes:
        lines.append(f"  - {n}")
    return "\n".join(x for x in lines if x is not None)


def format_backtest(result: BacktestResult) -> str:
    s = result.summary()
    lines = [
        f"Backtest — last {result.days} days of Kraken 15m OHLC (public REST).",
        "",
    ]
    for n in result.notes:
        lines.append(f"  {n}")
    lines += [
        "",
        f"Trades taken: {s['trades']}   wins {s['wins']}   losses {s['losses']}   scratches {s['scratches']}",
        f"Gross P&L {usd(s['gross_pnl'])}   fees {usd(s['fees'])}   net {usd(s['net_pnl'])}   "
        f"avg net/trade {usd(s['avg_net'])}",
        f"A/B signals skipped (not A+ or blocked): {s['skipped_signals']}",
        f"Days the −daily-loss halt fired: {s['daily_stop_hits']}",
        f"Times a 3rd+ clip was refused: {s['clips_capped']}",
        f"Exits: {s['exit_reasons'] or '{}'}",
        "",
        "Trade log:",
    ]
    if not result.trades:
        lines.append("  (none — no A+ clips cleared the locked filters in this window)")
    else:
        lines.append(
            f"  {'When (ET)':<18} {'Pair':<8} {'Entry':>10} {'Net':>10} {'R':>6} {'Exit':<22}"
        )
        for t in result.trades:
            lines.append(
                f"  {ts_et(t.entry_time):<18} {t.pair:<8} {t.entry:>10.4g} "
                f"{usd(t.net_pnl):>10} {t.r_multiple:>6.2f} {t.exit_reason:<22}"
            )
    lines += [
        "",
        "Plain English: net P&L already subtracts the 0.26% round-trip fee used on jose-main. "
        "Slippage is not modeled, so live taker fills will be worse. A small or negative net "
        "after fees is a no-go for Sunday live — the memo wants paper net ≥ −$200 on the $10k "
        "book (about −$20 live-equivalent) across Thu–Sat, and no two daily-stop breaches.",
        "This replay is not a substitute for the three-day paper log; it only asks whether the "
        "locked A+ rules historically cleared fees on these pairs.",
    ]
    return "\n".join(lines)
