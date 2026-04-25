---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T04: Playwright e2e — /parts catalog + /parts/:id detail with mocked API + 3-viewport screenshots

Add `frontend/e2e/price-history.spec.ts` exercising both S06 surfaces against a deterministic mock backend so CI does not need uvicorn + sample data. Step 1: define module-level fixture objects: `MOCK_PARTS` (3 parts: one with multi-observation summary, one single, one zero), `MOCK_BATCH_RESPONSE` (PriceHistoryBatchResponse keyed by part id), `MOCK_SINGLE_SUMMARY` (PriceHistorySinglePartResponse for the multi-observation part), `MOCK_LISTINGS` (one fresh + one 90-days-stale listing for the multi part). Step 2: write a `mockApi(page)` helper that calls `page.route('**/api/**', ...)` and switches on the URL — handle GET /parts/with-votes (returns paginated MOCK_PARTS), POST /parts/price-history (returns MOCK_BATCH_RESPONSE), GET /parts/:id (returns MOCK_PARTS[match]), GET /parts/:id/listings, GET /parts/:id/price-history?legacy=true (returns array shape used by the legacy chart), GET /parts/:id/price-history (without legacy flag — returns MOCK_SINGLE_SUMMARY), and GET /api/users/me + /api/app-settings (return null + {} for the auth + settings shape — see e2e/smoke.spec.ts for the existing pattern). Step 3: write three tests: (a) `/parts catalog renders sparklines + delta lines` — navigates to /parts, waits for networkidle + fonts.ready + 300ms, registers a `pageerror` listener that throws, asserts the multi part card has `[role=img]` (sparkline) AND a 'over' text token from the delta line, asserts the zero part card has neither, then captures `toHaveScreenshot({ fullPage: true })`. (b) `/parts/:id detail renders retailer breakdown + stale caveat` — navigates to /parts/<multi-id>, waits, asserts the new 'Price summary (90 days)' heading is present, asserts the stale 'as of' text is present for the 90-day-stale listing AND absent for the fresh one, captures `toHaveScreenshot({ fullPage: true })`. (c) `/parts/:id with zero observations hides Price summary` — navigates to /parts/<zero-id>, asserts the 'Price summary' heading is NOT present. Generate baselines via `npx playwright test e2e/price-history.spec.ts --update-snapshots` and commit them under `frontend/e2e/price-history.spec.ts-snapshots/`. Step 4: in the same test file, register a network-call counter via `page.on('request', ...)` and assert that exactly ONE POST to `/parts/price-history` fires for the catalog test. The full `npm run test:e2e` must continue to pass — adding new tests must not regress smoke.spec.ts or components.spec.ts.

## Inputs

- ``frontend/e2e/components.spec.ts``
- ``frontend/e2e/smoke.spec.ts``
- ``frontend/playwright.config.ts``
- ``frontend/src/types/Api.ts``
- ``frontend/src/components/parts/PartList.tsx``
- ``frontend/src/pages/builder/ViewPart.tsx``

## Expected Output

- ``frontend/e2e/price-history.spec.ts``
- ``frontend/e2e/price-history.spec.ts-snapshots/price-history-catalog-sparklines-1-mobile-linux.png``
- ``frontend/e2e/price-history.spec.ts-snapshots/price-history-catalog-sparklines-1-tablet-linux.png``
- ``frontend/e2e/price-history.spec.ts-snapshots/price-history-catalog-sparklines-1-desktop-linux.png``
- ``frontend/e2e/price-history.spec.ts-snapshots/price-history-detail-retailer-breakdown-1-mobile-linux.png``
- ``frontend/e2e/price-history.spec.ts-snapshots/price-history-detail-retailer-breakdown-1-tablet-linux.png``
- ``frontend/e2e/price-history.spec.ts-snapshots/price-history-detail-retailer-breakdown-1-desktop-linux.png``

## Verification

cd frontend && npm run test:e2e

## Observability Impact

Playwright traces saved on first retry per existing config; pageerror listener re-throws runtime React errors as hard test failures (matches the components.spec.ts pattern from S08 MEM/T06). The network-request counter assertion is the canonical proof that the catalog uses the BATCH endpoint, not per-row fetches.
