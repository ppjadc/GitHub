# Kraken Go-Live Strategy Memo — Sun Sep 20, 2026

**Author:** Grok (executor) for Jose A. Dominguez  
**As-of:** Thu Sep 17, 2026 ~1:05 PM ET  
**Live book:** ~$1,000 USD (read-only balance confirmed)  
**Paper workspace:** `jose-main` — $10,000 sim, fee_rate 0.26% RT, 0 trades to date  
**Constraint:** No live orders. Same-day flatten. Max 1–2 clips/day. No reckless leverage.

---

## 1. Market structure snapshot (15m + ticker)

| Pair | Last | 24h range | 24h struct | Dist to 24h high | 8h ATR15 | ATR / 0.26% fee |
|------|------|-----------|------------|------------------|----------|-----------------|
| BTC/USD (XBTUSD) | 76,818 | 74,957–77,095 | HH+HL (24h); mixed 8h | 0.36% | ~0.32% | ~1.2× |
| ETH/USD | 2,472 | 2,367–2,482 | Uptrend | 0.37% | ~0.45% | ~1.7× |
| SOL/USD | 101.52 | 96.03–101.70 | Uptrend | 0.18% | ~0.52% | ~2.0× |

**Tape read:** All three are pressed into session/24h highs after a midday dip-and-reclaim. Momentum is constructive on the day, but **price is extended** — not a pullback and not a confirmed breakout close.

**SOL note:** Prior SOL long plan remains **INVALIDATED** (broke under $101.40). A mere reclaim to ~101.5 is **not** a re-entry. Fresh long only on a **15m close above $101.70** with expansion, or a clean pullback setup under the new rules below.

---

## 2. Primary strategy (LOCKED): **15m Momentum Breakout**

**Why not mean reversion:** Majors are in a 24h uptrend into highs; fading strength against that tape is lower quality for a fee-heavy $1k book. Breakout + high-R + 1–2 clips/day matches the fee constraint better than scalping fades.

### Exact rules (size for LIVE $1,000; paper = 10× notionals)

**Universe:** BTC/USD, ETH/USD, SOL/USD only. One pair per clip. One open risk unit max.

**Entry (A+ only):**
1. Mark the trigger level = prior swing high or 24h/session high (whichever is the clear range top).
2. Require a **15m candle close above** the trigger (wicks alone do not count).
3. Prefer 2–8 candles of compression / inside-range before the break.
4. Enter on close or next open; limit preferred if spread is tight, else market with acceptance that fees already assume ~0.26% RT.
5. **No chase:** if price is already >0.4% through the trigger without a retest, skip.

**Stop:**
- Structural: below breakout candle low **or** last swing low inside the range — use the closer level that still fits risk.
- Hard cap: stop distance **0.50%–1.00%** from entry. If structure needs >1.00%, **skip** (do not widen).

**Targets:**
- **T1 (mandatory scale):** +2.0× stop distance (gross). At T1, take ≥50% off.
- **T2:** +3.0× stop distance or trail under 15m swing lows; **flatten flat by session end** (no overnight).
- Minimum acceptable planned R:R **gross ≥ 2.0**; after 0.26% RT fees, effective R:R should still be ≥ ~1.3.

**Invalidation / early exit:**
- 15m close back below trigger within 2 candles → scratch (accept fee hit).
- Thesis break: opposing HH/HL failure into LH/LL on 15m while in trade → flatten.
- Time stop: if neither T1 nor stop hit within 12×15m bars (3h) and momentum stalls → flatten.

**Risk ($1,000 live):**

| Knob | Live rule |
|------|-----------|
| Risk per trade | **$10–$15** hard (1.0–1.5% of equity), counted as *price stop + estimated RT fees on notional* |
| Typical notional | **$700–$1,000** (cash only; **no leverage / no margin**) |
| Max open risk | **$15** (never two correlated full-size positions) |
| Daily loss stop | **−$35** (−3.5%) → stop trading for the day |
| Weekly soft stop (validation) | **−$75** across Thu–Sat paper → do not go live Sun |
| Clips / day | **1–2 max** |
| Fee filter | Skip if 15m ATR < **1.5× fee** (ATR15 < ~0.39%) |

**Paper sizing translation (`jose-main` $10k):**
- Live risk $10–$20 → paper risk **$100–$200** (10×).
- Live notional $700–$1,000 → paper notional **$7,000–$10,000**.
- Probe clips (validation): prefer **paper risk ~$100–$150** (maps to live ~$10–$15).

