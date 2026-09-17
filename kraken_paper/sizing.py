"""Cash-only position sizing for the $1,000 live book (paper = 10x)."""

from __future__ import annotations

from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

from kraken_paper.constants import (
    FEE_RT,
    LIVE_EQUITY,
    LIVE_NOTIONAL_TYPICAL_MAX,
    LIVE_NOTIONAL_TYPICAL_MIN,
    LIVE_RISK_MAX,
    LIVE_RISK_MIN,
    LIVE_RISK_TARGET,
    PAPER_EQUITY,
    PAPER_MULT,
    PAPER_RISK_MAX,
    PAPER_RISK_MIN,
    PAPER_RISK_TARGET,
)
from kraken_paper.fees import notional_for_risk, round_trip_fee, total_risk_usd
from kraken_paper.models import SizePlan


def round_price(price: float, pair_decimals: int) -> float:
    q = Decimal("1").scaleb(-pair_decimals)
    return float(Decimal(str(price)).quantize(q, rounding=ROUND_HALF_UP))


def floor_qty(qty: float, lot_decimals: int) -> float:
    q = Decimal("1").scaleb(-lot_decimals)
    return float(Decimal(str(qty)).quantize(q, rounding=ROUND_DOWN))


def stop_pct(entry: float, stop: float) -> float:
    if entry <= 0:
        raise ValueError("entry must be > 0")
    if stop >= entry:
        raise ValueError("long stop must be below entry")
    return (entry - stop) / entry


def targets(entry: float, stop: float, t1_r: float = 2.0, t2_r: float = 3.0) -> tuple[float, float]:
    risk = entry - stop
    return entry + t1_r * risk, entry + t2_r * risk


def book_defaults(book: str) -> dict[str, float]:
    book = book.lower()
    if book == "live":
        return {
            "equity": LIVE_EQUITY,
            "risk_min": LIVE_RISK_MIN,
            "risk_max": LIVE_RISK_MAX,
            "risk_target": LIVE_RISK_TARGET,
        }
    if book == "paper":
        return {
            "equity": PAPER_EQUITY,
            "risk_min": PAPER_RISK_MIN,
            "risk_max": PAPER_RISK_MAX,
            "risk_target": PAPER_RISK_TARGET,
        }
    raise ValueError("book must be 'live' or 'paper'")


def size_long(
    entry: float,
    stop: float,
    *,
    book: str = "live",
    equity: float | None = None,
    risk_target: float | None = None,
    risk_min: float | None = None,
    risk_max: float | None = None,
    fee_rt: float = FEE_RT,
    pair_decimals: int | None = None,
    lot_decimals: int = 8,
    ordermin: float = 0.0,
    t1: float | None = None,
    t2: float | None = None,
) -> SizePlan:
    """Size a cash-only long. Never notionally exceeds equity (no leverage)."""
    defaults = book_defaults(book)
    equity = defaults["equity"] if equity is None else equity
    risk_target = defaults["risk_target"] if risk_target is None else risk_target
    risk_min = defaults["risk_min"] if risk_min is None else risk_min
    risk_max = defaults["risk_max"] if risk_max is None else risk_max
    if equity <= 0:
        raise ValueError("equity must be > 0")
    if risk_max < risk_min:
        raise ValueError("risk_max must be >= risk_min")

    sp = stop_pct(entry, stop)
    t1_px, t2_px = targets(entry, stop)
    if t1 is not None:
        t1_px = t1
    if t2 is not None:
        t2_px = t2

    notes: list[str] = []
    raw = notional_for_risk(risk_target, sp, fee_rt)
    cash_capped = False
    notional = raw
    if notional > equity:
        notional = equity
        cash_capped = True
        notes.append(
            f"Cash-only cap: wanted ${raw:.2f} notional for ${risk_target:.2f} risk; "
            f"capped at equity ${equity:.2f} (no leverage)."
        )

    # Never exceed the $15 (live) / $150 (paper) hard risk cap.
    risk_at = total_risk_usd(notional, sp, fee_rt)
    if risk_at > risk_max + 1e-9:
        notional = notional_for_risk(risk_max, sp, fee_rt)
        if notional > equity:
            notional = equity
            cash_capped = True
        notes.append(f"Risk cap: notional cut so total risk (stop + fees) ≤ ${risk_max:.2f}.")

    qty = floor_qty(notional / entry, lot_decimals)
    if ordermin and qty < ordermin:
        raise ValueError(f"qty {qty} below ordermin {ordermin}")
    notional = qty * entry
    if notional <= 0:
        raise ValueError("sized qty rounded to zero")

    price_risk = notional * sp
    fee_usd = round_trip_fee(notional, fee_rt)
    total_risk = price_risk + fee_usd
    # Tiny float residue can push a cash-capped $15.00 to 15.0000000002
    if total_risk > risk_max + 1e-6:
        # Floor qty one tick more if rounding pushed over the cap.
        step = float(Decimal("1").scaleb(-lot_decimals))
        qty = floor_qty(max(qty - step, 0), lot_decimals)
        notional = qty * entry
        price_risk = notional * sp
        fee_usd = round_trip_fee(notional, fee_rt)
        total_risk = price_risk + fee_usd
        notes.append("Qty stepped down one lot increment to stay inside the risk cap.")

    within = risk_min - 1e-6 <= total_risk <= risk_max + 1e-6
    if total_risk + 1e-6 < risk_min:
        notes.append(
            f"Total risk ${total_risk:.2f} is below the ${risk_min:.2f}–${risk_max:.2f} "
            "band because cash (no leverage) binds. That is smaller risk, not a wider stop."
        )
    if book == "live" and LIVE_NOTIONAL_TYPICAL_MIN <= notional <= LIVE_NOTIONAL_TYPICAL_MAX:
        notes.append(
            f"Live notional ${notional:.2f} sits in the memo's typical ${LIVE_NOTIONAL_TYPICAL_MIN:.0f}"
            f"–${LIVE_NOTIONAL_TYPICAL_MAX:.0f} cash clip."
        )
    elif book == "live" and notional + 1e-6 < LIVE_NOTIONAL_TYPICAL_MIN:
        notes.append(
            f"Live notional ${notional:.2f} is below the typical ${LIVE_NOTIONAL_TYPICAL_MIN:.0f} "
            "clip because the risk cap bound first."
        )

    def px(price: float) -> float:
        return price if pair_decimals is None else round_price(price, pair_decimals)

    return SizePlan(
        book=book,
        equity=equity,
        entry=px(entry),
        stop=px(stop),
        t1=px(t1_px),
        t2=px(t2_px),
        stop_pct=sp,
        qty=qty,
        notional=notional,
        price_risk=price_risk,
        fee_rt_usd=fee_usd,
        total_risk=total_risk,
        risk_min=risk_min,
        risk_max=risk_max,
        within_risk_band=within,
        cash_capped=cash_capped,
        notes=notes,
    )


def translate_live_to_paper(live: SizePlan) -> SizePlan:
    """10× notionals and risk for jose-main ($10k paper). Prices unchanged."""
    paper = size_long(
        live.entry,
        live.stop,
        book="paper",
        t1=live.t1,
        t2=live.t2,
    )
    paper.notes.insert(
        0,
        f"Paper translation: {PAPER_MULT:.0f}× live notional/risk on a "
        f"${PAPER_EQUITY:,.0f} sim book (jose-main).",
    )
    return paper
