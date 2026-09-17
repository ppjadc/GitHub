import unittest

from multi_market_paper.fees import (
    DEFAULT_FX_EDGE_MULTIPLE,
    DEFAULT_PAXG_EDGE_MULTIPLE,
    FX_FEES,
    PAXG_FEES,
    fee_usd,
    required_move_pct,
    round_trip_fee_usd,
    should_skip_for_fees,
)


class FeeTests(unittest.TestCase):
    def test_fx_round_trip_is_40bp(self):
        self.assertAlmostEqual(FX_FEES.round_trip_rate, 0.0040)
        self.assertAlmostEqual(round_trip_fee_usd(1000, FX_FEES), 4.0)

    def test_paxg_taker_round_trip_is_160bp(self):
        self.assertAlmostEqual(PAXG_FEES.fill_rate, 0.0080)
        self.assertAlmostEqual(PAXG_FEES.round_trip_rate, 0.0160)
        self.assertAlmostEqual(round_trip_fee_usd(1000, PAXG_FEES), 16.0)

    def test_fee_usd_rejects_negatives(self):
        with self.assertRaises(ValueError):
            fee_usd(-1, 0.002)
        with self.assertRaises(ValueError):
            fee_usd(100, -0.1)

    def test_fx_skip_when_asian_range_cannot_cover_fees(self):
        # 20 pips on EURUSD ≈ 0.174% vs 0.50% required at 1.25x * 0.40%
        skip, reason = should_skip_for_fees(0.00174, FX_FEES, DEFAULT_FX_EDGE_MULTIPLE)
        self.assertTrue(skip)
        self.assertIn("fee_skip", reason)

    def test_fx_allow_when_range_covers_fees(self):
        skip, reason = should_skip_for_fees(0.0070, FX_FEES, DEFAULT_FX_EDGE_MULTIPLE)
        self.assertFalse(skip)
        self.assertIn("fee_ok", reason)

    def test_paxg_requires_larger_move_than_fx(self):
        fx_need = required_move_pct(FX_FEES, DEFAULT_FX_EDGE_MULTIPLE)
        paxg_need = required_move_pct(PAXG_FEES, DEFAULT_PAXG_EDGE_MULTIPLE)
        self.assertGreater(paxg_need, fx_need)
        skip, _ = should_skip_for_fees(0.020, PAXG_FEES, DEFAULT_PAXG_EDGE_MULTIPLE)
        self.assertTrue(skip)  # 2.0% < 2.4% required
        skip, _ = should_skip_for_fees(0.025, PAXG_FEES, DEFAULT_PAXG_EDGE_MULTIPLE)
        self.assertFalse(skip)


if __name__ == "__main__":
    unittest.main()
