from kraken_paper.backtest import run_backtest
from kraken_paper.breakout import evaluate_breakout
from kraken_paper.models import Candle
from tests.factories import STEP, range_then_break


def test_backtest_t2_reports_r_against_original_stop():
    candles = range_then_break()
    i = len(candles) - 1
    setup = evaluate_breakout(candles, i, pair="BTC/USD")
    assert setup.tradable
    assert setup.t2 is not None and setup.stop is not None and setup.entry is not None
    ts = candles[-1].time
    mid = setup.entry + 0.01  # stay above entry so T1+T2 can fill without a BE stop
    for j in range(1, 6):
        candles.append(
            Candle(
                time=ts + j * STEP,
                open=setup.entry,
                high=setup.t2 + 0.05,
                low=mid,
                close=setup.t2,
                pair="BTC/USD",
            )
        )
    result = run_backtest({"BTC/USD": candles}, book="live", days=2)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "t2"
    assert trade.r_multiple > 2.0
    assert trade.net_pnl > 0
    assert trade.fees > 0
