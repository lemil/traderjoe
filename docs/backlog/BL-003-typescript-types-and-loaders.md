# BL-003 — TypeScript Types and Data Loaders

**Size**: S  
**Dependencies**: BL-001, BL-002

## User Story

As a developer, I want strongly-typed data models and async fetch utilities so that every component has compile-time guarantees about the shape of the data it receives, and no `any` types leak through the codebase.

## Acceptance Criteria

- `lib/types.ts` exports `Greeks`, `BSResult`, `OptionCell`, `OptionChain`, and `DataIndex` interfaces that exactly match the JSON structures produced by the Python library
- `lib/loaders.ts` exports `loadDataIndex()`, `loadBSResult(symbol, type)`, and `loadOptionChain(symbol, type)`, each returning a typed `Promise`
- `lib/loaders.ts` exports `buildCellMap(chain)` for O(1) cell lookup by strike+expiry key
- All loaders throw a descriptive `Error` on HTTP failure (non-2xx status)
- Zero `any` types in `lib/types.ts` and `lib/loaders.ts`
- TypeScript compiler (`npm run build`) passes with no errors after adding these files

## Technical Notes

**`lib/types.ts`** — implement these exact shapes (matching the Python JSON output):

```typescript
export interface Greeks {
  delta: number;
  gamma: number;
  theta: number;   // per calendar day (already divided by 365 in Python)
  vega: number;    // per 1-point vol move (e.g., 32.3, not 0.323)
  rho: number;     // per 1-point rate move
}

export interface BSResult {
  symbol: string;
  option_type: 'call' | 'put';
  S: number;        // spot price
  K: number;        // strike price
  T: number;        // time to expiry in years (decimal)
  r: number;        // risk-free rate (decimal, e.g. 0.0359)
  sigma: number;    // historical vol (decimal, e.g. 0.2567)
  expiry: string;   // YYYY-MM-DD
  bs_price: number;
  market_mid: number;
  greeks: Greeks;
}

export interface OptionCell {
  strike: number;
  expiry: string;   // YYYY-MM-DD
  bid: number;
  ask: number;
  mid: number;
  last: number;
  volume: number;
  open_interest: number;
  iv_market: number | null;   // annualised decimal; null if not computable
  iv_bs: number | null;       // BS-backed IV; null if not computable
  delta: number | null;
  gamma: number | null;
  theta: number | null;       // per calendar day
  vega: number | null;        // per 1-point vol move
  itm: boolean;               // pre-computed in Python (call: strike < spot; put: strike > spot)
}

export interface OptionChain {
  symbol: string;
  option_type: 'call' | 'put';
  spot: number;
  rate: number;
  as_of: string;        // YYYY-MM-DD snapshot date
  strikes: number[];    // sorted ascending
  expiries: string[];   // sorted ascending (YYYY-MM-DD)
  cells: OptionCell[];  // sparse — not all strike×expiry combos present
}

export interface DataIndex {
  symbols: string[];
  chainTypes: Array<'call' | 'put'>;
  pricingTypes: Record<string, Array<'call' | 'put'>>;
}

export type OptionType = 'call' | 'put';

// Union of all numeric fields on OptionCell that can be displayed in the matrix
export type CellField =
  | 'mid' | 'bid' | 'ask' | 'last'
  | 'iv_bs' | 'iv_market'
  | 'delta' | 'gamma' | 'theta' | 'vega'
  | 'volume' | 'open_interest';
```

**`lib/loaders.ts`**:

```typescript
import { BSResult, DataIndex, OptionChain, OptionCell } from './types';

const BASE = '/data';

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch ${url}: ${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export function loadDataIndex(): Promise<DataIndex> {
  return fetchJson<DataIndex>(`${BASE}/index.json`);
}

export function loadBSResult(symbol: string, type: 'call' | 'put'): Promise<BSResult> {
  const suffix = type === 'put' ? '_put' : '';
  return fetchJson<BSResult>(`${BASE}/fetch_bs_params_${symbol}${suffix}.json`);
}

export function loadOptionChain(symbol: string, type: 'call' | 'put'): Promise<OptionChain> {
  const suffix = type === 'put' ? '_put' : '';
  return fetchJson<OptionChain>(`${BASE}/option_chain_${symbol}${suffix}.json`);
}

/** Build a Map keyed by `"YYYY-MM-DD|strike"` for O(1) cell lookup in the matrix. */
export function buildCellMap(chain: OptionChain): Map<string, OptionCell> {
  const map = new Map<string, OptionCell>();
  for (const cell of chain.cells) {
    map.set(`${cell.expiry}|${cell.strike}`, cell);
  }
  return map;
}
```

**Unit note for display labels** — create `lib/greekMeta.ts` (reused by BL-005 and BL-012):
```typescript
export const GREEK_META = {
  delta: { label: 'Delta', unit: 'unitless' },
  gamma: { label: 'Gamma', unit: 'per $1 move' },
  theta: { label: 'Theta', unit: 'per day' },
  vega:  { label: 'Vega',  unit: 'per vol point' },
  rho:   { label: 'Rho',   unit: 'per rate point' },
} as const;
```

## Verification

1. Add the two files and run `npm run build` — must exit 0 with no type errors
2. In `app/page.tsx`, temporarily call `loadDataIndex()` inside a Server Component and `console.log` the result — verify the manifest loads correctly in dev
3. Check that `buildCellMap` returns the expected key format by logging `[...map.keys()].slice(0, 3)` in dev console
