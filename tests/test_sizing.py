import pytest

from kraken_paper.constants import LIVE_EQUITY, PAPER_EQUITY, PAPER_MULT
from kraken_paper.sizing import size_long, stop_pct, targets, translate_live_to_paper


def test_btc_worked_example_live_size():
    plan = size_long(77100.0, 76500.0, book="live")
    assert plan.cash_capped is True
    assert plan.notional <= LIVE_EQUITY + 1e-9
    assert plan.notional > 999.0  # near-full cash clip
    assert 10.0 <= plan.total_risk <= 11.0  # memo ≈ $10.40
    assert abs(plan.fee_rt_usd - plan.notional * 0.0026) < 1e-9
    t1, t2 = targets(77100.0, 76500.0)
    assert t1 == 78300.0
    assert t2 == 78900.0
    assert plan.t1 == 78300.0
    assert plan.t2 == 78900.0
    assert plan.within_risk_band is True


def test_never_uses_leverage():
    # 0.50% stop wants ~$1,974 notional for $15 risk — cash $1k binds.
    plan = size_long(100.0, 99.50, book="live", risk_target=15.0)
    assert plan.notional <= LIVE_EQUITY + 1e-9
    assert plan.cash_capped is True
    assert plan.qty * plan.entry == pytest.approx(plan.notional)
    assert plan.total_risk < 15.0  # smaller risk, not a wider stop


def test_hard_risk_cap_cuts_notional():
    plan = size_long(
        100.0,
        99.20,  # 0.80% stop
        book="live",
        equity=5000.0,
        risk_target=40.0,
        risk_min=10.0,
        risk_max=15.0,
    )
    assert plan.total_risk == pytest.approx(15.0, abs=0.02)
    assert plan.notional < 5000.0
    assert plan.notional == pytest.approx(15.0 / (0.008 + 0.0026), rel=0.01)


def test_paper_is_ten_times_live():
    live = size_long(77100.0, 76500.0, book="live")
    paper = translate_live_to_paper(live)
    assert paper.equity == PAPER_EQUITY
    assert paper.notional == pytest.approx(live.notional * PAPER_MULT, rel=0.02)
    assert paper.total_risk == pytest.approx(live.total_risk * PAPER_MULT, rel=0.02)
    assert paper.risk_min == live.risk_min * PAPER_MULT
    assert paper.risk_max == live.risk_max * PAPER_MULT
    assert paper.entry == live.entry
    assert paper.stop == live.stop


def test_stop_pct_rejects_stop_above_entry():
    with pytest.raises(ValueError):
        stop_pct(100.0, 100.0)
    with pytest.raises(ValueError):
        size_long(100.0, 100.50, book="live")


def test_qty_never_exceeds_cash_even_after_lot_rounding():
    plan = size_long(2472.55, 2455.00, book="live", lot_decimals=8)
    assert plan.qty * plan.entry <= LIVE_EQUITY + 1e-6
    assert plan.total_risk <= 15.0 + 1e-6
