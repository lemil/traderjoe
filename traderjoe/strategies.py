"""
24 option combination strategies.

Every builder function accepts market inputs (S, T, r, sigma) and computes
leg premiums via Black-Scholes.  The returned Strategy object exposes:
  - .payoff(S_T)  -> float  P&L per lot (100 shares) at expiry
  - .legs         -> list[Leg]
  - .net_premium  -> float  net cost per share (+debit / -credit)
  - .max_profit   -> float  (inf = unlimited)
  - .max_loss     -> float  (-inf = unlimited)
  - .breakevens   -> list[float]
"""

import math
from dataclasses import dataclass
from typing import Callable

from traderjoe.black_scholes import black_scholes

_INF = float("inf")
_SHARES = 100          # shares per contract


# ── core data model ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Leg:
    kind:      str    # "call" | "put" | "stock"
    direction: int    # +1 long, -1 short
    strike:    float  # 0 for stock legs
    expiry:    str    # "YYYY-MM-DD" label, "" for stock
    premium:   float  # cost per share: >0 paid, <0 received
    contracts: int    # number of contracts (1 = 100 shares)

    @property
    def label(self) -> str:
        d = "Long" if self.direction == 1 else "Short"
        if self.kind == "stock":
            return f"{d} Stock"
        return f"{d} {self.kind.capitalize()} K={self.strike}"


@dataclass
class Strategy:
    name:        str
    legs:        list
    spot:        float
    net_premium: float          # per share
    max_profit:  float          # per lot; inf = unlimited
    max_loss:    float          # per lot; -inf = unlimited
    breakevens:  list
    _payoff_fn:  Callable       # (S_T: float) -> float per lot

    def payoff(self, S_T: float) -> float:
        """Total P&L per lot (100 shares) at expiry."""
        return self._payoff_fn(S_T)


# ── internal helpers ──────────────────────────────────────────────────────────

def _bs(kind: str, S: float, K: float, T: float, r: float, sigma: float) -> float:
    price, _ = black_scholes(S, K, T, r, sigma, kind)
    return price


def _leg_payoff(leg: Leg, S_T: float) -> float:
    """P&L for one leg per share at expiry."""
    if leg.kind == "call":
        intrinsic = max(S_T - leg.strike, 0.0)
    elif leg.kind == "put":
        intrinsic = max(leg.strike - S_T, 0.0)
    else:                          # stock
        intrinsic = S_T
    return leg.direction * intrinsic - leg.premium


def _payoff(legs: list, S_T: float) -> float:
    """Total P&L per lot at expiry."""
    return sum(_leg_payoff(l, S_T) * l.contracts for l in legs) * _SHARES


def _analyze(legs: list, spot: float, s_lo: float, s_hi: float,
             payoff_fn: Callable, unlimited_profit=False, unlimited_loss=False):
    """
    Numerically compute max profit, max loss, and breakevens.
    Critical points are evaluated at every strike + a fine grid.
    """
    strikes = sorted({l.strike for l in legs if l.kind != "stock"})
    grid = [s_lo + (s_hi - s_lo) * i / 2000 for i in range(2001)]
    # include strike boundary points
    for k in strikes:
        grid += [k - 0.001, k, k + 0.001]
    grid = sorted(set(round(p, 6) for p in grid if s_lo <= p <= s_hi))

    values = [payoff_fn(p) for p in grid]

    max_p = _INF if unlimited_profit else max(values)
    max_l = -_INF if unlimited_loss else min(values)

    # breakevens: sign changes
    bes = []
    for i in range(len(grid) - 1):
        v0, v1 = values[i], values[i + 1]
        if v0 == 0.0:
            bes.append(round(grid[i], 4))
        elif v0 * v1 < 0:          # sign change → bisect
            lo, hi = grid[i], grid[i + 1]
            for _ in range(40):
                mid = (lo + hi) / 2
                if payoff_fn(mid) * v0 < 0:
                    hi = mid
                else:
                    lo = mid
            bes.append(round((lo + hi) / 2, 4))
    # deduplicate close breakevens
    deduped = []
    for be in bes:
        if not deduped or abs(be - deduped[-1]) > 0.05:
            deduped.append(be)

    return max_p, max_l, deduped


