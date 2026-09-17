import unittest
from datetime import datetime, timezone

from multi_market_paper.sessions import (
    in_asian_range,
    in_fx_entry_window,
    in_london,
    in_new_york,
    in_overlap,
    is_fx_weekday,
    next_fx_session_open,
)

UTC = timezone.utc


class SessionFilterTests(unittest.TestCase):
    def test_london_weekday_morning(self):
        ts = datetime(2026, 9, 17, 8, 0, tzinfo=UTC)  # Thursday
        self.assertTrue(is_fx_weekday(ts))
        self.assertTrue(in_london(ts))
        self.assertTrue(in_fx_entry_window(ts))
        self.assertFalse(in_new_york(ts))
        self.assertFalse(in_overlap(ts))
        self.assertFalse(in_asian_range(ts))

    def test_overlap_window(self):
        ts = datetime(2026, 9, 17, 13, 30, tzinfo=UTC)
        self.assertTrue(in_london(ts))
        self.assertTrue(in_new_york(ts))
        self.assertTrue(in_overlap(ts))
        self.assertTrue(in_fx_entry_window(ts))

    def test_ny_afternoon_is_not_fx_entry(self):
        ts = datetime(2026, 9, 17, 18, 0, tzinfo=UTC)
        self.assertTrue(in_new_york(ts))
        self.assertFalse(in_london(ts))
        self.assertFalse(in_overlap(ts))
        self.assertFalse(in_fx_entry_window(ts))

    def test_asian_range_hours(self):
        ts = datetime(2026, 9, 17, 3, 0, tzinfo=UTC)
        self.assertTrue(in_asian_range(ts))
        self.assertFalse(in_fx_entry_window(ts))

    def test_weekend_is_closed(self):
        saturday = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
        self.assertFalse(is_fx_weekday(saturday))
        self.assertFalse(in_london(saturday))
        self.assertFalse(in_fx_entry_window(saturday))
        self.assertFalse(in_overlap(saturday))

    def test_next_london_open_skips_weekend(self):
        friday_evening = datetime(2026, 9, 18, 18, 0, tzinfo=UTC)
        nxt = next_fx_session_open(friday_evening)
        self.assertEqual(nxt, datetime(2026, 9, 21, 7, 0, tzinfo=UTC))

    def test_next_london_open_same_morning(self):
        before = datetime(2026, 9, 17, 6, 0, tzinfo=UTC)
        nxt = next_fx_session_open(before)
        self.assertEqual(nxt, datetime(2026, 9, 17, 7, 0, tzinfo=UTC))

    def test_naive_datetime_treated_as_utc(self):
        ts = datetime(2026, 9, 17, 12, 0)
        self.assertTrue(in_overlap(ts))


if __name__ == "__main__":
    unittest.main()
