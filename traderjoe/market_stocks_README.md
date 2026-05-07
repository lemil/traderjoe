# market_stocks.py

Fetches the complete list of US-listed equity securities from the NASDAQ Trader public data files. Covers NASDAQ, NYSE, NYSE MKT (AMEX), NYSE ARCA, BATS, and IEXG. No API key required.

## Data source

Two pipe-delimited files published daily by NASDAQ:

| File | Contents |
|---|---|
| `nasdaqlisted.txt` | All NASDAQ-listed securities |
| `otherlisted.txt` | All non-NASDAQ US-listed securities (NYSE, AMEX, ARCA, …) |

Test-issue symbols (used for exchange testing only) are always excluded.

## Functions

### `get_all_stocks`

```python
from traderjoe.market_stocks import get_all_stocks

stocks = get_all_stocks(include_etfs=True, exchanges=None, timeout=15)
```

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `include_etfs` | bool | `True` | Include ETF securities |
| `exchanges` | list[str] \| None | `None` | Filter by exchange name(s). `None` returns all. Case-insensitive. |
| `timeout` | int | `15` | HTTP request timeout in seconds |

**Valid exchange names:** `"NASDAQ"`, `"NYSE"`, `"NYSE MKT"`, `"NYSE ARCA"`, `"BATS"`, `"IEXG"`

**Returns** `list[Stock]`

**Raises** `RuntimeError` if both data files fail to fetch.

---

### `get_symbols`

```python
from traderjoe.market_stocks import get_symbols

symbols = get_symbols(include_etfs=True, exchanges=None, timeout=15)
```

Convenience wrapper — same parameters as `get_all_stocks`, returns `list[str]` of ticker symbols only.

---

### `Stock` dataclass

```python
@dataclass(frozen=True)
class Stock:
    symbol:          str   # ticker (e.g. "AAPL")
    name:            str   # full security name
    exchange:        str   # e.g. "NASDAQ", "NYSE", "NYSE ARCA"
    market_category: str   # NASDAQ only: Q=Global Select, G=Global, S=Capital
    etf:             bool  # True if the security is an ETF
    test_issue:      bool  # always False (test issues are filtered out)
```

## Examples

### Get all US-listed stocks and ETFs

```python
from traderjoe.market_stocks import get_all_stocks

stocks = get_all_stocks()
print(f"Total securities: {len(stocks)}")
# Total securities: ~12000+
```

### Get only common stocks (no ETFs) on NYSE

```python
stocks = get_all_stocks(include_etfs=False, exchanges=["NYSE"])
print([s.symbol for s in stocks[:5]])
# ['A', 'AA', 'AAC', 'AACI', 'AAFG']
```

### Get all symbols as a flat list

```python
from traderjoe.market_stocks import get_symbols

symbols = get_symbols(include_etfs=False)
print(len(symbols))  # ~8000–9000 common stocks
```

### Combine with Black-Scholes for batch pricing

```python
from traderjoe.market_stocks import get_symbols

# Get all NASDAQ symbols to loop over for data fetching
nasdaq_symbols = get_symbols(exchanges=["NASDAQ"], include_etfs=False)
```

## Running tests

Tests use mocked HTTP responses and run without internet access:

```bash
PYTHONPATH=. python3 -m pytest tests/test_market_stocks.py -v
```
