"""15m momentum-breakout A+ detector. Rules are locked — skip rather than loosen."""

from __future__ import annotations

from kraken_paper.constants import (
    ATR_MIN_PCT,
    ATR_PERIOD,
    BARS_24H,
    CHASE_MAX_PCT,
    COMPRESSION_MIN,
    COMPRESSION_PREFERRED_MAX,
    FEE_RT,
    MIN_GROSS_RR,
    MIN_NET_RR,
    PLANNED_GROSS_R,
    STOP_MAX_PCT,
    STOP_MIN_PCT,
    T1_R,
    T2_R,
)
from kraken_paper.fees import blended_net_rr, passes_fee_filter, passes_net_rr
from kraken_paper.indicators import atr_8h_pct, atr_pct, last_swing_low_before
from kraken_paper.models import Candle, Setup, Ticker
from kraken_paper.sizing import targets


def range_trigger(history: list[Candle], lookback: int = BARS_24H) -> float | None:
    """Clear range top = highest high over the lookback (24h / session subset)."""
    if not history:
        return None
    window = history[-lookback:] if len(history) > lookback else history
    return max(c.high for c in window)


def compression_bars_since_high(history: list[Candle], trigger: float) -> int:
    """Bars after the most recent print of the range top, before the breakout bar."""
    idx = None
    for i in range(len(history) - 1, -1, -1):
        if history[i].high >= trigger - 1e-12:
            idx = i
            break
    if idx is None:
        return 0
    return len(history) - 1 - idx


def _structural_stop(entry: float, breakout: Candle, history: list[Candle]) -> tuple[float | None, str]:
    """Closer of breakout-candle low vs last inside-range swing low, if it fits 0.50–1.00%."""
    candidates: list[tuple[str, float]] = [("breakout candle low", breakout.low)]
    swing = last_swing_low_before(history, len(history))
    if swing is not None and swing.low < entry:
        candidates.append(("last swing low in range", swing.low))

    in_band: list[tuple[str, float, float]] = []
    rejected: list[str] = []
    for label, level in candidates:
        if level >= entry:
            rejected.append(f"{label} {level} is not below entry {entry}")
            continue
        pct = (entry - level) / entry
        if pct + 1e-12 < STOP_MIN_PCT:
            rejected.append(f"{label} stop {pct:.3%} is tighter than {STOP_MIN_PCT:.2%} — not in band")
            continue
        if pct - 1e-12 > STOP_MAX_PCT:
            rejected.append(f"{label} stop {pct:.3%} is wider than {STOP_MAX_PCT:.2%} — skip (do not widen)")
            continue
        in_band.append((label, level, pct))

    if not in_band:
        return None, "; ".join(rejected) if rejected else "no structural stop"

    # Closer to entry = smaller distance = higher stop price
    in_band.sort(key=lambda x: x[2])
    label, level, _pct = in_band[0]
    return level, f"stop at {label}"


def _grade(compression: int, hard_pass: bool) -> str:
    if not hard_pass:
        return "SKIP"
    if COMPRESSION_MIN <= compression <= COMPRESSION_PREFERRED_MAX:
        return "A+"
    if compression > COMPRESSION_PREFERRED_MAX:
        return "A"
    return "B"


