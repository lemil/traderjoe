# Phase 1 — traderjoe Web Dashboard

## Goal

Build a read-only web dashboard that visualises the JSON output produced by the traderjoe Python scripts. No backend, no live data feed — the site loads static JSON files and presents them clearly for options traders.

## Tech Stack

**Next.js 15 (App Router)** · TypeScript · Tailwind CSS · Recharts  
Location: `web/` subdirectory. JSON data served from `web/public/data/`.

---

## What Phase 1 Delivers

### Foundation (BL-001 to BL-003, BL-014)

Sets up the project and all shared infrastructure:

- A working Next.js project in `web/` with TypeScript and Tailwind
- JSON output files from the Python scripts copied into `web/public/data/` and served statically, with a manifest (`index.json`) listing available symbols and types
- Typed data models (`BSResult`, `OptionChain`, `OptionCell`, `Greeks`) and async loaders for all JSON files
- A `useDataLoader` hook, `<Spinner>`, `<ErrorCard>`, and `<ErrorBoundary>` shared by every view

### Shell and Navigation (BL-004, BL-009, BL-010)

Persistent chrome visible across all pages:

- Header with app name, symbol dropdown, and call/put toggle — synced to the URL (`?symbol=AAPL&type=call`) so every view is bookmarkable
- Tab navigation between Pricing, Chain, Greeks Surface, and IV Surface views
- Light/dark theme toggle with OS-preference detection and `localStorage` persistence

### Single Option Pricing Card (BL-005)

A card view for a single priced option (`fetch_bs_params_*.json`):

- Displays all five Black-Scholes inputs (S, K, T, r, σ) with correct units
- Shows BS price vs market mid price, with the difference color-coded green/red
- ITM / ATM / OTM moneyness badge
- All five Greeks (Δ, Γ, Θ, ν, ρ) with their correct per-unit labels

### Option Chain Matrix (BL-006, BL-007, BL-008, BL-011)

An interactive strike × expiry grid for a full option chain (`option_chain_*.json`):

- 74+ strike rows × 4 expiry columns with sticky headers and sticky strike column
- Field switcher to display any of: mid, bid, ask, IV, delta, gamma, theta, vega, volume, open interest
- ATM row highlighted in amber; ITM rows highlighted in blue — correct for call and put chains
- Optional heatmap overlay that color-codes cells by value intensity, with a diverging scale for signed Greeks and a sequential scale for prices/volume
- Responsive: horizontal-scroll container on mobile, full layout on desktop

### Visualisation (BL-012, BL-013)

Two chart views that render surfaces from the option chain data:

- **Greeks Surface** — one line per expiry showing how delta, gamma, theta, or vega varies across all strikes; ATM reference line; gaps where Greeks are null
- **IV Surface / Smile** — BS-implied and market-implied vol plotted against strike per expiry; Y-axis cap (default 200%) to suppress deep-ITM artifacts; identifies skew and term structure

---

## What Phase 1 Does Not Include

- Live market data — all data is static JSON refreshed manually by re-running the Python scripts
- Authentication or user accounts
- Put option chains (only call chains are currently generated; the single-option put pricer is supported)
- Writing or modifying any option parameters from the UI
- Deployment — local `npm run dev` only

---

## Backlog Summary

| ID | Title | Size | Sprint |
|---|---|---|---|
| BL-001 | Project Scaffold | S | 1 |
| BL-002 | Static Data Pipeline | S | 1 |
| BL-003 | TypeScript Types and Loaders | S | 1 |
| BL-014 | Loading and Error States | S | 1 |
| BL-004 | App Shell and Layout | M | 2 |
| BL-010 | Light/Dark Theme | S | 2 |
| BL-005 | Single Option Pricing Card | M | 3 |
| BL-006 | Option Chain Matrix Table | L | 3 |
| BL-009 | Symbol and Dataset Navigation | M | 3 |
| BL-007 | ATM/ITM Highlighting | S | 4 |
| BL-011 | Responsive Layout | M | 4 |
| BL-008 | Heatmap Coloring | M | 5 |
| BL-012 | Greeks Surface Chart | M | 5 |
| BL-013 | IV Surface / Smile Chart | M | 5 |

Detailed acceptance criteria, technical notes, and code sketches for each item live in [docs/backlog/](../backlog/).
