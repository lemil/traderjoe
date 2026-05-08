# BL-009 — Symbol and Dataset Navigation

**Size**: M  
**Dependencies**: BL-003, BL-004

## User Story

As a trader, I want to switch between different symbols (AAPL, NVDA) and call/put types so that I can compare options data across multiple underlyings from a single interface.

## Acceptance Criteria

- A symbol dropdown in the header (or sub-header bar) lists all symbols from the data manifest (`/data/index.json`)
- A call/put toggle (two-button segmented control) appears next to the symbol picker
- Switching symbol or type updates the URL query params (`?symbol=...&type=...`) and triggers a re-fetch of the relevant JSON file
- A loading indicator is shown during re-fetch
- If data for the selected combination does not exist (e.g., NVDA put chain), the UI shows "Data not available for NVDA put chain" — no crash, no blank screen
- The current symbol and type are reflected in the page URL so the view is bookmarkable and shareable
- On first load, URL params are used if present; if not, defaults to the first symbol in the manifest as a call
- The symbol picker and type toggle are visible from all routes (Pricing, Chain, Surface, IV)

## Technical Notes

**URL as the source of truth** — use Next.js `useSearchParams` and `useRouter` to read/write `?symbol=&type=`:

```tsx
'use client';
import { useRouter, useSearchParams, usePathname } from 'next/navigation';

export function useSymbolParams() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const symbol = params.get('symbol') ?? 'AAPL';
  const type = (params.get('type') ?? 'call') as 'call' | 'put';

  function setSymbol(s: string) {
    const p = new URLSearchParams(params.toString());
    p.set('symbol', s);
    router.push(`${pathname}?${p.toString()}`);
  }

  function setType(t: 'call' | 'put') {
    const p = new URLSearchParams(params.toString());
    p.set('type', t);
    router.push(`${pathname}?${p.toString()}`);
  }

  return { symbol, type, setSymbol, setType };
}
```

**Place in `Shell.tsx`** — wrap the symbol picker and type toggle in the header so they appear across all routes. Since `Shell.tsx` is already `"use client"`, it can call `useSymbolParams()` directly.

**Symbol dropdown:**
```tsx
const { data: index } = useDataLoader(loadDataIndex, []);

<select value={symbol} onChange={e => setSymbol(e.target.value)}
  className="border rounded px-2 py-1 text-sm bg-white dark:bg-slate-800 ...">
  {index?.symbols.map(s => (
    <option key={s} value={s}>{s}</option>
  ))}
</select>
```

**Call/put toggle:**
```tsx
{(['call', 'put'] as const).map(t => (
  <button key={t} onClick={() => setType(t)}
    aria-pressed={type === t}
    className={`px-3 py-1 text-sm rounded font-medium transition-colors
      ${type === t
        ? 'bg-blue-600 text-white'
        : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200'}`}>
    {t.toUpperCase()}
  </button>
))}
```

**"Data not available" handling** — in each page's data loader, catch 404-style errors:
```typescript
async function tryLoadOptionChain(symbol: string, type: 'call' | 'put'): Promise<OptionChain | null> {
  try {
    return await loadOptionChain(symbol, type);
  } catch {
    return null; // caller renders "not available" UI
  }
}
```

**`useSearchParams` and Suspense** — in Next.js 15, `useSearchParams()` requires the component tree to have a `<Suspense>` boundary. Wrap the Shell's nav section or the symbol picker in `<Suspense fallback={null}>` to satisfy this requirement.

**Manifest-driven availability** — use `DataIndex.pricingTypes` and `DataIndex.chainTypes` to know which combos exist. Grey out unavailable options rather than hiding them, to show the user what's missing.

## Verification

1. Load `localhost:3000/pricing` — should default to `?symbol=AAPL&type=call`
2. Change symbol dropdown to NVDA — URL updates, pricing card re-fetches NVDA data
3. Click PUT toggle — URL updates to `?type=put`, card re-fetches AAPL put data
4. Navigate to `/chain` — URL params carry over, chain table shows AAPL call chain
5. Try selecting NVDA PUT from the chain view — show "Data not available for NVDA put chain" (no put chain JSON exists yet)
6. Copy the URL and open in a new tab — same symbol/type should load
