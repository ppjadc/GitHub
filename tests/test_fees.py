from kraken_paper.constants import ATR_FEE_MULT, ATR_MIN_PCT, FEE_RT, PLANNED_GROSS_R
from kraken_paper.fees import (
    atr_min_pct,
    blended_net_rr,
    notional_for_risk,
    one_way_fee,
    passes_fee_filter,
    passes_net_rr,
    round_trip_fee,
    total_risk_usd,
)


def test_memo_fee_constants_are_locked():
    assert FEE_RT == 0.0026
    assert ATR_FEE_MULT == 1.5
    assert abs(ATR_MIN_PCT - 0.0039) < 1e-12
    assert abs(atr_min_pct() - 0.0039) < 1e-12
    assert abs(PLANNED_GROSS_R - 2.5) < 1e-12


def test_round_trip_fee_on_1000_is_2_60():
    assert abs(round_trip_fee(1000.0) - 2.60) < 1e-12
    assert abs(one_way_fee(1000.0) - 1.30) < 1e-12


def test_total_risk_matches_btc_worked_example():
    entry, stop, notional = 77100.0, 76500.0, 1000.0
    stop_pct = (entry - stop) / entry
    risk = total_risk_usd(notional, stop_pct)
    # Memo: price risk ≈ $7.80 + fees ≈ $2.60 → total ≈ $10.40
    assert abs(notional * stop_pct - 7.782101166) < 1e-6
    assert abs(risk - 10.382101166) < 1e-6


def test_notional_for_risk_inverts_total_risk():
    stop_pct = 0.0078
    n = notional_for_risk(12.5, stop_pct)
    assert abs(total_risk_usd(n, stop_pct) - 12.5) < 1e-9


def test_fee_filter_atr_vs_1_5x_rt():
    assert not passes_fee_filter(0.0030)
    assert not passes_fee_filter(0.003899)
    assert passes_fee_filter(0.0039)
    assert passes_fee_filter(0.0045)
    assert passes_fee_filter(0.0052)


def test_blended_net_rr_at_half_percent_stop_is_the_1_3_floor():
    # 50% at 2R + 50% at 3R = 2.5R gross. At 0.50% stop, net R ≈ 1.30 after 0.26% RT.
    net = blended_net_rr(0.0050)
    assert abs(net - 1.30) < 0.02
    assert passes_net_rr(0.0050)
    # 0.40% stop fails the 1.3 floor — do not take it
    assert blended_net_rr(0.0040) < 1.3
    assert not passes_net_rr(0.0040)


def test_worked_example_0_78_stop_clears_net_rr():
    stop_pct = (77100.0 - 76500.0) / 77100.0
    net = blended_net_rr(stop_pct)
    assert net >= 1.3
    assert passes_net_rr(stop_pct)
