#!/usr/bin/env python3
"""
pick_strategy.py — rank all 24 option strategies for a given market prediction.

Given a predicted future price and optional confidence / volatility outlook,
this script computes the expected P&L of every applicable strategy under the
prediction's distribution and ranks them.

Usage:
  python3 pick_strategy.py --spot 100 --target 110 --days 30
  python3 pick_strategy.py -s 150 -t 130 -d 60 --vol 0.35 --confidence 0.8
  python3 pick_strategy.py -s 100 -t 100 -d 45 --vol-change down --risk defined
  python3 pick_strategy.py -s 200 -t 220 -d 30 --vol 0.25 -c 0.7 --detail
"""

import argparse
import math
from statistics import NormalDist
from typing import Callable

from traderjoe.strategies import (
    bull_call_spread, bear_put_spread, bull_put_spread, bear_call_spread,
    long_straddle, short_straddle, long_strangle, short_strangle,
    iron_condor, iron_butterfly, covered_call, cash_secured_put,
    calendar_spread, diagonal_spread, butterfly_spread, condor_spread,
    jade_lizard, ratio_spread, back_spread, christmas_tree,
    synthetic_long, synthetic_short, risk_reversal, collar,
    Strategy, pretty_print_strategy,
)

_INF = float("inf")


# ── strike utilities ──────────────────────────────────────────────────────────

def _grid(S: float) -> float:
    """Appropriate strike grid size for the given price."""
    if S < 10:  return 0.5
    if S < 30:  return 1.0
    if S < 50:  return 2.5
    if S < 200: return 5.0
    return 10.0


def _snap(price: float, g: float) -> float:
    return round(price / g) * g


def _derive_strikes(S: float, target: float, sigma: float, T: float) -> dict:
    """
    Derive a consistent set of strikes from spot, prediction target, and vol.

    For directional strategies:
      K2 = lower of (ATM, target snapped to grid)
      K3 = upper of (ATM, target)
      K1 = K2 - wing,   K4 = K3 + wing   (wing = K3 - K2)

    For neutral strategies centered on ATM:
      K_put_wing / K_call_wing  = ±1 std-dev move from ATM
      K_put_far  / K_call_far   = ±2 std-dev moves (condor outer wings)

    The 1-std-dev move (sigma*sqrt(T)*S) is used as a floor for the wing width
    so neutral strategies stay meaningful even when target ≈ spot.
    """
    g   = _grid(S)
    atm = _snap(S, g)
    tgt = _snap(target, g)
    if atm == tgt:
        tgt = atm + g if target >= S else atm - g

    # Wing width = larger of |target - ATM| or 1 std-dev move
    one_sd = max(S * sigma * math.sqrt(T), g)
    move   = abs(tgt - atm)
    wing   = max(move, one_sd)
    wing   = _snap(wing, g) or g  # snap to grid, at least one step

    K_lo = min(atm, tgt)
    K_hi = max(atm, tgt)

    return dict(
        atm=atm, target=tgt,
        # directional strikes (bracket the expected move)
        K1=max(K_lo - wing, g), K2=K_lo, K3=K_hi, K4=K_hi + wing,
        # symmetric strikes around ATM (for neutral / income strategies)
        K_put_wing=max(atm - wing, g),  K_call_wing=atm + wing,
        K_put_far=max(atm - 2*wing, g), K_call_far=atm + 2*wing,
        wing=wing,
    )


# ── prediction distribution ───────────────────────────────────────────────────

def _pred_expected_pnl(
    payoff_fn: Callable, S: float, target: float,
    confidence: float, T: float, sigma: float,
) -> float:
    """
    E[payoff] under the trader's subjective distribution.

    The distribution is log-normal blended between:
      - Risk-neutral Q (confidence = 0): centred on S·e^{-½σ²T}
      - Point prediction (confidence = 1): centred on target

    blend_mu  = c·log(target) + (1-c)·(log(S) - ½σ²·T)
    blend_sig = σ·(1-c) + 0.005   [floor so we don't divide by zero]
    """
    rn_mu    = math.log(S) - 0.5 * sigma**2 * T
    pred_mu  = confidence * math.log(max(target, 1e-9)) + (1 - confidence) * rn_mu
    pred_sig = sigma * (1 - confidence) + 0.005

    n     = 500
    s_lo  = math.exp(pred_mu - 5 * pred_sig * math.sqrt(T))
    s_hi  = math.exp(pred_mu + 5 * pred_sig * math.sqrt(T))
    ratio = s_hi / s_lo

    total = 0.0
    sq2pi = math.sqrt(2 * math.pi)
    std_t = pred_sig * math.sqrt(T)
    for i in range(n):
        lo  = s_lo * ratio ** (i / n)
        hi  = s_lo * ratio ** ((i + 1) / n)
        mid = (lo + hi) / 2
        z   = (math.log(mid) - pred_mu) / std_t
        pdf = math.exp(-0.5 * z * z) / (mid * std_t * sq2pi)
        total += payoff_fn(mid) * pdf * (hi - lo)
    return total


