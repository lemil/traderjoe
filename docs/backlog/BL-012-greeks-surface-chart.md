# BL-012 — Greeks Surface Visualization

**Size**: M  
**Dependencies**: BL-003, BL-006

## User Story

As a trader, I want to see how a Greek varies across all strikes for each expiry in a single chart so that I can understand the risk profile of the option chain and how it changes with time to expiry.

## Acceptance Criteria

- A line chart shows the selected Greek on the Y-axis vs strike price on the X-axis
- Each expiry date is rendered as a separate line with a distinct color and a legend entry
- A Greek selector (dropdown or tab strip) allows switching between: **Delta, Gamma, Theta, Vega**
- Strikes with `null` Greek values are omitted from that expiry's line (gap in the line — lines do not connect across null values)
- A vertical reference line marks the ATM strike, labeled "ATM"
- Hovering a data point shows a tooltip: strike, expiry, and the Greek value with its unit
- X-axis label: "Strike Price ($)"; Y-axis label reflects the selected Greek and its unit
- Chart loads the option chain from URL params (`?symbol=AAPL&type=call`); shows spinner while loading
- Chart is readable at mobile widths (300px min height, responsive width)

## Technical Notes

**Install Recharts:**
```bash
npm install recharts
npm install -D @types/recharts  # if needed
```

**Files:**
- `app/surface/page.tsx` — page wrapper with `<Suspense>`
- `components/GreeksSurface.tsx` — `"use client"` chart component

**`lib/greekMeta.ts`** (defined in BL-003 — reuse here):
```typescript
export const GREEK_META = {
  delta: { label: 'Delta',  unit: 'unitless',       chartGreek: 'delta'  },
  gamma: { label: 'Gamma',  unit: 'per $1 move',    chartGreek: 'gamma'  },
  theta: { label: 'Theta',  unit: 'per day',         chartGreek: 'theta'  },
  vega:  { label: 'Vega',   unit: 'per vol point',  chartGreek: 'vega'   },
} as const;
export type ChartGreek = keyof typeof GREEK_META;
```

**Data transformation** — for each expiry, build an array of `{strike, value}` filtering nulls:
```typescript
const seriesData = chain.expiries.map(exp => ({
  expiry: exp,
  points: chain.strikes
    .map(strike => {
      const cell = cellMap.get(`${exp}|${strike}`);
      const val = cell ? (cell[greek] as number | null) : null;
      return val !== null ? { strike, value: val } : null;
    })
    .filter((p): p is { strike: number; value: number } => p !== null),
}));
```

**Recharts component structure:**
```tsx
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine, ResponsiveContainer } from 'recharts';

const PALETTE = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

// Merge all series into a single data array for LineChart (keyed by strike)
// Each expiry adds its own key: { strike, "2026-05-08": 0.464, "2026-05-11": 0.512 }
const mergedData: Record<string, number>[] = chain.strikes.map(strike => {
  const entry: Record<string, number> = { strike };
  for (const exp of chain.expiries) {
    const cell = cellMap.get(`${exp}|${strike}`);
    const val = cell ? (cell[greek] as number | null) : null;
    if (val !== null) entry[exp] = val;
  }
  return entry;
});

<ResponsiveContainer width="100%" height={Math.max(300, 400)}>
  <LineChart data={mergedData} margin={{ top: 10, right: 30, left: 0, bottom: 20 }}>
    <CartesianGrid strokeDasharray="3 3" className="stroke-slate-200 dark:stroke-slate-700" />
    <XAxis dataKey="strike" label={{ value: 'Strike Price ($)', position: 'insideBottom', offset: -10 }} />
    <YAxis label={{ value: `${GREEK_META[greek].label} (${GREEK_META[greek].unit})`, angle: -90, position: 'insideLeft' }} />
    <Tooltip formatter={(val: number) => [val.toFixed(4), GREEK_META[greek].label]} />
    <Legend verticalAlign="top" />
    <ReferenceLine x={atmStrike} stroke="#f59e0b" strokeDasharray="4 2" label={{ value: 'ATM', position: 'top' }} />
    {chain.expiries.map((exp, i) => (
      <Line key={exp} type="monotone" dataKey={exp} stroke={PALETTE[i % PALETTE.length]}
            dot={false} connectNulls={false} name={shortDate(exp)} />
    ))}
  </LineChart>
</ResponsiveContainer>
```

**`connectNulls={false}`** — critical for showing gaps where Greeks are null (deep ITM/OTM with no computable Greeks).

**`lib/palette.ts`** — define the color palette centrally so BL-013 can reuse the same expiry colors:
```typescript
export const EXPIRY_PALETTE = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];
```

## Verification

1. Navigate to `localhost:3000/surface?symbol=AAPL&type=call`
2. Default to Delta — verify 4 lines (one per expiry), ATM reference line visible
3. Switch to Theta — all values should be negative; Y-axis should auto-scale to negative range
4. Switch to Gamma — verify the characteristic bell-curve shape peaking near ATM
5. Hover data points — tooltip should show strike, expiry, and value with unit
6. Switch symbol to NVDA — chart re-renders with NVDA data
7. Check that null-Greek regions (deep ITM/OTM) appear as gaps, not as connected zero-lines
