import pytest

from kraken_paper.paper_plan import NoAPlusError, plans_from_setup
from kraken_paper.breakout import evaluate_breakout
from tests.factories import range_then_break


def test_paper_plan_sizes_a_plus_and_refuses_skips():
    candles = range_then_break()
    setup = evaluate_breakout(candles, len(candles) - 1, pair="BTC/USD")
    live, paper = plans_from_setup(setup)
    assert live.book == "live"
    assert paper.book == "paper"
    assert paper.notional > live.notional

    setup.tradable = False
    setup.grade = "SKIP"
    with pytest.raises(NoAPlusError):
        plans_from_setup(setup)
