"""Tests for all 24 option strategies."""

import math
import pytest
from traderjoe.strategies import (
    Strategy, Leg, Probabilities, RiskMetrics,
    bull_call_spread, bear_put_spread, bull_put_spread, bear_call_spread,
    long_straddle, short_straddle, long_strangle, short_strangle,
    iron_condor, iron_butterfly, covered_call, cash_secured_put,
    calendar_spread, diagonal_spread, butterfly_spread, condor_spread,
    jade_lizard, ratio_spread, back_spread, christmas_tree,
    synthetic_long, synthetic_short, risk_reversal, collar,
    pretty_print_strategy,
)

# ── shared fixtures ────────────────────────────────────────────────────────────

S, T, r, sigma = 100.0, 0.25, 0.05, 0.20

# strike helpers
K_atm          = 100.0
K_low, K_high  = 95.0, 105.0
K1, K2, K3, K4 = 90.0, 95.0, 105.0, 110.0


# ── generic contract tests (applied to every strategy) ───────────────────────

ALL_STRATEGIES = [
    ("bull_call_spread",  lambda: bull_call_spread(S, K_low, K_high, T, r, sigma)),
    ("bear_put_spread",   lambda: bear_put_spread(S, K_low, K_high, T, r, sigma)),
    ("bull_put_spread",   lambda: bull_put_spread(S, K_low, K_high, T, r, sigma)),
    ("bear_call_spread",  lambda: bear_call_spread(S, K_low, K_high, T, r, sigma)),
    ("long_straddle",     lambda: long_straddle(S, K_atm, T, r, sigma)),
    ("short_straddle",    lambda: short_straddle(S, K_atm, T, r, sigma)),
    ("long_strangle",     lambda: long_strangle(S, K_low, K_high, T, r, sigma)),
    ("short_strangle",    lambda: short_strangle(S, K_low, K_high, T, r, sigma)),
    ("iron_condor",       lambda: iron_condor(S, K1, K2, K3, K4, T, r, sigma)),
    ("iron_butterfly",    lambda: iron_butterfly(S, K_low, K_atm, K_high, T, r, sigma)),
    ("covered_call",      lambda: covered_call(S, K_high, T, r, sigma)),
    ("cash_secured_put",  lambda: cash_secured_put(S, K_low, T, r, sigma)),
    ("calendar_spread",   lambda: calendar_spread(S, K_atm, T, T * 2, r, sigma)),
    ("diagonal_spread",   lambda: diagonal_spread(S, K_atm, K_high, T, T * 2, r, sigma)),
    ("butterfly_spread",  lambda: butterfly_spread(S, K_low, K_atm, K_high, T, r, sigma)),
    ("condor_spread",     lambda: condor_spread(S, K1, K2, K3, K4, T, r, sigma)),
    ("jade_lizard",       lambda: jade_lizard(S, K_low, K_high, 110.0, T, r, sigma)),
    ("ratio_spread",      lambda: ratio_spread(S, K_low, K_high, T, r, sigma)),
    ("back_spread",       lambda: back_spread(S, K_low, K_high, T, r, sigma)),
    ("christmas_tree",    lambda: christmas_tree(S, K_low, K_atm, K_high, T, r, sigma)),
    ("synthetic_long",    lambda: synthetic_long(S, K_atm, T, r, sigma)),
    ("synthetic_short",   lambda: synthetic_short(S, K_atm, T, r, sigma)),
    ("risk_reversal",     lambda: risk_reversal(S, K_low, K_high, T, r, sigma)),
    ("collar",            lambda: collar(S, K_low, K_high, T, r, sigma)),
]


@pytest.mark.parametrize("name,factory", ALL_STRATEGIES)
def test_returns_strategy(name, factory):
    assert isinstance(factory(), Strategy)


@pytest.mark.parametrize("name,factory", ALL_STRATEGIES)
def test_has_legs(name, factory):
    st = factory()
    assert len(st.legs) >= 1
    assert all(isinstance(l, Leg) for l in st.legs)


@pytest.mark.parametrize("name,factory", ALL_STRATEGIES)
def test_payoff_is_finite_at_spot(name, factory):
    st = factory()
    val = st.payoff(S)
    assert math.isfinite(val)


@pytest.mark.parametrize("name,factory", ALL_STRATEGIES)
def test_payoff_callable(name, factory):
    st = factory()
    assert math.isfinite(st.payoff(80.0))
    assert math.isfinite(st.payoff(100.0))
    assert math.isfinite(st.payoff(120.0))


@pytest.mark.parametrize("name,factory", ALL_STRATEGIES)
def test_net_premium_is_float(name, factory):
    st = factory()
    assert isinstance(st.net_premium, float)


