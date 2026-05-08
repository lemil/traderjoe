"""
End-to-end example: download an option chain and explore the matrix.

Usage:
    PYTHONPATH=. python3 example.py           # defaults to AAPL calls
    PYTHONPATH=. python3 example.py TSLA put
"""

import sys
from traderjoe.option_chain import download_option_chain, pretty_print_matrix

# ── config ────────────────────────────────────────────────────────────────────
symbol      = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
option_type = sys.argv[2] if len(sys.argv) > 2 else "call"
MAX_EXPIRIES = 4
MAX_STRIKES  = 12

# ── 1. download ───────────────────────────────────────────────────────────────
print(f"\nDownloading {symbol} {option_type} chain …")
matrix = download_option_chain(
    symbol,
    option_type=option_type,
    max_expiries=MAX_EXPIRIES,
    min_volume=10,
)

print(f"  {len(matrix.strikes)} strikes  ×  {len(matrix.expiries)} expiries  "
      f"=  {len(matrix.cells)} contracts")

# ── 2. print mid-price matrix ─────────────────────────────────────────────────
pretty_print_matrix(matrix, field="mid",
                    max_strikes=MAX_STRIKES, max_expiries=MAX_EXPIRIES)

# ── 3. print implied-volatility surface ───────────────────────────────────────
pretty_print_matrix(matrix, field="iv",
                    max_strikes=MAX_STRIKES, max_expiries=MAX_EXPIRIES)

# ── 4. print delta surface ────────────────────────────────────────────────────
pretty_print_matrix(matrix, field="delta",
                    max_strikes=MAX_STRIKES, max_expiries=MAX_EXPIRIES)

# ── 5. inspect a single cell ──────────────────────────────────────────────────
expiry = matrix.expiries[0]
# pick the ATM strike (closest to spot)
atm = min(matrix.strikes, key=lambda k: abs(k - matrix.spot))
cell = matrix.get(expiry, atm)

if cell:
    print(f"  ATM contract  —  {symbol} {option_type.upper()} {atm}  exp {expiry}")
    print(f"  {'Spot':<18}: {matrix.spot:.2f}")
    print(f"  {'Bid / Ask':<18}: {cell.bid:.2f} / {cell.ask:.2f}  (mid {cell.mid:.2f})")
    print(f"  {'IV (BS)':<18}: {cell.iv_bs:.2%}")
    print(f"  {'Delta':<18}: {cell.delta:+.4f}")
    print(f"  {'Gamma':<18}: {cell.gamma:.6f}")
    print(f"  {'Theta / day':<18}: {cell.theta:+.4f}")
    print(f"  {'Vega':<18}: {cell.vega:.4f}")
    print(f"  {'Volume':<18}: {cell.volume:,}")
    print(f"  {'Open interest':<18}: {cell.open_interest:,}")
    print(f"  {'ITM':<18}: {cell.itm}")
    print()

# ── 6. scan for highest open interest across all expiries ─────────────────────
top = sorted(matrix.cells.values(), key=lambda c: c.open_interest, reverse=True)[:5]
print(f"  Top 5 contracts by open interest:")
print(f"  {'Strike':>8}  {'Expiry':<12}  {'OI':>8}  {'Mid':>7}  {'IV':>8}")
print(f"  {'-'*52}")
for c in top:
    print(f"  {c.strike:>8.2f}  {c.expiry:<12}  {c.open_interest:>8,}  "
          f"{c.mid:>7.2f}  {c.iv_bs:>7.1%}")
print()