def _build(name: str, legs: list, spot: float,
           s_lo: float, s_hi: float,
           unlimited_profit=False, unlimited_loss=False) -> Strategy:
    net = sum(l.premium * l.contracts for l in legs)
    fn = lambda S_T: _payoff(legs, S_T)
    max_p, max_l, bes = _analyze(
        legs, spot, s_lo, s_hi, fn, unlimited_profit, unlimited_loss)
    return Strategy(
        name=name, legs=legs, spot=spot,
        net_premium=net, max_profit=max_p, max_loss=max_l,
        breakevens=bes, _payoff_fn=fn,
    )


# ── 1. DIRECTIONAL SPREADS ────────────────────────────────────────────────────

def bull_call_spread(S: float, K1: float, K2: float,
                     T: float, r: float, sigma: float,
                     expiry: str = "T") -> Strategy:
    """Buy call K1, sell call K2 (K1 < K2). Bullish debit spread."""
    c1 = _bs("call", S, K1, T, r, sigma)
    c2 = _bs("call", S, K2, T, r, sigma)
    legs = [
        Leg("call", +1, K1, expiry,  c1, 1),
        Leg("call", -1, K2, expiry, -c2, 1),
    ]
    return _build("Bull Call Spread", legs, S, 0, K2 * 1.5)


def bear_put_spread(S: float, K1: float, K2: float,
                    T: float, r: float, sigma: float,
                    expiry: str = "T") -> Strategy:
    """Buy put K2, sell put K1 (K1 < K2). Bearish debit spread."""
    p1 = _bs("put", S, K1, T, r, sigma)
    p2 = _bs("put", S, K2, T, r, sigma)
    legs = [
        Leg("put", +1, K2, expiry,  p2, 1),
        Leg("put", -1, K1, expiry, -p1, 1),
    ]
    return _build("Bear Put Spread", legs, S, K1 * 0.5, S * 1.5)


def bull_put_spread(S: float, K1: float, K2: float,
                    T: float, r: float, sigma: float,
                    expiry: str = "T") -> Strategy:
    """Sell put K2, buy put K1 (K1 < K2). Bullish credit spread."""
    p1 = _bs("put", S, K1, T, r, sigma)
    p2 = _bs("put", S, K2, T, r, sigma)
    legs = [
        Leg("put", -1, K2, expiry, -p2, 1),
        Leg("put", +1, K1, expiry,  p1, 1),
    ]
    return _build("Bull Put Spread", legs, S, K1 * 0.5, S * 1.5)


def bear_call_spread(S: float, K1: float, K2: float,
                     T: float, r: float, sigma: float,
                     expiry: str = "T") -> Strategy:
    """Sell call K1, buy call K2 (K1 < K2). Bearish credit spread."""
    c1 = _bs("call", S, K1, T, r, sigma)
    c2 = _bs("call", S, K2, T, r, sigma)
    legs = [
        Leg("call", -1, K1, expiry, -c1, 1),
        Leg("call", +1, K2, expiry,  c2, 1),
    ]
    return _build("Bear Call Spread", legs, S, 0, K2 * 1.5)


# ── 2. VOLATILITY STRATEGIES ──────────────────────────────────────────────────

def long_straddle(S: float, K: float, T: float, r: float,
                  sigma: float, expiry: str = "T") -> Strategy:
    """Buy call + put at K. Profits from large moves in either direction."""
    c = _bs("call", S, K, T, r, sigma)
    p = _bs("put",  S, K, T, r, sigma)
    legs = [
        Leg("call", +1, K, expiry, c, 1),
        Leg("put",  +1, K, expiry, p, 1),
    ]
    return _build("Long Straddle", legs, S, 0, K * 2, unlimited_profit=True)


