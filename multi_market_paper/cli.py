"""CLI: scan | paper-plan | backtest. Public data only. No live orders."""

from __future__ import annotations

import argparse
import json
import sys

from multi_market_paper import CRYPTO_LANE_NAME, CRYPTO_LANE_STATUS, LANE_NAME, __version__
from multi_market_paper.backtest import run_backtest
from multi_market_paper.paper import Book, paper_plan
from multi_market_paper.public_client import PublicClient
from multi_market_paper.scan import scan_market


def _print(payload: dict, as_json: bool) -> None:
    if as_json:
        json.dump(payload, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
        return
    mode = payload.get("mode", "")
    print(f"lane={payload.get('lane')} mode={mode} live_orders={payload.get('live_orders', False)}")
    if mode == "scan":
        sess = payload["sessions"]
        print(
            "sessions: london={london} ny={new_york} overlap={overlap} "
            "fx_entry={fx_entry_window}".format(**sess)
        )
        print(f"next London open: {sess['next_london_open_utc']}")
        print("\nFX")
        for row in payload["fx"]:
            print(
                f"  {row['display']:<10} last={row['last']:.5f} "
                f"spread={row['spread_pct']:.4%} vol={row['volume']:.0f} "
                f"rt_fee={row['round_trip']:.2%}"
            )
        g = payload["gold"]
        print("\nGOLD PROXY")
        print(
            f"  {g['display']:<10} last={g['last']:.2f} "
            f"spread={g['spread_pct']:.4%} vol={g['volume']:.2f} "
            f"rt_fee={g['round_trip']:.2%}"
        )
        print("\nXSTOCKS (research catalog only — not traded in this lane)")
        for row in payload["xstocks_research"]:
            last = row.get("last")
            last_s = f"{last:.2f}" if isinstance(last, (int, float)) else row.get("error", "n/a")
            print(f"  {row['display']:<12} last={last_s} tradable_here=no")
        print(f"\ngeo: {payload['xstocks_meta']['geo']}")
        covering = payload.get("active_macro_events") or []
        if covering:
            shown = ", ".join(f"{e['name']} {e['day']}" for e in covering)
            print(f"active macro: {shown}")
        nxt = payload.get("next_macro_event")
        if nxt:
            print(f"next macro: {nxt['name']} {nxt['day']}")
        return
    if mode == "paper-plan":
        print(
            f"book=${payload['book_usd']:.0f} risk={payload['risk_pct']:.2%} "
            f"max_notional={payload['max_notional_pct']:.0%}"
        )
        for plan in payload["plans"]:
            size = plan.get("size") or {}
            print(
                f"  [{plan['action']}] {plan['instrument']:<8} {plan['reason']}"
            )
            if plan["action"] == "PLAN":
                print(
                    f"           BUY {size.get('qty', 0):.6f} @ {plan['entry']} "
                    f"stop={plan['stop']} target={plan['target']} "
                    f"notional=${size.get('notional_usd', 0):.2f} "
                    f"fee=${size.get('fee_usd', 0):.2f}"
                )
        return
    if mode == "backtest":
        print(f"days={payload['days']} book=${payload['book_usd']:.0f}")
        for rep in payload["reports"]:
            print(
                f"  {rep['strategy']:<24} {rep['instrument']:<8} "
                f"taken={rep.get('taken', 0)} skipped={rep.get('skipped', 0)} "
                f"pnl=${rep.get('pnl_usd', 0):.2f}"
            )
            reasons: dict[str, int] = {}
            shown = 0
            for trade in rep.get("trades", []):
                key = trade.get("reason", "")
                # collapse fee skip details
                if isinstance(key, str) and key.startswith("fee_skip"):
                    key = "fee_skip"
                reasons[key] = reasons.get(key, 0) + 1
                if trade.get("action") == "PLAN" and shown < 12:
                    print(
                        f"    {trade.get('day')} PLAN {trade.get('reason')} "
                        f"exit={trade.get('exit')} pnl=${trade.get('pnl_usd', 0):.2f}"
                    )
                    shown += 1
            if reasons:
                summary = ", ".join(f"{k}={v}" for k, v in sorted(reasons.items()))
                print(f"    skip/plan mix: {summary}")
        return
    json.dump(payload, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


def _shared_flags() -> argparse.ArgumentParser:
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--json", action="store_true", help="machine-readable output")
    shared.add_argument("--book", type=float, default=2500.0, help="USD cash book (default 2500)")
    shared.add_argument("--risk-pct", type=float, default=0.01, help="fraction of cash at risk")
    shared.add_argument(
        "--max-notional-pct",
        type=float,
        default=0.35,
        help="max fraction of cash in one position",
    )
    shared.add_argument(
        "--strategy",
        choices=("all", "fx", "paxg"),
        default="all",
        help="which research strategy to run",
    )
    return shared


def build_parser() -> argparse.ArgumentParser:
    shared = _shared_flags()
    p = argparse.ArgumentParser(
        prog="multi-market-paper",
        description=(
            "Parallel research lane for Kraken FX / PAXG / xStocks public data. "
            "Cash only. No live orders. Does not modify the locked crypto 15m playbook."
        ),
        parents=[shared],
    )
    p.add_argument("--version", action="version", version=f"{LANE_NAME} {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan", help="public tickers + session + xStocks catalog", parents=[shared])
    sub.add_parser("paper-plan", help="size hypothetical cash entries; never orders", parents=[shared])
    bt = sub.add_parser("backtest", help="replay public OHLC", parents=[shared])
    bt.add_argument("--days", type=int, required=True, help="lookback days (Kraken OHLC max ~720 bars)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.book < 1000 or args.book > 5000:
        print(
            "warning: this lane is sized for $1k–$5k cash books; "
            f"got ${args.book:.0f}",
            file=sys.stderr,
        )
    client = PublicClient()
    book = Book(
        cash_usd=args.book,
        risk_pct=args.risk_pct,
        max_notional_pct=args.max_notional_pct,
    )
    banner = (
        f"# {LANE_NAME} v{__version__} | crypto lane {CRYPTO_LANE_NAME}={CRYPTO_LANE_STATUS} | "
        "cash-only paper research | no secrets | no live orders"
    )
    if not args.json:
        print(banner)
    if args.cmd == "scan":
        payload = scan_market(client)
    elif args.cmd == "paper-plan":
        payload = paper_plan(client, book, strategy=args.strategy)
    elif args.cmd == "backtest":
        payload = run_backtest(client, book, days=args.days, strategy=args.strategy)
    else:
        raise SystemExit(2)
    _print(payload, args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
