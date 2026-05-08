# BL-008 — Heatmap Coloring

**Size**: M  
**Dependencies**: BL-006, BL-007

## User Story

As a trader, I want to toggle heatmap coloring on the chain matrix so that high and low values are instantly visible by color without reading every number, helping me spot where liquidity concentrates or where Greeks peak.

## Acceptance Criteria

- A "Heatmap" toggle button above the table enables and disables heatmap coloring
- When enabled, each cell's background color reflects its value relative to all other non-null cells for the current field
- Fields that can be negative (delta, theta) use a **diverging** scale (blue → white → red, centered at zero)
- Purely positive fields (gamma, vega, volume, prices, IV) use a **sequential** scale (white → orange)
- `null` / `n/a` cells are always uncolored regardless of heatmap state
- Empty cells (`—`) are always uncolored
- A color-scale legend bar (min value → gradient → max value) appears above the table when heatmap is active
- Heatmap updates instantly when the field switcher changes
- Cell text remains legible in both light and dark modes (sufficient contrast)
- Heatmap state is a local UI toggle — not synced to the URL

## Technical Notes

**`lib/heatmap.ts`:**
```typescript
/** Returns an rgba background color string and a text contrast hint. */
export function interpolateColor(
  value: number,
  min: number,
  max: number,
  diverging: boolean,
  isDark: boolean
): { bg: string; text: 'dark' | 'light' } {
  if (min === max) return { bg: 'transparent', text: 'dark' };

  if (diverging) {
    // Map to [-1, 1] range centered at 0
    const absMax = Math.max(Math.abs(min), Math.abs(max));
    const t = value / absMax; // -1 to 1
    if (t >= 0) {
      // 0 → white, 1 → red
      const alpha = t * 0.7;
      return { bg: `rgba(239, 68, 68, ${alpha})`, text: alpha > 0.4 ? 'light' : 'dark' };
    } else {
      // 0 → white, -1 → blue
      const alpha = -t * 0.7;
      return { bg: `rgba(59, 130, 246, ${alpha})`, text: alpha > 0.4 ? 'light' : 'dark' };
    }
  } else {
    // Sequential: white → orange
    const t = (value - min) / (max - min); // 0 to 1
    const alpha = t * 0.75;
    return { bg: `rgba(234, 88, 12, ${alpha})`, text: alpha > 0.45 ? 'light' : 'dark' };
  }
}
```

**Domain computation** (compute once when field or chain changes):
```typescript
const domain = useMemo(() => {
  const values = chain.cells
    .map(c => c[field] as number | null)
    .filter((v): v is number => v !== null);
  if (values.length === 0) return [0, 1] as [number, number];
  return [Math.min(...values), Math.max(...values)] as [number, number];
}, [chain.cells, field]);
```

**Cell background application:**
```tsx
const config = FIELD_CONFIG[field];
const heatColor = heatmapEnabled && value !== null
  ? interpolateColor(value, domain[0], domain[1], config.diverging, isDark)
  : null;

<td style={heatColor ? { backgroundColor: heatColor.bg } : undefined}
    className={heatColor?.text === 'light' ? 'text-white' : ''}>
  {formattedValue}
</td>
```

**Dark mode awareness** — pass `isDark` from the `useTheme()` hook (BL-010). In dark mode, slightly reduce opacity (`alpha * 0.85`) so colors don't overwhelm dark backgrounds.

**Legend bar:**
```tsx
{heatmapEnabled && (
  <div className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-400 mb-2">
    <span>{FIELD_CONFIG[field].format(domain[0])}</span>
    <div className="h-3 w-32 rounded"
      style={{ background: diverging
        ? 'linear-gradient(to right, #3b82f6, white, #ef4444)'
        : 'linear-gradient(to right, white, #ea580c)' }} />
    <span>{FIELD_CONFIG[field].format(domain[1])}</span>
  </div>
)}
```

**Deep-ITM IV outliers** — for `iv_bs` and `iv_market` fields, values for deep-ITM options can reach 7+ (700%+), which would wash out the heatmap. Cap the domain for IV fields:
```typescript
if (field === 'iv_bs' || field === 'iv_market') {
  cappedMax = Math.min(domain[1], 2.0); // cap at 200% IV
}
```

## Verification

1. Open `localhost:3000/chain?symbol=AAPL&type=call`, enable heatmap
2. With "Mid Price" selected: near-ATM options should show stronger orange (higher premium); deep OTM/ITM very cheap options show near-white
3. Switch to "Delta": calls should show gradient from blue (near 0 for deep OTM) to white (ATM) to red (deep ITM near 1)
4. Switch to "Theta": all values negative — should show a blue gradient, deeper for near-ATM
5. Toggle heatmap off — all custom backgrounds disappear, text color resets
6. Verify `n/a` and `—` cells remain uncolored with heatmap on
