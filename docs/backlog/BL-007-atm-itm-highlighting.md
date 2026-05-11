# BL-007 — ATM/ITM Visual Highlighting

**Size**: S  
**Dependencies**: BL-006

## User Story

As a trader, I want ITM options visually distinguished from OTM options in the chain matrix so that I can instantly understand which contracts are in or out of the money without doing the arithmetic myself.

## Acceptance Criteria

- All ITM rows have a distinct background (light blue tint in light mode, dark blue tint in dark mode)
- The ATM row (strike closest to spot price) has a bold left border accent and a distinct amber/yellow background different from generic ITM rows
- OTM rows have the default background
- ITM/OTM determination is correct for the loaded option type:
  - Calls: `strike < spot` = ITM
  - Puts: `strike > spot` = ITM
  - (Use the `itm` field from an available cell in the row, or compute from `strike` vs `chain.spot`)
- The spot price is shown in the metadata bar above the table (e.g., "Spot: $292.67")
- Row highlighting is preserved when the field switcher changes the displayed value
- Row highlighting updates correctly when the user switches symbol or option type

## Technical Notes

**ATM strike** (precompute once when chain loads):
```typescript
const atmStrike = chain.strikes.reduce((best, s) =>
  Math.abs(s - chain.spot) < Math.abs(best - chain.spot) ? s : best
);
```

**ITM determination per row** — for each strike, check any available cell's `itm` flag; fall back to computed logic:
```typescript
function isItm(strike: number, spot: number, optionType: 'call' | 'put', cellMap: Map<string, OptionCell>, expiries: string[]): boolean {
  for (const exp of expiries) {
    const cell = cellMap.get(`${exp}|${strike}`);
    if (cell) return cell.itm;
  }
  // fallback if no cells exist for this strike
  return optionType === 'call' ? strike < spot : strike > spot;
}
```

**Row class logic** (applied to each `<tr>`):
```typescript
const isAtm = strike === atmStrike;
const itm = isItm(strike, chain.spot, chain.option_type, cellMap, chain.expiries);

const rowClass = isAtm
  ? 'bg-amber-50 dark:bg-amber-900/20 border-l-4 border-amber-400 font-semibold'
  : itm
  ? 'bg-sky-50 dark:bg-sky-900/20'
  : 'bg-white dark:bg-slate-900';
```

**Strike cell** — in the sticky first column, display strike with a monospace font and right-align for easy scanning:
```tsx
<td className={`sticky left-0 z-10 font-mono text-right pr-3 ${rowClass}`}>
  {strike.toFixed(0)}
</td>
```

**ATM label** — add a small "ATM" badge next to the strike price in the ATM row:
```tsx
{isAtm && <span className="ml-1 text-xs bg-amber-400 text-white rounded px-1">ATM</span>}
```

**Spot display in metadata bar** (above the table):
```tsx
<div className="flex items-center gap-4 text-sm text-slate-600 dark:text-slate-400 mb-2">
  <span>Spot: <strong className="font-mono text-slate-900 dark:text-white">${chain.spot.toFixed(2)}</strong></span>
  <span>As of: {chain.as_of}</span>
  <span>{chain.strikes.length} strikes × {chain.expiries.length} expiries</span>
</div>
```

## Verification

1. Open `localhost:3000/chain?symbol=AAPL&type=call` (spot ≈ $292.67)
2. Confirm: strikes below 292.67 have blue tint (ITM for calls)
3. Confirm: strike closest to 292.67 (likely $290 or $295) has amber background + "ATM" badge + bold text
4. Switch to `?type=put` — confirm ITM/OTM flips (strikes above spot now have blue tint)
5. Switch field to "Delta" — highlighting should remain unchanged
6. Switch symbol to NVDA — highlighting should recalculate for NVDA's spot price
