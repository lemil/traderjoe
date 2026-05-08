# BL-002 — Static Data Pipeline

**Size**: S  
**Dependencies**: BL-001

## User Story

As a developer, I want the JSON output files from the traderjoe Python scripts to be served as static assets so that the frontend can load them with a plain `fetch()` call and no backend is required.

## Acceptance Criteria

- The following files exist under `web/public/data/` and are accessible at runtime:
  - `fetch_bs_params_AAPL.json` (AAPL call pricing)
  - `fetch_bs_params_AAPL_put.json` (AAPL put pricing)
  - `fetch_bs_params_NVDA.json` (NVDA call pricing)
  - `option_chain_AAPL.json` (AAPL call option chain)
  - `option_chain_NVDA.json` (NVDA call option chain)
- A manifest file `web/public/data/index.json` exists and is valid JSON
- During `npm run dev`, `fetch("/data/option_chain_AAPL.json")` returns a 200 with the correct JSON body
- `web/README.md` documents how to regenerate data files and update the manifest

## Technical Notes

**File naming conventions:**
| Python output | Web asset path |
|---|---|
| `tmp/output/fetch_bs_params_AAPL.json` | `web/public/data/fetch_bs_params_AAPL.json` |
| `tmp/output/fetch_bs_params_AAPL_put.json` | `web/public/data/fetch_bs_params_AAPL_put.json` |
| `tmp/output/fetch_bs_params_NVDA.json` | `web/public/data/fetch_bs_params_NVDA.json` |
| `tmp/output/option_chain_AAPL.json` | `web/public/data/option_chain_AAPL.json` |
| `tmp/output/option_chain_NVDA.json` | `web/public/data/option_chain_NVDA.json` |

**Manifest file** (`web/public/data/index.json`):
```json
{
  "symbols": ["AAPL", "NVDA"],
  "chainTypes": ["call"],
  "pricingTypes": {
    "AAPL": ["call", "put"],
    "NVDA": ["call"]
  }
}
```
The symbol navigator (BL-009) reads this manifest to know which datasets are available. Update it whenever new output files are added.

**Regenerating data** — document this workflow in `web/README.md`:
```bash
# From repo root, re-run scripts to refresh data
.venv/Scripts/python -m traderjoe.fetch_bs_params AAPL --json > tmp/output/fetch_bs_params_AAPL.json
.venv/Scripts/python -m traderjoe.fetch_bs_params AAPL --type put --json > tmp/output/fetch_bs_params_AAPL_put.json
.venv/Scripts/python -m traderjoe.fetch_bs_params NVDA --json > tmp/output/fetch_bs_params_NVDA.json
# Then copy to web/public/data/
cp tmp/output/*.json web/public/data/
```

**Files in `public/`** are served verbatim by Next.js — no import or API route needed.

## Verification

```bash
cd web && npm run dev
# In a browser or terminal:
curl http://localhost:3000/data/index.json        # should return the manifest
curl http://localhost:3000/data/option_chain_AAPL.json | head -c 200  # should return JSON
```
