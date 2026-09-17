"""Cash-only position sizing. No leverage, no margin, no shorts of unowned base."""

from __future__ import annotations

from dataclasses import dataclass

from multi_market_paper.fees import FeeSchedule, fee_usd


@dataclass(frozen=True)
class InstrumentLimits:
    lot_decimals: int
    order_min: float
    cost_min: float


@dataclass(frozen=True)
class SizeRequest:
    cash_usd: float
    price: float
    stop_distance: float
    risk_pct: float
    max_notional_pct: float
    schedule: FeeSchedule
    limits: InstrumentLimits


@dataclass(frozen=True)
class SizeResult:
    skipped: bool
    reason: str
    qty: float
    notional_usd: float
    fee_usd: float
    cash_after_entry: float
    risk_usd: float


def _round_qty(qty: float, lot_decimals: int) -> float:
    if lot_decimals < 0:
        raise ValueError("lot_decimals must be >= 0")
    factor = 10 ** lot_decimals
    return int(qty * factor) / factor


def size_cash_long(req: SizeRequest) -> SizeResult:
    """Size a long using USD cash only.

    Constraints, in order:
    1. Cash must cover notional + entry fee (no leverage).
    2. Notional capped at max_notional_pct of cash.
    3. Qty from dollar risk / stop distance, then reduced to fit caps.
    4. Respect Kraken ordermin / costmin.
    """
    if req.cash_usd <= 0:
        return SizeResult(True, "no_cash", 0.0, 0.0, 0.0, req.cash_usd, 0.0)
    if req.price <= 0:
        raise ValueError("price must be > 0")
    if req.stop_distance <= 0:
        return SizeResult(True, "invalid_stop", 0.0, 0.0, 0.0, req.cash_usd, 0.0)
    if not (0 < req.risk_pct <= 1):
        raise ValueError("risk_pct must be in (0, 1]")
    if not (0 < req.max_notional_pct <= 1):
        raise ValueError("max_notional_pct must be in (0, 1]")

    rate = req.schedule.fill_rate
    # Leave room so notional + fee never exceeds cash.
    max_notional = min(
        req.cash_usd * req.max_notional_pct,
        req.cash_usd / (1.0 + rate),
    )
    if max_notional <= 0:
        return SizeResult(True, "cash_cannot_cover_fees", 0.0, 0.0, 0.0, req.cash_usd, 0.0)

    risk_usd = req.cash_usd * req.risk_pct
    qty_from_risk = risk_usd / req.stop_distance
    qty_from_notional = max_notional / req.price
    qty = _round_qty(min(qty_from_risk, qty_from_notional), req.limits.lot_decimals)

    if qty <= 0:
        return SizeResult(True, "qty_rounded_to_zero", 0.0, 0.0, 0.0, req.cash_usd, risk_usd)

    notional = qty * req.price
    entry_fee = fee_usd(notional, rate)
    if notional < req.limits.cost_min:
        return SizeResult(
            True,
            f"below_costmin notional={notional:.4f} min={req.limits.cost_min}",
            0.0,
            0.0,
            0.0,
            req.cash_usd,
            risk_usd,
        )
    if qty < req.limits.order_min:
        return SizeResult(
            True,
            f"below_ordermin qty={qty} min={req.limits.order_min}",
            0.0,
            0.0,
            0.0,
            req.cash_usd,
            risk_usd,
        )
    if notional + entry_fee > req.cash_usd + 1e-9:
        return SizeResult(True, "exceeds_cash", 0.0, 0.0, 0.0, req.cash_usd, risk_usd)

    stop_risk = qty * req.stop_distance
    return SizeResult(
        skipped=False,
        reason="sized",
        qty=qty,
        notional_usd=notional,
        fee_usd=entry_fee,
        cash_after_entry=req.cash_usd - notional - entry_fee,
        risk_usd=stop_risk,
    )
