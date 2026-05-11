# BL-011 — Responsive Layout

**Size**: M  
**Dependencies**: BL-004, BL-005, BL-006

## User Story

As a trader, I want the site to be usable on my phone and tablet so that I can check option data on the go, not just at a desktop workstation.

## Acceptance Criteria

- Pricing card (BL-005): single-column on < 640px, two-column grid on ≥ 640px
- Option chain table (BL-006): scrolls horizontally within its container on all screen sizes; strike column stays sticky during horizontal scroll; no horizontal overflow on the page body itself
- Field switcher: compact `<select>` dropdown on < 640px; full segmented button group on ≥ 640px
- Charts (BL-012, BL-013): minimum height 300px, fill container width; axis labels don't overlap on small screens
- App shell: bottom nav tab bar on < 768px; top horizontal nav on ≥ 768px (already specified in BL-004)
- No horizontal scrollbar on the `<body>` element at any viewport width
- Tested breakpoints: 375px (iPhone SE), 768px (iPad portrait), 1280px (desktop)

## Technical Notes

**Overflow discipline** — the most common cause of unwanted horizontal scroll is a child element wider than the viewport. Rules:
- Set `overflow-x: hidden` on `<body>` is a band-aid — instead, fix the root cause
- The chain table wrapper must be `overflow-x-auto` on a container with `max-w-full`:
  ```tsx
  <div className="w-full overflow-x-auto rounded border border-slate-200 dark:border-slate-700">
    <table className="min-w-max text-sm"> {/* min-w-max lets table grow beyond container */}
  ```
- Charts: always wrap in `<div className="w-full">` and use `<ResponsiveContainer width="100%" height={320}>`

**Field switcher responsive swap:**
```tsx
{/* Mobile: native select */}
<select className="sm:hidden border rounded px-2 py-1 text-sm" value={field} onChange={e => setField(e.target.value as CellField)}>
  {Object.entries(FIELD_CONFIG).map(([k, v]) => (
    <option key={k} value={k}>{v.label}</option>
  ))}
</select>

{/* Desktop: button group */}
<div className="hidden sm:flex flex-wrap gap-1">
  {Object.entries(FIELD_CONFIG).map(([k, v]) => (
    <button key={k} onClick={() => setField(k as CellField)}
      className={`px-2 py-1 text-xs rounded ${field === k ? 'bg-blue-600 text-white' : 'bg-slate-100 dark:bg-slate-800'}`}>
      {v.label}
    </button>
  ))}
</div>
```

**Pricing card two-column grid:**
```tsx
<div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
  <div> {/* Inputs section */} </div>
  <div> {/* Prices section */} </div>
</div>
```

**Greeks table** (in PricingCard) — readable at any width since it's a simple two-column list, not a matrix.

**Chart height on mobile:**
```typescript
// hooks/useWindowSize.ts
import { useEffect, useState } from 'react';
export function useWindowSize() {
  const [size, setSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    const update = () => setSize({ width: window.innerWidth, height: window.innerHeight });
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, []);
  return size;
}
```
Use in chart components: `height={Math.max(300, windowSize.height * 0.4)}`.

**Bottom nav height** — ensure the `<main>` padding-bottom accounts for the bottom nav on mobile so content isn't hidden behind it:
```tsx
<main className="flex-1 overflow-y-auto p-4 pb-20 md:pb-6 md:p-6">
```

## Verification

1. Open Chrome DevTools → Device Mode → iPhone SE (375×667)
   - Pricing card: single column, all text readable, no overflow
   - Chain table: scrolls horizontally within its container, strike column stays put
   - Field switcher: shows `<select>` dropdown
   - Bottom nav visible and not overlapping content
2. Switch to iPad (768×1024)
   - Top nav appears, bottom nav hidden
   - Two-column pricing card layout
3. Desktop (1280×800)
   - Full segmented button group for field switcher
   - Table has ample space
4. Run `npm run build` — no TypeScript errors introduced by responsive changes
