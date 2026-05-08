"""
CLI wrapper around traderjoe.pricer.price_option.

Usage:
    python -m traderjoe.fetch_bs_params AAPL
    python -m traderjoe.fetch_bs_params TSLA --expiry 2025-06-20 --strike 200
    python -m traderjoe.fetch_bs_params SPY --type put
"""

import argparse
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from traderjoe.pricer import price_option


def main():
    parser = argparse.ArgumentParser(description="Black-Scholes option pricer")
    parser.add_argument("symbol", help="Ticker symbol (e.g. AAPL, SPY, TSLA)")
    parser.add_argument("--expiry", help="Option expiry date YYYY-MM-DD (default: nearest ~30d)")
    parser.add_argument("--strike", type=float, help="Strike price (default: ATM)")
    parser.add_argument("--type", dest="option_type", choices=["call", "put"], default="call")
    parser.add_argument("--vol-window", type=int, default=30, help="Days of history for HV (default: 30)")
    args = parser.parse_args()

    print(f"\nFetching Black-Scholes parameters for {args.symbol.upper()} ({args.option_type.upper()})")
    print("─" * 55)

    result = price_option(
        args.symbol,
        expiry=args.expiry,
        strike=args.strike,
        option_type=args.option_type,
        vol_window=args.vol_window,
    )

    moneyness = (
        "ATM" if abs(result.K - result.S) / result.S < 0.01
        else ("ITM" if (result.K < result.S and result.option_type == "call") or (result.K > result.S and result.option_type == "put")
              else "OTM")
    )

    print(f"  S  (spot price)        : {result.S:.4f}")
    print(f"  r  (risk-free rate)    : {result.r:.4%}  (13-wk T-bill)")
    print(f"  σ  (hist. volatility)  : {result.sigma:.4%}  ({args.vol_window}-day annualised)")
    print(f"  T  (time to expiry)    : {result.T:.6f} yrs  [{result.expiry}]")
    print(f"  K  (strike)            : {result.K:.4f}  ({moneyness})")
    print("\n" + "─" * 55)
    print(f"  BS price               : {result.bs_price:.4f}")
    if result.market_mid is not None:
        print(f"  Market mid             : {result.market_mid:.4f}  (bid/ask spread)")
    print()
    print(f"  Δ  delta               : {result.greeks.delta:+.4f}")
    print(f"  Γ  gamma               : {result.greeks.gamma:.6f}")
    print(f"  Θ  theta (per day)     : {result.greeks.theta:+.4f}")
    print(f"  ν  vega  (per vol pt)  : {result.greeks.vega:.4f}")
    print(f"  ρ  rho   (per rate pt) : {result.greeks.rho:.4f}")
    print()
    print("  params = {")
    print(f'      "S": {result.S},')
    print(f'      "K": {result.K},')
    print(f'      "T": {result.T:.6f},')
    print(f'      "r": {result.r:.6f},')
    print(f'      "sigma": {result.sigma:.6f},')
    print(f'      "option_type": "{result.option_type}",')
    print("  }")
    print()


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
