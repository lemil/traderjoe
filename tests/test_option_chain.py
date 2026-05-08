"""Tests for option_chain.py — yfinance calls are mocked."""

import math
import io
import unittest.mock as mock
import pytest
import pandas as pd

from traderjoe.option_chain import (
    OptionCell, OptionMatrix,
    download_option_chain, pretty_print_matrix,
    _time_to_expiry, _compute_bs_fields,
)

# ── fixtures ──────────────────────────────────────────────────────────────────

def _make_calls_df():
    return pd.DataFrame([
        {"strike": 190.0, "bid": 3.80, "ask": 4.00, "lastPrice": 3.90,
         "volume": 500, "openInterest": 2000, "impliedVolatility": 0.22},
        {"strike": 195.0, "bid": 1.90, "ask": 2.10, "lastPrice": 2.00,
         "volume": 300, "openInterest": 1500, "impliedVolatility": 0.23},
        {"strike": 200.0, "bid": 0.80, "ask": 1.00, "lastPrice": 0.90,
         "volume": 150, "openInterest": 800,  "impliedVolatility": 0.24},
    ])


def _make_puts_df():
    return pd.DataFrame([
        {"strike": 190.0, "bid": 2.00, "ask": 2.20, "lastPrice": 2.10,
         "volume": 400, "openInterest": 1800, "impliedVolatility": 0.21},
        {"strike": 195.0, "bid": 4.00, "ask": 4.30, "lastPrice": 4.15,
         "volume": 250, "openInterest": 1200, "impliedVolatility": 0.22},
    ])


ChainResult = mock.MagicMock()
ChainResult.calls = _make_calls_df()
ChainResult.puts  = _make_puts_df()


def _make_ticker(symbol):
    t = mock.MagicMock()
    t.options = ["2025-06-20", "2025-07-18"]
    t.history.return_value = pd.DataFrame({"Close": [192.0]})
    t.option_chain.return_value = ChainResult
    return t


# ── unit tests ────────────────────────────────────────────────────────────────

def test_time_to_expiry_positive():
    from datetime import date, timedelta
    future = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
    assert _time_to_expiry(future) > 0


def test_compute_bs_fields_returns_tuple():
    iv, delta, gamma, theta, vega = _compute_bs_fields(192, 190, 0.1, 0.05, "call", 3.9)
    assert not math.isnan(iv)
    assert 0 < delta < 1
    assert gamma > 0
    assert vega > 0


def test_compute_bs_fields_bad_price_returns_nan():
    iv, delta, *_ = _compute_bs_fields(192, 190, 0.1, 0.05, "call", -1.0)
    assert math.isnan(iv)


# ── download_option_chain tests ───────────────────────────────────────────────

@mock.patch("traderjoe.option_chain.yf.Ticker")
@mock.patch("traderjoe.option_chain._risk_free_rate", return_value=0.05)
def test_returns_option_matrix(mock_r, mock_ticker):
    mock_ticker.return_value = _make_ticker("AAPL")
    matrix = download_option_chain("AAPL", "call")
    assert isinstance(matrix, OptionMatrix)


@mock.patch("traderjoe.option_chain.yf.Ticker")
@mock.patch("traderjoe.option_chain._risk_free_rate", return_value=0.05)
def test_matrix_symbol_and_type(mock_r, mock_ticker):
    mock_ticker.return_value = _make_ticker("AAPL")
    matrix = download_option_chain("AAPL", "call")
    assert matrix.symbol == "AAPL"
    assert matrix.option_type == "call"


@mock.patch("traderjoe.option_chain.yf.Ticker")
@mock.patch("traderjoe.option_chain._risk_free_rate", return_value=0.05)
def test_matrix_spot(mock_r, mock_ticker):
    mock_ticker.return_value = _make_ticker("AAPL")
    matrix = download_option_chain("AAPL", "call")
    assert matrix.spot == 192.0


@mock.patch("traderjoe.option_chain.yf.Ticker")
@mock.patch("traderjoe.option_chain._risk_free_rate", return_value=0.05)
def test_matrix_strikes_sorted(mock_r, mock_ticker):
    mock_ticker.return_value = _make_ticker("AAPL")
    matrix = download_option_chain("AAPL", "call")
    assert matrix.strikes == sorted(matrix.strikes)


@mock.patch("traderjoe.option_chain.yf.Ticker")
@mock.patch("traderjoe.option_chain._risk_free_rate", return_value=0.05)
def test_matrix_expiries_sorted(mock_r, mock_ticker):
    mock_ticker.return_value = _make_ticker("AAPL")
    matrix = download_option_chain("AAPL", "call")
    assert matrix.expiries == sorted(matrix.expiries)