def short_straddle(S: float, K: float, T: float, r: float,
                   sigma: float, expiry: str = "T") -> Strategy:
    """Sell call + put at K. Profits from low volatility / range-bound market."""
    c = _bs("call", S, K, T, r, sigma)
    p = _bs("put",  S, K, T, r, sigma)
    legs = [
        Leg("call", -1, K, expiry, -c, 1),
        Leg("put",  -1, K, expiry, -p, 1),
    ]
    return _build("Short Straddle", legs, S, 0, K * 2,
                  unlimited_loss=True)


def long_strangle(S: float, K1: float, K2: float,
                  T: float, r: float, sigma: float,
                  expiry: str = "T") -> Strategy:
    """Buy OTM put K1 + OTM call K2 (K1 < K2). Cheaper straddle alternative."""
    p = _bs("put",  S, K1, T, r, sigma)
    c = _bs("call", S, K2, T, r, sigma)
    legs = [
        Leg("put",  +1, K1, expiry, p, 1),
        Leg("call", +1, K2, expiry, c, 1),
    ]
    return _build("Long Strangle", legs, S, 0, K2 * 2, unlimited_profit=True)


def short_strangle(S: float, K1: float, K2: float,
                   T: float, r: float, sigma: float,
                   expiry: str = "T") -> Strategy:
    """Sell OTM put K1 + OTM call K2 (K1 < K2). Wide profit zone, unlimited risk."""
    p = _bs("put",  S, K1, T, r, sigma)
    c = _bs("call", S, K2, T, r, sigma)
    legs = [
        Leg("put",  -1, K1, expiry, -p, 1),
        Leg("call", -1, K2, expiry, -c, 1),
    ]
    return _build("Short Strangle", legs, S, 0, K2 * 2,
                  unlimited_loss=True)


# ── 3. INCOME / DEFINED-RISK ──────────────────────────────────────────────────

def iron_condor(S: float, K1: float, K2: float, K3: float, K4: float,
                T: float, r: float, sigma: float,
                expiry: str = "T") -> Strategy:
    """
    Short strangle (K2, K3) + long wings (K1, K4).
    K1 < K2 < K3 < K4. Net credit; max profit between K2 and K3.
    """
    p1 = _bs("put",  S, K1, T, r, sigma)
    p2 = _bs("put",  S, K2, T, r, sigma)
    c3 = _bs("call", S, K3, T, r, sigma)
    c4 = _bs("call", S, K4, T, r, sigma)
    legs = [
        Leg("put",  +1, K1, expiry,  p1, 1),
        Leg("put",  -1, K2, expiry, -p2, 1),
        Leg("call", -1, K3, expiry, -c3, 1),
        Leg("call", +1, K4, expiry,  c4, 1),
    ]
    return _build("Iron Condor", legs, S, K1 * 0.8, K4 * 1.2)


def iron_butterfly(S: float, K1: float, K2: float, K3: float,
                   T: float, r: float, sigma: float,
                   expiry: str = "T") -> Strategy:
    """
    Short ATM straddle (K2) + long OTM wings (K1 put, K3 call).
    K1 < K2 < K3. Net credit; max profit at K2.
    """
    p1 = _bs("put",  S, K1, T, r, sigma)
    c2 = _bs("call", S, K2, T, r, sigma)
    p2 = _bs("put",  S, K2, T, r, sigma)
    c3 = _bs("call", S, K3, T, r, sigma)
    legs = [
        Leg("put",  +1, K1, expiry,  p1, 1),
        Leg("put",  -1, K2, expiry, -p2, 1),
        Leg("call", -1, K2, expiry, -c2, 1),
        Leg("call", +1, K3, expiry,  c3, 1),
    ]
    return _build("Iron Butterfly", legs, S, K1 * 0.8, K3 * 1.2)


