# BL-004 — App Shell and Layout

**Size**: M  
**Dependencies**: BL-001, BL-003

## User Story

As a trader, I want a consistent page frame with a header and navigation so that I can always orient myself and move between the Pricing Card and Option Chain views.

## Acceptance Criteria

- A persistent top header shows the app name "traderjoe" and the current symbol + option type
- Navigation tabs (or sidebar) allow switching between at least: **Pricing**, **Chain**, **Greeks Surface**, **IV Surface**
- The active route is visually indicated (bold tab, underline, or accent border)
- The main content area fills the remaining viewport height; inner sections scroll independently (no full-page scroll for the shell itself)
- On mobile (< 768px), navigation collapses to a compact bottom tab bar or hamburger menu
- A theme toggle button (sun/moon icon) lives in the header (wired to actual logic in BL-010)
- The shell renders correctly at 375px, 768px, and 1440px widths with no layout overflow

## Technical Notes

**File structure:**
```
app/
├── layout.tsx          ← root layout: renders <Shell> around <children>
├── page.tsx            ← redirect to /pricing (use next/navigation redirect())
├── pricing/
│   └── page.tsx        ← renders <PricingCard /> (BL-005)
├── chain/
│   └── page.tsx        ← renders <ChainTable /> (BL-006)
├── surface/
│   └── page.tsx        ← renders <GreeksSurface /> (BL-012)
└── iv/
    └── page.tsx        ← renders <IVSurface /> (BL-013)

components/
└── Shell.tsx           ← "use client" — header + nav + slot for children
```

**`app/layout.tsx`** (Server Component):
```tsx
import Shell from '@/components/Shell';
import './globals.css';

export const metadata = { title: 'traderjoe' };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
```

**`components/Shell.tsx`** skeleton:
```tsx
'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const NAV = [
  { href: '/pricing', label: 'Pricing' },
  { href: '/chain',   label: 'Chain' },
  { href: '/surface', label: 'Greeks' },
  { href: '/iv',      label: 'IV Surface' },
];

export default function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  return (
    <div className="flex flex-col h-screen bg-white dark:bg-slate-900">
      <header className="flex items-center justify-between px-4 h-14 border-b border-slate-200 dark:border-slate-700 shrink-0">
        <span className="font-bold text-lg tracking-tight">traderjoe</span>
        <nav className="hidden md:flex gap-1">
          {NAV.map(n => (
            <Link key={n.href} href={n.href}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors
                ${path.startsWith(n.href)
                  ? 'bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-white'
                  : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800'}`}>
              {n.label}
            </Link>
          ))}
        </nav>
        {/* Theme toggle placeholder — wired in BL-010 */}
        <button aria-label="Toggle theme" className="p-2 rounded hover:bg-slate-100 dark:hover:bg-slate-800">
          ☀️
        </button>
      </header>
      <main className="flex-1 overflow-y-auto p-4 md:p-6">
        {children}
      </main>
      {/* Mobile bottom nav */}
      <nav className="md:hidden flex border-t border-slate-200 dark:border-slate-700 shrink-0">
        {NAV.map(n => (
          <Link key={n.href} href={n.href}
            className={`flex-1 py-2 text-center text-xs font-medium
              ${path.startsWith(n.href) ? 'text-blue-600' : 'text-slate-500'}`}>
            {n.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
```

**Symbol/type context** — `app/layout.tsx` should NOT embed AppContext (layout is a Server Component). Instead, each page reads `?symbol=AAPL&type=call` from `useSearchParams` directly. The shell header can display the symbol by reading search params from a client component slot.

**`app/page.tsx`** — redirect to default view:
```tsx
import { redirect } from 'next/navigation';
export default function Home() {
  redirect('/pricing?symbol=AAPL&type=call');
}
```

## Verification

1. `npm run dev` — navigate to `localhost:3000`, confirm redirect to `/pricing?symbol=AAPL&type=call`
2. Click each nav tab — active tab should highlight, URL should change
3. Resize browser to 375px — bottom nav should appear, top nav should hide
4. Run `npm run build` — no TypeScript errors
