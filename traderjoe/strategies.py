"""
24 option combination strategies.

Every builder function accepts market inputs (S, T, r, sigma) and computes
leg premiums via Black-Scholes.  The returned Strategy object exposes:
  - .payoff(S_T)      -> float  P&L per lot (100 shares) at expiry
  - .legs             -> list[Leg]
  - .net_premium      -> float  net cost per share (+debit / -credit)
  - .max_profit       -> float  (inf = unlimited)
  - .max_loss         -> float  (-inf = unlimited)
  - .breakevens       -> list[float]
  - .probabilities    -> Probabilities
  - .risk             -> RiskMetrics
"""

import math
from dataclasses import dataclass
from statistics import NormalDist
from typing import Callable

from traderjoe.black_scholes import black_scholes

_INF    = float("inf")
_SHARES = 100              # shares per contract
_norm   = NormalDist()


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


@dataclass(frozen=True)
class Probabilities:
    """
    Risk-neutral probabilities derived from the log-normal distribution of S_T.

    prob_profit     : P(strategy P&L > 0 at expiry)
    prob_max_profit : P(S_T in max-profit zone); nan when max profit is unlimited
    prob_max_loss   : P(S_T in max-loss zone);   nan when max loss is unlimited
    """
    prob_profit:     float
    prob_max_profit: float
    prob_max_loss:   float


@dataclass(frozen=True)
class RiskMetrics:
    """
    Aggregate risk analytics for a multi-leg strategy.

    Greeks are aggregated across all legs (per lot = 100 shares):
      delta  : $ change in portfolio value per $1 move in underlying
      gamma  : rate of delta change per $1 move in underlying
      theta  : $ time decay per calendar day
      vega   : $ change per 1 percentage-point increase in implied vol
      rho    : $ change per 1 percentage-point increase in risk-free rate

    Expected values are risk-neutral (Q-measure) integrals of the payoff
    weighted by the log-normal distribution of S_T:
      expected_pnl    : E^Q[payoff]  (per lot)
      expected_profit : E^Q[payoff · 1(payoff > 0)]  (per lot)
      expected_loss   : E^Q[payoff · 1(payoff ≤ 0)]  (per lot)

    reward_risk_ratio : max_profit / |max_loss|
                        inf  when max_profit is unlimited and max_loss is bounded
                        0.0  when max_loss is unlimited and max_profit is bounded
                        nan  when both are unlimited
    """
    delta:             float
    gamma:             float
    theta:             float
    vega:              float
    rho:               float
    expected_pnl:      float
    expected_profit:   float
    expected_loss:     float
    reward_risk_ratio: float


@dataclass
class Strategy:
    name:          str
    legs:          list
    spot:          float
    T:             float        # time horizon used for probability calculation
    r:             float
    sigma:         float
    net_premium:   float        # per share
    max_profit:    float        # per lot; inf = unlimited
    max_loss:      float        # per lot; -inf = unlimited
    breakevens:    list
    probabilities: Probabilities
    risk:          RiskMetrics
    _payoff_fn:    Callable     # (S_T: float) -> float per lot

    def payoff(self, S_T: float) -> float:
        """Total P&L per lot (100 shares) at expiry."""
        return self._payoff_fn(S_T)


# ── probability helpers ───────────────────────────────────────────────────────

