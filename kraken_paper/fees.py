"""Fee math locked to the memo: 0.26% round-trip on notional."""

from __future__ import annotations

from kraken_paper.constants import (
    ATR_FEE_MULT,
    ATR_MIN_PCT,
    FEE_RT,
    MIN_NET_RR,
    PLANNED_GROSS_R,
    T1_R,
    T2_R,
)


def round_trip_fee(notional: float, fee_rt: float = FEE_RT) -> float:
    if notional < 0:
        raise ValueError("notional must be >= 0")
    return notional * fee_rt


def one_way_fee(notional: float, fee_rt: float = FEE_RT) -> float:
    return round_trip_fee(notional, fee_rt) / 2.0


def total_risk_usd(notional: float, stop_pct: float, fee_rt: float = FEE_RT) -> float:
    """Price risk + estimated RT fees on notional (memo definition)."""
    if stop_pct < 0:
        raise ValueError("stop_pct must be >= 0")
    return notional * (stop_pct + fee_rt)


def notional_for_risk(risk_usd: float, stop_pct: float, fee_rt: float = FEE_RT) -> float:
    denom = stop_pct + fee_rt
    if denom <= 0:
        raise ValueError("stop_pct + fee_rt must be > 0")
    return risk_usd / denom


def planned_gross_r(t1_r: float = T1_R, t2_r: float = T2_R, t1_frac: float = 0.5) -> float:
    return t1_frac * t1_r + (1.0 - t1_frac) * t2_r


def blended_net_rr(
    stop_pct: float,
    fee_rt: float = FEE_RT,
    t1_r: float = T1_R,
    t2_r: float = T2_R,
    t1_frac: float = 0.5,
) -> float:
    """Net R:R after RT fees, using 50% scale at T1 and remainder at T2.

    Risk in the denominator is price-stop + RT fees (memo). Reward is
    blended gross target minus RT fees. At a 0.50% stop this sits near
    the 1.3 floor — tighter stops fail the filter on purpose.
    """
    if stop_pct <= 0:
        raise ValueError("stop_pct must be > 0")
    gross_r = planned_gross_r(t1_r, t2_r, t1_frac)
    reward_pct = gross_r * stop_pct - fee_rt
    risk_pct = stop_pct + fee_rt
    return reward_pct / risk_pct


def passes_fee_filter(atr_pct: float, fee_rt: float = FEE_RT, mult: float = ATR_FEE_MULT) -> bool:
    return atr_pct + 1e-15 >= fee_rt * mult


def atr_min_pct(fee_rt: float = FEE_RT, mult: float = ATR_FEE_MULT) -> float:
    return fee_rt * mult


def passes_net_rr(stop_pct: float, fee_rt: float = FEE_RT, min_net: float = MIN_NET_RR) -> bool:
    return blended_net_rr(stop_pct, fee_rt) + 1e-12 >= min_net


def assert_locked_fee_constants() -> None:
    """Guard against accidental loosening of the memo's fee filter."""
    assert abs(FEE_RT - 0.0026) < 1e-12
    assert abs(ATR_MIN_PCT - 0.0039) < 1e-12
    assert abs(PLANNED_GROSS_R - 2.5) < 1e-12
