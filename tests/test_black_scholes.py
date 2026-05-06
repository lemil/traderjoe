"""Tests for Black-Scholes pricing and Greeks."""

import math
import pytest
from traderjoe.black_scholes import black_scholes, implied_volatility, Greeks

# Reference values computed with an independent tool (e.g. options-price calculator)
# S=100, K=100, T=1, r=0.05, sigma=0.20 — ATM 1-year options

S, K, T, r, sigma = 100.0, 100.0, 1.0, 0.05, 0.20


def test_call_price():
    price, _ = black_scholes(S, K, T, r, sigma)
    assert abs(price - 10.4506) < 1e-3


def test_put_price():
    price, _ = black_scholes(S, K, T, r, sigma, option_type="put")
    assert abs(price - 5.5735) < 1e-3


def test_put_call_parity():
    call, _ = black_scholes(S, K, T, r, sigma, "call")
    put, _ = black_scholes(S, K, T, r, sigma, "put")
    # C - P = S - K * e^(-rT)
    expected = S - K * math.exp(-r * T)
    assert abs((call - put) - expected) < 1e-8


def test_call_delta_range():
    _, g = black_scholes(S, K, T, r, sigma, "call")
    assert 0.0 < g.delta < 1.0


def test_put_delta_range():
    _, g = black_scholes(S, K, T, r, sigma, "put")
    assert -1.0 < g.delta < 0.0


def test_delta_put_call_relationship():
    _, cg = black_scholes(S, K, T, r, sigma, "call")
    _, pg = black_scholes(S, K, T, r, sigma, "put")
    assert abs(cg.delta - pg.delta - 1.0) < 1e-8


def test_gamma_positive():
    _, g = black_scholes(S, K, T, r, sigma)
    assert g.gamma > 0


def test_vega_positive():
    _, g = black_scholes(S, K, T, r, sigma)
    assert g.vega > 0


def test_call_theta_negative():
    _, g = black_scholes(S, K, T, r, sigma, "call")
    assert g.theta < 0


def test_greeks_is_dataclass():
    _, g = black_scholes(S, K, T, r, sigma)
    assert isinstance(g, Greeks)


def test_implied_vol_roundtrip_call():
    price, _ = black_scholes(S, K, T, r, sigma, "call")
    iv = implied_volatility(price, S, K, T, r, "call")
    assert abs(iv - sigma) < 1e-5


def test_implied_vol_roundtrip_put():
    price, _ = black_scholes(S, K, T, r, sigma, "put")
    iv = implied_volatility(price, S, K, T, r, "put")
    assert abs(iv - sigma) < 1e-5


def test_implied_vol_otm_call():
    K_otm = 110.0
    price, _ = black_scholes(S, K_otm, T, r, sigma, "call")
    iv = implied_volatility(price, S, K_otm, T, r, "call")
    assert abs(iv - sigma) < 1e-5


def test_invalid_S():
    with pytest.raises(ValueError):
        black_scholes(-1, K, T, r, sigma)


def test_invalid_sigma():
    with pytest.raises(ValueError):
        black_scholes(S, K, T, r, -0.1)


def test_invalid_option_type():
    with pytest.raises(ValueError):
        black_scholes(S, K, T, r, sigma, option_type="future")


def test_invalid_market_price_below_intrinsic():
    with pytest.raises(ValueError):
        implied_volatility(-1.0, S, K, T, r, "call")
