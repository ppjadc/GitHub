import unittest
from datetime import datetime, timezone

from multi_market_paper.cli import build_parser, main
from multi_market_paper.paper import Book, paper_plan
from multi_market_paper.public_client import Candle


class FakeClient:
    def ticker(self, pair, asset_class=None):
        raise AssertionError("scan not used in this test")

    def ohlc(self, pair, interval, asset_class=None, since=None, drop_uncommitted=True):
        ts = datetime(2026, 9, 17, 0, tzinfo=timezone.utc)
        # Enough empty-ish candles that strategies skip without network.
        return [
            Candle(ts, 1.15, 1.15, 1.15, 1.15, 0.0, True),
        ]


class CliTests(unittest.TestCase):
    def test_subcommands_exist(self):
        p = build_parser()
        scan = p.parse_args(["scan"])
        self.assertEqual(scan.cmd, "scan")
        plan = p.parse_args(["paper-plan", "--strategy", "fx"])
        self.assertEqual(plan.cmd, "paper-plan")
        bt = p.parse_args(["backtest", "--days", "14"])
        self.assertEqual(bt.cmd, "backtest")
        self.assertEqual(bt.days, 14)

    def test_paper_plan_never_flags_live_orders(self):
        payload = paper_plan(FakeClient(), Book(2500), as_of=datetime(2026, 9, 17, 12, tzinfo=timezone.utc), strategy="fx")
        self.assertFalse(payload["live_orders"])
        self.assertTrue(payload["cash_only"])
        self.assertFalse(payload["leverage"])
        self.assertNotIn("api_key", str(payload).lower())
        self.assertNotIn("secret", str(payload).lower())

    def test_main_rejects_unknown_command(self):
        with self.assertRaises(SystemExit):
            main(["not-a-command"])


if __name__ == "__main__":
    unittest.main()
