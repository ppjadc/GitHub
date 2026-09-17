"""Kraken PUBLIC REST client. No API keys. No private endpoints."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from kraken_paper.constants import (
    INTERVAL_MIN,
    KRAKEN_PAIR,
    PUBLIC_REST_BASE,
    UNIVERSE,
    USER_AGENT,
)
from kraken_paper.models import Candle, PairInfo, Ticker


class PublicRestError(RuntimeError):
    pass


def _get(path: str, params: dict[str, Any], timeout: float = 20.0, retries: int = 4) -> dict[str, Any]:
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    url = f"{PUBLIC_REST_BASE}/{path}?{query}" if query else f"{PUBLIC_REST_BASE}/{path}"
    delay = 0.6
    last_err: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_err = exc
            time.sleep(delay)
            delay *= 2
            continue
        errors = payload.get("error") or []
        if errors:
            joined = "; ".join(str(e) for e in errors)
            if any(tok in joined for tok in ("Rate", "Unavailable", "Busy", "timeout")) and attempt + 1 < retries:
                time.sleep(delay)
                delay *= 2
                last_err = PublicRestError(joined)
                continue
            raise PublicRestError(joined)
        result = payload.get("result")
        if not isinstance(result, dict):
            raise PublicRestError("Kraken public REST returned no result object")
        return result
    raise PublicRestError(f"Kraken public REST failed after retries: {last_err}")


def fetch_asset_pairs(pairs: tuple[str, ...] = UNIVERSE) -> dict[str, PairInfo]:
    kraken = ",".join(KRAKEN_PAIR[p] for p in pairs)
    result = _get("AssetPairs", {"pair": kraken})
    out: dict[str, PairInfo] = {}
    for display in pairs:
        want = KRAKEN_PAIR[display]
        match_key = None
        match_val = None
        for key, val in result.items():
            if not isinstance(val, dict):
                continue
            if key == want or val.get("altname") == want or val.get("wsname") in {display, display.replace("BTC", "XBT")}:
                match_key, match_val = key, val
                break
        if match_val is None:
            raise PublicRestError(f"AssetPairs missing {display} ({want})")
        out[display] = PairInfo(
            display=display,
            kraken=want,
            result_key=match_key,
            pair_decimals=int(match_val.get("pair_decimals", 1)),
            lot_decimals=int(match_val.get("lot_decimals", 8)),
            ordermin=float(match_val.get("ordermin") or 0),
            costmin=float(match_val.get("costmin") or 0.5),
        )
    return out


_TICKER_ALIASES = {
    "BTC/USD": ("XXBTZUSD", "XBTUSD"),
    "ETH/USD": ("XETHZUSD", "ETHUSD"),
    "SOL/USD": ("SOLUSD",),
}


def fetch_tickers(pairs: tuple[str, ...] = UNIVERSE) -> dict[str, Ticker]:
    kraken = ",".join(KRAKEN_PAIR[p] for p in pairs)
    result = _get("Ticker", {"pair": kraken})
    out: dict[str, Ticker] = {}
    for display in pairs:
        key = next((k for k in _TICKER_ALIASES[display] if k in result), None)
        if key is None:
            key = next((k for k in result if KRAKEN_PAIR[display] in k), None)
        if key is None:
            raise PublicRestError(f"Ticker missing {display}")
        val = result[key]
        out[display] = Ticker(
            pair=display,
            last=float(val["c"][0]),
            bid=float(val["b"][0]),
            ask=float(val["a"][0]),
            high_24h=float(val["h"][1]),
            low_24h=float(val["l"][1]),
            open_today=float(val["o"]),
            high_today=float(val["h"][0]),
            low_today=float(val["l"][0]),
        )
    missing = [p for p in pairs if p not in out]
    if missing:
        raise PublicRestError(f"Ticker missing pairs: {missing}")
    return out


def _parse_ohlc_result(result: dict[str, Any], pair: str) -> tuple[list[Candle], int]:
    last = int(result.get("last") or 0)
    series_key = next(k for k in result if k != "last")
    rows = result[series_key]
    candles: list[Candle] = []
    for row in rows:
        ts = int(row[0])
        candles.append(
            Candle(
                time=ts,
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                vwap=float(row[5]),
                volume=float(row[6]),
                trades=int(row[7]),
                pair=pair,
            )
        )
    return candles, last


def fetch_ohlc(pair: str, interval: int = INTERVAL_MIN, since: int | None = None) -> tuple[list[Candle], int]:
    kraken = KRAKEN_PAIR[pair]
    result = _get("OHLC", {"pair": kraken, "interval": interval, "since": since})
    return _parse_ohlc_result(result, pair)


def committed_candles(candles: list[Candle], last_id: int) -> tuple[list[Candle], Candle | None]:
    """Split forming (uncommitted) bar from committed history.

    Kraken's `last` is the timestamp of the last committed candle. Any row
    with time > last is still forming and must not count as a close.
    """
    if not candles:
        return [], None
    committed = [c for c in candles if c.time <= last_id]
    forming = None
    rest = [c for c in candles if c.time > last_id]
    if rest:
        forming = rest[-1]
    if not committed and last_id == 0:
        # Defensive: if last is missing, drop the newest row as forming.
        forming = candles[-1]
        committed = candles[:-1]
    return committed, forming


def fetch_ohlc_range(
    pair: str,
    *,
    days: int,
    interval: int = INTERVAL_MIN,
    now: int | None = None,
) -> list[Candle]:
    """Paginate public OHLC to cover the last `days` (plus one extra bar overlap)."""
    if days <= 0:
        raise ValueError("days must be > 0")
    now = int(time.time() if now is None else now)
    start = now - days * 24 * 60 * 60 - interval * 60
    collected: dict[int, Candle] = {}
    last_id = 0
    since: int | None = start
    for _ in range(12):
        chunk, last_id = fetch_ohlc(pair, interval=interval, since=since)
        if not chunk:
            break
        for c in chunk:
            collected[c.time] = c
        newest = chunk[-1].time
        if newest >= now - interval * 60 or len(chunk) < 2:
            break
        next_since = newest
        if since is not None and next_since <= since:
            break
        since = next_since
        time.sleep(0.35)
    committed, _forming = committed_candles(sorted(collected.values(), key=lambda c: c.time), last_id)
    return [c for c in committed if c.time >= start]
