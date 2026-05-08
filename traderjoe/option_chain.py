"""Download option chains and structure them as a Strike × Expiry matrix."""

import math
from dataclasses import dataclass, field
from datetime import date, datetime

import yfinance as yf

from traderjoe.black_scholes import black_scholes, implied_volatility


# ── data model ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class OptionCell:
    strike:        float
    expiry:        str
    bid:           float
    ask:           float
    mid:           float
    last:          float
    volume:        int
    open_interest: int
    iv_market:     float   # yfinance implied vol (annualised)
    iv_bs:         float   # IV backed out via our BS model
    delta:         float
    gamma:         float
    theta:         float
    vega:          float
    itm:           bool


@dataclass
class OptionMatrix:
    symbol:      str
    option_type: str          # "call" or "put"
    spot:        float
    rate:        float        # risk-free rate used for Greeks
    as_of:       date
    strikes:     list[float]  # sorted
    expiries:    list[str]    # sorted YYYY-MM-DD
    cells:       dict         # (expiry, strike) -> OptionCell

    def get(self, expiry: str, strike: float) -> OptionCell | None:
        return self.cells.get((expiry, strike))

    def column(self, expiry: str) -> list[OptionCell]:
        """All cells for a given expiry, sorted by strike."""
        return sorted(
            [c for (e, _), c in self.cells.items() if e == expiry],
            key=lambda c: c.strike,
        )

    def row(self, strike: float) -> list[OptionCell]:
        """All cells for a given strike, sorted by expiry."""
        return sorted(
            [c for (_, s), c in self.cells.items() if s == strike],
            key=lambda c: c.expiry,
        )


# ── helpers ──────────────────────────────────────────────────────────────────

def _risk_free_rate(timeout: int = 10) -> float:
    try:
        irx = yf.Ticker("^IRX")
        hist = irx.history(period="5d", timeout=timeout)
        if not hist.empty:
            return float(hist["Close"].iloc[-1]) / 100.0
    except Exception:
        pass
    return 0.05


def _time_to_expiry(expiry_str: str) -> float:
    expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
    days = (expiry - date.today()).days
    return max(days, 1) / 365.0


def _compute_bs_fields(
    spot: float,
    strike: float,
    T: float,
    r: float,
    option_type: str,
    mid: float,
) -> tuple[float, float, float, float, float]:
    """Returns (iv_bs, delta, gamma, theta, vega)."""
    try:
        iv = implied_volatility(mid, spot, strike, T, r, option_type)
        _, g = black_scholes(spot, strike, T, r, iv, option_type)
        return iv, g.delta, g.gamma, g.theta, g.vega
    except Exception:
        return float("nan"), float("nan"), float("nan"), float("nan"), float("nan")


# ── main downloader ───────────────────────────────────────────────────────────

def download_option_chain(
    symbol: str,
    option_type: str = "call",
    *,
    max_expiries: int | None = None,
    min_volume: int = 0,
    timeout: int = 15,
) -> OptionMatrix:
    """
    Download the full option chain for `symbol` and return an OptionMatrix.

    Parameters
    ----------
    symbol : str
        Ticker symbol (e.g. "AAPL").
    option_type : str
        "call" or "put".
    max_expiries : int | None
        Limit to the nearest N expiry dates. None fetches all.
    min_volume : int
        Exclude contracts with volume below this threshold (0 = include all).
    timeout : int
        HTTP timeout in seconds.

    Returns
    -------
    OptionMatrix
        strikes × expiries grid with pricing and Greeks in each cell.

    Raises
    ------
    ValueError
        On unknown option_type.
    RuntimeError
        If the ticker has no options data.
    """
    opt = option_type.lower()
    if opt not in ("call", "put"):
        raise ValueError(f"option_type must be 'call' or 'put', got {option_type!r}")

    ticker = yf.Ticker(symbol.upper())

    expiries = ticker.options
    if not expiries:
        raise RuntimeError(f"No options data available for {symbol!r}")

    if max_expiries is not None:
        expiries = expiries[:max_expiries]

    # spot price
    try:
        hist = ticker.history(period="1d", timeout=timeout)
        spot = float(hist["Close"].iloc[-1])
    except Exception as exc:
        raise RuntimeError(f"Could not fetch spot price for {symbol!r}: {exc}") from exc

    r = _risk_free_rate(timeout)

    cells: dict = {}
    all_strikes: set[float] = set()
    all_expiries: list[str] = []

    for expiry in expiries:
        try:
            chain = ticker.option_chain(expiry)
        except Exception:
            continue

        df = chain.calls if opt == "call" else chain.puts
        if df.empty:
            continue

        T = _time_to_expiry(expiry)
        all_expiries.append(expiry)

        for _, row in df.iterrows():
            strike = float(row["strike"])
            bid    = float(row.get("bid", 0) or 0)
            ask    = float(row.get("ask", 0) or 0)
            last   = float(row.get("lastPrice", 0) or 0)
            vol    = int(row.get("volume", 0) or 0)
            oi     = int(row.get("openInterest", 0) or 0)
            iv_mkt = float(row.get("impliedVolatility", float("nan")) or float("nan"))

            if vol < min_volume:
                continue

            mid = (bid + ask) / 2.0 if bid > 0 and ask > 0 else last
            if mid <= 0:
                continue

            iv_bs, delta, gamma, theta, vega = _compute_bs_fields(spot, strike, T, r, opt, mid)

            itm = (strike < spot) if opt == "call" else (strike > spot)

            all_strikes.add(strike)
            cells[(expiry, strike)] = OptionCell(
                strike=strike, expiry=expiry,
                bid=bid, ask=ask, mid=mid, last=last,
                volume=vol, open_interest=oi,
                iv_market=iv_mkt, iv_bs=iv_bs,
                delta=delta, gamma=gamma, theta=theta, vega=vega,
                itm=itm,
            )

    if not cells:
        raise RuntimeError(f"No option contracts found for {symbol!r} after filtering")

    return OptionMatrix(
        symbol=symbol.upper(),
        option_type=opt,
        spot=spot,
        rate=r,
        as_of=date.today(),
        strikes=sorted(all_strikes),
        expiries=sorted(all_expiries),
        cells=cells,
    )


