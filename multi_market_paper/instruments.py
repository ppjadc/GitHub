"""Tradable research universe via Kraken public data.

Cash-only. No leverage flags are used even when Kraken lists them.
xStocks are catalogued for research and never sized or paper-traded here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from multi_market_paper.fees import FX_FEES, PAXG_FEES, FeeSchedule
from multi_market_paper.sizing import InstrumentLimits


@dataclass(frozen=True)
class Instrument:
    symbol: str
    display: str
    kind: str  # fx | gold | xstock
    pair: str
    asset_class: str | None
    quote: str
    schedule: FeeSchedule
    limits: InstrumentLimits
    interval_scan: int
    interval_backtest: int
    tradable_in_this_lane: bool
    notes: str
    tags: tuple[str, ...] = field(default_factory=tuple)


EURUSD = Instrument(
    symbol="EURUSD",
    display="EUR/USD",
    kind="fx",
    pair="EURUSD",
    asset_class=None,
    quote="USD",
    schedule=FX_FEES,
    limits=InstrumentLimits(lot_decimals=8, order_min=4.0, cost_min=0.5),
    interval_scan=60,
    interval_backtest=60,
    tradable_in_this_lane=True,
    notes="Primary FX session-breakout pair. Cash long only.",
    tags=("london", "ny", "g10"),
)

GBPUSD = Instrument(
    symbol="GBPUSD",
    display="GBP/USD",
    kind="fx",
    pair="GBPUSD",
    asset_class=None,
    quote="USD",
    schedule=FX_FEES,
    limits=InstrumentLimits(lot_decimals=8, order_min=4.0, cost_min=0.5),
    interval_scan=60,
    interval_backtest=60,
    tradable_in_this_lane=True,
    notes="Secondary FX pair; often wider Asian range than EUR/USD.",
    tags=("london", "ny", "g10"),
)

PAXGUSD = Instrument(
    symbol="PAXGUSD",
    display="PAXG/USD",
    kind="gold",
    pair="PAXGUSD",
    asset_class=None,
    quote="USD",
    schedule=PAXG_FEES,
    limits=InstrumentLimits(lot_decimals=8, order_min=0.001, cost_min=0.5),
    interval_scan=240,
    interval_backtest=240,
    tradable_in_this_lane=True,
    notes="Gold proxy (1 PAXG ≈ 1 troy oz). Spot-crypto fees apply, not FX fees.",
    tags=("macro", "gold", "swing"),
)

# Documented only. Public ticker/OHLC exist, but geo + product rules vary and
# this lane does not paper-trade them.
XSTOCK_RESEARCH = (
    Instrument(
        symbol="SPYxUSD",
        display="SPYx/USD",
        kind="xstock",
        pair="SPYxUSD",
        asset_class="tokenized_asset",
        quote="USD",
        schedule=PAXG_FEES,
        limits=InstrumentLimits(lot_decimals=8, order_min=0.0, cost_min=0.5),
        interval_scan=60,
        interval_backtest=60,
        tradable_in_this_lane=False,
        notes="Tokenized S&P 500 ETF. Research catalog only.",
        tags=("etf", "xstock"),
    ),
    Instrument(
        symbol="QQQxUSD",
        display="QQQx/USD",
        kind="xstock",
        pair="QQQxUSD",
        asset_class="tokenized_asset",
        quote="USD",
        schedule=PAXG_FEES,
        limits=InstrumentLimits(lot_decimals=8, order_min=0.0, cost_min=0.5),
        interval_scan=60,
        interval_backtest=60,
        tradable_in_this_lane=False,
        notes="Tokenized Nasdaq-100 ETF. Research catalog only.",
        tags=("etf", "xstock"),
    ),
    Instrument(
        symbol="GLDxUSD",
        display="GLDx/USD",
        kind="xstock",
        pair="GLDxUSD",
        asset_class="tokenized_asset",
        quote="USD",
        schedule=PAXG_FEES,
        limits=InstrumentLimits(lot_decimals=8, order_min=0.0, cost_min=0.5),
        interval_scan=60,
        interval_backtest=60,
        tradable_in_this_lane=False,
        notes="Tokenized gold ETF. Prefer PAXG/USD for gold research in this lane.",
        tags=("etf", "gold", "xstock"),
    ),
    Instrument(
        symbol="AAPLxUSD",
        display="AAPLx/USD",
        kind="xstock",
        pair="AAPLxUSD",
        asset_class="tokenized_asset",
        quote="USD",
        schedule=PAXG_FEES,
        limits=InstrumentLimits(lot_decimals=8, order_min=0.0, cost_min=0.5),
        interval_scan=60,
        interval_backtest=60,
        tradable_in_this_lane=False,
        notes="Tokenized single name. Research catalog only.",
        tags=("equity", "xstock"),
    ),
)

TRADE_UNIVERSE = (EURUSD, GBPUSD, PAXGUSD)
FX_UNIVERSE = (EURUSD, GBPUSD)
ALL_KNOWN = TRADE_UNIVERSE + XSTOCK_RESEARCH

XSTOCKS_PUBLIC_ENDPOINT = (
    "https://api.kraken.com/0/public/AssetPairs?aclass_base=tokenized_asset"
)
XSTOCKS_TICKER_ENDPOINT = (
    "https://api.kraken.com/0/public/Ticker?asset_class=tokenized_asset"
)
XSTOCKS_SUPPORT = "https://support.kraken.com/articles/xstocks-availability"

XSTOCKS_GEO_NOTES = (
    "xStocks are not available in the United States, Australia, Canada, the UK, "
    "or other prohibited regions. They are not registered US securities. "
    "EEA access may be convert-only (no Kraken Pro / API order book). "
    "Always re-check Kraken's availability article before treating a ticker as tradable."
)


def get_instrument(symbol: str) -> Instrument:
    key = symbol.replace("/", "").upper()
    for inst in ALL_KNOWN:
        if inst.symbol.upper() == key or inst.display.replace("/", "").upper() == key:
            return inst
    raise KeyError(f"unknown instrument: {symbol}")
