"""
Live Black-Scholes option pricer.

Fetches all market inputs (spot, risk-free rate, historical volatility,
options chain) from Yahoo Finance and returns the theoretical price and
Greeks for the requested contract.
"""

import dataclasses
import math
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import yfinance as yf

from traderjoe.black_scholes import Greeks, black_scholes


@dataclass
class PriceResult:
    symbol: str
    option_type: str
    S: float          # spot price
    K: float          # strike
    T: float          # time to expiry in years
    r: float          # risk-free rate (decimal)
    sigma: float      # historical volatility (decimal)
    expiry: str       # YYYY-MM-DD
    bs_price: float
    market_mid: float | None  # bid/ask midpoint, or None if unavailable
    greeks: Greeks

    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        return d


# ── market data helpers ───────────────────────────────────────────────────────

def fetch_spot(ticker: yf.Ticker) -> float:
    info = ticker.fast_info
    price = getattr(info, "last_price", None) or getattr(info, "regularMarketPrice", None)
    if price is None:
        hist = ticker.history(period="1d")
        if hist.empty:
            raise RuntimeError("Could not fetch spot price")
        price = float(hist["Close"].iloc[-1])
    return float(price)


def fetch_risk_free_rate() -> float:
    """13-week US T-bill yield (^IRX) as a decimal."""
    irx = yf.Ticker("^IRX")
    hist = irx.history(period="5d")
    if hist.empty:
        return 0.05
    return float(hist["Close"].iloc[-1]) / 100.0


def historical_volatility(ticker: yf.Ticker, window: int = 30) -> float:
    """Annualised close-to-close volatility over `window` trading days."""
    hist = ticker.history(period=f"{window + 10}d")
    if len(hist) < 2:
        raise RuntimeError("Not enough history to compute volatility")
    closes = hist["Close"].iloc[-(window + 1):]
    log_returns = [
        math.log(closes.iloc[i] / closes.iloc[i - 1])
        for i in range(1, len(closes))
    ]
    mean = sum(log_returns) / len(log_returns)
    variance = sum((r - mean) ** 2 for r in log_returns) / (len(log_returns) - 1)
    return math.sqrt(variance * 252)


def pick_expiry(ticker: yf.Ticker, target: str | None) -> str:
    """Return the nearest available expiry (~30 days out by default)."""
    exps = ticker.options
    if not exps:
        raise RuntimeError("No options data available for this ticker")
    if target is None:
        today = date.today()
        target_date = today + timedelta(days=30)
        return min(exps, key=lambda e: abs((datetime.strptime(e, "%Y-%m-%d").date() - target_date).days))
    for e in sorted(exps):
        if e >= target:
            return e
    raise RuntimeError(f"No expiry found on or after {target}. Available: {exps}")


def pick_strike(chain, spot: float, target: float | None, option_type: str) -> float:
    """Return the strike closest to `target` (or ATM if None)."""
    df = chain.calls if option_type == "call" else chain.puts
    if df.empty:
        raise RuntimeError(f"No {option_type} contracts found for this expiry")
    strikes = df["strike"].tolist()
    anchor = target if target is not None else spot
    return min(strikes, key=lambda k: abs(k - anchor))


def time_to_expiry(expiry_str: str) -> float:
    expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
    days = (expiry - date.today()).days
    if days <= 0:
        raise RuntimeError(f"Expiry {expiry_str} is in the past")
    return days / 365.0


# ── public API ────────────────────────────────────────────────────────────────

def price_option(
    symbol: str,
    *,
    expiry: str | None = None,
    strike: float | None = None,
    option_type: str = "call",
    vol_window: int = 30,
) -> PriceResult:
    """
    Fetch live market data and return the Black-Scholes price for an option.

    Parameters
    ----------
    symbol : str
        Ticker symbol, e.g. "AAPL", "SPY".
    expiry : str, optional
        Option expiry date as YYYY-MM-DD. Defaults to the nearest ~30-day expiry.
    strike : float, optional
        Strike price. Defaults to the ATM strike.
    option_type : str
        "call" or "put". Default "call".
    vol_window : int
        Trading days of history used to compute historical volatility (default 30).

    Returns
    -------
    PriceResult
    """
    symbol = symbol.upper()
    opt = option_type.lower()
    if opt not in ("call", "put"):
        raise ValueError(f"option_type must be 'call' or 'put', got {option_type!r}")

    ticker = yf.Ticker(symbol)

    S = fetch_spot(ticker)
    r = fetch_risk_free_rate()
    sigma = historical_volatility(ticker, vol_window)
    exp_str = pick_expiry(ticker, expiry)
    T = time_to_expiry(exp_str)

    chain = ticker.option_chain(exp_str)
    K = pick_strike(chain, S, strike, opt)

    df = chain.calls if opt == "call" else chain.puts
    row = df[df["strike"] == K]
    market_mid = None
    if not row.empty:
        bid = float(row["bid"].iloc[0])
        ask = float(row["ask"].iloc[0])
        if bid > 0 and ask > 0:
            market_mid = (bid + ask) / 2.0

    bs_price, greeks = black_scholes(S, K, T, r, sigma, opt)

    return PriceResult(
        symbol=symbol,
        option_type=opt,
        S=S,
        K=K,
        T=T,
        r=r,
        sigma=sigma,
        expiry=exp_str,
        bs_price=bs_price,
        market_mid=market_mid,
        greeks=greeks,
    )
