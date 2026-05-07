# fetch_bs_params.py

Fetches live market data from Yahoo Finance and populates every Black-Scholes input parameter for a given asset, then prints the theoretical option price, all five Greeks, and a copy-pasteable parameter dict.

## Dependencies

```bash
pip install yfinance
```

Requires internet access to `query1.finance.yahoo.com`, `query2.finance.yahoo.com`, and `finance.yahoo.com`.

## Usage

```
python3 fetch_bs_params.py <SYMBOL> [--expiry YYYY-MM-DD] [--strike FLOAT] [--type call|put] [--vol-window INT]
```

### Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `SYMBOL` | yes | — | Ticker symbol (e.g. `AAPL`, `SPY`, `TSLA`) |
| `--expiry` | no | nearest ~30-day expiry | Option expiration date `YYYY-MM-DD` |
| `--strike` | no | ATM (closest to spot) | Strike price |
| `--type` | no | `call` | `call` or `put` |
| `--vol-window` | no | `30` | Trading days of history used to compute historical volatility |

## Examples

### ATM call, auto-selected expiry (~30 days out)
```bash
PYTHONPATH=. python3 fetch_bs_params.py AAPL
```

### Specific expiry and strike
```bash
PYTHONPATH=. python3 fetch_bs_params.py TSLA --expiry 2025-06-20 --strike 200
```

### OTM put
```bash
PYTHONPATH=. python3 fetch_bs_params.py SPY --type put --strike 490
```

### Use 60-day historical volatility window
```bash
PYTHONPATH=. python3 fetch_bs_params.py MSFT --vol-window 60
```

## Sample output

```
Fetching Black-Scholes parameters for AAPL (CALL)
───────────────────────────────────────────────────────
  S  (spot price)        : 189.3000
  r  (risk-free rate)    : 5.2400%  (13-wk T-bill)
  σ  (hist. volatility)  : 22.1500%  (30-day annualised)
  T  (time to expiry)    : 0.082192 yrs  [2025-06-06]
  K  (strike)            : 190.0000  (ATM)

───────────────────────────────────────────────────────
  BS price               : 4.2317
  Market mid             : 4.3500  (bid/ask spread)

  Δ  delta               : +0.4821
  Γ  gamma               : 0.048312
  Θ  theta (per day)     : -0.0891
  ν  vega  (per vol pt)  : 0.1523
  ρ  rho   (per rate pt) : 0.0412

  params = {
      "S": 189.3,
      "K": 190.0,
      "T": 0.082192,
      "r": 0.052400,
      "sigma": 0.221500,
      "option_type": "call",
  }
```

## How each parameter is sourced

| Parameter | Source |
|---|---|
| **S** — spot price | `yfinance` last trade price |
| **r** — risk-free rate | `^IRX` 13-week US T-bill yield (annualised, decimal) |
| **σ** — volatility | Annualised close-to-close historical volatility over `--vol-window` trading days |
| **T** — time to expiry | `(expiry_date − today).days / 365` |
| **K** — strike | Options chain: strike closest to spot (or to `--strike` if provided) |

The **market mid** (bid/ask midpoint) is shown alongside the BS theoretical price when bid and ask are both nonzero, so you can directly observe any mispricing or vol surface skew.

## Notes

- Historical volatility is a backward-looking estimate; the market may be pricing in a different forward volatility.
- The 13-week T-bill rate is used as the risk-free rate, consistent with short-dated options pricing convention.
- If Yahoo Finance cannot be reached, the script exits with a non-zero status and an error message.
