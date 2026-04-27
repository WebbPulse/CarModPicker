---
estimated_steps: 19
estimated_files: 6
skills_used: []
---

# T05: Refresh Playwright visual-regression baselines at 3 viewports for every page touched by S01

Per-slice baseline refresh (R060, MEM148). Every page touched by T02–T04 needs `toHaveScreenshot()` baselines refreshed at the 3 configured viewports (mobile 375×667, tablet 768×1024, desktop 1280×800 — these are what `playwright.config.ts` actually defines; the M003 vocabulary calls mobile '360' but the implemented value is 375 and we keep it that way for S01 — see research).

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| Backend dev server (`uvicorn`) | If backend down, frontend e2e specs fail at network calls. Mitigation: start `cd backend && docker-compose up -d && uvicorn app.main:app --port 8000` before running Playwright. | 120s playwright `webServer` timeout | N/A |
| Frontend dev server (`npm run dev`) | playwright.config.ts auto-starts via `webServer` config; reuses existing if running. | 120s timeout | N/A |

## Load Profile

- **Shared resources**: dev backend (sample data), dev frontend (Vite HMR), Playwright workers (`fullyParallel: true`).
- **Per-operation cost**: ~24 PNGs at 3 viewports across ~8 specs. Full sweep ~3–5 min on a warm machine.
- **10x breakpoint**: N/A — single dev-machine run.

## Negative Tests

- After refresh, run the full Playwright suite WITHOUT `--update-snapshots` and confirm 0 diffs. Any non-zero diff means the refresh missed a viewport or spec.
- Inspect each refreshed PNG diff (or the `playwright-report/` HTML) before commit. Expected diffs are limited to color-channel changes (token-swap noise — usually <1px shift). Anything else (layout shift, font change, structural rearrangement) is a real regression and must be investigated, not blindly accepted.

## Steps

1. Ensure backend + frontend dev servers are reachable. If not running, start them: `cd backend && docker-compose up -d` then `uvicorn app.main:app --port 8000` in one terminal; `cd frontend && npm run dev` in another (or rely on Playwright's webServer config).
2. Run `cd frontend && npx playwright test --update-snapshots` to refresh ALL baselines. Specs touched by S01: `admin.spec.ts`, `build-list.spec.ts`, `components.spec.ts`, `parts-catalog.spec.ts`, `price-alerts.spec.ts`, `price-history.spec.ts` — all six are at risk because S01 touches admin pages, build-list pages, kitchen-sink (alert.tsx success variant), parts pages, and price pages.
3. After update, re-run `npx playwright test` (without `--update-snapshots`) and confirm 0 diffs.
4. Spot-check 3–5 refreshed PNGs visually (e.g. `frontend/e2e/parts-catalog.spec.ts-snapshots/*-mobile-linux.png`) — confirm diffs are limited to expected token-swap color changes (text-neutral-400 → text-muted-foreground, etc.). No layout / font / structural diffs.
5. Stage all refreshed `.png` files for commit alongside the migration commits.

## Inputs

- `frontend/playwright.config.ts`
- `frontend/e2e/admin.spec.ts`
- `frontend/e2e/build-list.spec.ts`
- `frontend/e2e/components.spec.ts`
- `frontend/e2e/parts-catalog.spec.ts`
- `frontend/e2e/price-alerts.spec.ts`
- `frontend/e2e/price-history.spec.ts`

## Expected Output

- `frontend/e2e/admin.spec.ts-snapshots/`
- `frontend/e2e/build-list.spec.ts-snapshots/`
- `frontend/e2e/components.spec.ts-snapshots/`
- `frontend/e2e/parts-catalog.spec.ts-snapshots/`
- `frontend/e2e/price-alerts.spec.ts-snapshots/`
- `frontend/e2e/price-history.spec.ts-snapshots/`

## Verification

cd frontend && npx playwright test 2>&1 | tee /tmp/playwright-s01-verify.log | grep -E '(passed|failed)' && grep -q 'failed' /tmp/playwright-s01-verify.log && exit 1 || echo 'all snapshots green'