@mock.patch("traderjoe.option_chain.yf.Ticker")
@mock.patch("traderjoe.option_chain._risk_free_rate", return_value=0.05)
def test_cells_are_option_cell(mock_r, mock_ticker):
    mock_ticker.return_value = _make_ticker("AAPL")
    matrix = download_option_chain("AAPL", "call")
    assert all(isinstance(c, OptionCell) for c in matrix.cells.values())


@mock.patch("traderjoe.option_chain.yf.Ticker")
@mock.patch("traderjoe.option_chain._risk_free_rate", return_value=0.05)
def test_itm_flag_call(mock_r, mock_ticker):
    mock_ticker.return_value = _make_ticker("AAPL")
    matrix = download_option_chain("AAPL", "call")
    for cell in matrix.cells.values():
        expected_itm = cell.strike < matrix.spot
        assert cell.itm == expected_itm


@mock.patch("traderjoe.option_chain.yf.Ticker")
@mock.patch("traderjoe.option_chain._risk_free_rate", return_value=0.05)
def test_put_chain(mock_r, mock_ticker):
    mock_ticker.return_value = _make_ticker("AAPL")
    matrix = download_option_chain("AAPL", "put")
    assert matrix.option_type == "put"
    assert len(matrix.cells) > 0


@mock.patch("traderjoe.option_chain.yf.Ticker")
@mock.patch("traderjoe.option_chain._risk_free_rate", return_value=0.05)
def test_max_expiries(mock_r, mock_ticker):
    mock_ticker.return_value = _make_ticker("AAPL")
    matrix = download_option_chain("AAPL", "call", max_expiries=1)
    assert len(matrix.expiries) == 1


@mock.patch("traderjoe.option_chain.yf.Ticker")
@mock.patch("traderjoe.option_chain._risk_free_rate", return_value=0.05)
def test_min_volume_filter(mock_r, mock_ticker):
    mock_ticker.return_value = _make_ticker("AAPL")
    matrix = download_option_chain("AAPL", "call", min_volume=400)
    for cell in matrix.cells.values():
        assert cell.volume >= 400


@mock.patch("traderjoe.option_chain.yf.Ticker")
def test_invalid_option_type(mock_ticker):
    mock_ticker.return_value = _make_ticker("AAPL")
    with pytest.raises(ValueError):
        download_option_chain("AAPL", "future")


@mock.patch("traderjoe.option_chain.yf.Ticker")
def test_no_options_raises(mock_ticker):
    t = _make_ticker("AAPL")
    t.options = []
    mock_ticker.return_value = t
    with pytest.raises(RuntimeError):
        download_option_chain("AAPL")


# ── pretty_print_matrix tests ─────────────────────────────────────────────────

@mock.patch("traderjoe.option_chain.yf.Ticker")
@mock.patch("traderjoe.option_chain._risk_free_rate", return_value=0.05)
def test_pretty_print_runs(mock_r, mock_ticker, capsys):
    mock_ticker.return_value = _make_ticker("AAPL")
    matrix = download_option_chain("AAPL", "call")
    pretty_print_matrix(matrix, field="mid")
    out = capsys.readouterr().out
    assert "AAPL" in out
    assert "Mid Price" in out


@mock.patch("traderjoe.option_chain.yf.Ticker")
@mock.patch("traderjoe.option_chain._risk_free_rate", return_value=0.05)
def test_pretty_print_all_fields(mock_r, mock_ticker, capsys):
    mock_ticker.return_value = _make_ticker("AAPL")
    matrix = download_option_chain("AAPL", "call")
    for f in ["mid", "bid", "ask", "iv", "delta", "gamma", "theta", "vega", "volume", "oi"]:
        pretty_print_matrix(matrix, field=f)
    out = capsys.readouterr().out
    assert out  # something was printed


@mock.patch("traderjoe.option_chain.yf.Ticker")
@mock.patch("traderjoe.option_chain._risk_free_rate", return_value=0.05)
def test_pretty_print_invalid_field(mock_r, mock_ticker):
    mock_ticker.return_value = _make_ticker("AAPL")
    matrix = download_option_chain("AAPL", "call")
    with pytest.raises(ValueError):
        pretty_print_matrix(matrix, field="nonsense")


@mock.patch("traderjoe.option_chain.yf.Ticker")
@mock.patch("traderjoe.option_chain._risk_free_rate", return_value=0.05)
def test_pretty_print_itm_marker(mock_r, mock_ticker, capsys):
    mock_ticker.return_value = _make_ticker("AAPL")
    matrix = download_option_chain("AAPL", "call")
    pretty_print_matrix(matrix, show_itm_marker=True)
    out = capsys.readouterr().out
    assert "*" in out
