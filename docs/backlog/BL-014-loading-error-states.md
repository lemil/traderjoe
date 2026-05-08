# BL-014 — Shared Loading and Error States

**Size**: S  
**Dependencies**: BL-001, BL-010

## User Story

As a trader, I want clear feedback when data is loading or unavailable so that I'm never left staring at a blank, broken screen and I can recover from errors without a full page reload.

## Acceptance Criteria

- A `<Spinner />` component renders a centered animated loading indicator with an optional text label
- An `<ErrorCard />` component renders a styled error message with a "Retry" button
- A `useDataLoader<T>` hook wraps async fetches and exposes `{ data, loading, error, retry }` — used by all data-fetching components
- A `<ErrorBoundary />` class component wraps each route, catching uncaught render errors and showing a fallback "Reload page" UI instead of a blank screen
- All loading and error components are theme-aware (work in both light and dark modes from BL-010)

## Technical Notes

**`components/Spinner.tsx`:**
```tsx
interface SpinnerProps {
  label?: string;
}
export default function Spinner({ label }: SpinnerProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-slate-400 dark:text-slate-500">
      <div className="w-8 h-8 rounded-full border-4 border-slate-200 dark:border-slate-700 border-t-blue-500 animate-spin" />
      {label && <p className="text-sm">{label}</p>}
    </div>
  );
}
```

**`components/ErrorCard.tsx`:**
```tsx
interface ErrorCardProps {
  message: string;
  onRetry?: () => void;
}
export default function ErrorCard({ message, onRetry }: ErrorCardProps) {
  return (
    <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-6 text-center">
      <p className="text-red-700 dark:text-red-300 text-sm mb-3">{message}</p>
      {onRetry && (
        <button onClick={onRetry}
          className="px-4 py-1.5 text-sm rounded bg-red-600 hover:bg-red-700 text-white transition-colors">
          Retry
        </button>
      )}
    </div>
  );
}
```

**`hooks/useDataLoader.ts`:**
```typescript
'use client';
import { useEffect, useState, useCallback } from 'react';

export function useDataLoader<T>(
  fetcher: () => Promise<T>,
  deps: unknown[]
): { data: T | null; loading: boolean; error: string | null; retry: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetcher()
      .then(d => { if (!cancelled) setData(d); })
      .catch(e => { if (!cancelled) setError(String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  const retry = useCallback(() => setTick(t => t + 1), []);
  return { data, loading, error, retry };
}
```

**`components/ErrorBoundary.tsx`** (class component — required by React API):
```tsx
import { Component, ReactNode } from 'react';

interface Props { children: ReactNode; }
interface State { hasError: boolean; message: string; }

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, message: '' };
  }
  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message };
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center min-h-[40vh] gap-4 p-8">
          <p className="text-slate-600 dark:text-slate-400 text-sm">Something went wrong.</p>
          <p className="font-mono text-xs text-red-500">{this.state.message}</p>
          <button onClick={() => window.location.reload()}
            className="px-4 py-2 rounded bg-blue-600 text-white text-sm hover:bg-blue-700">
            Reload page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
```

**Wire up ErrorBoundary in `app/layout.tsx`:**
```tsx
<Shell>
  <ErrorBoundary>
    {children}
  </ErrorBoundary>
</Shell>
```

**Usage in data-fetching components** (BL-005, BL-006, BL-012, BL-013):
```tsx
const { data: chain, loading, error, retry } = useDataLoader(
  () => loadOptionChain(symbol, type),
  [symbol, type]
);

if (loading) return <Spinner label="Loading option chain..." />;
if (error || !chain) return <ErrorCard message={error ?? 'Data unavailable'} onRetry={retry} />;
```

## Verification

1. Temporarily break a fetch URL (rename a JSON file) — spinner appears then error card with Retry
2. Click Retry — fetch attempts again (tick increments)
3. Restore the file and click Retry — data loads successfully
4. Throw an error inside a component's render — ErrorBoundary catches it, shows "Reload page" UI
5. Verify Spinner and ErrorCard look correct in both light and dark themes
