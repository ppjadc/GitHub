"""Locked parameters from the Sep 20, 2026 go-live memo. Do not loosen."""

# Universe — spot USD pairs only
UNIVERSE = ("BTC/USD", "ETH/USD", "SOL/USD")
KRAKEN_PAIR = {
    "BTC/USD": "XBTUSD",
    "ETH/USD": "ETHUSD",
    "SOL/USD": "SOLUSD",
}

INTERVAL_MIN = 15
BARS_PER_HOUR = 60 // INTERVAL_MIN
BARS_24H = 24 * BARS_PER_HOUR  # 96
BARS_8H = 8 * BARS_PER_HOUR  # 32

# jose-main paper book quotes 0.26% round-trip. Live Kraken starter *taker*
# is 0.26% *per side* (~0.52% RT if both fills take). Do not treat 0.26% RT
# as a reason to size larger; it is the memo's paper fee, not a looser live fee.
FEE_RT = 0.0026
ATR_FEE_MULT = 1.5
ATR_MIN_PCT = FEE_RT * ATR_FEE_MULT  # ~0.39%
ATR_PERIOD = 14

CHASE_MAX_PCT = 0.004  # no chase >0.4% through the trigger
STOP_MIN_PCT = 0.005  # 0.50%
STOP_MAX_PCT = 0.010  # 1.00% — skip if structure needs more; do not widen

T1_R = 2.0
T2_R = 3.0
T1_SCALE_FRAC = 0.50  # take >=50% off at T1
PLANNED_GROSS_R = T1_SCALE_FRAC * T1_R + (1.0 - T1_SCALE_FRAC) * T2_R  # 2.5
MIN_GROSS_RR = 2.0
MIN_NET_RR = 1.3

COMPRESSION_MIN = 2
COMPRESSION_PREFERRED_MAX = 8

SWING_LEFT = 2
SWING_RIGHT = 2

TIME_STOP_BARS = 12  # 3 hours
SCRATCH_BARS = 2  # 15m close back below trigger within 2 candles
MAX_CLIPS_PER_DAY = 2
MAX_OPEN_POSITIONS = 1

LIVE_EQUITY = 1000.0
LIVE_RISK_MIN = 10.0
LIVE_RISK_MAX = 15.0
LIVE_RISK_TARGET = 12.5
LIVE_NOTIONAL_TYPICAL_MIN = 700.0
LIVE_NOTIONAL_TYPICAL_MAX = 1000.0
LIVE_DAILY_LOSS_STOP = 35.0
LIVE_WEEKLY_SOFT_STOP = 75.0
LIVE_MAX_OPEN_RISK = 15.0

PAPER_MULT = 10.0
PAPER_EQUITY = LIVE_EQUITY * PAPER_MULT  # 10_000
PAPER_RISK_MIN = LIVE_RISK_MIN * PAPER_MULT  # 100
PAPER_RISK_MAX = LIVE_RISK_MAX * PAPER_MULT  # 150  (probe band, not the $200 loose cap)
PAPER_RISK_TARGET = LIVE_RISK_TARGET * PAPER_MULT  # 125
PAPER_DAILY_LOSS_STOP = LIVE_DAILY_LOSS_STOP * PAPER_MULT  # 350
PAPER_WEEKLY_SOFT_STOP = LIVE_WEEKLY_SOFT_STOP * PAPER_MULT  # 750

SESSION_TZ = "America/New_York"

PUBLIC_REST_BASE = "https://api.kraken.com/0/public"
USER_AGENT = "kraken-paper-toolkit/0.1 (public-rest-only; no-auth)"
