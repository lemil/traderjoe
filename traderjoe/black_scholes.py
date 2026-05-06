"""Black-Scholes option pricing model."""

import math
from dataclasses import dataclass
from statistics import NormalDist

_norm = NormalDist()
_cdf = _norm.cdf
_pdf = _norm.pdf


@dataclass(frozen=True)
class Greeks:
    delta: float
    gamma: float
    theta: float  # per calendar day
    vega: float   # per 1-point move in vol (not per 1%)
    rho: float    # per 1-point move in rate (not per 1%)


def _d1_d2(S: float, K: float, T: float, r: float, sigma: float) -> tuple[float, float]:
    """Compute d1 and d2 for the Black-Scholes formula."""
    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T
    return d1, d2


def black_scholes(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str = "call",
) -> tuple[float, Greeks]:
    """
    Price a European option using the Black-Scholes model.

    Parameters
    ----------
    S : float
        Current underlying price.
    K : float
        Strike price.
    T : float
        Time to expiration in years (e.g. 30 days → 30/365).
    r : float
        Continuously compounded risk-free rate (e.g. 0.05 for 5%).
    sigma : float
        Annualised volatility (e.g. 0.20 for 20%).
    option_type : str
        "call" or "put".

    Returns
    -------
    price : float
    greeks : Greeks
        delta, gamma, theta (per calendar day), vega (per vol point), rho (per rate point).

    Raises
    ------
    ValueError
        On invalid inputs or unknown option_type.
    """
    if S <= 0:
        raise ValueError(f"S must be positive, got {S}")
    if K <= 0:
        raise ValueError(f"K must be positive, got {K}")
    if T <= 0:
        raise ValueError(f"T must be positive, got {T}")
    if sigma <= 0:
        raise ValueError(f"sigma must be positive, got {sigma}")

    opt = option_type.lower()
    if opt not in ("call", "put"):
        raise ValueError(f"option_type must be 'call' or 'put', got {option_type!r}")

    d1, d2 = _d1_d2(S, K, T, r, sigma)
    sqrt_T = math.sqrt(T)
    disc = math.exp(-r * T)

    if opt == "call":
        price = S * _cdf(d1) - K * disc * _cdf(d2)
        delta = _cdf(d1)
        rho = K * T * disc * _cdf(d2)
    else:
        price = K * disc * _cdf(-d2) - S * _cdf(-d1)
        delta = _cdf(d1) - 1.0
        rho = -K * T * disc * _cdf(-d2)

    gamma = _pdf(d1) / (S * sigma * sqrt_T)
    vega = S * _pdf(d1) * sqrt_T
    # theta expressed per calendar day (divide annual by 365)
    theta = (
        -(S * _pdf(d1) * sigma) / (2 * sqrt_T)
        - r * K * disc * (_cdf(d2) if opt == "call" else _cdf(-d2)) * (-1 if opt == "put" else 1)
    )
    # sign correction: for put the r*K*disc term is added, not subtracted
    if opt == "put":
        theta = (
            -(S * _pdf(d1) * sigma) / (2 * sqrt_T)
            + r * K * disc * _cdf(-d2)
        )
    else:
        theta = (
            -(S * _pdf(d1) * sigma) / (2 * sqrt_T)
            - r * K * disc * _cdf(d2)
        )
    theta /= 365.0

    greeks = Greeks(delta=delta, gamma=gamma, theta=theta, vega=vega, rho=rho)
    return price, greeks


def implied_volatility(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: str = "call",
    *,
    tol: float = 1e-6,
    max_iter: int = 200,
) -> float:
    """
    Compute implied volatility via Newton-Raphson with bisection fallback.

    Parameters
    ----------
    market_price : float
        Observed option price.
    S, K, T, r : float
        Same as :func:`black_scholes`.
    option_type : str
        "call" or "put".
    tol : float
        Convergence tolerance on the price difference.
    max_iter : int
        Maximum iterations.

    Returns
    -------
    float
        Implied volatility.

    Raises
    ------
    ValueError
        If IV cannot be found within bounds or max_iter is exceeded.
    """
    # Intrinsic-value lower bound check
    disc = math.exp(-r * T)
    if option_type.lower() == "call":
        intrinsic = max(S - K * disc, 0.0)
    else:
        intrinsic = max(K * disc - S, 0.0)

    if market_price < intrinsic - tol:
        raise ValueError(
            f"market_price {market_price} is below intrinsic value {intrinsic:.6f}"
        )

    # Initial guess via Brenner-Subrahmanyam approximation
    sigma = math.sqrt(2 * math.pi / T) * market_price / S
    sigma = max(min(sigma, 10.0), 1e-4)

    lo, hi = 1e-4, 10.0

    for _ in range(max_iter):
        try:
            price, greeks = black_scholes(S, K, T, r, sigma, option_type)
        except ValueError:
            sigma = (lo + hi) / 2
            continue

        diff = price - market_price
        if abs(diff) < tol:
            return sigma

        vega = greeks.vega
        if abs(vega) > 1e-10:
            step = diff / vega
            sigma_new = sigma - step
            if lo < sigma_new < hi:
                sigma = sigma_new
                continue

        # Bisection fallback
        if diff > 0:
            hi = sigma
        else:
            lo = sigma
        sigma = (lo + hi) / 2

        if hi - lo < 1e-8:
            return sigma

    raise ValueError(f"Implied volatility did not converge after {max_iter} iterations")