@pytest.mark.parametrize("name,factory", ALL_STRATEGIES)
def test_breakevens_are_positive(name, factory):
    st = factory()
    assert all(be > 0 for be in st.breakevens)


@pytest.mark.parametrize("name,factory", ALL_STRATEGIES)
def test_pretty_print_runs(name, factory, capsys):
    st = factory()
    pretty_print_strategy(st)
    out = capsys.readouterr().out
    assert st.name in out


# ── strategy-specific tests ───────────────────────────────────────────────────

def test_bull_call_spread_debit():
    st = bull_call_spread(S, K_low, K_high, T, r, sigma)
    assert st.net_premium > 0          # debit strategy

def test_bull_call_spread_payoff_above_high():
    st = bull_call_spread(S, K_low, K_high, T, r, sigma)
    assert st.payoff(200.0) > 0        # profitable above K2

def test_bull_call_spread_payoff_below_low():
    st = bull_call_spread(S, K_low, K_high, T, r, sigma)
    assert st.payoff(1.0) < 0          # full loss below K1

def test_bear_put_spread_debit():
    st = bear_put_spread(S, K_low, K_high, T, r, sigma)
    assert st.net_premium > 0

def test_bear_put_spread_payoff_below_low():
    st = bear_put_spread(S, K_low, K_high, T, r, sigma)
    assert st.payoff(1.0) > 0          # profitable well below K1

def test_bull_put_spread_credit():
    st = bull_put_spread(S, K_low, K_high, T, r, sigma)
    assert st.net_premium < 0          # credit strategy

def test_bear_call_spread_credit():
    st = bear_call_spread(S, K_low, K_high, T, r, sigma)
    assert st.net_premium < 0          # credit strategy

def test_long_straddle_payoff_symmetric():
    st = long_straddle(S, K_atm, T, r, sigma)
    up   = st.payoff(K_atm + 20)
    down = st.payoff(K_atm - 20)
    assert abs(up - down) < 5.0        # roughly symmetric at equal distances

def test_long_straddle_max_loss_at_strike():
    st = long_straddle(S, K_atm, T, r, sigma)
    assert st.payoff(K_atm) < 0        # worst point is ATM

def test_short_straddle_max_profit_at_strike():
    st = short_straddle(S, K_atm, T, r, sigma)
    assert st.payoff(K_atm) > 0        # best point is ATM

def test_short_straddle_unlimited_loss():
    st = short_straddle(S, K_atm, T, r, sigma)
    assert st.max_loss == float("-inf")

def test_iron_condor_max_profit_between_inner_strikes():
    st = iron_condor(S, K1, K2, K3, K4, T, r, sigma)
    assert st.payoff(100.0) > 0        # S between K2 and K3

def test_iron_condor_defined_max_loss():
    st = iron_condor(S, K1, K2, K3, K4, T, r, sigma)
    assert st.max_loss != float("-inf")

def test_iron_butterfly_max_profit_at_body():
    st = iron_butterfly(S, K_low, K_atm, K_high, T, r, sigma)
    assert st.payoff(K_atm) > 0

def test_covered_call_profit_capped():
    st = covered_call(S, K_high, T, r, sigma)
    p_at_high = st.payoff(K_high)
    p_far_above = st.payoff(K_high * 2)
    assert abs(p_at_high - p_far_above) < 1.0  # profit flat above K

def test_cash_secured_put_max_profit_is_premium():
    st = cash_secured_put(S, K_low, T, r, sigma)
    assert st.net_premium < 0          # credit received
    assert st.payoff(200.0) > 0        # keep premium if stock rises

def test_butterfly_spread_max_profit_at_body():
    st = butterfly_spread(S, K_low, K_atm, K_high, T, r, sigma)
    assert st.payoff(K_atm) > st.payoff(K_atm + 20)
    assert st.payoff(K_atm) > st.payoff(K_atm - 20)

def test_condor_spread_profit_between_inner_strikes():
    st = condor_spread(S, K1, K2, K3, K4, T, r, sigma)
    assert st.payoff(100.0) > 0

def test_ratio_spread_unlimited_loss():
    st = ratio_spread(S, K_low, K_high, T, r, sigma)
    assert st.max_loss == float("-inf")

def test_back_spread_unlimited_profit():
    st = back_spread(S, K_low, K_high, T, r, sigma)
    assert st.max_profit == float("inf")

def test_synthetic_long_payoff_like_stock():
    st = synthetic_long(S, K_atm, T, r, sigma)
    # payoff should increase as S_T increases
    assert st.payoff(110.0) > st.payoff(100.0) > st.payoff(90.0)

def test_synthetic_short_payoff_inverse():
    st = synthetic_short(S, K_atm, T, r, sigma)
    assert st.payoff(90.0) > st.payoff(100.0) > st.payoff(110.0)