# ── strategy catalogue ────────────────────────────────────────────────────────

def _build_candidates(S: float, T: float, r: float, sigma: float,
                      sk: dict) -> list[tuple[Strategy, set]]:
    """
    Instantiate all 24 strategies using the derived strikes.

    Returns list of (Strategy, tags) where tags describe directional bias,
    vol outlook, and risk profile.
    """
    atm         = sk["atm"]
    K1, K2, K3, K4 = sk["K1"], sk["K2"], sk["K3"], sk["K4"]
    K_pw, K_cw  = sk["K_put_wing"], sk["K_call_wing"]
    K_pf, K_cf  = sk["K_put_far"],  sk["K_call_far"]
    T2          = T * 2

    candidates: list[tuple[Strategy, set]] = []

    def _add(fn, *tags):
        try:
            candidates.append((fn(), set(tags)))
        except Exception:
            pass

    # 1. Directional spreads
    _add(lambda: bull_call_spread(S, K2, K3, T, r, sigma),
         "bullish", "defined_risk")
    _add(lambda: bear_put_spread(S, K2, K3, T, r, sigma),
         "bearish", "defined_risk")
    _add(lambda: bull_put_spread(S, K2, K3, T, r, sigma),
         "bullish", "defined_risk")
    _add(lambda: bear_call_spread(S, K2, K3, T, r, sigma),
         "bearish", "defined_risk")

    # 2. Volatility strategies (symmetric around ATM)
    _add(lambda: long_straddle(S, atm, T, r, sigma),
         "neutral", "long_vol")
    _add(lambda: short_straddle(S, atm, T, r, sigma),
         "neutral", "short_vol", "defined_risk")
    _add(lambda: long_strangle(S, K_pw, K_cw, T, r, sigma),
         "neutral", "long_vol")
    _add(lambda: short_strangle(S, K_pw, K_cw, T, r, sigma),
         "neutral", "short_vol", "unlimited_risk")

    # 3. Income / defined-risk
    _add(lambda: iron_condor(S, K_pf, K_pw, K_cw, K_cf, T, r, sigma),
         "neutral", "short_vol", "defined_risk")
    _add(lambda: iron_butterfly(S, K_pw, atm, K_cw, T, r, sigma),
         "neutral", "short_vol", "defined_risk")
    _add(lambda: covered_call(S, K_cw, T, r, sigma),
         "neutral_bullish", "short_vol", "defined_risk")
    _add(lambda: cash_secured_put(S, K_pw, T, r, sigma),
         "neutral_bullish", "short_vol", "defined_risk")
    _add(lambda: calendar_spread(S, atm, T, T2, r, sigma),
         "neutral", "short_vol", "defined_risk")
    _add(lambda: diagonal_spread(S, atm, K_cw, T, T2, r, sigma),
         "neutral_bullish", "short_vol", "defined_risk")

    # 4. Multi-leg advanced
    _add(lambda: butterfly_spread(S, K_pw, atm, K_cw, T, r, sigma),
         "neutral", "short_vol", "defined_risk")
    _add(lambda: condor_spread(S, K_pf, K_pw, K_cw, K_cf, T, r, sigma),
         "neutral", "short_vol", "defined_risk")
    _add(lambda: jade_lizard(S, K2, K3, K4, T, r, sigma),
         "neutral_bullish", "short_vol")
    _add(lambda: ratio_spread(S, K2, K3, T, r, sigma),
         "neutral_bullish", "short_vol", "unlimited_risk")
    _add(lambda: back_spread(S, K2, K3, T, r, sigma),
         "bullish", "long_vol")
    _add(lambda: christmas_tree(S, K2, K3, K4, T, r, sigma),
         "bullish", "short_vol", "unlimited_risk")

    # 5. Synthetics / stock replacement
    _add(lambda: synthetic_long(S, atm, T, r, sigma),
         "bullish", "long_vol", "unlimited_risk")
    _add(lambda: synthetic_short(S, atm, T, r, sigma),
         "bearish", "long_vol", "unlimited_risk")
    _add(lambda: risk_reversal(S, K_pw, K_cw, T, r, sigma),
         "bullish", "long_vol", "unlimited_risk")
    _add(lambda: collar(S, K_pw, K_cw, T, r, sigma),
         "neutral", "defined_risk")

    return candidates


