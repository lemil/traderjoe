# option_chain.py

Downloads the full option chain for a stock and structures it as a **Strike × Expiry matrix**. Each cell holds pricing data and Greeks computed via the Black-Scholes model. Includes a pretty-printer that renders the matrix as a formatted ASCII table.

## Functions

### `download_option_chain`

```python
from traderjoe.option_chain import download_option_chain

matrix = download_option_chain("AAPL", option_type="call", max_expiries=4)
```

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `symbol` | str | — | Ticker symbol (e.g. `"AAPL"`) |
| `option_type` | str | `"call"` | `"call"` or `"put"` |
| `max_expiries` | int \| None | `None` | Limit to nearest N expiry dates |
| `min_volume` | int | `0` | Exclude contracts with volume below this |
| `timeout` | int | `15` | HTTP request timeout in seconds |

**Returns** `OptionMatrix`

**Raises**
- `ValueError` — unknown `option_type`
- `RuntimeError` — ticker has no options data or spot price unavailable

---

### `pretty_print_matrix`

```python
from traderjoe.option_chain import pretty_print_matrix

pretty_print_matrix(matrix, field="mid", max_strikes=20, max_expiries=6)
```

Prints a Strike × Expiry table to stdout. Strikes are centred around ATM. ITM rows are marked with `*`.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `matrix` | OptionMatrix | — | Matrix returned by `download_option_chain` |
| `field` | str | `"mid"` | Which value to show in each cell (see table below) |
| `max_strikes` | int \| None | `20` | Cap strike rows, centred on ATM |
| `max_expiries` | int \| None | `6` | Cap expiry columns (nearest first) |
| `show_itm_marker` | bool | `True` | Append `*` to in-the-money strike labels |

**Available fields**

| `field` | Displays |
|---|---|
| `mid` | Mid price `(bid + ask) / 2` |
| `bid` | Bid price |
| `ask` | Ask price |
| `iv` | Implied volatility (Black-Scholes, annualised %) |
| `delta` | Delta `Δ` |
| `gamma` | Gamma `Γ` |
| `theta` | Theta per calendar day `Θ` |
| `vega` | Vega per vol point `ν` |
| `volume` | Daily trading volume |
| `oi` | Open interest |

---

### `OptionMatrix`

```python
matrix.symbol       # "AAPL"
matrix.option_type  # "call"
matrix.spot         # 192.0
matrix.rate         # 0.052  (13-wk T-bill)
matrix.as_of        # date(2025, 5, 7)
matrix.strikes      # [185.0, 190.0, 195.0, ...]   sorted
matrix.expiries     # ["2025-06-20", "2025-07-18", ...]  sorted

matrix.get("2025-06-20", 190.0)   # -> OptionCell | None
matrix.column("2025-06-20")       # -> list[OptionCell] sorted by strike
matrix.row(190.0)                 # -> list[OptionCell] sorted by expiry
```

### `OptionCell`

```python
cell.strike         # 190.0
cell.expiry         # "2025-06-20"
cell.bid            # 3.80
cell.ask            # 4.00
cell.mid            # 3.90
cell.last           # 3.85
cell.volume         # 500
cell.open_interest  # 2000
cell.iv_market      # 0.22   (yfinance implied vol)
cell.iv_bs          # 0.218  (IV from our BS model)
cell.delta          # +0.621
cell.gamma          # 0.0412
cell.theta          # -0.0143  (per calendar day)
cell.vega           # 0.1523
cell.itm            # True / False
```

## Examples

### Print mid prices

```python
from traderjoe.option_chain import download_option_chain, pretty_print_matrix

matrix = download_option_chain("AAPL", max_expiries=4)
pretty_print_matrix(matrix, field="mid")
```

```
  AAPL CALL Options — Mid Price
  Spot: 192.00  |  Rate: 5.24%  |  As of: 2025-05-07
  * = in the money

  ──────────────────────────────────────────────────────────────────
      Strike      2025-06-20    2025-07-18    2025-08-15    2025-09-19
  ──────────────────────────────────────────────────────────────────
     185.00 *       8.40          10.20         12.10         14.30
     190.00 *       4.10           6.50          8.70         10.90
     195.00          1.80          3.80          5.90          8.10
     200.00          0.65          2.10          3.80          5.90
  ──────────────────────────────────────────────────────────────────
```

### Print implied volatility surface

```python
pretty_print_matrix(matrix, field="iv")
```

### Print delta across strikes and expiries

```python
pretty_print_matrix(matrix, field="delta")
```

### Access cells programmatically

```python
cell = matrix.get("2025-06-20", 190.0)
if cell:
    print(f"IV: {cell.iv_bs:.1%}, Delta: {cell.delta:+.3f}")
```

## Running tests

All tests use mocked yfinance responses — no internet required:

```bash
PYTHONPATH=. python3 -m pytest tests/test_option_chain.py -v
```