def covered_call(S: float, K: float, T: float, r: float,
                 sigma: float, expiry: str = "T") -> Strategy:
    """Long stock + short OTM call. Generates income; caps upside."""
    c = _bs("call", S, K, T, r, sigma)
    legs = [
        Leg("stock", +1, 0, "",     S,  1),
        Leg("call",  -1, K, expiry, -c, 1),
    ]
    return _build("Covered Call", legs, S, 0, K * 1.5)


def cash_secured_put(S: float, K: float, T: float, r: float,
                     sigma: float, expiry: str = "T") -> Strategy:
    """Short put backed by cash. Income strategy; obliged to buy stock at K."""
    p = _bs("put", S, K, T, r, sigma)
    legs = [Leg("put", -1, K, expiry, -p, 1)]
    return _build("Cash-Secured Put", legs, S, 0, S * 1.5)


def calendar_spread(S: float, K: float, T1: float, T2: float,
                    r: float, sigma: float,
                    expiry1: str = "T1", expiry2: str = "T2") -> Strategy:
    """
    Sell near-dated call (T1), buy far-dated call (T2) at same strike K.
    Payoff evaluated at near expiry, far option valued by BS with remaining T2-T1.
    """
    c_near = _bs("call", S, K, T1, r, sigma)
    c_far  = _bs("call", S, K, T2, r, sigma)
    legs = [
        Leg("call", -1, K, expiry1, -c_near, 1),
        Leg("call", +1, K, expiry2,  c_far,  1),
    ]
    T_rem = T2 - T1

    def _cal_payoff(S_T: float) -> float:
        # near leg expired; far leg still has T_rem remaining
        near_pnl = (-max(S_T - K, 0) + c_near)
        try:
            far_val, _ = black_scholes(S_T, K, T_rem, r, sigma, "call")
        except Exception:
            far_val = max(S_T - K, 0)
        far_pnl = far_val - c_far
        return (near_pnl + far_pnl) * _SHARES

    net = -c_near + c_far
    max_p, max_l, bes = _analyze(legs, S, S * 0.6, S * 1.4, _cal_payoff)
    return Strategy(
        name="Calendar Spread", legs=legs, spot=S,
        net_premium=net, max_profit=max_p, max_loss=max_l,
        breakevens=bes, _payoff_fn=_cal_payoff,
    )


def diagonal_spread(S: float, K1: float, K2: float,
                    T1: float, T2: float, r: float, sigma: float,
                    expiry1: str = "T1", expiry2: str = "T2") -> Strategy:
    """
    Sell near-dated call K1 (T1), buy far-dated call K2 (T2). K2 > K1 typically.
    Payoff at near expiry; far option BS-valued with remaining T2-T1.
    """
    c1 = _bs("call", S, K1, T1, r, sigma)
    c2 = _bs("call", S, K2, T2, r, sigma)
    legs = [
        Leg("call", -1, K1, expiry1, -c1, 1),
        Leg("call", +1, K2, expiry2,  c2, 1),
    ]
    T_rem = T2 - T1

    def _diag_payoff(S_T: float) -> float:
        near_pnl = (-max(S_T - K1, 0) + c1)
        try:
            far_val, _ = black_scholes(S_T, K2, T_rem, r, sigma, "call")
        except Exception:
            far_val = max(S_T - K2, 0)
        far_pnl = far_val - c2
        return (near_pnl + far_pnl) * _SHARES

    net = -c1 + c2
    max_p, max_l, bes = _analyze(legs, S, S * 0.6, S * 1.6, _diag_payoff)
    return Strategy(
        name="Diagonal Spread", legs=legs, spot=S,
        net_premium=net, max_profit=max_p, max_loss=max_l,
        breakevens=bes, _payoff_fn=_diag_payoff,
    )


# ── 4. MULTI-LEG ADVANCED ─────────────────────────────────────────────────────

