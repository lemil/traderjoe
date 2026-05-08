"""Tests for traderjoe.pricer — yfinance calls are mocked."""

import math
import unittest.mock as mock
from datetime import date, timedelta

import pandas as pd
import pytest

from traderjoe.pricer import (
    PriceResult,
    fetch_risk_free_rate,
    fetch_spot,
    historical_volatility,
    pick_expiry,
    pick_strike,
    price_option,
    time_to_expiry,
)


# ── fixtures / helpers ────────────────────────────────────────────────────────

def _make_history(closes: list[float]) -> pd.DataFrame:
    """Return a minimal DataFrame with a Close column."""
    return pd.DataFrame({"Close": closes})


def _make_ticker(
    spot: float = 150.0,
    rate_close: float = 5.0,       # percent (^IRX convention)
    closes: list[float] | None = None,
    options: list[str] | None = None,
    chain_calls: pd.DataFrame | None = None,
    chain_puts: pd.DataFrame | None = None,
):
    """Build a mock yfinance.Ticker with sensible defaults."""
    if closes is None:
        closes = [spot * (1 + 0.001 * i) for i in range(40)]
    if options is None:
        today = date.today()
        options = [(today + timedelta(days=30)).strftime("%Y-%m-%d")]
    if chain_calls is None:
        chain_calls = pd.DataFrame({"strike": [145.0, 150.0, 155.0],
                                    "bid":    [6.0,   4.5,   3.0],
                                    "ask":    [6.5,   5.0,   3.5]})
    if chain_puts is None:
        chain_puts = pd.DataFrame({"strike": [145.0, 150.0, 155.0],
                                   "bid":    [2.0,   3.0,   4.5],
                                   "ask":    [2.5,   3.5,   5.0]})

    ticker = mock.MagicMock()
    ticker.fast_info.last_price = spot
    ticker.history.return_value = _make_history(closes)
    ticker.options = options
    chain = mock.MagicMock()
    chain.calls = chain_calls
    chain.puts = chain_puts
    ticker.option_chain.return_value = chain
    return ticker


def _mock_irx(rate_pct: float = 5.0):
    irx = mock.MagicMock()
    irx.history.return_value = _make_history([rate_pct])
    return irx


# ── fetch_spot ────────────────────────────────────────────────────────────────

def test_fetch_spot_uses_fast_info():
    ticker = _make_ticker(spot=200.0)
    assert fetch_spot(ticker) == 200.0


def test_fetch_spot_falls_back_to_history():
    ticker = mock.MagicMock()
    ticker.fast_info.last_price = None
    ticker.fast_info.regularMarketPrice = None
    ticker.history.return_value = _make_history([123.45])
    assert fetch_spot(ticker) == pytest.approx(123.45)


def test_fetch_spot_raises_on_empty_history():
    ticker = mock.MagicMock()
    ticker.fast_info.last_price = None
    ticker.fast_info.regularMarketPrice = None
    ticker.history.return_value = pd.DataFrame({"Close": []})
    with pytest.raises(RuntimeError, match="spot price"):
        fetch_spot(ticker)


# ── fetch_risk_free_rate ──────────────────────────────────────────────────────

def test_fetch_risk_free_rate_converts_percent():
    with mock.patch("traderjoe.pricer.yf.Ticker", return_value=_mock_irx(5.24)):
        r = fetch_risk_free_rate()
    assert r == pytest.approx(0.0524)


def test_fetch_risk_free_rate_defaults_on_empty():
    irx = mock.MagicMock()
    irx.history.return_value = pd.DataFrame({"Close": []})
    with mock.patch("traderjoe.pricer.yf.Ticker", return_value=irx):
        r = fetch_risk_free_rate()
    assert r == 0.05


# ── historical_volatility ─────────────────────────────────────────────────────

def test_historical_volatility_positive():
    closes = [100 * math.exp(0.01 * i) for i in range(40)]
    ticker = _make_ticker(closes=closes)
    vol = historical_volatility(ticker, window=30)
    assert vol > 0


def test_historical_volatility_raises_on_short_history():
    ticker = _make_ticker(closes=[100.0])
    with pytest.raises(RuntimeError, match="Not enough history"):
        historical_volatility(ticker)


def test_historical_volatility_constant_prices_is_zero():
    # All identical closes → zero variance → zero vol
    ticker = _make_ticker(closes=[100.0] * 40)
    vol = historical_volatility(ticker, window=30)
    assert vol == pytest.approx(0.0)


# ── pick_expiry ───────────────────────────────────────────────────────────────

def test_pick_expiry_default_nearest_30d():
    today = date.today()
    exp_30 = (today + timedelta(days=30)).strftime("%Y-%m-%d")
    exp_60 = (today + timedelta(days=60)).strftime("%Y-%m-%d")
    ticker = _make_ticker(options=[exp_30, exp_60])
    assert pick_expiry(ticker, None) == exp_30


