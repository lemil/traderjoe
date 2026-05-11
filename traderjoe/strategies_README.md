# strategies.py

24 option combination strategies built on the Black-Scholes model. Every builder function computes leg premiums automatically and returns a `Strategy` object with payoff function, analytics, and a pretty-printer.

## Quick start

```python
from traderjoe.strategies import iron_condor, pretty_print_strategy

st = iron_condor(S=100, K1=90, K2=95, K3=105, K4=110, T=0.25, r=0.05, sigma=0.20)
pretty_print_strategy(st)
print(st.payoff(100))   # P&L at expiry if stock stays at 100
```

## Strategy reference

### 1. Directional spreads

| Function | Legs | Outlook | Cost |
|---|---|---|---|
| `bull_call_spread(S, K1, K2, T, r, sigma)` | Long call K1, short call K2 | Bullish | Debit |
| `bear_put_spread(S, K1, K2, T, r, sigma)` | Long put K2, short put K1 | Bearish | Debit |
| `bull_put_spread(S, K1, K2, T, r, sigma)` | Short put K2, long put K1 | Bullish | Credit |
| `bear_call_spread(S, K1, K2, T, r, sigma)` | Short call K1, long call K2 | Bearish | Credit |

### 2. Volatility strategies

| Function | Legs | Outlook |
|---|---|---|
| `long_straddle(S, K, T, r, sigma)` | Long call + put at K | Long vol — big move either way |
| `short_straddle(S, K, T, r, sigma)` | Short call + put at K | Short vol — range-bound |
| `long_strangle(S, K1, K2, T, r, sigma)` | Long OTM put K1 + OTM call K2 | Long vol (cheaper than straddle) |
| `short_strangle(S, K1, K2, T, r, sigma)` | Short OTM put K1 + OTM call K2 | Short vol (wider profit zone) |

### 3. Income / defined-risk

| Function | Legs | Notes |
|---|---|---|
| `iron_condor(S, K1, K2, K3, K4, T, r, sigma)` | Short strangle K2/K3 + long wings K1/K4 | Max profit between K2–K3 |
| `iron_butterfly(S, K1, K2, K3, T, r, sigma)` | Short straddle K2 + long wings K1/K3 | Max profit at K2 |
| `covered_call(S, K, T, r, sigma)` | Long stock + short call K | Generates income; caps upside |
| `cash_secured_put(S, K, T, r, sigma)` | Short put K | Obliged to buy stock at K |
| `calendar_spread(S, K, T1, T2, r, sigma)` | Short near call T1 + long far call T2 | Profits from time decay difference |
| `diagonal_spread(S, K1, K2, T1, T2, r, sigma)` | Short near call K1/T1 + long far call K2/T2 | Calendar + direction |

### 4. Multi-leg advanced

| Function | Legs | Notes |
|---|---|---|
| `butterfly_spread(S, K1, K2, K3, T, r, sigma)` | Long K1, short 2×K2, long K3 | Max profit at K2; low cost |
| `condor_spread(S, K1, K2, K3, K4, T, r, sigma)` | Long K1, short K2, short K3, long K4 | Wider profit zone than butterfly |
| `jade_lizard(S, K1, K2, K3, T, r, sigma)` | Short put K1, short call K2, long call K3 | No upside risk if credit > K3−K2 |
| `ratio_spread(S, K1, K2, T, r, sigma, ratio=2)` | Long 1 call K1, short N calls K2 | Profits moderately; naked above K2 |
| `back_spread(S, K1, K2, T, r, sigma, ratio=2)` | Short 1 call K1, long N calls K2 | Long vol/gamma; strong upside move |
| `christmas_tree(S, K1, K2, K3, T, r, sigma)` | Long call K1, short K2, short K3 | Bullish; reduced cost vs spread |

### 5. Synthetic / stock replacement

| Function | Legs | Notes |
|---|---|---|
| `synthetic_long(S, K, T, r, sigma)` | Long call + short put at K | Replicates long stock |
| `synthetic_short(S, K, T, r, sigma)` | Short call + long put at K | Replicates short stock |
| `risk_reversal(S, K1, K2, T, r, sigma)` | Short OTM put K1 + long OTM call K2 | Bullish; often near zero cost |
| `collar(S, K1, K2, T, r, sigma)` | Long stock + long put K1 + short call K2 | Downside protection; capped upside |

## Parameters (all strategies)

