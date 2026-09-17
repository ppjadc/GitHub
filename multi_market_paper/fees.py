"""Starter-tier Kraken Pro fee assumptions for cash (non-levered) research.

Sources (public fee schedule, conservative $0-volume tier):
- FX / cash pairs (EUR/USD, GBP/USD, USD/JPY): 0.20% maker and taker.
- PAXG/USD is a spot crypto pair: Tier 1 taker 0.80%, maker 0.40%.
- xStocks are documented only; this module does not size live xStock trades.

Paper fills assume taker execution. Live maker fills would be cheaper; this
lane therefore overstates cost on purpose so weak setups get skipped.
"""

from __future__ import annotations

from dataclasses import dataclass

# Kraken Pro starter-tier rates (fraction of notional).
FX_TAKER_RATE = 0.0020
FX_MAKER_RATE = 0.0020
PAXG_TAKER_RATE = 0.0080
PAXG_MAKER_RATE = 0.0040

# Skip a setup unless expected move covers round-trip fees by this multiple.
DEFAULT_FX_EDGE_MULTIPLE = 1.25
DEFAULT_PAXG_EDGE_MULTIPLE = 1.50


@dataclass(frozen=True)
class FeeSchedule:
    name: str
    taker_rate: float
    maker_rate: float
    assume_taker: bool = True

    @property
    def fill_rate(self) -> float:
        return self.taker_rate if self.assume_taker else self.maker_rate

    @property
    def round_trip_rate(self) -> float:
        return 2.0 * self.fill_rate


FX_FEES = FeeSchedule("fx_cash", FX_TAKER_RATE, FX_MAKER_RATE)
PAXG_FEES = FeeSchedule("paxg_spot", PAXG_TAKER_RATE, PAXG_MAKER_RATE)


def fee_usd(notional_usd: float, rate: float) -> float:
    if notional_usd < 0:
        raise ValueError("notional_usd must be >= 0")
    if rate < 0:
        raise ValueError("rate must be >= 0")
    return notional_usd * rate


def round_trip_fee_usd(notional_usd: float, schedule: FeeSchedule) -> float:
    return fee_usd(notional_usd, schedule.round_trip_rate)


def required_move_pct(schedule: FeeSchedule, edge_multiple: float) -> float:
    if edge_multiple <= 0:
        raise ValueError("edge_multiple must be > 0")
    return schedule.round_trip_rate * edge_multiple


def should_skip_for_fees(
    expected_move_pct: float,
    schedule: FeeSchedule,
    edge_multiple: float,
) -> tuple[bool, str]:
    """Return (skip, reason) when the expected move cannot cover fees."""
    if expected_move_pct < 0:
        raise ValueError("expected_move_pct must be >= 0")
    need = required_move_pct(schedule, edge_multiple)
    if expected_move_pct + 1e-12 < need:
        return True, (
            f"fee_skip expected_move={expected_move_pct:.4%} "
            f"< required={need:.4%} "
            f"(round_trip={schedule.round_trip_rate:.4%} x {edge_multiple:g})"
        )
    return False, (
        f"fee_ok expected_move={expected_move_pct:.4%} "
        f">= required={need:.4%}"
    )
