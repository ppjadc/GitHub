"""Kraken public REST client. No API keys, no private endpoints, no orders."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

KRAKEN_PUBLIC = "https://api.kraken.com/0/public"
USER_AGENT = "multi-market-paper/0.1 (research; public-data-only)"
UTC = timezone.utc


class PublicAPIError(RuntimeError):
    pass


@dataclass(frozen=True)
class Candle:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    committed: bool


@dataclass(frozen=True)
class Ticker:
    pair: str
    bid: float
    ask: float
    last: float
    volume: float
    high: float
    low: float
    open: float

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def spread_pct(self) -> float:
        if self.mid <= 0:
            return 0.0
        return (self.ask - self.bid) / self.mid


class PublicClient:
    def __init__(self, base: str = KRAKEN_PUBLIC, timeout: float = 20.0, pause_s: float = 0.4):
        self.base = base.rstrip("/")
        self.timeout = timeout
        self.pause_s = pause_s
        self._last_call = 0.0

    def _sleep(self) -> None:
        gap = time.monotonic() - self._last_call
        if gap < self.pause_s:
            time.sleep(self.pause_s - gap)

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._sleep()
        query = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None})
        url = f"{self.base}/{endpoint.lstrip('/')}"
        if query:
            url = f"{url}?{query}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise PublicAPIError(f"network error calling {url}: {exc}") from exc
        finally:
            self._last_call = time.monotonic()
        errors = payload.get("error") or []
        if errors:
            raise PublicAPIError(f"kraken public error {errors} for {url}")
        result = payload.get("result")
        if result is None:
            raise PublicAPIError(f"missing result for {url}")
        return result

    def ticker(self, pair: str, asset_class: str | None = None) -> Ticker:
        result = self.get("Ticker", {"pair": pair, "asset_class": asset_class})
        if not result:
            raise PublicAPIError(f"empty ticker for {pair}")
        key, raw = next(iter(result.items()))
        return Ticker(
            pair=key,
            bid=float(raw["b"][0]),
            ask=float(raw["a"][0]),
            last=float(raw["c"][0]),
            volume=float(raw["v"][1]),
            high=float(raw["h"][1]),
            low=float(raw["l"][1]),
            open=float(raw["o"]),
        )

    def ohlc(
        self,
        pair: str,
        interval: int,
        asset_class: str | None = None,
        since: int | None = None,
        drop_uncommitted: bool = True,
    ) -> list[Candle]:
        result = self.get(
            "OHLC",
            {
                "pair": pair,
                "interval": interval,
                "asset_class": asset_class,
                "since": since,
            },
        )
        series_key = next(k for k in result.keys() if k != "last")
        rows = result[series_key]
        candles: list[Candle] = []
        for i, row in enumerate(rows):
            committed = i < len(rows) - 1
            candles.append(
                Candle(
                    time=datetime.fromtimestamp(int(row[0]), tz=UTC),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[6]),
                    committed=committed,
                )
            )
        if drop_uncommitted and candles:
            candles = [c for c in candles if c.committed]
        return candles

    def asset_pairs(self, aclass_base: str | None = None) -> dict[str, Any]:
        params = {"aclass_base": aclass_base} if aclass_base else None
        return self.get("AssetPairs", params)