def test_collar_bounded_loss():
    st = collar(S, K_low, K_high, T, r, sigma)
    loss_deep = st.payoff(1.0)
    loss_at_put = st.payoff(K_low)
    # losses are bounded — at very low prices, payoff should plateau
    assert abs(loss_deep - loss_at_put) < 2.0

def test_risk_reversal_bullish():
    st = risk_reversal(S, K_low, K_high, T, r, sigma)
    assert st.payoff(120.0) > st.payoff(80.0)

def test_jade_lizard_credit():
    st = jade_lizard(S, K_low, K_high, 110.0, T, r, sigma)
    assert st.net_premium < 0          # net credit

def test_calendar_spread_returns_strategy():
    st = calendar_spread(S, K_atm, T, T * 2, r, sigma)
    assert isinstance(st, Strategy)
    assert len(st.legs) == 2

def test_diagonal_spread_returns_strategy():
    st = diagonal_spread(S, K_atm, K_high, T, T * 2, r, sigma)
    assert isinstance(st, Strategy)
    assert len(st.legs) == 2

def test_christmas_tree_unlimited_loss():
    st = christmas_tree(S, K_low, K_atm, K_high, T, r, sigma)
    assert st.max_loss == float("-inf")


# ── RiskMetrics tests ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("name,factory", ALL_STRATEGIES)
def test_has_risk_metrics(name, factory):
    st = factory()
    assert isinstance(st.risk, RiskMetrics)


@pytest.mark.parametrize("name,factory", ALL_STRATEGIES)
def test_risk_greeks_finite(name, factory):
    rm = factory().risk
    for greek in (rm.delta, rm.gamma, rm.theta, rm.vega, rm.rho):
        assert math.isfinite(greek)


@pytest.mark.parametrize("name,factory", ALL_STRATEGIES)
def test_risk_expected_pnl_finite(name, factory):
    rm = factory().risk
    assert math.isfinite(rm.expected_pnl)
    assert math.isfinite(rm.expected_profit)
    assert math.isfinite(rm.expected_loss)


@pytest.mark.parametrize("name,factory", ALL_STRATEGIES)
def test_risk_expected_pnl_splits(name, factory):
    rm = factory().risk
    assert rm.expected_profit >= 0
    assert rm.expected_loss <= 0
    assert abs(rm.expected_pnl - (rm.expected_profit + rm.expected_loss)) < 1.0


@pytest.mark.parametrize("name,factory", ALL_STRATEGIES)
def test_risk_reward_risk_ratio_valid(name, factory):
    st = factory()
    rr = st.risk.reward_risk_ratio
    if math.isinf(st.max_profit) and math.isinf(st.max_loss):
        assert math.isnan(rr)
    elif math.isinf(st.max_profit):
        assert math.isinf(rr) and rr > 0
    elif math.isinf(st.max_loss):
        assert rr == 0.0
    else:
        assert math.isfinite(rr) and rr >= 0


def test_iron_condor_reward_risk_positive():
    st = iron_condor(S, K1, K2, K3, K4, T, r, sigma)
    assert st.risk.reward_risk_ratio > 0

def test_bull_call_spread_delta_positive():
    st = bull_call_spread(S, K_low, K_high, T, r, sigma)
    assert st.risk.delta > 0

def test_bear_call_spread_delta_negative():
    st = bear_call_spread(S, K_low, K_high, T, r, sigma)
    assert st.risk.delta < 0

def test_long_straddle_gamma_positive():
    st = long_straddle(S, K_atm, T, r, sigma)
    assert st.risk.gamma > 0

def test_short_straddle_gamma_negative():
    st = short_straddle(S, K_atm, T, r, sigma)
    assert st.risk.gamma < 0

def test_long_straddle_vega_positive():
    st = long_straddle(S, K_atm, T, r, sigma)
    assert st.risk.vega > 0

def test_short_straddle_theta_positive():
    st = short_straddle(S, K_atm, T, r, sigma)
    assert st.risk.theta > 0  # short options earn time decay (positive theta)

def test_covered_call_delta_less_than_stock():
    st = covered_call(S, K_high, T, r, sigma)
    assert 0 < st.risk.delta < 100  # partial delta from short call

def test_calendar_spread_risk_metrics():
    st = calendar_spread(S, K_atm, T, T * 2, r, sigma)
    assert isinstance(st.risk, RiskMetrics)
    assert math.isfinite(st.risk.delta)

def test_diagonal_spread_risk_metrics():
    st = diagonal_spread(S, K_atm, K_high, T, T * 2, r, sigma)
    assert isinstance(st.risk, RiskMetrics)
    assert math.isfinite(st.risk.delta)
