"""Build synthetic 15m candles for breakout tests (no network)."""

from __future__ import annotations

from kraken_paper.models import Candle

STEP = 15 * 60
START = 1_700_000_000


def candle(i: int, o: float, h: float, l: float, c: float, pair: str = "BTC/USD") -> Candle:
    assert h >= max(o, c) - 1e-12
    assert l <= min(o, c) + 1e-12
    return Candle(time=START + i * STEP, open=o, high=h, low=l, close=c, volume=1.0, pair=pair)


def range_then_break(
    *,
    n_hist: int = 120,
    range_high: float = 101.0,
    range_high_offset: int = 6,
    breakout_close: float = 101.18,
    breakout_high: float = 101.30,
    breakout_low: float = 100.35,
    body_high: float = 100.55,
    body_low: float = 99.95,
    pair: str = "BTC/USD",
) -> list[Candle]:
    """Flat range, then a marked high, then inside bars, then a close through the high.

    `range_high_offset` is how many history bars sit after the range-high print
    (compression). The breakout is appended as the last candle.
    """
    bars: list[Candle] = []
    high_i = n_hist - 1 - range_high_offset
    mid = (body_high + body_low) / 2.0
    for i in range(n_hist):
        if i == high_i:
            bars.append(candle(i, mid, range_high, body_low, mid, pair))
        else:
            bars.append(candle(i, mid, body_high, body_low, mid, pair))
    bars.append(
        candle(n_hist, 100.60, breakout_high, breakout_low, breakout_close, pair)
    )
    return bars