def butterfly_spread(S: float, K1: float, K2: float, K3: float,
                     T: float, r: float, sigma: float,
                     expiry: str = "T") -> Strategy:
    """
    Buy call K1, sell 2 calls K2, buy call K3 (K2-K1 = K3-K2).
    Max profit at K2; defined risk.
    """
    c1 = _bs("call", S, K1, T, r, sigma)
    c2 = _bs("call", S, K2, T, r, sigma)
    c3 = _bs("call", S, K3, T, r, sigma)
    legs = [
        Leg("call", +1, K1, expiry,  c1, 1),
        Leg("call", -1, K2, expiry, -c2, 2),
        Leg("call", +1, K3, expiry,  c3, 1),
    ]
    return _build("Butterfly Spread", legs, S, K1 * 0.8, K3 * 1.2)


def condor_spread(S: float, K1: float, K2: float, K3: float, K4: float,
                  T: float, r: float, sigma: float,
                  expiry: str = "T") -> Strategy:
    """
    Buy call K1, sell call K2, sell call K3, buy call K4 (K1<K2<K3<K4).
    Wider profit zone than butterfly.
    """
    c1 = _bs("call", S, K1, T, r, sigma)
    c2 = _bs("call", S, K2, T, r, sigma)
    c3 = _bs("call", S, K3, T, r, sigma)
    c4 = _bs("call", S, K4, T, r, sigma)
    legs = [
        Leg("call", +1, K1, expiry,  c1, 1),
        Leg("call", -1, K2, expiry, -c2, 1),
        Leg("call", -1, K3, expiry, -c3, 1),
        Leg("call", +1, K4, expiry,  c4, 1),
    ]
    return _build("Condor Spread", legs, S, K1 * 0.8, K4 * 1.2)


def jade_lizard(S: float, K1: float, K2: float, K3: float,
                T: float, r: float, sigma: float,
                expiry: str = "T") -> Strategy:
    """
    Short OTM put K1, short OTM call K2, long OTM call K3 (K1 < S < K2 < K3).
    No upside risk when net credit > K3 - K2.
    """
    p1 = _bs("put",  S, K1, T, r, sigma)
    c2 = _bs("call", S, K2, T, r, sigma)
    c3 = _bs("call", S, K3, T, r, sigma)
    legs = [
        Leg("put",  -1, K1, expiry, -p1, 1),
        Leg("call", -1, K2, expiry, -c2, 1),
        Leg("call", +1, K3, expiry,  c3, 1),
    ]
    return _build("Jade Lizard", legs, S, K1 * 0.7, K3 * 1.3)


def ratio_spread(S: float, K1: float, K2: float,
                 T: float, r: float, sigma: float,
                 ratio: int = 2, expiry: str = "T") -> Strategy:
    """
    Buy 1 call K1, sell `ratio` calls K2 (K1 < K2).
    Profits moderately from upside; naked short above K2.
    """
    c1 = _bs("call", S, K1, T, r, sigma)
    c2 = _bs("call", S, K2, T, r, sigma)
    legs = [
        Leg("call", +1, K1, expiry,  c1, 1),
        Leg("call", -1, K2, expiry, -c2, ratio),
    ]
    return _build("Ratio Spread", legs, S, 0, K2 * 2, unlimited_loss=True)


def back_spread(S: float, K1: float, K2: float,
                T: float, r: float, sigma: float,
                ratio: int = 2, expiry: str = "T") -> Strategy:
    """
    Sell 1 call K1, buy `ratio` calls K2 (K1 < K2).
    Long vol / long gamma; benefits from strong upside move.
    """
    c1 = _bs("call", S, K1, T, r, sigma)
    c2 = _bs("call", S, K2, T, r, sigma)
    legs = [
        Leg("call", -1, K1, expiry, -c1, 1),
        Leg("call", +1, K2, expiry,  c2, ratio),
    ]
    return _build("Back Spread", legs, S, 0, K2 * 2, unlimited_profit=True)


