"""CLI: scan | backtest | paper-plan. Public REST only. Live trading is out of scope."""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Sequence

from kraken_paper import __version__
from kraken_paper.backtest import result_as_dict, run_backtest
from kraken_paper.constants import FEE_RT, UNIVERSE
from kraken_paper.formatters import format_backtest, format_scan, format_size_plan
from kraken_paper.paper_plan import NoAPlusError, plans_from_setup
from kraken_paper.public_rest import PublicRestError, fetch_asset_pairs, fetch_ohlc_range
from kraken_paper.scan import scan_pairs


def _pairs_arg(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return UNIVERSE
    items = tuple(p.strip().upper().replace("XBT", "BTC") for p in raw.split(",") if p.strip())
    normalized = []
    for p in items:
        if "/" not in p:
            p = f"{p}/USD"
        if p not in UNIVERSE:
            raise SystemExit(f"Pair {p} is outside the locked universe {UNIVERSE}")
        normalized.append(p)
    return tuple(normalized)


def cmd_scan(args: argparse.Namespace) -> int:
    setups, tickers = scan_pairs(_pairs_arg(args.pair))
    if args.json:
        print(json.dumps({"setups": [s.as_dict() for s in setups]}, indent=2, default=str))
    else:
        print(format_scan(setups, tickers))
    return 0


def cmd_paper_plan(args: argparse.Namespace) -> int:
    pairs = _pairs_arg(args.pair)
    setups, tickers = scan_pairs(pairs)
    meta = fetch_asset_pairs(pairs)
    tradable = [s for s in setups if s.tradable]
    if args.json:
        payload = []
        for s in tradable:
            live, paper = plans_from_setup(s, meta.get(s.pair))
            payload.append({"setup": s.as_dict(), "live": live.as_dict(), "paper": paper.as_dict()})
        print(json.dumps({"plans": payload, "skipped": [s.as_dict() for s in setups if not s.tradable]}, indent=2, default=str))
        return 0 if tradable else 2
    if not tradable:
        print("No A+ clip right now — do not send a paper (or live) order.")
        print()
        print(format_scan(setups, tickers))
        return 2
    for s in tradable:
        live, paper = plans_from_setup(s, meta.get(s.pair))
        print(format_size_plan(live, paper, s))
        print()
    if len(tradable) > 1:
        print(
            "More than one A+ printed. Locked rule: one open risk unit. "
            "Take the single best (highest net R) and skip the rest."
        )
    return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    pairs = _pairs_arg(args.pair)
    meta = fetch_asset_pairs(pairs)
    candles = {}
    for i, pair in enumerate(pairs):
        if i:
            time.sleep(0.35)
        candles[pair] = fetch_ohlc_range(pair, days=args.days)
        if len(candles[pair]) < 100:
            print(f"warning: {pair} only returned {len(candles[pair])} committed 15m bars", file=sys.stderr)
    result = run_backtest(
        candles,
        book=args.book,
        days=args.days,
        fee_rt=FEE_RT,
        pair_meta=meta,
    )
    if args.json:
        print(json.dumps(result_as_dict(result), indent=2, default=str))
    else:
        print(format_backtest(result))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kraken-paper",
        description=(
            "Jose's Kraken go-live toolkit: 15m momentum-breakout scan, backtest, and paper plan. "
            "Uses Kraken PUBLIC REST only. No API secrets. Live orders are out of scope."
        ),
    )
    p.add_argument("--version", action="version", version=f"kraken-paper {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument(
            "--pair",
            default=None,
            help="Comma-separated subset of BTC/USD,ETH/USD,SOL/USD (default: all three)",
        )
        sp.add_argument("--json", action="store_true", help="Machine-readable JSON instead of prose")

    sc = sub.add_parser("scan", help="Grade the latest committed 15m bar on each pair")
    add_common(sc)
    sc.set_defaults(func=cmd_scan)

    bt = sub.add_parser("backtest", help="Replay locked A+ rules over the last N days of 15m OHLC")
    add_common(bt)
    bt.add_argument("--days", type=int, default=7, help="Lookback in days (default 7; public OHLC paginates)")
    bt.add_argument(
        "--book",
        choices=("live", "paper"),
        default="live",
        help="live = $1,000 / $10–$15 risk; paper = $10,000 / $100–$150 (10×)",
    )
    bt.set_defaults(func=cmd_backtest)

    pp = sub.add_parser("paper-plan", help="Exact entry/stop/targets/size if an A+ is live; else explain the skip")
    add_common(pp)
    pp.set_defaults(func=cmd_paper_plan)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except PublicRestError as exc:
        print(f"Kraken public REST error: {exc}", file=sys.stderr)
        return 1
    except NoAPlusError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
