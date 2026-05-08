# BL-005 — Single Option Pricing Card

**Size**: M  
**Dependencies**: BL-003, BL-004

## User Story

As a trader, I want to see a clear summary card for a single priced option so that I can quickly compare the Black-Scholes model price against the market mid price and inspect all five Greeks with their correct units.

## Acceptance Criteria

- Card displays all BS inputs: spot (S), strike (K), time to expiry in days (T × 365, rounded), risk-free rate (r as %), historical vol (sigma as %)
- Card displays: BS price, market mid price, and the difference (BS − market mid) with a green/red color indicator
- A moneyness badge shows **ITM**, **ATM** (within 0.5% of spot), or **OTM**
- Greeks section shows delta, gamma, theta, vega, rho — each with a label, value, and unit
- Numeric precision: prices to 2 dp, rates/vols as % to 2 dp, Greeks: delta 3 dp, gamma 5 dp, theta 4 dp, vega 4 dp, rho 4 dp
- Symbol and option type come from the current URL query params (`?symbol=AAPL&type=call`)
- A loading spinner is shown while data is fetching; an error state with retry is shown on failure
- Component is fully keyboard accessible — no hover-only information

## Technical Notes

**Files:**
- `app/pricing/page.tsx` — Server Component wrapper
- `components/PricingCard.tsx` — `"use client"` component that fetches and renders

**`app/pricing/page.tsx`:**
```tsx
import { Suspense } from 'react';
import PricingCard from '@/components/PricingCard';
import Spinner from '@/components/Spinner';

export default function PricingPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <PricingCard />
    </Suspense>
  );
}
```

**`components/PricingCard.tsx`** key logic:
```tsx
'use client';
import { useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { loadBSResult } from '@/lib/loaders';
import { BSResult } from '@/lib/types';
import { GREEK_META } from '@/lib/greekMeta';

export default function PricingCard() {
  const params = useSearchParams();
  const symbol = params.get('symbol') ?? 'AAPL';
  const type = (params.get('type') ?? 'call') as 'call' | 'put';

  const [data, setData] = useState<BSResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    loadBSResult(symbol, type)
      .then(setData)
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false));
  }, [symbol, type]);

  if (loading) return <Spinner />;
  if (error || !data) return <ErrorCard message={error ?? 'Unknown error'} onRetry={...} />;

  const diff = data.bs_price - data.market_mid;
  const daysToExpiry = Math.round(data.T * 365);
  const moneyness = Math.abs(data.S - data.K) / data.S < 0.005
    ? 'ATM'
    : data.option_type === 'call'
      ? data.K < data.S ? 'ITM' : 'OTM'
      : data.K > data.S ? 'ITM' : 'OTM';

  return ( /* render card */ );
}
```

**Display layout** (2-column grid on `sm:` and above, 1-column on mobile):

```
┌─────────────────────────────────────────┐
│  AAPL  [CALL]  [ATM]      Jun 05, 2026 │
├──────────────────┬──────────────────────┤
│  Inputs          │  Prices              │
│  S   $292.67     │  BS Price   $7.47    │
│  K   $295.00     │  Mkt Mid    $6.60    │
│  T   28 days     │  Diff      +$0.87 ✓ │
│  r   3.60%       │                      │
│  σ   25.67%      │                      │
├──────────────────┴──────────────────────┤
│  Greeks                                  │
│  Delta   0.464    (unitless)             │
│  Gamma   0.01350  (per $1 move)          │
│  Theta  -0.2280   (per day)              │
│  Vega   29.4000   (per vol point)        │
│  Rho    10.3000   (per rate point)       │
└─────────────────────────────────────────┘
```

**Greek unit labels** — import from `lib/greekMeta.ts` (defined in BL-003) so labels stay consistent with BL-012.

**Moneyness badge colors:**
- ITM: `bg-sky-100 text-sky-800 dark:bg-sky-900 dark:text-sky-200`
- ATM: `bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200`
- OTM: `bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300`

**Diff color:**
- `diff > 0`: `text-green-600 dark:text-green-400` (BS above market — potentially underpriced)
- `diff < 0`: `text-red-600 dark:text-red-400`
- `diff === 0`: neutral

## Verification

1. Navigate to `localhost:3000/pricing?symbol=AAPL&type=call` — card should render with AAPL data
2. Change to `?symbol=NVDA&type=call` — card should re-fetch and show NVDA data
3. Change to `?symbol=AAPL&type=put` — card should show put data
4. Try `?symbol=FAKE` — should show error card with retry button
5. Confirm all Greek values match the source JSON (spot-check against `tmp/output/fetch_bs_params_AAPL.json`)