def christmas_tree(S: float, K1: float, K2: float, K3: float,
                   T: float, r: float, sigma: float,
                   expiry: str = "T") -> Strategy:
    """
    Buy call K1, sell call K2, sell call K3 (K1 < K2 < K3).
    Bullish with reduced cost; unlimited risk above K3.
    """
    c1 = _bs("call", S, K1, T, r, sigma)
    c2 = _bs("call", S, K2, T, r, sigma)
    c3 = _bs("call", S, K3, T, r, sigma)
    legs = [
        Leg("call", +1, K1, expiry,  c1, 1),
        Leg("call", -1, K2, expiry, -c2, 1),
        Leg("call", -1, K3, expiry, -c3, 1),
    ]
    return _build("Christmas Tree", legs, S, 0, K3 * 1.6, unlimited_loss=True)


# ── 5. SYNTHETIC / STOCK REPLACEMENT ─────────────────────────────────────────

def synthetic_long(S: float, K: float, T: float, r: float,
                   sigma: float, expiry: str = "T") -> Strategy:
    """Long call + short put at same strike K. Replicates long stock exposure."""
    c = _bs("call", S, K, T, r, sigma)
    p = _bs("put",  S, K, T, r, sigma)
    legs = [
        Leg("call", +1, K, expiry,  c, 1),
        Leg("put",  -1, K, expiry, -p, 1),
    ]
    return _build("Synthetic Long Stock", legs, S, 0, K * 2,
                  unlimited_profit=True, unlimited_loss=True)


def synthetic_short(S: float, K: float, T: float, r: float,
                    sigma: float, expiry: str = "T") -> Strategy:
    """Short call + long put at same strike K. Replicates short stock exposure."""
    c = _bs("call", S, K, T, r, sigma)
    p = _bs("put",  S, K, T, r, sigma)
    legs = [
        Leg("call", -1, K, expiry, -c, 1),
        Leg("put",  +1, K, expiry,  p, 1),
    ]
    return _build("Synthetic Short Stock", legs, S, 0, K * 2,
                  unlimited_profit=True, unlimited_loss=True)


def risk_reversal(S: float, K1: float, K2: float,
                  T: float, r: float, sigma: float,
                  expiry: str = "T") -> Strategy:
    """
    Long OTM call K2 + short OTM put K1 (K1 < S < K2).
    Bullish; low/zero cost. Profits from upside, exposed to downside.
    """
    p1 = _bs("put",  S, K1, T, r, sigma)
    c2 = _bs("call", S, K2, T, r, sigma)
    legs = [
        Leg("put",  -1, K1, expiry, -p1, 1),
        Leg("call", +1, K2, expiry,  c2, 1),
    ]
    return _build("Risk Reversal", legs, S, 0, K2 * 2,
                  unlimited_profit=True, unlimited_loss=True)


def collar(S: float, K1: float, K2: float,
           T: float, r: float, sigma: float,
           expiry: str = "T") -> Strategy:
    """
    Long stock + long put K1 + short call K2 (K1 < S < K2).
    Protects downside; caps upside. Often near zero-cost.
    """
    p1 = _bs("put",  S, K1, T, r, sigma)
    c2 = _bs("call", S, K2, T, r, sigma)
    legs = [
        Leg("stock", +1, 0,  "",     S,  1),
        Leg("put",   +1, K1, expiry, p1, 1),
        Leg("call",  -1, K2, expiry, -c2, 1),
    ]
    return _build("Collar", legs, S, 0, K2 * 1.5)


# ── pretty printer ────────────────────────────────────────────────────────────