**Worked live example (BTC):**
- Entry 77,100 on break of 77,095; stop 76,500 (−0.78%); notional $1,000 → price risk ≈ $7.80 + fees ≈ $2.60 → **total risk ≈ $10.40** (within band).
- T1 ≈ 78,300 (+~1.56%); T2 ≈ 78,900. Flatten same day.

---

## 3. Fee math — plain verdict

**Day-trading $1,000 at ~0.26% RT is weak but not impossible if extremely selective.**

- RT fee on full $1k notional = **$2.60 / clip** (before slippage).
- At a realistic 0.7–1.0% stop on full book, fees are **~20–30% of the loss budget**.
- Proper $15 risk at 0.8% stop wants ~**$1,875 notional** → **above cash** without leverage → $1k forces near-all-in or tighter stops.

**Recommendation:**
- **Absolute floor to run this strategy cleanly:** **~$2,000** (still high utilization).
- **Preferred minimum:** **$3,000–$5,000** so 1.0–1.5% risk fits 0.7–1.0% stops at ≤60% book utilization and fees hurt less.
- Until then: treat $1k as a **strict A+-only** book (this memo), or add capital before Sunday go-live.

---

## 4. Paper action taken (Thu Sep 17, ~1:05 PM ET)

**Clips placed: 0 / 2**

**Why zero:** No clean setup **now**.
- BTC/ETH/SOL all within ~0.2–0.4% of 24h highs → extended, not pullback.
- No 15m **close** above trigger highs (BTC 77,095 / ETH 2,481.58 / SOL 101.70).
- SOL prior plan invalidated; reclaim ≠ new signal.

`jose-main` status at check: $10,000 USD, 0 open orders, 0 trades, unrealized PnL $0.

---

## 5. Three-day paper validation plan (Thu / Fri / Sat)

Goal: prove the breakout rules can clear fees with ≤2 clips/day before any live risk Sunday.

### Thu Sep 17 (today) — Observe + arm
- [ ] No force-fills. Watch for: (a) 15m close above listed highs, or (b) pullback into prior swing low then reclaim.
- [ ] Log every A+/B/skip decision (pair, trigger, stop, R:R after fees).
- [ ] If a true A+ prints, place **at most 1** paper clip at paper risk ~$100–$150.
- [ ] End-of-day: flatten any open paper; write 5-line journal.

### Fri Sep 18 — Probe day
- [ ] Up to **2** paper clips under locked rules (10× live notionals).
- [ ] Must pre-define stop/targets in the decision log before send.
- [ ] Kill criteria mid-day: −$150 paper (~−$15 live-equivalent) → stop for the day.
- [ ] Score: wins must be net-of-fee; scratches count as small losses.

### Sat Sep 19 — Confirm or no-go
- [ ] Up to 2 paper clips; prefer the **best single** A+ over filling quota.
- [ ] **Go-live checklist for Sun Sep 20:**
  - At least **3 graded decisions** logged Thu–Sat (including skips).
  - Net paper PnL **≥ −$200** on jose-main (~−$20 live-equiv) **and** no daily-stop breach twice.
  - Fee awareness demonstrated (no sub-1.5R planned trades).
  - Live cash still ≥ ~$1,000; API read-only sanity check.
  - Emotional/process: followed max 1–2 clips and same-day flatten in paper.
- [ ] If checklist fails → **delay live**; keep paper until rules prove edge after fees.

### Sun Sep 20 — LIVE only if checklist green
- First live clip: **half** normal risk ($8–$10), BTC or ETH preferred over SOL until SOL prints a fresh A+ under new rules.
- Hard live daily stop −$35 remains.
- **Do not enable** automated live trading from agents; manual/confirmed only.

---

## 6. Blockers for go-live

1. **Capital / fee drag:** $1k is below preferred $3–5k; strategy is fee-fragile.
2. **No validated paper track record yet:** jose-main still 0 trades.
3. **SOL prior thesis dead:** do not revive $101.40 long without fresh breakout/pullback rules.
4. **Current tape extended:** waiting for trigger closes or pullbacks — patience is part of the edge.
5. **Live trading disabled by design** this session — correct; go-live is a Sunday human decision after Fri/Sat probes.

---

## 7. Quick reference card

```
STRATEGY: 15m Momentum Breakout (BTC/ETH/SOL)
LIVE RISK: $10–15 / trade | daily −$35 | max open $15 | 1–2 clips | cash only
ENTRY: 15m close above swing/24h high after compression; no >0.4% chase
STOP: structure, 0.50–1.00%; skip if wider
T1/T2: 2R / 3R gross; flatten same day
SKIP: ATR15 < 0.39% | SOL revive of old $101.40 plan | extended chase
PAPER: 10× live notionals on jose-main
FEES: 0.26% RT — prefer high-R only; ideal capital $3k–$5k
```