# ── pretty printer ────────────────────────────────────────────────────────────

_FIELDS = {
    "mid":   ("Mid Price",  lambda c: f"{c.mid:.2f}"),
    "bid":   ("Bid",        lambda c: f"{c.bid:.2f}"),
    "ask":   ("Ask",        lambda c: f"{c.ask:.2f}"),
    "iv":    ("IV (BS)",    lambda c: f"{c.iv_bs:.1%}" if not math.isnan(c.iv_bs) else "  n/a "),
    "delta": ("Delta",      lambda c: f"{c.delta:+.3f}" if not math.isnan(c.delta) else "  n/a "),
    "gamma": ("Gamma",      lambda c: f"{c.gamma:.4f}" if not math.isnan(c.gamma) else "  n/a "),
    "theta": ("Theta/day",  lambda c: f"{c.theta:+.4f}" if not math.isnan(c.theta) else "  n/a "),
    "vega":  ("Vega",       lambda c: f"{c.vega:.4f}" if not math.isnan(c.vega) else "  n/a "),
    "volume":("Volume",     lambda c: f"{c.volume:,}"),
    "oi":    ("Open Int",   lambda c: f"{c.open_interest:,}"),
}

_ITM_MARKER = "*"   # appended to strike label for in-the-money rows


def pretty_print_matrix(
    matrix: OptionMatrix,
    field: str = "mid",
    *,
    max_strikes: int | None = 20,
    max_expiries: int | None = 6,
    show_itm_marker: bool = True,
) -> None:
    """
    Print the OptionMatrix as a formatted Strike × Expiry table.

    Parameters
    ----------
    matrix : OptionMatrix
    field : str
        Which value to display in each cell. One of:
        "mid", "bid", "ask", "iv", "delta", "gamma", "theta", "vega",
        "volume", "oi".
    max_strikes : int | None
        Cap the number of strikes shown (centred around ATM). None = all.
    max_expiries : int | None
        Cap the number of expiry columns shown. None = all.
    show_itm_marker : bool
        Append "*" to in-the-money strike labels.
    """
    if field not in _FIELDS:
        raise ValueError(f"field must be one of {list(_FIELDS)}, got {field!r}")

    label, fmt = _FIELDS[field]

    # ── select strikes centred on ATM ────────────────────────────────────────
    strikes = matrix.strikes
    if max_strikes and len(strikes) > max_strikes:
        atm_idx = min(range(len(strikes)), key=lambda i: abs(strikes[i] - matrix.spot))
        half = max_strikes // 2
        lo = max(0, atm_idx - half)
        hi = lo + max_strikes
        if hi > len(strikes):
            hi = len(strikes)
            lo = max(0, hi - max_strikes)
        strikes = strikes[lo:hi]

    # ── select expiries ──────────────────────────────────────────────────────
    expiries = matrix.expiries
    if max_expiries and len(expiries) > max_expiries:
        expiries = expiries[:max_expiries]

    # ── column widths ────────────────────────────────────────────────────────
    strike_col_w = 12
    cell_w = max(10, max(len(e) for e in expiries) + 2)

    # ── header ───────────────────────────────────────────────────────────────
    opt_label = matrix.option_type.upper()
    print(f"\n  {matrix.symbol} {opt_label} Options — {label}")
    print(f"  Spot: {matrix.spot:.2f}  |  Rate: {matrix.rate:.2%}  |  As of: {matrix.as_of}")
    if show_itm_marker:
        print(f"  {_ITM_MARKER} = in the money")

    sep = "─" * (strike_col_w + 1 + (cell_w + 1) * len(expiries))
    print(f"\n  {sep}")

    # column headers
    header = f"  {'Strike':>{strike_col_w - 2}}"
    for exp in expiries:
        header += f"  {exp:^{cell_w - 2}}"
    print(header)
    print(f"  {sep}")

    # ── rows ─────────────────────────────────────────────────────────────────
    for strike in strikes:
        # determine ITM for this strike
        itm = (strike < matrix.spot) if matrix.option_type == "call" else (strike > matrix.spot)
        marker = _ITM_MARKER if (itm and show_itm_marker) else " "
        strike_label = f"{strike:>8.2f} {marker}"

        row = f"  {strike_label:>{strike_col_w}}"
        for exp in expiries:
            cell = matrix.get(exp, strike)
            if cell is None:
                val = "-"
            else:
                val = fmt(cell)
            row += f"  {val:^{cell_w - 2}}"
        print(row)

    print(f"  {sep}\n")