def test_pick_expiry_specific_target():
    today = date.today()
    exp_30 = (today + timedelta(days=30)).strftime("%Y-%m-%d")
    exp_60 = (today + timedelta(days=60)).strftime("%Y-%m-%d")
    ticker = _make_ticker(options=[exp_30, exp_60])
    assert pick_expiry(ticker, exp_60) == exp_60


def test_pick_expiry_rounds_up_to_next_available():
    today = date.today()
    exp_45 = (today + timedelta(days=45)).strftime("%Y-%m-%d")
    ticker = _make_ticker(options=[exp_45])
    # target is 30 days, only 45d available → should return 45d
    assert pick_expiry(ticker, None) == exp_45


def test_pick_expiry_no_options_raises():
    ticker = _make_ticker(options=[])
    with pytest.raises(RuntimeError, match="No options data"):
        pick_expiry(ticker, None)


# ── pick_strike ───────────────────────────────────────────────────────────────

def test_pick_strike_atm():
    chain = mock.MagicMock()
    chain.calls = pd.DataFrame({"strike": [140.0, 150.0, 160.0], "bid": [1]*3, "ask": [2]*3})
    assert pick_strike(chain, 151.0, None, "call") == 150.0


def test_pick_strike_specific_target():
    chain = mock.MagicMock()
    chain.calls = pd.DataFrame({"strike": [140.0, 150.0, 160.0], "bid": [1]*3, "ask": [2]*3})
    assert pick_strike(chain, 151.0, 158.0, "call") == 160.0


def test_pick_strike_put_uses_puts_df():
    chain = mock.MagicMock()
    chain.puts = pd.DataFrame({"strike": [130.0, 140.0], "bid": [1]*2, "ask": [2]*2})
    assert pick_strike(chain, 135.0, None, "put") == 130.0


# ── time_to_expiry ────────────────────────────────────────────────────────────

def test_time_to_expiry_positive():
    future = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
    T = time_to_expiry(future)
    assert T == pytest.approx(30 / 365.0, rel=1e-3)


def test_time_to_expiry_past_raises():
    past = "2000-01-01"
    with pytest.raises(RuntimeError, match="past"):
        time_to_expiry(past)


# ── price_option (end-to-end, fully mocked) ───────────────────────────────────

def _patch_price_option(spot=150.0, rate_pct=5.0, closes=None):
    """Context manager that patches yf.Ticker for price_option calls."""
    today = date.today()
    expiry_str = (today + timedelta(days=30)).strftime("%Y-%m-%d")

    if closes is None:
        # Simulate realistic daily returns (~1.5% daily vol → ~24% annualised)
        daily_returns = [
            0.012, -0.008, 0.015, -0.011, 0.009, -0.014, 0.007, 0.013,
            -0.010, 0.016, -0.006, 0.011, -0.013, 0.008, -0.009, 0.014,
            0.010, -0.012, 0.007, -0.015, 0.013, 0.006, -0.011, 0.017,
            -0.008, 0.012, -0.010, 0.009, 0.014, -0.007, 0.011, -0.013,
            0.008, -0.009, 0.015, 0.006, -0.012, 0.010, -0.008, 0.013,
        ]
        c = spot
        closes = []
        for r in daily_returns:
            c *= (1 + r)
            closes.append(c)

    main_ticker = _make_ticker(spot=spot, closes=closes,
                               options=[expiry_str])
    irx_ticker = _mock_irx(rate_pct)

    def _ticker_factory(sym):
        return irx_ticker if sym == "^IRX" else main_ticker

    return mock.patch("traderjoe.pricer.yf.Ticker", side_effect=_ticker_factory)


def test_price_option_returns_price_result():
    with _patch_price_option():
        result = price_option("AAPL")
    assert isinstance(result, PriceResult)


def test_price_option_symbol_uppercased():
    with _patch_price_option():
        result = price_option("aapl")
    assert result.symbol == "AAPL"


def test_price_option_bs_price_positive():
    with _patch_price_option():
        result = price_option("AAPL")
    assert result.bs_price > 0


def test_price_option_call_delta_between_0_and_1():
    with _patch_price_option():
        result = price_option("AAPL", option_type="call")
    assert 0 < result.greeks.delta < 1


def test_price_option_put_delta_between_neg1_and_0():
    with _patch_price_option():
        result = price_option("AAPL", option_type="put")
    assert -1 < result.greeks.delta < 0


def test_price_option_invalid_type_raises():
    with pytest.raises(ValueError, match="option_type"):
        price_option("AAPL", option_type="banana")


def test_price_option_market_mid_populated():
    with _patch_price_option(spot=150.0):
        result = price_option("AAPL")
    # default mock chain has bid/ask → market_mid should be set
    assert result.market_mid is not None
    assert result.market_mid > 0
