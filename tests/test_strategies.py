import unittest
from datetime import datetime, timedelta, timezone

from multi_market_paper.instruments import EURUSD, PAXGUSD
from multi_market_paper.macro_calendar import in_macro_window, next_event
from multi_market_paper.public_client import Candle
from multi_market_paper.strategies.fx_session_breakout import evaluate_fx_breakout
from multi_market_paper.strategies.paxg_macro_swing import evaluate_paxg_swing

UTC = timezone.utc


def _bar(ts: datetime, o, h, l, c, committed=True) -> Candle:
    return Candle(ts, float(o), float(h), float(l), float(c), 1.0, committed)


def _hourly_day(day: datetime, asian_high=1.1600, asian_low=1.1500, london_close=None):
    candles = []
    for hour in range(24):
        ts = day.replace(hour=hour, minute=0, second=0, microsecond=0)
        if hour < 7:
            high, low, close = asian_high, asian_low, (asian_high + asian_low) / 2
        else:
            close = london_close if london_close is not None else (asian_high + asian_low) / 2
            high = max(close, asian_high)
            low = min(close, asian_low)
        candles.append(_bar(ts, close, high, low, close))
    return candles


class FxStrategyTests(unittest.TestCase):
    def setUp(self):
        self.day = datetime(2026, 9, 17, tzinfo=UTC)  # Thursday
        self.as_of = datetime(2026, 9, 17, 15, 0, tzinfo=UTC)

    def test_weekend_skip(self):
        candles = _hourly_day(datetime(2026, 9, 19, tzinfo=UTC), london_close=1.1700)
        sig = evaluate_fx_breakout(EURUSD, candles, datetime(2026, 9, 19, 12, tzinfo=UTC), 2500, 0.01, 0.35)
        self.assertEqual(sig.action, "SKIP")
        self.assertEqual(sig.reason, "weekend_fx_closed")

    def test_fee_skip_on_tiny_asian_range(self):
        candles = _hourly_day(self.day, asian_high=1.1502, asian_low=1.1500, london_close=1.1520)
        sig = evaluate_fx_breakout(EURUSD, candles, self.as_of, 2500, 0.01, 0.35)
        self.assertEqual(sig.action, "SKIP")
        self.assertIn("fee_skip", sig.reason)

    def test_plans_long_on_london_high_break(self):
        candles = _hourly_day(self.day, asian_high=1.1600, asian_low=1.1500, london_close=1.1720)
        sig = evaluate_fx_breakout(EURUSD, candles, self.as_of, 2500, 0.01, 0.35)
        self.assertEqual(sig.action, "PLAN")
        self.assertEqual(sig.side, "long")
        self.assertGreater(sig.size.qty, 0)
        self.assertLessEqual(sig.size.notional_usd + sig.size.fee_usd, 2500)

    def test_cash_only_skips_short_break(self):
        candles = _hourly_day(self.day, asian_high=1.1600, asian_low=1.1500, london_close=1.1400)
        sig = evaluate_fx_breakout(EURUSD, candles, self.as_of, 2500, 0.01, 0.35)
        self.assertEqual(sig.action, "SKIP")
        self.assertEqual(sig.reason, "cash_only_no_short")

    def test_after_london_close_skips(self):
        candles = _hourly_day(self.day, asian_high=1.1600, asian_low=1.1500, london_close=1.1720)
        sig = evaluate_fx_breakout(
            EURUSD, candles, datetime(2026, 9, 17, 18, 0, tzinfo=UTC), 2500, 0.01, 0.35
        )
        self.assertEqual(sig.action, "SKIP")
        self.assertEqual(sig.reason, "after_london_close")


class PaxgStrategyTests(unittest.TestCase):
    def _series(self, start: datetime, n=16, breakout=True):
        candles = []
        price = 4000.0
        for i in range(n):
            ts = start + timedelta(hours=4 * i)
            high = price + 5
            low = price - 5
            close = price + (80 if breakout and i == n - 1 else 0)
            high = max(high, close)
            candles.append(_bar(ts, price, high, low, close))
            price += 1
        return candles

    def test_skips_outside_macro_window(self):
        # 17 Sep 2026 is after the 16 Sep FOMC window end (17 Sep 21:00 UTC)
        ts = datetime(2026, 9, 18, 12, tzinfo=UTC)
        candles = self._series(datetime(2026, 9, 10, tzinfo=UTC))
        sig = evaluate_paxg_swing(PAXGUSD, candles, ts, 2500, 0.01, 0.35)
        self.assertEqual(sig.action, "SKIP")
        self.assertIn("not_in_macro_window", sig.reason)

    def test_next_event_is_october_nfp(self):
        nxt = next_event(datetime(2026, 9, 18, tzinfo=UTC))
        self.assertIsNotNone(nxt)
        self.assertEqual(nxt.name, "NFP")
        self.assertEqual(nxt.day.isoformat(), "2026-10-02")

    def test_macro_window_covers_fomc_decision_day(self):
        self.assertTrue(in_macro_window(datetime(2026, 9, 16, 18, tzinfo=UTC)))

    def test_fee_skip_inside_window_when_range_too_small(self):
        # Quiet 4h bars inside FOMC window: range ~0.25% << 2.4% required
        start = datetime(2026, 9, 15, 0, tzinfo=UTC)
        candles = self._series(start, n=16, breakout=True)
        # flatten the series to tiny range
        tiny = [
            _bar(c.time, 4000, 4001, 3999, 4000.5 if i < 15 else 4010)
            for i, c in enumerate(candles)
        ]
        as_of = tiny[-1].time
        self.assertTrue(in_macro_window(as_of))
        sig = evaluate_paxg_swing(PAXGUSD, tiny, as_of, 2500, 0.01, 0.35)
        self.assertEqual(sig.action, "SKIP")
        self.assertIn("fee_skip", sig.reason)

    def test_plans_long_when_range_and_macro_align(self):
        start = datetime(2026, 9, 14, 0, tzinfo=UTC)
        candles = []
        price = 4000.0
        for i in range(16):
            ts = start + timedelta(hours=4 * i)
            # ~3% lookback range so fees pass
            high = 4120.0
            low = 4000.0
            close = 4135.0 if i == 15 else 4060.0
            candles.append(_bar(ts, price, high if i < 15 else close, low, close))
        as_of = candles[-1].time
        self.assertTrue(in_macro_window(as_of))
        sig = evaluate_paxg_swing(PAXGUSD, candles, as_of, 2500, 0.01, 0.35)
        self.assertEqual(sig.action, "PLAN")
        self.assertEqual(sig.side, "long")
        self.assertIn("FOMC", sig.event_name)
        self.assertGreater(sig.size.qty, 0)


if __name__ == "__main__":
    unittest.main()