def _prob_above(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Risk-neutral P(S_T > K) via Black-Scholes d2."""
    try:
        d2 = (math.log(S / K) + (r - 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        return _norm.cdf(d2)
    except (ValueError, ZeroDivisionError):
        return 0.0


def _prob_between(S: float, K_lo: float, K_hi: float,
                  T: float, r: float, sigma: float) -> float:
    """Risk-neutral P(K_lo < S_T < K_hi)."""
    p_above_lo = 1.0 if K_lo <= 0 else _prob_above(S, K_lo, T, r, sigma)
    p_above_hi = _prob_above(S, K_hi, T, r, sigma)
    return max(0.0, p_above_lo - p_above_hi)


def _find_zones(payoff_fn: Callable, target: float, S: float,
                tol: float) -> list[tuple[float, float]]:
    """Return price intervals where |payoff(p) - target| <= tol."""
    s_lo, s_hi = S * 0.001, S * 20
    n = 3000
    grid = [s_lo + (s_hi - s_lo) * i / n for i in range(n + 1)]
    in_zone, zone_lo, zones = False, 0.0, []
    for p in grid:
        hit = abs(payoff_fn(p) - target) <= tol
        if hit and not in_zone:
            zone_lo, in_zone = p, True
        elif not hit and in_zone:
            zones.append((zone_lo, p))
            in_zone = False
    if in_zone:
        zones.append((zone_lo, s_hi))
    return zones


def _compute_probs(payoff_fn: Callable, breakevens: list,
                   S: float, T: float, r: float, sigma: float,
                   max_p: float, max_l: float) -> Probabilities:
    """Compute risk-neutral Probabilities for a strategy."""
    S_MAX = S * 20
    zone_tol = 1.0  # $1 per lot absolute tolerance for zone detection

    # ── prob_profit ──────────────────────────────────────────────────────────
    bounds = [1e-6] + sorted(b for b in breakevens if 0 < b < S_MAX) + [S_MAX]
    prob_profit = 0.0
    for i in range(len(bounds) - 1):
        lo, hi = bounds[i], bounds[i + 1]
        if payoff_fn((lo + hi) / 2) > zone_tol:
            prob_profit += _prob_between(S, lo, hi, T, r, sigma)

    # ── prob_max_profit ──────────────────────────────────────────────────────
    if math.isinf(max_p):
        prob_max_profit = float("nan")
    else:
        tol = zone_tol + abs(max_p) * 0.005
        zones = _find_zones(payoff_fn, max_p, S, tol)
        prob_max_profit = sum(_prob_between(S, lo, hi, T, r, sigma) for lo, hi in zones)

    # ── prob_max_loss ────────────────────────────────────────────────────────
    if math.isinf(max_l):
        prob_max_loss = float("nan")
    else:
        tol = zone_tol + abs(max_l) * 0.005
        zones = _find_zones(payoff_fn, max_l, S, tol)
        prob_max_loss = sum(_prob_between(S, lo, hi, T, r, sigma) for lo, hi in zones)

    return Probabilities(
        prob_profit=min(max(prob_profit, 0.0), 1.0),
        prob_max_profit=prob_max_profit,
        prob_max_loss=prob_max_loss,
    )


# ── risk-metric helpers ───────────────────────────────────────────────────────

def _lognorm_pdf(S_T: float, S: float, T: float, r: float, sigma: float) -> float:
    """Log-normal PDF of S_T under risk-neutral measure Q."""
    if S_T <= 0 or T <= 0 or sigma <= 0:
        return 0.0
    mu  = math.log(S) + (r - 0.5 * sigma ** 2) * T
    std = sigma * math.sqrt(T)
    z   = (math.log(S_T) - mu) / std
    return math.exp(-0.5 * z * z) / (S_T * std * math.sqrt(2 * math.pi))


def _compute_expected_pnl(payoff_fn: Callable, S: float,
                           T: float, r: float, sigma: float
                           ) -> tuple[float, float, float]:
    """
    Numerically integrate E^Q[payoff] over the log-normal distribution of S_T.

    Returns (expected_pnl, expected_profit, expected_loss).
    Uses a log-spaced grid spanning ±5σ√T to cover the distribution tails.
    """
    n     = 2000
    s_lo  = S * math.exp(-5 * sigma * math.sqrt(T))
    s_hi  = S * math.exp(+5 * sigma * math.sqrt(T))
    ratio = s_hi / s_lo
    prices = [s_lo * ratio ** (i / n) for i in range(n + 1)]

    total = exp_profit = exp_loss = 0.0
    for i in range(n):
        lo, hi  = prices[i], prices[i + 1]
        mid     = (lo + hi) / 2
        weight  = _lognorm_pdf(mid, S, T, r, sigma) * (hi - lo)
        contrib = payoff_fn(mid) * weight
        total  += contrib
        if contrib > 0:
            exp_profit += contrib
        else:
            exp_loss   += contrib
    return total, exp_profit, exp_loss


def _compute_risk(payoff_fn: Callable, legs: list,
                  spot: float, T: float, r: float, sigma: float,
                  max_profit: float, max_loss: float,
                  *, leg_Ts: list[float] | None = None) -> RiskMetrics:
    """
    Compute RiskMetrics for a strategy.

    leg_Ts : per-leg time-to-expiry overrides (for calendar/diagonal spreads).
             If None, the strategy's T is used for all option legs.
    """
    if leg_Ts is None:
        leg_Ts = [T] * len(legs)

    # aggregate Greeks
    delta = gamma = theta = vega = rho = 0.0
    for leg, leg_T in zip(legs, leg_Ts):
        n = leg.direction * leg.contracts * _SHARES
        if leg.kind == "stock":
            delta += float(n)
        else:
            try:
                _, g = black_scholes(spot, leg.strike, leg_T, r, sigma, leg.kind)
                delta += g.delta * n
                gamma += g.gamma * n
                theta += g.theta * n
                vega  += g.vega  * n
                rho   += g.rho   * n
            except Exception:
                pass

    # expected P&L under Q
    exp_pnl, exp_profit, exp_loss = _compute_expected_pnl(payoff_fn, spot, T, r, sigma)

    # reward / risk ratio
    mp, ml = max_profit, max_loss
    if math.isinf(mp) and math.isinf(ml):
        rr = float("nan")
    elif math.isinf(mp):
        rr = float("inf")
    elif math.isinf(ml):
        rr = 0.0
    elif abs(ml) < 1e-9:
        rr = float("inf")
    else:
        rr = mp / abs(ml)

    return RiskMetrics(
        delta=delta, gamma=gamma, theta=theta, vega=vega, rho=rho,
        expected_pnl=exp_pnl, expected_profit=exp_profit, expected_loss=exp_loss,
        reward_risk_ratio=rr,
    )


# ── payoff helpers ────────────────────────────────────────────────────────────

def _bs(kind: str, S: float, K: float, T: float, r: float, sigma: float) -> float:
    price, _ = black_scholes(S, K, T, r, sigma, kind)
    return price


def _leg_payoff(leg: Leg, S_T: float) -> float:
    """P&L for one leg per share at expiry."""
    if leg.kind == "call":
        intrinsic = max(S_T - leg.strike, 0.0)
    elif leg.kind == "put":
        intrinsic = max(leg.strike - S_T, 0.0)
    else:
        intrinsic = S_T
    return leg.direction * intrinsic - leg.premium


def _payoff(legs: list, S_T: float) -> float:
    """Total P&L per lot at expiry."""
    return sum(_leg_payoff(l, S_T) * l.contracts for l in legs) * _SHARES


def _analyze(legs: list, spot: float, s_lo: float, s_hi: float,
             payoff_fn: Callable, unlimited_profit=False, unlimited_loss=False):
    """Numerically compute max profit, max loss, and breakevens."""
    strikes = sorted({l.strike for l in legs if l.kind != "stock"})
    grid = [s_lo + (s_hi - s_lo) * i / 2000 for i in range(2001)]
    for k in strikes:
        grid += [k - 0.001, k, k + 0.001]
    grid = sorted(set(round(p, 6) for p in grid if s_lo <= p <= s_hi))

    values = [payoff_fn(p) for p in grid]
    max_p = _INF if unlimited_profit else max(values)
    max_l = -_INF if unlimited_loss else min(values)

    bes = []
    for i in range(len(grid) - 1):
        v0, v1 = values[i], values[i + 1]
        if v0 == 0.0:
            bes.append(round(grid[i], 4))
        elif v0 * v1 < 0:
            lo, hi = grid[i], grid[i + 1]
            for _ in range(40):
                mid = (lo + hi) / 2
                if payoff_fn(mid) * v0 < 0:
                    hi = mid
                else:
                    lo = mid
            bes.append(round((lo + hi) / 2, 4))
    deduped: list[float] = []
    for be in bes:
        if not deduped or abs(be - deduped[-1]) > 0.05:
            deduped.append(be)
    return max_p, max_l, deduped


def _build(name: str, legs: list, spot: float,
           s_lo: float, s_hi: float,
           T: float, r: float, sigma: float,
           unlimited_profit=False, unlimited_loss=False) -> Strategy:
    net = sum(l.premium * l.contracts for l in legs)
    fn = lambda S_T: _payoff(legs, S_T)
    max_p, max_l, bes = _analyze(
        legs, spot, s_lo, s_hi, fn, unlimited_profit, unlimited_loss)
    probs = _compute_probs(fn, bes, spot, T, r, sigma, max_p, max_l)
    risk  = _compute_risk(fn, legs, spot, T, r, sigma, max_p, max_l)
    return Strategy(
        name=name, legs=legs, spot=spot, T=T, r=r, sigma=sigma,
        net_premium=net, max_profit=max_p, max_loss=max_l,
        breakevens=bes, probabilities=probs, risk=risk, _payoff_fn=fn,
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
    return _build("Bull Call Spread", legs, S, 0, K2 * 1.5, T, r, sigma)


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
    return _build("Bear Put Spread", legs, S, K1 * 0.5, S * 1.5, T, r, sigma)


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
    return _build("Bull Put Spread", legs, S, K1 * 0.5, S * 1.5, T, r, sigma)


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
    return _build("Bear Call Spread", legs, S, 0, K2 * 1.5, T, r, sigma)


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
    return _build("Long Straddle", legs, S, 0, K * 2, T, r, sigma,
                  unlimited_profit=True)


def short_straddle(S: float, K: float, T: float, r: float,
                   sigma: float, expiry: str = "T") -> Strategy:
    """Sell call + put at K. Profits from low volatility / range-bound market."""
    c = _bs("call", S, K, T, r, sigma)
    p = _bs("put",  S, K, T, r, sigma)
    legs = [
        Leg("call", -1, K, expiry, -c, 1),
        Leg("put",  -1, K, expiry, -p, 1),
    ]
    return _build("Short Straddle", legs, S, 0, K * 2, T, r, sigma,
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
    return _build("Long Strangle", legs, S, 0, K2 * 2, T, r, sigma,
                  unlimited_profit=True)


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
    return _build("Short Strangle", legs, S, 0, K2 * 2, T, r, sigma,
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
    return _build("Iron Condor", legs, S, K1 * 0.8, K4 * 1.2, T, r, sigma)


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
    return _build("Iron Butterfly", legs, S, K1 * 0.8, K3 * 1.2, T, r, sigma)


def covered_call(S: float, K: float, T: float, r: float,
                 sigma: float, expiry: str = "T") -> Strategy:
    """Long stock + short OTM call. Generates income; caps upside."""
    c = _bs("call", S, K, T, r, sigma)
    legs = [
        Leg("stock", +1, 0, "",     S,  1),
        Leg("call",  -1, K, expiry, -c, 1),
    ]
    return _build("Covered Call", legs, S, 0, K * 1.5, T, r, sigma)


def cash_secured_put(S: float, K: float, T: float, r: float,
                     sigma: float, expiry: str = "T") -> Strategy:
    """Short put backed by cash. Income strategy; obliged to buy stock at K."""
    p = _bs("put", S, K, T, r, sigma)
    legs = [Leg("put", -1, K, expiry, -p, 1)]
    return _build("Cash-Secured Put", legs, S, 0, S * 1.5, T, r, sigma)


def calendar_spread(S: float, K: float, T1: float, T2: float,
                    r: float, sigma: float,
                    expiry1: str = "T1", expiry2: str = "T2") -> Strategy:
    """
    Sell near-dated call (T1), buy far-dated call (T2) at same strike K.
    Payoff evaluated at near expiry; far option BS-valued with remaining T2-T1.
    """
    c_near = _bs("call", S, K, T1, r, sigma)
    c_far  = _bs("call", S, K, T2, r, sigma)
    legs = [
        Leg("call", -1, K, expiry1, -c_near, 1),
        Leg("call", +1, K, expiry2,  c_far,  1),
    ]
    T_rem = T2 - T1

    def _cal_payoff(S_T: float) -> float:
        near_pnl = -max(S_T - K, 0) + c_near
        try:
            far_val, _ = black_scholes(S_T, K, T_rem, r, sigma, "call")
        except Exception:
            far_val = max(S_T - K, 0)
        return (near_pnl + far_val - c_far) * _SHARES

    net = -c_near + c_far
    max_p, max_l, bes = _analyze(legs, S, S * 0.6, S * 1.4, _cal_payoff)
    probs = _compute_probs(_cal_payoff, bes, S, T1, r, sigma, max_p, max_l)
    risk  = _compute_risk(_cal_payoff, legs, S, T1, r, sigma, max_p, max_l,
                          leg_Ts=[T1, T2])
    return Strategy(
        name="Calendar Spread", legs=legs, spot=S, T=T1, r=r, sigma=sigma,
        net_premium=net, max_profit=max_p, max_loss=max_l,
        breakevens=bes, probabilities=probs, risk=risk, _payoff_fn=_cal_payoff,
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
        near_pnl = -max(S_T - K1, 0) + c1
        try:
            far_val, _ = black_scholes(S_T, K2, T_rem, r, sigma, "call")
        except Exception:
            far_val = max(S_T - K2, 0)
        return (near_pnl + far_val - c2) * _SHARES

    net = -c1 + c2
    max_p, max_l, bes = _analyze(legs, S, S * 0.6, S * 1.6, _diag_payoff)
    probs = _compute_probs(_diag_payoff, bes, S, T1, r, sigma, max_p, max_l)
    risk  = _compute_risk(_diag_payoff, legs, S, T1, r, sigma, max_p, max_l,
                          leg_Ts=[T1, T2])
    return Strategy(
        name="Diagonal Spread", legs=legs, spot=S, T=T1, r=r, sigma=sigma,
        net_premium=net, max_profit=max_p, max_loss=max_l,
        breakevens=bes, probabilities=probs, risk=risk, _payoff_fn=_diag_payoff,
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
    return _build("Butterfly Spread", legs, S, K1 * 0.8, K3 * 1.2, T, r, sigma)


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
    return _build("Condor Spread", legs, S, K1 * 0.8, K4 * 1.2, T, r, sigma)


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
    return _build("Jade Lizard", legs, S, K1 * 0.7, K3 * 1.3, T, r, sigma)


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
    return _build("Ratio Spread", legs, S, 0, K2 * 2, T, r, sigma,
                  unlimited_loss=True)


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
    return _build("Back Spread", legs, S, 0, K2 * 2, T, r, sigma,
                  unlimited_profit=True)


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
    return _build("Christmas Tree", legs, S, 0, K3 * 1.6, T, r, sigma,
                  unlimited_loss=True)


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
    return _build("Synthetic Long Stock", legs, S, 0, K * 2, T, r, sigma,
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
    return _build("Synthetic Short Stock", legs, S, 0, K * 2, T, r, sigma,
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
    return _build("Risk Reversal", legs, S, 0, K2 * 2, T, r, sigma,
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
        Leg("stock", +1, 0,  "",      S,  1),
        Leg("put",   +1, K1, expiry,  p1, 1),
        Leg("call",  -1, K2, expiry, -c2, 1),
    ]
    return _build("Collar", legs, S, 0, K2 * 1.5, T, r, sigma)


# ── pretty printer ────────────────────────────────────────────────────────────

def pretty_print_strategy(strategy: Strategy, width: int = 60) -> None:
    """Print a formatted strategy sheet with legs, analytics, and payoff chart."""
    s = strategy
    bar = "─" * (width - 2)

    print(f"\n  {bar}")
    print(f"  Strategy : {s.name}")
    print(f"  Spot     : {s.spot:.2f}   T={s.T:.4f}yr   r={s.r:.2%}   σ={s.sigma:.2%}")
    print(f"  {bar}")

    # legs table
    print(f"  {'Leg':<28} {'Strike':>8} {'Expiry':>10} {'Premium':>9}")
    print(f"  {'-' * (width - 2)}")
    for leg in s.legs:
        sign = "+" if leg.premium < 0 else "-"
        print(f"  {leg.label:<28} {leg.strike:>8.2f} {leg.expiry:>10} "
              f"  {sign}${abs(leg.premium * 100):.2f}")

    print(f"  {bar}")

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
        print(f"  Breakeven(s) : {'  /  '.join(f'{b:.2f}' for b in s.breakevens)}")
    else:
        print(f"  Breakeven(s) : none in range")

    # probabilities
    p = s.probabilities
    print(f"  {bar}")

    def _pct(v: float) -> str:
        return f"{v:>6.1%}" if not math.isnan(v) else "   n/a"

    print(f"  Prob. of profit     : {_pct(p.prob_profit)}")
    print(f"  Prob. of max profit : {_pct(p.prob_max_profit)}")
    print(f"  Prob. of max loss   : {_pct(p.prob_max_loss)}")

    # risk metrics
    rm = s.risk
    print(f"  {bar}")

    def _fmt_greek(v: float, unit: str = "") -> str:
        return f"{v:+.4f}{unit}"

    def _fmt_dollar(v: float) -> str:
        return f"${v:+.2f}"

    def _fmt_rr(v: float) -> str:
        if math.isnan(v):
            return "   n/a"
        if math.isinf(v):
            return "    ∞"
        return f"{v:.2f}×"

    print(f"  Greeks (per lot)")
    print(f"    Delta : {_fmt_greek(rm.delta):>10}   Gamma : {_fmt_greek(rm.gamma):>10}")
    print(f"    Theta : {_fmt_greek(rm.theta, '/d'):>10}   Vega  : {_fmt_greek(rm.vega, '/1%σ'):>13}")
    print(f"    Rho   : {_fmt_greek(rm.rho,   '/1%r'):>10}")
    print(f"  Expected P&L      : {_fmt_dollar(rm.expected_pnl):>10} / lot")
    print(f"    Profit zone E[·]: {_fmt_dollar(rm.expected_profit):>10} / lot")
    print(f"    Loss zone  E[·] : {_fmt_dollar(rm.expected_loss):>10} / lot")
    print(f"  Reward / Risk     : {_fmt_rr(rm.reward_risk_ratio):>8}")
    print(f"  {bar}")

    _print_payoff_chart(strategy, width)
    print()


def _print_payoff_chart(strategy: Strategy, width: int = 60) -> None:
    """Render a compact ASCII payoff diagram."""
    chart_w = width - 6
    chart_h = 12

    strikes = [l.strike for l in strategy.legs if l.kind != "stock"]
    s_lo = min(strategy.spot * 0.70, min(strikes, default=strategy.spot) * 0.85)
    s_hi = max(strategy.spot * 1.30, max(strikes, default=strategy.spot) * 1.15)

    prices  = [s_lo + (s_hi - s_lo) * i / (chart_w - 1) for i in range(chart_w)]
    payoffs = [strategy.payoff(p) for p in prices]

    p_max = max(payoffs)
    p_min = min(payoffs)

    display_max = p_max if p_max != _INF else p_min + (p_min if p_min < 0 else 1) * -2
    display_min = p_min if p_min != -_INF else p_max - abs(p_max) * 2 or -1

    def to_row(val: float) -> int:
        clamped = max(display_min, min(display_max, val))
        frac = (clamped - display_min) / (display_max - display_min + 1e-12)
        return chart_h - 1 - int(frac * (chart_h - 1))

    zero_row = to_row(0.0)
    grid = [[" "] * chart_w for _ in range(chart_h)]

    for x in range(chart_w):
        grid[zero_row][x] = "·"

    for x, val in enumerate(payoffs):
        row = max(0, min(chart_h - 1, to_row(val)))
        grid[row][x] = "█" if val >= 0 else "▄"

    spot_x = max(0, min(chart_w - 1,
                        int((strategy.spot - s_lo) / (s_hi - s_lo) * (chart_w - 1))))
    if 0 <= zero_row < chart_h:
        grid[zero_row][spot_x] = "S"

    print(f"  P&L  ^")
    for row_i, row in enumerate(grid):
        if row_i == 0 and not math.isinf(display_max):
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
