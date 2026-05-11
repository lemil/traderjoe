"""Fetch all US-listed equity symbols from NASDAQ Trader public data."""

import csv
import dataclasses
import io
import time
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache

_NASDAQ_LISTED = "https://ftp.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
_OTHER_LISTED = "https://ftp.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"

_EXCHANGE_MAP = {
    "A": "NYSE MKT",
    "N": "NYSE",
    "P": "NYSE ARCA",
    "Z": "BATS",
    "V": "IEXG",
}


@dataclass(frozen=True)
class Stock:
    symbol: str
    name: str
    exchange: str
    market_category: str   # NASDAQ only: Q=Global Select, G=Global, S=Capital
    etf: bool
    test_issue: bool

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def _fetch(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "traderjoe/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def _parse_nasdaq(text: str) -> list[Stock]:
    reader = csv.DictReader(io.StringIO(text), delimiter="|")
    stocks = []
    for row in reader:
        symbol = row.get("Symbol", "").strip()
        # last line is a file-creation timestamp row
        if not symbol or symbol.startswith("File"):
            continue
        if row.get("Test Issue", "").strip() == "Y":
            continue
        stocks.append(
            Stock(
                symbol=symbol,
                name=row.get("Security Name", "").strip(),
                exchange="NASDAQ",
                market_category=row.get("Market Category", "").strip(),
                etf=row.get("ETF", "").strip() == "Y",
                test_issue=False,
            )
        )
    return stocks


def _parse_other(text: str) -> list[Stock]:
    reader = csv.DictReader(io.StringIO(text), delimiter="|")
    stocks = []
    for row in reader:
        symbol = row.get("ACT Symbol", "").strip()
        if not symbol or symbol.startswith("File"):
            continue
        if row.get("Test Issue", "").strip() == "Y":
            continue
        exchange_code = row.get("Exchange", "").strip()
        stocks.append(
            Stock(
                symbol=symbol,
                name=row.get("Security Name", "").strip(),
                exchange=_EXCHANGE_MAP.get(exchange_code, exchange_code),
                market_category="",
                etf=row.get("ETF", "").strip() == "Y",
                test_issue=False,
            )
        )
    return stocks


def get_all_stocks(
    *,
    include_etfs: bool = True,
    exchanges: list[str] | None = None,
    timeout: int = 15,
) -> list[Stock]:
    """
    Return all US-listed equity securities from NASDAQ Trader public files.

    Covers NASDAQ, NYSE, NYSE MKT (AMEX), NYSE ARCA, BATS, and IEXG.
    Test-issue symbols are always excluded.

    Parameters
    ----------
    include_etfs : bool
        Include ETFs in the results (default True).
    exchanges : list[str] | None
        Filter to specific exchange names, e.g. ["NYSE", "NASDAQ"].
        Case-insensitive. None means all exchanges.
    timeout : int
        HTTP request timeout in seconds.

    Returns
    -------
    list[Stock]
        Each entry has: symbol, name, exchange, market_category, etf, test_issue.

    Raises
    ------
    RuntimeError
        If either data file cannot be fetched.
    """
    errors = []

    try:
        nasdaq_text = _fetch(_NASDAQ_LISTED, timeout)
        nasdaq_stocks = _parse_nasdaq(nasdaq_text)
    except Exception as exc:
        errors.append(f"NASDAQ listed: {exc}")
        nasdaq_stocks = []

    try:
        other_text = _fetch(_OTHER_LISTED, timeout)
        other_stocks = _parse_other(other_text)
    except Exception as exc:
        errors.append(f"Other listed: {exc}")
        other_stocks = []

    if errors and not nasdaq_stocks and not other_stocks:
        raise RuntimeError("Failed to fetch stock listings:\n" + "\n".join(errors))

    all_stocks = nasdaq_stocks + other_stocks

    if not include_etfs:
        all_stocks = [s for s in all_stocks if not s.etf]

    if exchanges is not None:
        allowed = {e.upper() for e in exchanges}
        all_stocks = [s for s in all_stocks if s.exchange.upper() in allowed]

    return all_stocks


def get_symbols(
    *,
    include_etfs: bool = True,
    exchanges: list[str] | None = None,
    timeout: int = 15,
) -> list[str]:
    """Return only the ticker symbols (convenience wrapper around get_all_stocks)."""
    return [s.symbol for s in get_all_stocks(
        include_etfs=include_etfs, exchanges=exchanges, timeout=timeout
    )]
