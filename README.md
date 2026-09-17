# Two paper-research lanes

This repo is split into two **independent** lanes. Do not merge their rules.

| | Crypto day-trade lane | Multi-market research lane |
| --- | --- | --- |
| Folder | `kraken_paper/` (locked playbook; not present on this clone of `master`) | `multi_market_paper/` (this package) |
| Status | **LOCKED** for live ~Sep 20, 2026 | Research / paper only |
| Book | ~$1,000 | $1,000–$5,000 cash |
| Markets | BTC / ETH / SOL | EUR/USD, GBP/USD, PAXG/USD; xStocks documented |
| Timeframe | 15-minute momentum breakout | Session (hours) and swing (1–2 days) |
| Leverage | Whatever that playbook already locked in — **do not change it here** | **None.** Cash longs only |
| Orders | Live path is owned by that playbook | **No live orders. No API secrets.** |
| When to use | Intraday crypto only, around the Sep 20 go-live | When you want FX/gold research **without** touching the crypto book |

## When to use which lane

**Use the crypto 15m lane** when the question is “should the locked BTC/ETH/SOL breakout fire on this 15-minute bar?” That book is small, fast, and already decided. Do not loosen stops, add pairs, or port those rules into FX/gold.

**Use this multi-market lane** when the question is “is there a *slower* cash setup in G10 FX or gold that still pays after Kraken fees?” Typical answers:

- London/NY FX breakout on EUR/USD or GBP/USD, sized off a $1k–$5k USD cash balance.
- PAXG swing around FOMC / CPI / NFP, skipped unless the lookback range clears starter-tier crypto fees.
- Catalog tokenized stocks/ETFs (xStocks) from public endpoints — **not traded here**.

If a setup needs shorts, margin, or sub-hour scalps, this lane refuses it.

## Constraints (this lane)

- Cash only; `qty * price + fee <= cash`.
- No leverage, no margin, no stop-hunting scalps.
- Public Kraken REST only (`Ticker`, `OHLC`, `AssetPairs`). No private endpoints.
- Paper-plan emits a *hypothetical* size. It never calls AddOrder / paper buy.
- xStocks: listed for research. Geo-blocked in the US, UK, CA, AU, and elsewhere. EEA is often convert-only.

## Strategies

### (a) FX London/NY session breakout

1. Asian range = 00:00–07:00 UTC on 60-minute candles.
2. **Fee skip** if `range% < 0.20% × 2 × 1.25` (starter FX is 0.20% each way).
3. 07:00–16:00 UTC: cash **long** if a committed candle closes above Asian high + 10% of range.
4. Stop = Asian low. Target = 1R. Time stop = 16:00 UTC (no NY-afternoon hold).
5. Downside breaks → `cash_only_no_short`.

### (b) PAXG swing/breakout around macro events

PAXG is a gold proxy (1 token ≈ 1 troy ounce) but it is a **spot crypto** pair, so starter taker is 0.80% (1.60% round trip) — not the 0.20% FX schedule.

1. Only inside a documented FOMC / CPI / NFP *day* window (not the print minute).
2. 10-bar 4h lookback high/low.
3. **Fee skip** unless that range ≥ 1.60% × 1.50.
4. Long a close through the high. Stop = lookback low. Hold up to the end of the window.

Remaining 2026 dates baked into `macro_calendar.py`: FOMC 16 Sep / 28 Oct / 9 Dec; CPI 14 Oct / 10 Nov / 10 Dec; NFP 2 Oct / 6 Nov / 4 Dec.

## CLI

No install required (stdlib only):

```bash
python3 -m multi_market_paper scan
python3 -m multi_market_paper paper-plan --book 2500
python3 -m multi_market_paper backtest --days 14
python3 -m multi_market_paper backtest --days 30 --strategy paxg --json
```

Flags: `--book`, `--risk-pct` (default 1%), `--max-notional-pct` (default 35%), `--strategy {all,fx,paxg}`, `--json`.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Unit tests cover fee skips, cash sizing (no leverage, ordermin, fee debit), and London/NY/weekend session filters. They do not hit the network.

## Public endpoints used

| Data | URL |
| --- | --- |
| FX / PAXG ticker | `https://api.kraken.com/0/public/Ticker?pair=EURUSD,GBPUSD,PAXGUSD` |
| OHLC | `https://api.kraken.com/0/public/OHLC?pair=EURUSD&interval=60` |
| xStocks pairs | `https://api.kraken.com/0/public/AssetPairs?aclass_base=tokenized_asset` |
| xStocks ticker | `https://api.kraken.com/0/public/Ticker?asset_class=tokenized_asset` |

Availability: [xStocks on Kraken](https://support.kraken.com/articles/xstocks-availability). Sample catalog names: `SPYx/USD`, `QQQx/USD`, `GLDx/USD`, `AAPLx/USD`.

## Sample `scan` output

See [`examples/sample_scan.txt`](examples/sample_scan.txt) (captured from a live public-data run). Fees and session flags are the research output; nothing in that file is an order.

## What this package will not do

- Change `kraken_paper/` or the 15m BTC/ETH/SOL playbook.
- Place or validate live Kraken orders.
- Store API keys.
- Trade xStocks.
- Use leverage even when Kraken lists it on PAXG.
