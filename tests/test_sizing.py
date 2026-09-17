import unittest

from multi_market_paper.fees import FX_FEES, PAXG_FEES
from multi_market_paper.instruments import EURUSD, PAXGUSD
from multi_market_paper.sizing import SizeRequest, size_cash_long


class SizingTests(unittest.TestCase):
    def test_notional_plus_fee_never_exceeds_cash(self):
        result = size_cash_long(
            SizeRequest(
                cash_usd=1000,
                price=1.15,
                stop_distance=0.004,
                risk_pct=0.01,
                max_notional_pct=1.0,
                schedule=FX_FEES,
                limits=EURUSD.limits,
            )
        )
        self.assertFalse(result.skipped)
        self.assertLessEqual(result.notional_usd + result.fee_usd, 1000 + 1e-9)
        self.assertGreater(result.qty, 0)
        # No leverage: qty * price == notional <= cash
        self.assertLessEqual(result.qty * 1.15, 1000)

    def test_max_notional_pct_caps_position(self):
        result = size_cash_long(
            SizeRequest(
                cash_usd=2500,
                price=1.15,
                stop_distance=0.00001,  # tiny stop would otherwise size huge
                risk_pct=0.01,
                max_notional_pct=0.35,
                schedule=FX_FEES,
                limits=EURUSD.limits,
            )
        )
        self.assertFalse(result.skipped)
        self.assertLessEqual(result.notional_usd, 2500 * 0.35 + 1e-6)

    def test_paxg_fee_is_deducted_from_cash(self):
        result = size_cash_long(
            SizeRequest(
                cash_usd=2000,
                price=4000.0,
                stop_distance=40.0,
                risk_pct=0.01,
                max_notional_pct=0.35,
                schedule=PAXG_FEES,
                limits=PAXGUSD.limits,
            )
        )
        self.assertFalse(result.skipped)
        expected_fee = result.notional_usd * PAXG_FEES.fill_rate
        self.assertAlmostEqual(result.fee_usd, expected_fee)
        self.assertAlmostEqual(
            result.cash_after_entry,
            2000 - result.notional_usd - result.fee_usd,
        )

    def test_below_ordermin_skips(self):
        result = size_cash_long(
            SizeRequest(
                cash_usd=1000,
                price=1.15,
                stop_distance=5.0,  # huge stop → qty below EURUSD ordermin of 4
                risk_pct=0.01,
                max_notional_pct=0.35,
                schedule=FX_FEES,
                limits=EURUSD.limits,
            )
        )
        self.assertTrue(result.skipped)
        self.assertIn("below_ordermin", result.reason)

    def test_no_cash_skips(self):
        result = size_cash_long(
            SizeRequest(
                cash_usd=0,
                price=1.15,
                stop_distance=0.004,
                risk_pct=0.01,
                max_notional_pct=0.35,
                schedule=FX_FEES,
                limits=EURUSD.limits,
            )
        )
        self.assertTrue(result.skipped)
        self.assertEqual(result.reason, "no_cash")

    def test_invalid_stop_skips(self):
        result = size_cash_long(
            SizeRequest(
                cash_usd=1000,
                price=1.15,
                stop_distance=0.0,
                risk_pct=0.01,
                max_notional_pct=0.35,
                schedule=FX_FEES,
                limits=EURUSD.limits,
            )
        )
        self.assertTrue(result.skipped)
        self.assertEqual(result.reason, "invalid_stop")


if __name__ == "__main__":
    unittest.main()
