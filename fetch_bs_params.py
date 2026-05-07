"""
Fetch real market data for all Black-Scholes input parameters.

Usage:
    python3 fetch_bs_params.py AAPL
    python3 fetch_bs_params.py TSLA --expiry 2025-06-20 --strike 200
    python3 fetch_bs_params.py SPY --type put
"""

import argparse
import math
import sys
from datetime import date, datetime, timedelta

import yfinance as yf

from traderjoe.black_scholes import black_scholes


# ── helpers ──────────────────────────────────────────────────────────────────

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
        print("  [warn] Could not fetch T-bill rate; defaulting to 5%")
        return 0.05
    rate = float(hist["Close"].iloc[-1]) / 100.0
    return rate


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
    """Return the nearest expiry on or after `target` (YYYY-MM-DD), or the next available."""
    exps = ticker.options
    if not exps:
        raise RuntimeError("No options data available for this ticker")
    if target is None:
        # pick the expiry closest to 30 days out
        today = date.today()
        target_date = today + timedelta(days=30)
        best = min(exps, key=lambda e: abs((datetime.strptime(e, "%Y-%m-%d").date() - target_date).days))
        return best
    # find nearest expiry >= target
    for e in sorted(exps):
        if e >= target:
            return e
    raise RuntimeError(f"No expiry found on or after {target}. Available: {exps}")


def pick_strike(chain, spot: float, target: float | None, option_type: str) -> float:
    """Return the strike closest to `target` (or to spot if None)."""
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


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fetch Black-Scholes parameters for an asset")
    parser.add_argument("symbol", help="Ticker symbol (e.g. AAPL, SPY, TSLA)")
    parser.add_argument("--expiry", help="Option expiry date YYYY-MM-DD (default: nearest ~30d)")
    parser.add_argument("--strike", type=float, help="Strike price (default: ATM)")
    parser.add_argument("--type", dest="option_type", choices=["call", "put"], default="call")
    parser.add_argument("--vol-window", type=int, default=30, help="Days of history for HV (default: 30)")
    args = parser.parse_args()

    symbol = args.symbol.upper()
    print(f"\nFetching Black-Scholes parameters for {symbol} ({args.option_type.upper()})")
    print("─" * 55)

    ticker = yf.Ticker(symbol)

    # ── S: spot price ────────────────────────────────────────
    S = fetch_spot(ticker)
    print(f"  S  (spot price)        : {S:.4f}")

    # ── r: risk-free rate ────────────────────────────────────
    r = fetch_risk_free_rate()
    print(f"  r  (risk-free rate)    : {r:.4%}  (13-wk T-bill)")

    # ── sigma: historical volatility ─────────────────────────
    sigma = historical_volatility(ticker, args.vol_window)
    print(f"  σ  (hist. volatility)  : {sigma:.4%}  ({args.vol_window}-day annualised)")

    # ── expiry / T ───────────────────────────────────────────
    expiry = pick_expiry(ticker, args.expiry)
    T = time_to_expiry(expiry)
    print(f"  T  (time to expiry)    : {T:.6f} yrs  [{expiry}]")

    # ── K: strike ────────────────────────────────────────────
    chain = ticker.option_chain(expiry)
    K = pick_strike(chain, S, args.strike, args.option_type)
    moneyness = "ATM" if abs(K - S) / S < 0.01 else ("ITM" if (K < S and args.option_type == "call") or (K > S and args.option_type == "put") else "OTM")
    print(f"  K  (strike)            : {K:.4f}  ({moneyness})")

    # ── market price of the option ───────────────────────────
    df = chain.calls if args.option_type == "call" else chain.puts
    row = df[df["strike"] == K]
    market_mid = None
    if not row.empty:
        bid = float(row["bid"].iloc[0])
        ask = float(row["ask"].iloc[0])
        if bid > 0 and ask > 0:
            market_mid = (bid + ask) / 2.0

    # ── Black-Scholes price & Greeks ─────────────────────────
    print("\n" + "─" * 55)
    price, greeks = black_scholes(S, K, T, r, sigma, args.option_type)

    print(f"  BS price               : {price:.4f}")
    if market_mid is not None:
        print(f"  Market mid             : {market_mid:.4f}  (bid/ask spread)")
    print()
    print(f"  Δ  delta               : {greeks.delta:+.4f}")
    print(f"  Γ  gamma               : {greeks.gamma:.6f}")
    print(f"  Θ  theta (per day)     : {greeks.theta:+.4f}")
    print(f"  ν  vega  (per vol pt)  : {greeks.vega:.4f}")
    print(f"  ρ  rho   (per rate pt) : {greeks.rho:.4f}")
    print()

    # ── summary dict (machine-readable) ─────────────────────
    print("  params = {")
    print(f'      "S": {S},')
    print(f'      "K": {K},')
    print(f'      "T": {T:.6f},')
    print(f'      "r": {r:.6f},')
    print(f'      "sigma": {sigma:.6f},')
    print(f'      "option_type": "{args.option_type}",')
    print("  }")
    print()


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
