# BL-006 — Option Chain Matrix Table

**Size**: L  
**Dependencies**: BL-003, BL-004

## User Story

As a trader, I want to view the option chain as a strike × expiry grid so that I can compare prices or Greeks across all available strikes and expirations at once, and switch between different display fields without reloading.

## Acceptance Criteria

- Table renders strikes as rows (sorted ascending) and expiries as columns (sorted ascending, displayed as short dates e.g. "May 08")
- A field switcher above the table allows selecting which value to display in each cell: **mid, bid, ask, iv_bs, delta, gamma, theta, vega, volume, open_interest**
- Cells with no data for that strike/expiry combination show `—` (em-dash), centered in muted text
- Cells where the selected field value is `null` show `n/a` in muted text
- The header row (expiry dates) is sticky on vertical scroll
- The strike column is sticky on horizontal scroll
- A "Jump to ATM" button scrolls the nearest-to-spot row into view
- A metadata bar above the table shows: symbol, option type, spot price, as-of date, row/column counts
- The table loads data via URL params (`?symbol=AAPL&type=call`); shows a spinner while loading and an error state on failure
- Numeric formatting per field:
  - Prices (mid/bid/ask/last): 2 decimal places
  - IV (iv_bs/iv_market): displayed as percentage, 1 decimal place (multiply by 100)
  - Delta: ±3 decimal places
  - Gamma: 5 decimal places
  - Theta: ±4 decimal places
  - Vega: 4 decimal places
  - Volume / open_interest: integer with comma separator

## Technical Notes

**Files:**
- `app/chain/page.tsx` — page wrapper with `<Suspense>`
- `components/ChainTable/index.tsx` — `"use client"` main component
- `components/ChainTable/FieldSwitcher.tsx` — segmented control / select for field selection
- `components/ChainTable/MatrixCell.tsx` — single cell renderer
- `lib/fieldConfig.ts` — `FIELD_CONFIG` constant (shared with BL-008 and BL-012)

**`lib/fieldConfig.ts`:**
```typescript
import { CellField, OptionCell } from './types';

export type FieldConfig = {
  label: string;
  format: (v: number) => string;
  domain: [number, number];   // rough domain for heatmap scaling (BL-008)
  diverging: boolean;          // true if field can be negative
};

export const FIELD_CONFIG: Record<CellField, FieldConfig> = {
  mid:           { label: 'Mid Price',    format: v => v.toFixed(2),              domain: [0, 50],   diverging: false },
  bid:           { label: 'Bid',          format: v => v.toFixed(2),              domain: [0, 50],   diverging: false },
  ask:           { label: 'Ask',          format: v => v.toFixed(2),              domain: [0, 50],   diverging: false },
  iv_bs:         { label: 'IV (BS)',      format: v => `${(v*100).toFixed(1)}%`,  domain: [0, 2],    diverging: false },
  iv_market:     { label: 'IV (Mkt)',     format: v => `${(v*100).toFixed(1)}%`,  domain: [0, 2],    diverging: false },
  delta:         { label: 'Delta',        format: v => v.toFixed(3),              domain: [-1, 1],   diverging: true  },
  gamma:         { label: 'Gamma',        format: v => v.toFixed(5),              domain: [0, 0.05], diverging: false },
  theta:         { label: 'Theta',        format: v => v.toFixed(4),              domain: [-1, 0],   diverging: true  },
  vega:          { label: 'Vega',         format: v => v.toFixed(4),              domain: [0, 80],   diverging: false },
  volume:        { label: 'Volume',       format: v => v.toLocaleString(),        domain: [0, 5000], diverging: false },
  open_interest: { label: 'Open Interest',format: v => v.toLocaleString(),        domain: [0, 10000],diverging: false },
};
```

**ATM detection:**
```typescript
const atmStrike = chain.strikes.reduce((best, s) =>
  Math.abs(s - chain.spot) < Math.abs(best - chain.spot) ? s : best
);
```

**Sticky header + sticky first column** (Tailwind):
```tsx
// Header row cells
<th className="sticky top-0 bg-white dark:bg-slate-900 z-20 ...">

// First column cells (strike)
<td className="sticky left-0 bg-white dark:bg-slate-900 z-10 ...">

// Corner cell (must be above both)
<th className="sticky top-0 left-0 bg-white dark:bg-slate-900 z-30 ...">
```

**Cell value extraction:**
```typescript
function getCellValue(cell: OptionCell, field: CellField): number | null {
  const v = cell[field] as number | null;
  return v;
}
```

**Jump to ATM:**
```typescript
const atmRowRef = useRef<HTMLTableRowElement>(null);
// On button click:
atmRowRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
```

**Data loading pattern** (use `useDataLoader` hook from BL-014):
```tsx
const { data: chain, loading, error, retry } = useDataLoader(
  () => loadOptionChain(symbol, type),
  [symbol, type]
);
```

**Short date format for expiry columns:**
```typescript
const shortDate = (iso: string) =>
  new Date(iso + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: '2-digit' });
// "2026-05-08" → "May 08"
```

**Important — cell sparsity:** The `cells` array is sparse. Use `buildCellMap(chain)` from `lib/loaders.ts` to create a `Map<string, OptionCell>` keyed by `"${expiry}|${strike}"`. Look up each table cell with `cellMap.get(...)` — returns `undefined` for missing cells (render `—`).

## Verification

1. Navigate to `localhost:3000/chain?symbol=AAPL&type=call`
2. Confirm table renders with correct number of rows (74 strikes) and columns (4 expiries)
3. Toggle between all 10 field options — values should update immediately
4. Click "Jump to ATM" — table should scroll to the ~$295 strike row for AAPL
5. Verify sticky behavior: scroll down (header stays), scroll right (strike column stays)
6. Check that missing cells show `—` and null-Greek cells show `n/a`
7. Switch to `?symbol=NVDA` — table should re-render with NVDA data (83 strikes)