# ── scoring ───────────────────────────────────────────────────────────────────

def _score(
    st: Strategy, tags: set,
    S: float, target: float, T: float, sigma: float,
    confidence: float, vol_change: str, risk_tol: str,
) -> tuple[float, float]:
    """
    Score a strategy against the prediction. Returns (composite_score, exp_pnl).

    Composite score = expected_pnl_pred
                    + direction_bonus   (±10% / ±30%)
                    + vol_bonus         (±10% / ±15%)
                    - risk_penalty      (40% if tolerance is 'defined')
    """
    exp_pnl = _pred_expected_pnl(st.payoff, S, target, confidence, T, sigma)

    # Direction
    move_pct = (target - S) / S
    if abs(move_pct) < 0.02:
        outlook = "neutral"
    elif move_pct > 0:
        outlook = "bullish"
    else:
        outlook = "bearish"

    dir_bonus = 0.0
    aligned = outlook in tags or f"neutral_{outlook}" in tags
    opposed = (
        (outlook == "bullish" and "bearish" in tags) or
        (outlook == "bearish" and "bullish" in tags)
    )
    if aligned:
        dir_bonus = abs(exp_pnl) * 0.10
    elif opposed:
        dir_bonus = -abs(exp_pnl) * 0.30

    # Vol outlook
    vol_bonus = 0.0
    if vol_change == "up":
        if "long_vol" in tags:
            vol_bonus = abs(exp_pnl) * 0.10
        elif "short_vol" in tags:
            vol_bonus = -abs(exp_pnl) * 0.15
    elif vol_change == "down":
        if "short_vol" in tags:
            vol_bonus = abs(exp_pnl) * 0.10
        elif "long_vol" in tags:
            vol_bonus = -abs(exp_pnl) * 0.15

    # Risk tolerance
    risk_penalty = 0.0
    if risk_tol == "defined" and "unlimited_risk" in tags:
        risk_penalty = abs(exp_pnl) * 0.40

    score = exp_pnl + dir_bonus + vol_bonus - risk_penalty
    return score, exp_pnl


# ── output ────────────────────────────────────────────────────────────────────

def _fmt_pnl(v: float) -> str:
    if math.isinf(v) and v > 0: return "unlim"
    if math.isinf(v) and v < 0: return "-unlim"
    return f"${v:+.0f}"


def _fmt_rr(rr: float) -> str:
    if math.isnan(rr):  return " n/a"
    if math.isinf(rr):  return "  ∞"
    return f"{rr:.1f}×"


def _print_header(S: float, target: float, T: float, r: float, sigma: float,
                  confidence: float, vol_change: str) -> None:
    move_pct = (target - S) / S
    outlook  = ("bullish" if move_pct > 0.02
                else "bearish" if move_pct < -0.02
                else "neutral")
    bar = "═" * 72
    print(f"\n{bar}")
    print(" STRATEGY SELECTOR")
    print(bar)
    print(f"  Spot          : ${S:.2f}")
    print(f"  Prediction    : ${target:.2f}  ({move_pct:+.1%})  →  {outlook.upper()}")
    print(f"  Horizon       : {T * 365:.0f} days  ({T:.4f} yr)")
    print(f"  Vol (σ)       : {sigma:.1%}  |  Vol outlook : {vol_change}")
    print(f"  Rate (r)      : {r:.2%}  |  Confidence  : {confidence:.0%}")
    print(bar)


def _print_table(ranked: list[tuple], top_n: int) -> None:
    cols = f"  {'#':<3} {'Strategy':<26} {'Score':>9} {'E[P&L]':>9} " \
           f"{'@Target':>9} {'MaxProfit':>10} {'MaxLoss':>10} {'R/R':>6}"
    print(f"\n{cols}")
    print(f"  {'-' * 84}")
    for rank, (score, exp_pnl, at_tgt, st) in enumerate(ranked[:top_n], 1):
        mp  = _fmt_pnl(st.max_profit)
        ml  = _fmt_pnl(st.max_loss)
        rr  = _fmt_rr(st.risk.reward_risk_ratio)
        print(f"  {rank:<3} {st.name:<26} {score:>+9.2f} {exp_pnl:>+9.2f} "
              f"{at_tgt:>+9.2f} {mp:>10} {ml:>10} {rr:>6}")

    print(f"\n  Score   = prediction-adjusted composite (direction + vol + risk fit)")
    print(f"  E[P&L]  = expected P&L / lot under prediction distribution")
    print(f"  @Target = P&L / lot if stock ends exactly at the predicted price")
    print(f"  R/R     = max profit / |max loss|  (reward-to-risk ratio)")
    print()