| Parameter | Description |
|---|---|
| `S` | Current underlying price |
| `K`, `K1`…`K4` | Strike prices (must satisfy K1 < K2 < K3 < K4 where applicable) |
| `T`, `T1`, `T2` | Time to expiry in years (`T1 < T2` for calendar/diagonal) |
| `r` | Continuously compounded risk-free rate (e.g. `0.05`) |
| `sigma` | Annualised volatility (e.g. `0.20`) |
| `expiry` | Optional label string for the expiry date (e.g. `"2025-06-20"`) |

## Strategy object

```python
st.name          # "Iron Condor"
st.legs          # list[Leg]
st.spot          # 100.0
st.T             # time to expiry (years)
st.r             # risk-free rate
st.sigma         # implied / historical vol
st.net_premium   # per share: >0 = debit, <0 = credit
st.max_profit    # per lot (100 shares); float('inf') = unlimited
st.max_loss      # per lot; float('-inf') = unlimited
st.breakevens    # list[float]
st.probabilities # Probabilities object (see below)
st.risk          # RiskMetrics object (see below)
st.payoff(S_T)   # P&L per lot at expiry price S_T
```

### Probabilities object

```python
p = st.probabilities
p.prob_profit      # P(P&L > 0 at expiry), risk-neutral
p.prob_max_profit  # P(S_T in max-profit zone); nan if unlimited
p.prob_max_loss    # P(S_T in max-loss zone);   nan if unlimited
```

Probabilities are computed under the risk-neutral (Q) measure using the
log-normal distribution of `S_T` implied by Black-Scholes.

### RiskMetrics object

```python
rm = st.risk

# Aggregate Greeks (per lot = 100 shares)
rm.delta   # $ P&L change per $1 move in underlying
rm.gamma   # delta change per $1 move in underlying
rm.theta   # $ time decay per calendar day
rm.vega    # $ change per 1 percentage-point increase in vol
rm.rho     # $ change per 1 percentage-point increase in rate

# Risk-neutral expected values (per lot)
rm.expected_pnl      # E^Q[payoff at expiry]
rm.expected_profit   # E^Q[payoff × 1(payoff > 0)]
rm.expected_loss     # E^Q[payoff × 1(payoff ≤ 0)]

# Reward / risk
rm.reward_risk_ratio  # max_profit / |max_loss|
                      # inf  when max_profit unlimited, max_loss bounded
                      # 0.0  when max_loss unlimited, max_profit bounded
                      # nan  when both unlimited
```

Expected values are computed by numerically integrating the payoff function
weighted by the log-normal PDF over ±5σ√T from spot.

### Leg object

```python
leg.kind        # "call" | "put" | "stock"
leg.direction   # +1 long, -1 short
leg.strike      # strike price
leg.expiry      # expiry label
leg.premium     # cost per share (>0 paid, <0 received)
leg.contracts   # number of contracts
leg.label       # human-readable: "Long Call K=95.0"
```

## Pretty printer

```python
from traderjoe.strategies import pretty_print_strategy

pretty_print_strategy(strategy, width=60)
```

Prints:
- Legs table (kind, direction, strike, expiry, premium)
- Analytics (net premium, max profit/loss, breakevens)
- ASCII payoff chart (P&L vs stock price at expiry)

### Sample output

```
  ──────────────────────────────────────────────────────────
  Strategy : Iron Condor
  Spot     : 100.00
  ──────────────────────────────────────────────────────────
  Leg                            Strike     Expiry   Premium
  ----------------------------------------------------------
  Long Put K=90.0                 90.00          T    +$0.72
  Short Put K=95.0                95.00          T    -$2.14
  Short Call K=105.0             105.00          T    -$2.05
  Long Call K=110.0              110.00          T    +$0.66
  ──────────────────────────────────────────────────────────
  Net premium  :    $281.00 / contract  (credit)
  Max profit   :    $281.00 / lot
  Max loss     :    $219.00 / lot
  Breakeven(s) : 92.19  /  107.81
  ──────────────────────────────────────────────────────────
  P&L  ^
  +281|·············███████████████████·············
      |·········███·····················███·········
      |·····███·····························███·····
    $0|···█·································█···S··
      |·█·····································█···
  -219|█·········································█·
       +──────────────────────────────────────────>
          70.0                               130.0  price
```

## Notes on calendar and diagonal spreads

Payoff is evaluated **at the near expiry** (`T1`) with the far-dated option priced by Black-Scholes at the remaining time `T2 − T1`. This is the standard approach but assumes the same volatility holds at `T1`. At expiry of both legs (`T2`) the far option simply has intrinsic value.

## Running tests

```bash
PYTHONPATH=. python3 -m pytest tests/test_strategies.py -v
```

326 tests: 12 parametrised checks × 24 strategies + 38 strategy-specific tests.
