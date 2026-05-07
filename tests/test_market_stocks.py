"""Tests for market_stocks.py — HTTP calls are mocked."""

import unittest.mock as mock
import pytest

from traderjoe.market_stocks import (
    Stock,
    _parse_nasdaq,
    _parse_other,
    get_all_stocks,
    get_symbols,
)

_NASDAQ_SAMPLE = """\
Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares
AAPL|Apple Inc. - Common Stock|Q|N|N|100|N|N
MSFT|Microsoft Corporation - Common Stock|Q|N|N|100|N|N
QQQ|Invesco QQQ Trust Series 1|G|N|N|100|Y|N
ZZZZ|Test Corp|Q|Y|N|100|N|N
File Creation Time: 0507202512:00
"""

_OTHER_SAMPLE = """\
ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol
JPM|JPMorgan Chase & Co. Common Stock|N|JPM|N|100|N|JPM
SPY|SPDR S&P 500 ETF Trust|P|SPY|Y|100|N|SPY
GS|Goldman Sachs Group Inc.|N|GS|N|100|N|GS
BOGUS|Bogus Issue|N|BOG|N|100|Y|BOG
File Creation Time: 0507202512:00
"""


def _mock_fetch(url, timeout=15):
    if "nasdaqlisted" in url:
        return _NASDAQ_SAMPLE
    return _OTHER_SAMPLE


# ── parser unit tests ────────────────────────────────────────────────────────

def test_parse_nasdaq_count():
    stocks = _parse_nasdaq(_NASDAQ_SAMPLE)
    assert len(stocks) == 3  # ZZZZ (test issue) excluded


def test_parse_nasdaq_test_issue_excluded():
    stocks = _parse_nasdaq(_NASDAQ_SAMPLE)
    assert all(s.symbol != "ZZZZ" for s in stocks)


def test_parse_nasdaq_etf_flag():
    stocks = _parse_nasdaq(_NASDAQ_SAMPLE)
    qqq = next(s for s in stocks if s.symbol == "QQQ")
    assert qqq.etf is True
    aapl = next(s for s in stocks if s.symbol == "AAPL")
    assert aapl.etf is False


def test_parse_nasdaq_exchange():
    stocks = _parse_nasdaq(_NASDAQ_SAMPLE)
    assert all(s.exchange == "NASDAQ" for s in stocks)


def test_parse_other_count():
    stocks = _parse_other(_OTHER_SAMPLE)
    assert len(stocks) == 3  # BOGUS (test issue) excluded


def test_parse_other_exchange_mapping():
    stocks = _parse_other(_OTHER_SAMPLE)
    spy = next(s for s in stocks if s.symbol == "SPY")
    assert spy.exchange == "NYSE ARCA"
    jpm = next(s for s in stocks if s.symbol == "JPM")
    assert jpm.exchange == "NYSE"


# ── get_all_stocks integration tests (mocked HTTP) ──────────────────────────

def test_get_all_stocks_total():
    with mock.patch("traderjoe.market_stocks._fetch", side_effect=_mock_fetch):
        stocks = get_all_stocks()
    assert len(stocks) == 6  # 3 NASDAQ + 3 other


def test_get_all_stocks_returns_stock_dataclass():
    with mock.patch("traderjoe.market_stocks._fetch", side_effect=_mock_fetch):
        stocks = get_all_stocks()
    assert all(isinstance(s, Stock) for s in stocks)


def test_get_all_stocks_exclude_etfs():
    with mock.patch("traderjoe.market_stocks._fetch", side_effect=_mock_fetch):
        stocks = get_all_stocks(include_etfs=False)
    assert all(not s.etf for s in stocks)
    assert len(stocks) == 4  # QQQ and SPY excluded


def test_get_all_stocks_filter_exchange():
    with mock.patch("traderjoe.market_stocks._fetch", side_effect=_mock_fetch):
        stocks = get_all_stocks(exchanges=["NYSE"])
    assert all(s.exchange == "NYSE" for s in stocks)
    assert {s.symbol for s in stocks} == {"JPM", "GS"}


def test_get_all_stocks_filter_exchange_case_insensitive():
    with mock.patch("traderjoe.market_stocks._fetch", side_effect=_mock_fetch):
        stocks = get_all_stocks(exchanges=["nasdaq"])
    assert len(stocks) == 3


def test_get_symbols_returns_strings():
    with mock.patch("traderjoe.market_stocks._fetch", side_effect=_mock_fetch):
        symbols = get_symbols()
    assert all(isinstance(s, str) for s in symbols)
    assert "AAPL" in symbols
    assert "JPM" in symbols


def test_get_all_stocks_raises_on_total_failure():
    with mock.patch("traderjoe.market_stocks._fetch", side_effect=Exception("network error")):
        with pytest.raises(RuntimeError, match="Failed to fetch"):
            get_all_stocks()
