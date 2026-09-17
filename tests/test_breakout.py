from kraken_paper.breakout import evaluate_breakout
from kraken_paper.constants import CHASE_MAX_PCT, STOP_MAX_PCT
from tests.factories import range_then_break


def _score(**kwargs):
    candles = range_then_break(**kwargs)
    return evaluate_breakout(candles, len(candles) - 1, pair="BTC/USD"), candles


def test_close_above_trigger_is_a_plus():
    setup, candles = _score()
    bar = candles[-1]
    assert bar.close > setup.trigger
    assert setup.grade == "A+"
    assert setup.tradable is True
    assert setup.stop is not None
    assert 0.005 <= setup.stop_pct <= 0.010
    assert setup.t1 is not None and setup.t2 is not None
    assert setup.net_rr is not None and setup.net_rr >= 1.3
    assert 2 <= setup.compression_bars <= 8


def test_wick_through_trigger_without_close_is_not_a_signal():
    setup, candles = _score(breakout_close=100.90, breakout_high=101.40, breakout_low=100.40)
    assert candles[-1].high > 101.0
    assert candles[-1].close < 101.0
    assert setup.tradable is False
    assert setup.grade == "SKIP"
    assert any("wick" in r.lower() or "close" in r.lower() for r in setup.reasons)


def test_no_chase_more_than_0_4_percent_through():
    # 101.0 trigger → 0.4% = 101.404; 101.50 is a chase.
    setup, _ = _score(breakout_close=101.50, breakout_high=101.55, breakout_low=100.40)
    assert setup.tradable is False
    assert setup.grade == "SKIP"
    assert setup.chase_pct is not None and setup.chase_pct > CHASE_MAX_PCT
    assert any("chase" in r.lower() for r in setup.reasons)


def test_stop_wider_than_one_percent_is_skipped_not_widened():
    setup, candles = _score(breakout_low=99.80, breakout_close=101.18, breakout_high=101.30)
    stop_if_used = (candles[-1].close - candles[-1].low) / candles[-1].close
    assert stop_if_used > STOP_MAX_PCT
    assert setup.tradable is False
    assert setup.grade == "SKIP"
    assert any("widen" in r.lower() or "wider" in r.lower() or "1.00%" in r for r in setup.reasons)


def test_low_atr_fails_fee_filter():
    setup, _ = _score(body_high=100.12, body_low=100.08)
    assert setup.tradable is False
    assert setup.grade == "SKIP"
    assert setup.atr_pct is not None
    assert setup.atr_pct < 0.0039
    assert any("fee filter" in r.lower() or "atr15" in r.lower() for r in setup.reasons)


def test_short_compression_is_not_a_plus():
    setup, _ = _score(range_high_offset=1)
    assert setup.grade in {"B", "SKIP"}
    assert setup.tradable is False
    assert setup.compression_bars is not None
    assert setup.compression_bars < 2


def test_long_coil_is_a_not_a_plus():
    setup, _ = _score(range_high_offset=20)
    # Still must pass hard filters; if it does, grade is A not A+.
    if setup.stop is not None and setup.atr_pct and setup.atr_pct >= 0.0039:
        assert setup.grade == "A"
        assert setup.tradable is False
    else:
        assert setup.tradable is False


def test_preferred_compression_window_is_two_to_eight():
    for n in range(2, 9):
        setup, _ = _score(range_high_offset=n)
        assert setup.grade == "A+", (n, setup.grade, setup.reasons)
        assert setup.tradable is True