def evaluate_breakout(
    candles: list[Candle],
    index: int,
    *,
    pair: str,
    ticker: Ticker | None = None,
    last_price: float | None = None,
    fee_rt: float = FEE_RT,
) -> Setup:
    """Score candle `index` as a 15m close breakout. Wicks alone never count."""
    reasons: list[str] = []
    if index <= 0 or index >= len(candles):
        return Setup(pair=pair, grade="SKIP", tradable=False, reasons=["index out of range"])

    bar = candles[index]
    history = candles[:index]
    last_price = bar.close if last_price is None else last_price
    dist_24h = None
    if ticker is not None and ticker.high_24h > 0:
        dist_24h = (ticker.high_24h - last_price) / ticker.high_24h

    min_bars = max(BARS_24H, ATR_PERIOD + 2, 20)
    if len(history) < min_bars:
        return Setup(
            pair=pair,
            grade="SKIP",
            tradable=False,
            reasons=[f"need ≥{min_bars} prior 15m bars, have {len(history)}"],
            bar_time=bar.time,
            last_price=last_price,
            dist_to_24h_high_pct=dist_24h,
        )

    trigger = range_trigger(history)
    # ATR on the range *before* the breakout bar so a single spike cannot buy the fee filter.
    atrp = atr_pct(history)
    atr8 = atr_8h_pct(history)
    compression = compression_bars_since_high(history, trigger) if trigger else 0

    setup = Setup(
        pair=pair,
        grade="SKIP",
        tradable=False,
        reasons=reasons,
        trigger=trigger,
        entry=bar.close,
        compression_bars=compression,
        atr_pct=atrp,
        atr_8h_pct=atr8,
        bar_time=bar.time,
        last_price=last_price,
        dist_to_24h_high_pct=dist_24h,
        gross_rr=PLANNED_GROSS_R,
    )

    if trigger is None:
        reasons.append("no trigger")
        return setup

    if bar.close <= trigger:
        reasons.append(
            f"no 15m close above trigger {trigger:.6g} (close {bar.close:.6g}; "
            f"wick high {bar.high:.6g} does not count)"
        )
        if ticker is not None:
            reasons.append(
                f"armed: need a 15m close above {trigger:.6g} "
                f"(24h high {ticker.high_24h:.6g}, last {last_price:.6g})"
            )
        setup.grade = "SKIP"
        return setup

    chase = (bar.close - trigger) / trigger
    setup.chase_pct = chase
    if chase > CHASE_MAX_PCT + 1e-12:
        reasons.append(
            f"chase {chase:.3%} through trigger — skip (> {CHASE_MAX_PCT:.2%} without a retest)"
        )
        setup.grade = "SKIP"
        return setup
    reasons.append(f"15m close {bar.close:.6g} above trigger {trigger:.6g} ({chase:.3%} through)")

    if atrp is None:
        reasons.append("ATR unavailable")
        setup.grade = "SKIP"
        return setup
    if not passes_fee_filter(atrp, fee_rt):
        reasons.append(
            f"fee filter: ATR15 {atrp:.3%} < {ATR_MIN_PCT:.2%} (1.5× {fee_rt:.2%} RT fee)"
        )
        setup.grade = "SKIP"
        return setup
    reasons.append(f"ATR15 {atrp:.3%} clears {ATR_MIN_PCT:.2%} fee filter")

    stop, stop_why = _structural_stop(bar.close, bar, history)
    if stop is None:
        reasons.append(f"no stop in {STOP_MIN_PCT:.2%}–{STOP_MAX_PCT:.2%} band ({stop_why})")
        setup.grade = "SKIP"
        return setup
    setup.stop = stop
    setup.stop_pct = (bar.close - stop) / bar.close
    t1, t2 = targets(bar.close, stop, T1_R, T2_R)
    setup.t1, setup.t2 = t1, t2
    reasons.append(f"{stop_why} ({setup.stop_pct:.3%} from entry)")

    net = blended_net_rr(setup.stop_pct, fee_rt)
    setup.net_rr = net
    if PLANNED_GROSS_R + 1e-12 < MIN_GROSS_RR:
        reasons.append("planned gross R:R below 2.0")
        setup.grade = "SKIP"
        return setup
    if not passes_net_rr(setup.stop_pct, fee_rt, MIN_NET_RR):
        reasons.append(
            f"after {fee_rt:.2%} RT fees, blended T1/T2 R:R {net:.2f} < {MIN_NET_RR:.1f} — skip"
        )
        setup.grade = "SKIP"
        return setup
    reasons.append(
        f"planned gross {PLANNED_GROSS_R:.1f}R (T1 {T1_R:.0f}R / T2 {T2_R:.0f}R); "
        f"net after fees {net:.2f}R"
    )

    if compression < COMPRESSION_MIN:
        reasons.append(
            f"compression {compression} bar(s) since range high — prefer {COMPRESSION_MIN}–"
            f"{COMPRESSION_PREFERRED_MAX}; not A+"
        )
    elif compression > COMPRESSION_PREFERRED_MAX:
        reasons.append(
            f"compression {compression} bars (long coil, >{COMPRESSION_PREFERRED_MAX}) — A not A+"
        )
    else:
        reasons.append(
            f"compression {compression} bars in preferred {COMPRESSION_MIN}–{COMPRESSION_PREFERRED_MAX} window"
        )

    hard_pass = True  # all skip-returns already happened
    setup.grade = _grade(compression, hard_pass)
    setup.tradable = setup.grade == "A+"
    if not setup.tradable:
        reasons.append("locked book trades A+ only — this clip is logged, not sized to send")
    return setup


def evaluate_latest(candles: list[Candle], pair: str, ticker: Ticker | None = None) -> Setup:
    if len(candles) < 2:
        return Setup(pair=pair, grade="SKIP", tradable=False, reasons=["not enough candles"])
    last = candles[-1]
    return evaluate_breakout(
        candles,
        len(candles) - 1,
        pair=pair,
        ticker=ticker,
        last_price=ticker.last if ticker else last.close,
    )
