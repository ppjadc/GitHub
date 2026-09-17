"""Paper-plan helpers. Never places orders. Never reads secrets."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from multi_market_paper.instruments import FX_UNIVERSE, PAXGUSD
from multi_market_paper.public_client import PublicClient
from multi_market_paper.strategies.fx_session_breakout import FxSignal, evaluate_fx_breakout
from multi_market_paper.strategies.paxg_macro_swing import PaxgSignal, evaluate_paxg_swing

UTC = timezone.utc


@dataclass(frozen=True)
class Book:
    cash_usd: float
    risk_pct: float = 0.01
    max_notional_pct: float = 0.35


def _signal_to_dict(sig: FxSignal | PaxgSignal) -> dict:
    payload = asdict(sig)
    payload["ts"] = sig.ts.isoformat()
    if sig.size is not None:
        payload["size"] = asdict(sig.size)
    return payload


def plan_fx(client: PublicClient, book: Book, as_of: datetime | None = None) -> list[dict]:
    as_of = as_of or datetime.now(tz=UTC)
    rows = []
    for inst in FX_UNIVERSE:
        candles = client.ohlc(inst.pair, inst.interval_scan, inst.asset_class)
        sig = evaluate_fx_breakout(
            inst, candles, as_of, book.cash_usd, book.risk_pct, book.max_notional_pct
        )
        rows.append(_signal_to_dict(sig))
    return rows


def plan_paxg(client: PublicClient, book: Book, as_of: datetime | None = None) -> list[dict]:
    as_of = as_of or datetime.now(tz=UTC)
    candles = client.ohlc(PAXGUSD.pair, PAXGUSD.interval_scan, PAXGUSD.asset_class)
    sig = evaluate_paxg_swing(
        PAXGUSD, candles, as_of, book.cash_usd, book.risk_pct, book.max_notional_pct
    )
    return [_signal_to_dict(sig)]


def paper_plan(
    client: PublicClient,
    book: Book,
    as_of: datetime | None = None,
    strategy: str = "all",
) -> dict:
    as_of = as_of or datetime.now(tz=UTC)
    plans: list[dict] = []
    if strategy in {"all", "fx"}:
        plans.extend(plan_fx(client, book, as_of))
    if strategy in {"all", "paxg"}:
        plans.extend(plan_paxg(client, book, as_of))
    live_orders = [p for p in plans if p.get("live_order")]
    if live_orders:
        raise RuntimeError("refusing to emit live orders from paper-plan")
    return {
        "lane": "multi_market_paper",
        "mode": "paper-plan",
        "live_orders": False,
        "leverage": False,
        "cash_only": True,
        "as_of": as_of.isoformat(),
        "book_usd": book.cash_usd,
        "risk_pct": book.risk_pct,
        "max_notional_pct": book.max_notional_pct,
        "plans": plans,
    }
