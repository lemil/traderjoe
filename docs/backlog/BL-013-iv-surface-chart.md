# BL-013 — IV Surface / Smile Chart

**Size**: M  
**Dependencies**: BL-003, BL-006, BL-012

## User Story

As a trader, I want to see the implied volatility smile across all strikes and expiries so that I can identify skew (asymmetric vol) and term structure (how IV changes with time to expiry) in the market.

## Acceptance Criteria

- A line chart shows `iv_bs` (BS-backed implied vol) on the Y-axis vs strike on the X-axis, one line per expiry
- `iv_market` (exchange-reported IV) is shown as semi-transparent dots on the same axes for comparison
- The Y-axis displays IV as a percentage (multiply stored decimal by 100; e.g., 0.25 → 25.0%)
- A Y-axis cap slider or input defaults to 200% to exclude deep-ITM artifacts (values like 740% from illiquid contracts)
- `null` IV values are omitted from their line (gap, no connection across nulls)
- A vertical ATM reference line is present, same as BL-012
- Chart title: `"{SYMBOL} {CALL/PUT} — Implied Volatility Smile"`
- A tooltip shows: strike, expiry, iv_bs (%), iv_market (%) for the hovered point
- Legend distinguishes iv_bs lines from iv_market scatter dots, colored per expiry
- Chart is responsive (min 300px height, full container width)

## Technical Notes

**Files:**
- `app/iv/page.tsx` — page wrapper with `<Suspense>`
- `components/IVSurface.tsx` — `"use client"` chart component

**IV unit note:** `iv_bs` and `iv_market` in the JSON are stored as annualised decimal fractions (e.g., 0.256 = 25.6%). Deep-ITM options have extreme values (7.4 = 740%) due to illiquid bid/ask spreads feeding abnormal mid prices. Filter or cap these.

**Y-axis capping:**
```typescript
const [ivCap, setIvCap] = useState(200); // percent

// Filter cells above the cap
const isValidIV = (v: number | null): v is number =>
  v !== null && (v * 100) <= ivCap;
```

**Recharts `<ComposedChart>`** — use `<Line>` for iv_bs and `<Scatter>` for iv_market dots:
```tsx
import { ComposedChart, Line, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine, ResponsiveContainer } from 'recharts';
```

**Data shape for ComposedChart:**

Strategy: build separate datasets for `iv_bs` lines and `iv_market` scatter, or merge into one dataset with multiple keys.

Recommended approach — one merged dataset (same as BL-012):
```typescript
const mergedData = chain.strikes.map(strike => {
  const entry: Record<string, number | undefined> = { strike };
  for (const exp of chain.expiries) {
    const cell = cellMap.get(`${exp}|${strike}`);
    // Store as percent, only if within cap
    const ivBs = cell?.iv_bs != null && (cell.iv_bs * 100) <= ivCap ? cell.iv_bs * 100 : undefined;
    const ivMkt = cell?.iv_market != null && (cell.iv_market * 100) <= ivCap ? cell.iv_market * 100 : undefined;
    if (ivBs !== undefined) entry[`bs_${exp}`] = ivBs;
    if (ivMkt !== undefined) entry[`mkt_${exp}`] = ivMkt;
  }
  return entry;
});
```

Then render one `<Line>` per expiry for `bs_*` keys (solid line) and one `<Scatter>` per expiry for `mkt_*` keys (dots), using the same color from `EXPIRY_PALETTE`.

**Scatter dot appearance:**
```tsx
<Scatter dataKey={`mkt_${exp}`} fill={color} opacity={0.5} r={3} />
// Note: Recharts Scatter in ComposedChart works on the merged data array
```

**Y-axis formatting:**
```tsx
<YAxis
  tickFormatter={v => `${v.toFixed(0)}%`}
  label={{ value: 'Implied Volatility (%)', angle: -90, position: 'insideLeft' }}
  domain={[0, 'auto']}
/>
```

**IV cap control:**
```tsx
<div className="flex items-center gap-2 mb-3 text-sm">
  <label htmlFor="iv-cap">Max IV:</label>
  <input id="iv-cap" type="range" min={50} max={500} step={25}
    value={ivCap} onChange={e => setIvCap(Number(e.target.value))}
    className="w-32" />
  <span className="font-mono w-12">{ivCap}%</span>
</div>
```

**Chart title:**
```tsx
<h2 className="text-base font-semibold mb-2">
  {chain.symbol} {chain.option_type.toUpperCase()} — Implied Volatility Smile
</h2>
```

**Reuse from BL-012:** `EXPIRY_PALETTE`, `shortDate()`, `atmStrike` computation, `useDataLoader` hook.

## Verification

1. Navigate to `localhost:3000/iv?symbol=AAPL&type=call`
2. Confirm the classic smile shape: near-ATM IV lower, tails higher (or flat for calls)
3. Set IV cap to 50% — deep-ITM/OTM artifacts disappear, smile is clearly visible
4. Hover a data point — tooltip shows strike, expiry, iv_bs %, iv_market %
5. Market IV dots (semi-transparent) should roughly track the BS IV lines
6. ATM reference line visible at ~$292–$295 strike
7. Switch symbol to NVDA — chart rerenders with NVDA IV data
8. Verify no data crashes when iv_bs is null for many cells (should just show gaps)
