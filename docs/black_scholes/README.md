# black_scholes.py

European option pricing using the Black-Scholes model. Pure Python stdlib — no external dependencies.

## Functions

### `black_scholes`

```python
from traderjoe.black_scholes import black_scholes

price, greeks = black_scholes(S, K, T, r, sigma, option_type="call")
```

**Parameters**

| Parameter | Type | Description |
|---|---|---|
| `S` | float | Current underlying price |
| `K` | float | Strike price |
| `T` | float | Time to expiration in years (e.g. 30 days → `30/365`) |
| `r` | float | Continuously compounded risk-free rate (e.g. `0.05` for 5%) |
| `sigma` | float | Annualised volatility (e.g. `0.20` for 20%) |
| `option_type` | str | `"call"` (default) or `"put"` |

**Returns** `(price: float, greeks: Greeks)`

**Raises** `ValueError` on invalid inputs (non-positive S/K/T/sigma, unknown option_type).

---

### `implied_volatility`

```python
from traderjoe.black_scholes import implied_volatility

iv = implied_volatility(market_price, S, K, T, r, option_type="call")
```

Solves for the volatility that makes the Black-Scholes price equal to the observed market price. Uses Newton-Raphson with bisection fallback.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `market_price` | float | — | Observed option price |
| `S` | float | — | Spot price |
| `K` | float | — | Strike price |
| `T` | float | — | Time to expiration in years |
| `r` | float | — | Risk-free rate |
| `option_type` | str | `"call"` | `"call"` or `"put"` |
| `tol` | float | `1e-6` | Convergence tolerance on price difference |
| `max_iter` | int | `200` | Maximum iterations |

**Returns** `float` — implied volatility

**Raises** `ValueError` if the market price is below intrinsic value or IV does not converge.

---

### `Greeks` dataclass

```python
@dataclass(frozen=True)
class Greeks:
    delta: float   # rate of price change vs underlying
    gamma: float   # rate of delta change vs underlying
    theta: float   # time decay per calendar day
    vega:  float   # price sensitivity per 1-point vol move (not per 1%)
    rho:   float   # price sensitivity per 1-point rate move (not per 1%)
```

## Examples

### Price an ATM call

```python
from traderjoe.black_scholes import black_scholes

price, g = black_scholes(S=100, K=100, T=1.0, r=0.05, sigma=0.20, option_type="call")
print(f"Price : {price:.4f}")   # 10.4506
print(f"Delta : {g.delta:.4f}") # 0.6368
print(f"Theta : {g.theta:.4f}") # -0.0152  (per calendar day)
```

### Price a put and verify put-call parity

```python
import math
call, _ = black_scholes(100, 100, 1.0, 0.05, 0.20, "call")
put,  _ = black_scholes(100, 100, 1.0, 0.05, 0.20, "put")

parity = call - put - (100 - 100 * math.exp(-0.05 * 1.0))
print(f"Parity error: {parity:.2e}")  # ~0.00e+00
```

### Compute implied volatility

```python
from traderjoe.black_scholes import black_scholes, implied_volatility

price, _ = black_scholes(100, 105, 0.25, 0.05, 0.20, "call")
iv = implied_volatility(price, S=100, K=105, T=0.25, r=0.05, option_type="call")
print(f"IV: {iv:.4%}")  # 20.0000%
```

## Greek conventions

| Greek | Unit |
|---|---|
| theta | per **calendar** day (annual ÷ 365) |
| vega  | per **1-point** move in volatility (e.g. 0.20 → 0.21) |
| rho   | per **1-point** move in rate (e.g. 0.05 → 0.06) |

To convert vega to "per 1% move" divide by 100. To convert rho similarly, divide by 100.

## Running tests

```bash
PYTHONPATH=. python3 -m pytest tests/ -v
```

17 tests covering: ATM prices, put-call parity, Greek signs and ranges, IV round-trips (ATM and OTM), and input validation.
