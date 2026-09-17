from __future__ import annotations

import time

from kraken_paper.breakout import evaluate_latest
from kraken_paper.models import Setup, Ticker
from kraken_paper.public_rest import committed_candles, fetch_ohlc, fetch_tickers


def scan_pairs(pairs: tuple[str, ...]) -> tuple[list[Setup], dict[str, Ticker]]:
    tickers = fetch_tickers(pairs)
    setups: list[Setup] = []
    for i, pair in enumerate(pairs):
        if i:
            time.sleep(0.35)
        candles, last_id = fetch_ohlc(pair)
        committed, forming = committed_candles(candles, last_id)
        ticker = tickers[pair]
        last_price = forming.close if forming else ticker.last
        if not committed:
            setups.append(
                Setup(pair=pair, grade="SKIP", tradable=False, reasons=["no committed 15m bars"])
            )
            continue
        st = evaluate_latest(committed, pair, ticker=ticker)
        st.last_price = last_price
        if ticker.high_24h > 0:
            st.dist_to_24h_high_pct = (ticker.high_24h - last_price) / ticker.high_24h
        setups.append(st)
    return setups, tickers