def pretty_print_strategy(strategy: Strategy, width: int = 60) -> None:
    """Print a formatted strategy sheet with legs, analytics, and payoff chart."""
    s = strategy
    sep = "─" * width

    print(f"\n  {'─' * (width - 2)}")
    print(f"  Strategy : {s.name}")
    print(f"  Spot     : {s.spot:.2f}")
    print(f"  {'─' * (width - 2)}")

    # legs table
    print(f"  {'Leg':<28} {'Strike':>8} {'Expiry':>10} {'Premium':>9}")
    print(f"  {'-' * (width - 2)}")
    for leg in s.legs:
        sign = "+" if leg.premium < 0 else "-"
        print(f"  {leg.label:<28} {leg.strike:>8.2f} {leg.expiry:>10} "
              f"  {sign}${abs(leg.premium * 100):.2f}")

    print(f"  {'─' * (width - 2)}")

    # analytics
    net_sign = "debit" if s.net_premium > 0 else "credit"
    print(f"  Net premium  : {'$':>3}{abs(s.net_premium * 100):>7.2f} / contract  ({net_sign})")

    if s.max_profit == _INF:
        print(f"  Max profit   : {'unlimited':>12}")
    else:
        print(f"  Max profit   : {'$':>3}{s.max_profit:>7.2f} / lot")

    if s.max_loss == -_INF:
        print(f"  Max loss     : {'unlimited':>12}")
    else:
        print(f"  Max loss     : {'$':>3}{s.max_loss:>7.2f} / lot")

    if s.breakevens:
        be_str = "  /  ".join(f"{b:.2f}" for b in s.breakevens)
        print(f"  Breakeven(s) : {be_str}")
    else:
        print(f"  Breakeven(s) : none in range")

    print(f"  {'─' * (width - 2)}")

    # ASCII payoff chart
    _print_payoff_chart(strategy, width)
    print()


def _print_payoff_chart(strategy: Strategy, width: int = 60) -> None:
    """Render a compact ASCII payoff diagram."""
    chart_w = width - 6
    chart_h = 12

    # price range: spot ± 30% but at least covering all strikes
    strikes = [l.strike for l in strategy.legs if l.kind != "stock"]
    s_lo = min(strategy.spot * 0.70, min(strikes, default=strategy.spot) * 0.85)
    s_hi = max(strategy.spot * 1.30, max(strikes, default=strategy.spot) * 1.15)

    prices = [s_lo + (s_hi - s_lo) * i / (chart_w - 1) for i in range(chart_w)]
    payoffs = [strategy.payoff(p) for p in prices]

    p_max = max(payoffs)
    p_min = min(payoffs)
    p_range = p_max - p_min or 1.0

    # clamp chart height for unlimited scenarios
    display_max = p_max if p_max != _INF else p_min + p_range
    display_min = p_min if p_min != -_INF else p_max - p_range

    def to_row(val: float) -> int:
        clamped = max(display_min, min(display_max, val))
        frac = (clamped - display_min) / (display_max - display_min + 1e-12)
        return chart_h - 1 - int(frac * (chart_h - 1))

    zero_row = to_row(0.0)

    grid = [[" "] * chart_w for _ in range(chart_h)]

    # draw zero line
    for x in range(chart_w):
        grid[zero_row][x] = "·"

    # draw payoff curve
    for x, val in enumerate(payoffs):
        r = to_row(val)
        r = max(0, min(chart_h - 1, r))
        grid[r][x] = "█" if val >= 0 else "▄"

    # spot marker on zero line
    spot_x = int((strategy.spot - s_lo) / (s_hi - s_lo) * (chart_w - 1))
    spot_x = max(0, min(chart_w - 1, spot_x))
    if 0 <= zero_row < chart_h:
        grid[zero_row][spot_x] = "S"

    # print
    print(f"  P&L  ^")
    for row_i, row in enumerate(grid):
        if row_i == 0 and display_max != _INF:
            label = f"{display_max:+.0f}"
        elif row_i == zero_row:
            label = "  $0 "
        elif row_i == chart_h - 1:
            label = f"{display_min:+.0f}"
        else:
            label = "     "
        print(f"  {label:>5}|{''.join(row)}")
    print(f"       +{'─' * chart_w}>")
    print(f"       {s_lo:>6.1f}{' ' * (chart_w - 14)}{s_hi:>6.1f}  price")
