# BL-010 — Light/Dark Theme

**Size**: S  
**Dependencies**: BL-004

## User Story

As a trader, I want to toggle between light and dark themes so that I can use the dashboard comfortably regardless of ambient lighting, and have my preference remembered on return visits.

## Acceptance Criteria

- A theme toggle button (sun icon for light, moon icon for dark) in the header switches between modes
- The preference is persisted in `localStorage` under key `"traderjoe-theme"`
- On first visit, the theme defaults to the OS preference (`prefers-color-scheme: dark`)
- All components render correctly in both themes — no hardcoded colors that only work in one mode
- The toggle is keyboard accessible: focusable via Tab, toggles on Enter or Space
- No flash of incorrect theme on initial page load (theme applied before first paint)

## Technical Notes

**Tailwind dark mode** — configure class-based dark mode in `tailwind.config.ts`:
```ts
import type { Config } from 'tailwindcss';
const config: Config = {
  darkMode: 'class',   // ← enables dark: variant when 'dark' class is on <html>
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  // ...
};
export default config;
```

**Prevent flash** — inject a blocking script before the React bundle in `app/layout.tsx`:
```tsx
// In <head>, before any stylesheet or script
<script dangerouslySetInnerHTML={{ __html: `
  (function() {
    var stored = localStorage.getItem('traderjoe-theme');
    var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (stored === 'dark' || (!stored && prefersDark)) {
      document.documentElement.classList.add('dark');
    }
  })();
` }} />
```

**`hooks/useTheme.ts`:**
```typescript
'use client';
import { useEffect, useState } from 'react';

export function useTheme() {
  const [theme, setTheme] = useState<'light' | 'dark'>('light');

  useEffect(() => {
    // Read initial value from DOM (set by blocking script above)
    const isDark = document.documentElement.classList.contains('dark');
    setTheme(isDark ? 'dark' : 'light');
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    localStorage.setItem('traderjoe-theme', theme);
  }, [theme]);

  const toggle = () => setTheme(t => t === 'dark' ? 'light' : 'dark');
  return { theme, toggle };
}
```

**Theme toggle button** (in `Shell.tsx`, replace the placeholder from BL-004):
```tsx
const { theme, toggle } = useTheme();
<button
  onClick={toggle}
  aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
  className="p-2 rounded hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
>
  {theme === 'dark' ? '☀️' : '🌙'}
</button>
```

**Global color convention** — all components must use paired Tailwind classes:
```
bg-white dark:bg-slate-900           ← page background
bg-slate-50 dark:bg-slate-800        ← card / panel background
border-slate-200 dark:border-slate-700  ← borders
text-slate-900 dark:text-slate-100   ← primary text
text-slate-600 dark:text-slate-400   ← secondary / muted text
```

**Heatmap integration** — `useTheme` is exported for use in BL-008's `interpolateColor()` so heatmap colors adapt to the active theme.

## Verification

1. Load `localhost:3000` — note the OS theme is applied with no flash
2. Click the toggle — entire page switches theme instantly
3. Refresh the page — theme is preserved from `localStorage`
4. Open DevTools → Application → localStorage — confirm `traderjoe-theme` key is set
5. Set OS preference to dark and clear localStorage — page should default to dark on next load
6. Focus the toggle with Tab, press Enter — theme should toggle (keyboard accessible)
