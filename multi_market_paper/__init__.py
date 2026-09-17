"""Cash-only multi-market paper research lane.

This package is a *parallel* research lane. It does not place live orders,
does not use leverage, and does not read API secrets. It is not a substitute
for the locked crypto 15m momentum breakout playbook (BTC/ETH/SOL).
"""

__version__ = "0.1.0"

LANE_NAME = "multi_market_paper"
CRYPTO_LANE_NAME = "kraken_paper"
CRYPTO_LANE_STATUS = "LOCKED"
