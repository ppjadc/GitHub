# Kraken go-live paper/backtest toolkit

For **Jose**. Target live date **Sunday Sep 20, 2026**. This folder is the only trading code in the repo.

It talks to **Kraken PUBLIC REST only** (ticker + 15m OHLC + asset-pair ticks). There are **no API keys**, **no private endpoints**, and **no live orders**. If a command prints an entry, that is a plan — it does not send anything to Kraken.

The rules are locked in `kraken_paper/STRATEGY.md` (the Sep 20 go-live memo). The code **skips** when a rule fails. It does not widen stops, chase, add leverage, or take B-setups on a $1,000 book.

## What it does

15-minute **momentum breakout** on **BTC/USD, ETH/USD, SOL/USD**:

1. Trigger = the clear 24h range top (highest high on prior 15m bars).
2. A+ needs a **15m close above** that trigger. Wicks do not count.
3. Prefer **2–8** inside bars of compression before the break.
4. **No chase** if the close is already **>0.4%** through the trigger.
5. Stop is structural (breakout-candle low or last swing low), and must sit **0.50%–1.00%** from entry. Wider than 1% → skip (do not widen).
6. Targets: **T1 = 2R** (take ≥50% off), **T2 = 3R**. Flatten the same New York calendar day. Time stop at 12 bars (3 hours) if T1 never prints. Scratch if price **closes back below the trigger within 2 bars**.
7. Fee filter: skip when 15m ATR < **1.5 × 0.26%** (ATR15 < **~0.39%**).
8. Planned blended R:R after fees (50% at T1, 50% at T2) must still be **≥ ~1.3**.

## Live $1,000 sizing (cash only)

| Knob | Locked live rule |
|------|------------------|
| Equity | $1,000 cash |
| Risk per trade | **$10–$15** = price stop + 0.26% round-trip fees on notional |
| Notional | typically $700–$1,000; **never more than cash** (no leverage / no margin) |
| Max open risk | $15 (one pair, one clip) |
| Clips / day | 1–2 |
| Daily loss stop | −$35 → done for the day |

If a 0.50% stop “wants” ~$1,975 notional to put $15 at risk, the toolkit **caps at $1,000**. That is *less* risk, not a looser stop. The memo’s BTC worked example (entry 77,100 / stop 76,500 / $1,000 notional ≈ **$10.40** total risk, T1 78,300 / T2 78,900) is a unit test.

### Paper translation (`jose-main` $10,000)

Paper is **10× live** on prices that stay the same:

| | Live | Paper |
|--|------|-------|
| Equity | $1,000 | $10,000 |
| Risk / clip | $10–$15 | $100–$150 |
| Typical notional | $700–$1,000 | $7,000–$10,000 |
| Daily loss stop | −$35 | −$350 |

Probe clips should stay in the $100–$150 paper band (maps to live $10–$15). Do not use the looser “$200 paper” figure — that would map to $20 live and break the lock.

## Fees (read this before you trust a backtest)

`jose-main` paper is quoted at **0.26% round-trip**. This toolkit uses that number, because that is what the memo locked.

Kraken’s public starter **taker** fee is **0.26% per fill**. Two market fills would be about **0.52% round-trip** live — worse than paper. Limit / maker (0.16% per side) is closer to the paper assumption. Slippage is **not** modeled. Treat any backtest net as optimistic.

Until the book is closer to **$3k–$5k**, this is an A+-only $1k book. Day-trading $1,000 through 0.26% RT fees is fragile; the memo says so.

## Install and run

Python 3.10+. No third-party runtime deps (stdlib `urllib` only). Pytest is for tests.

```bash
cd /path/to/this/repo
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

From the repo root (or with the venv active):

```bash
python -m kraken_paper scan
python -m kraken_paper backtest --days 7
python -m kraken_paper paper-plan
```

Same commands as `kraken-paper scan` after the editable install.

Useful flags:

```bash
python -m kraken_paper scan --pair BTC/USD
python -m kraken_paper scan --json
python -m kraken_paper backtest --days 14 --book live
python -m kraken_paper backtest --days 7 --book paper
python -m kraken_paper paper-plan --pair ETH/USD,SOL/USD
```

`--book live` sizes a $1,000 / $10–$15 book. `--book paper` sizes jose-main ($10,000 / $100–$150).

## How to read the output

**scan** — one row per pair (last, 24h range, distance to 24h high, ATR15, ATR vs the 0.26% fee, grade). Then the English reasons.

- **A+** = the only grade `paper-plan` will size. A 15m close above the trigger, compression 2–8, stop in band, ATR and net R:R clear.
- **A** = long coil (more than 8 inside bars). Logged, not sent on this book.
- **B** = close above the high but too little compression (or similar preference miss). Not sent.
- **SKIP** = do nothing. Extended into the high, wick-only, chase, dead ATR, stop that would need more than 1%, etc.

If all three pairs are SKIP, that is a *valid* session. The Thu Sep 17 memo printed 0/2 clips for the same reason: tape was pressed into highs with no close through.

**paper-plan** — if an A+ just printed, prints exact **entry, stop, T1, T2, qty, notional, total risk** for live *and* the 10× paper twin. If nothing is A+, it exits 2 and tells you why. Exit 2 means “no clip,” not a crash.

**backtest** — walks committed 15m history, takes A+ only, max 2 clips per ET day, one open risk unit, same-day flatten, fee-inclusive P&L. Net already subtracts 0.26% RT. A small/negative net after fees is a Sunday **no-go**, not a reason to loosen rules.

The three-day paper checklist in the memo still matters more than this replay: ≥3 graded decisions Thu–Sat (skips count), jose-main net **≥ −$200**, no daily-stop breach twice, no sub-1.5R planned trades.

## Tests

```bash
python -m pytest tests
```

Unit tests cover fee math, the $10–$15 cash-only sizer (including the BTC worked example and the 10× paper translation), and breakout detection (close vs wick, 0.4% chase, 1% stop cap, ATR fee filter, A+ compression window). They do not hit the network.

## Out of scope

- Live buys/sells, cancel, withdraw, futures, margin, earn
- Storing Kraken API keys in this repo
- Reviving the old SOL $101.40 long (that plan is dead; SOL needs a **fresh** A+ under these rules)
- Automated Sunday go-live — that is a human decision after Fri/Sat paper probes

## Layout

```
kraken_paper/          Python package (CLI + rules)
kraken_paper/STRATEGY.md   Locked memo
tests/                 Unit tests (offline)
```
