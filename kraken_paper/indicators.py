from __future__ import annotations

from kraken_paper.constants import ATR_PERIOD, BARS_8H, SWING_LEFT, SWING_RIGHT
from kraken_paper.models import Candle


def true_range(candle: Candle, prev_close: float | None) -> float:
    if prev_close is None:
        return candle.high - candle.low
    return max(
        candle.high - candle.low,
        abs(candle.high - prev_close),
        abs(candle.low - prev_close),
    )


def atr(candles: list[Candle], period: int = ATR_PERIOD) -> float | None:
    """Simple mean true range over `period` bars ending at the last candle."""
    if period <= 0 or len(candles) < period + 1:
        return None
    window = candles[-(period + 1) :]
    trs: list[float] = []
    for i in range(1, len(window)):
        trs.append(true_range(window[i], window[i - 1].close))
    if len(trs) < period:
        return None
    return sum(trs[-period:]) / period


def atr_pct(candles: list[Candle], period: int = ATR_PERIOD) -> float | None:
    value = atr(candles, period)
    if value is None or candles[-1].close <= 0:
        return None
    return value / candles[-1].close


def atr_8h_pct(candles: list[Candle]) -> float | None:
    return atr_pct(candles, period=BARS_8H)


def swing_high_indices(candles: list[Candle], left: int = SWING_LEFT, right: int = SWING_RIGHT) -> list[int]:
    out: list[int] = []
    n = len(candles)
    for i in range(left, n - right):
        h = candles[i].high
        if all(h >= candles[i - j].high for j in range(1, left + 1)) and all(
            h > candles[i + j].high for j in range(1, right + 1)
        ):
            out.append(i)
    return out


def swing_low_indices(candles: list[Candle], left: int = SWING_LEFT, right: int = SWING_RIGHT) -> list[int]:
    out: list[int] = []
    n = len(candles)
    for i in range(left, n - right):
        lo = candles[i].low
        if all(lo <= candles[i - j].low for j in range(1, left + 1)) and all(
            lo < candles[i + j].low for j in range(1, right + 1)
        ):
            out.append(i)
    return out


def last_swing_low_before(candles: list[Candle], index: int) -> Candle | None:
    """Last confirmed swing low strictly before `index` (right-side confirmation)."""
    if index <= 0:
        return None
    prefix = candles[:index]
    idxs = swing_low_indices(prefix)
    if not idxs:
        return None
    return prefix[idxs[-1]]