def _explain_prediction(S: float, target: float, confidence: float,
                        vol_change: str, risk_tol: str) -> None:
    move_pct = (target - S) / S
    direction = ("bullish" if move_pct > 0.02
                 else "bearish" if move_pct < -0.02
                 else "neutral / range-bound")
    print(f"  Interpretation: you expect a {direction} move of "
          f"{abs(move_pct):.1%} ({confidence:.0%} confidence),")
    vol_msg = {"up": "with rising volatility", "down": "with falling volatility",
               "flat": "with stable volatility"}[vol_change]
    risk_msg = {"defined": "preferring defined-risk strategies",
                "unlimited": "open to unlimited-risk strategies",
                "any": "with no risk-profile restriction"}[risk_tol]
    print(f"  {vol_msg}, {risk_msg}.")
    print()


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Rank 24 option strategies for a given market prediction.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("-s", "--spot",       type=float, required=True,
                    help="Current stock / underlying price")
    ap.add_argument("-t", "--target",     type=float, required=True,
                    help="Predicted price at expiry")
    ap.add_argument("-d", "--days",       type=int,   required=True,
                    help="Days until expiry")
    ap.add_argument("-r", "--rate",       type=float, default=0.05,
                    help="Risk-free rate (default: 0.05)")
    ap.add_argument("-v", "--vol",        type=float, default=0.20,
                    help="Implied/historical annualised vol (default: 0.20)")
    ap.add_argument("-c", "--confidence", type=float, default=0.5,
                    help="Prediction confidence 0–1 (default: 0.5)")
    ap.add_argument("--vol-change",       choices=["up", "down", "flat"], default="flat",
                    help="Expected vol direction: up | down | flat (default: flat)")
    ap.add_argument("--risk",             choices=["defined", "unlimited", "any"], default="any",
                    help="Risk tolerance: defined | unlimited | any (default: any)")
    ap.add_argument("--top",              type=int, default=5,
                    help="Number of top strategies to show (default: 5)")
    ap.add_argument("--detail",           action="store_true",
                    help="Print full strategy sheet for the #1 ranked pick")

    args = ap.parse_args()

    S          = args.spot
    target     = args.target
    T          = args.days / 365.0
    r          = args.rate
    sigma      = args.vol
    confidence = max(0.0, min(1.0, args.confidence))
    vol_change = args.vol_change
    risk_tol   = args.risk

    if T <= 0:
        ap.error("--days must be positive")
    if sigma <= 0:
        ap.error("--vol must be positive")
    if S <= 0 or target <= 0:
        ap.error("--spot and --target must be positive")

    # Derive strikes
    sk = _derive_strikes(S, target, sigma, T)

    # Build all strategies
    candidates = _build_candidates(S, T, r, sigma, sk)

    # Filter by risk tolerance
    if risk_tol == "defined":
        candidates = [(st, tags) for st, tags in candidates
                      if "unlimited_risk" not in tags]
    elif risk_tol == "unlimited":
        candidates = [(st, tags) for st, tags in candidates
                      if "unlimited_risk" in tags]

    # Score each strategy
    rows: list[tuple] = []
    for st, tags in candidates:
        score, exp_pnl = _score(
            st, tags, S, target, T, sigma, confidence, vol_change, risk_tol)
        at_tgt = st.payoff(target)
        rows.append((score, exp_pnl, at_tgt, st))

    ranked = sorted(rows, key=lambda x: x[0], reverse=True)

    # Print results
    _print_header(S, target, T, r, sigma, confidence, vol_change)
    _explain_prediction(S, target, confidence, vol_change, risk_tol)
    _print_table(ranked, args.top)

    # Optionally print full detail of the top pick
    if args.detail and ranked:
        top_st = ranked[0][3]
        print(f"  ── Full details: {top_st.name} ──")
        pretty_print_strategy(top_st)


if __name__ == "__main__":
    main()
