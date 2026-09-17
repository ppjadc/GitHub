from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(frozen=True)
class Candle:
    time: int
    open: float
    high: float
    low: float
    close: float
    vwap: float = 0.0
    volume: float = 0.0
    trades: int = 0
    pair: str = ""


@dataclass(frozen=True)
class PairInfo:
    display: str
    kraken: str
    result_key: str
    pair_decimals: int = 1
    lot_decimals: int = 8
    ordermin: float = 0.0
    costmin: float = 0.5


@dataclass
class Ticker:
    pair: str
    last: float
    bid: float
    ask: float
    high_24h: float
    low_24h: float
    open_today: float
    high_today: float
    low_today: float


@dataclass
class SizePlan:
    book: str
    equity: float
    entry: float
    stop: float
    t1: float
    t2: float
    stop_pct: float
    qty: float
    notional: float
    price_risk: float
    fee_rt_usd: float
    total_risk: float
    risk_min: float
    risk_max: float
    within_risk_band: bool
    cash_capped: bool
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Setup:
    pair: str
    grade: str
    tradable: bool
    reasons: list[str]
    trigger: float | None = None
    entry: float | None = None
    stop: float | None = None
    t1: float | None = None
    t2: float | None = None
    stop_pct: float | None = None
    compression_bars: int | None = None
    atr_pct: float | None = None
    atr_8h_pct: float | None = None
    chase_pct: float | None = None
    gross_rr: float | None = None
    net_rr: float | None = None
    bar_time: int | None = None
    last_price: float | None = None
    dist_to_24h_high_pct: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Fill:
    time: int
    price: float
    qty: float
    side: str
    reason: str
    fee: float


@dataclass
class Trade:
    pair: str
    entry_time: int
    exit_time: int
    entry: float
    stop: float
    t1: float
    t2: float
    trigger: float
    qty: float
    notional: float
    exit_reason: str
    gross_pnl: float
    fees: float
    net_pnl: float
    r_multiple: float
    clips_date: str
    fills: list[Fill] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d
