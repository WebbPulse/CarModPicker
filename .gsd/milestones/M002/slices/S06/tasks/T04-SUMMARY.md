---
id: T04
parent: S06
milestone: M002
key_files:
  - frontend/e2e/price-history.spec.ts
  - frontend/e2e/price-history.spec.ts-snapshots/-parts-catalog-renders-sparklines-delta-lines-1-mobile-linux.png
  - frontend/e2e/price-history.spec.ts-snapshots/-parts-catalog-renders-sparklines-delta-lines-1-tablet-linux.png
  - frontend/e2e/price-history.spec.ts-snapshots/-parts-catalog-renders-sparklines-delta-lines-1-desktop-linux.png
  - frontend/e2e/price-history.spec.ts-snapshots/-parts-id-detail-renders-retailer-breakdown-stale-caveat-1-mobile-linux.png
  - frontend/e2e/price-history.spec.ts-snapshots/-parts-id-detail-renders-retailer-breakdown-stale-caveat-1-tablet-linux.png
  - frontend/e2e/price-history.spec.ts-snapshots/-parts-id-detail-renders-retailer-breakdown-stale-caveat-1-desktop-linux.png
key_decisions:
  - Restricted page.route() matcher to /\/api\/(?!.*\.ts)/ so Vite's source-module URLs at /src/api/*.ts are NOT intercepted (MEM078) — intercepting them with JSON crashes the bundle.
  - Used scrollIntoViewIfNeeded() on the multi-observation row's [data-part-id] before asserting [role=img] visibility — IntersectionObserver-driven SparklineCell needs the row in view to fire its lazy fetch, and the responsive table scrolls horizontally on tablet/mobile (MEM079).
  - Pinned Date.now() via page.addInitScript so the 60-day stale-caveat threshold is deterministic across CI runs without affecting Playwright/React internals that use the Date constructor.
  - Used dual network-counter (route handler + page.on('request') listener) for the 1-batch-POST assertion — belt-and-braces witness that survives even if the route mock is bypassed.
  - Accepted the divergence between the plan's heuristic snapshot filenames and Playwright's actual test-title-derived slugs — Playwright's naming is canonical and the file count/coverage matches the plan.
duration: 
verification_result: passed
completed_at: 2026-04-25T21:56:14.080Z
blocker_discovered: false
---

# T04: Add Playwright e2e spec covering /parts catalog sparklines + /parts/:id retailer breakdown across 3 viewports with mocked API and 1-batch-POST contract assertion

**Add Playwright e2e spec covering /parts catalog sparklines + /parts/:id retailer breakdown across 3 viewports with mocked API and 1-batch-POST contract assertion**

## What Happened

Verified the prior-session implementation of `frontend/e2e/price-history.spec.ts` plus its 6 baseline screenshots (3 viewports × 2 screenshot tests) under `frontend/e2e/price-history.spec.ts-snapshots/` matches the T04 plan exactly and that the slice verification command (`cd frontend && npm run test:e2e`) is green.

The spec defines module-level fixtures for three parts (multi/single/zero observation), a deterministic `mockApi(page)` router that intercepts only the `/api/` path (not Vite's `/src/api/*.ts` source modules — see MEM078), and three tests:

1. `/parts catalog renders sparklines + delta lines` — pins `Date.now()` for stable stale-caveat math, registers a `pageerror` listener that re-throws, scrolls the multi-observation row's `[data-part-id=...]` into view (MEM079: tablet/mobile horizontally scroll the responsive table), asserts the multi row has both a sparkline `[role=img]` and the `$120 → $150` delta token, asserts the zero row has neither, asserts exactly ONE POST `/parts/price-history` fired (proves the BATCH endpoint is in use, not per-row fetches), then captures `toHaveScreenshot({ fullPage: true })`.
2. `/parts/:id detail renders retailer breakdown + stale caveat` — asserts the new "Price summary (90 days)" heading, asserts the `(as of <date>)` stale caveat appears exactly once (fresh listing has none, 90-day-stale listing has one), captures full-page screenshot.
3. `/parts/:id with zero observations hides Price summary block` — asserts the retailer-breakdown rows / stat-strip test surfaces are absent for the zero-observation part.

Cross-checked `playwright.config.ts` confirms 3 chromium-only projects (mobile 375×667, tablet 768×1024, desktop 1280×800) all spreading `devices['Desktop Chrome']` so baselines stay engine-consistent (MEM066/MEM068).

Ran `cd frontend && npm run test:e2e` — 15/15 passed in 6.0s (3 viewports × 5 tests: 3 price-history + 1 smoke + 1 components). Smoke and components specs continue to pass — no regression. Vite proxy ECONNREFUSED messages in stderr are dev-server noise (no real backend running) and do not affect the tests since `page.route()` short-circuits all `/api/` calls before they hit the proxy.

Note on plan/output naming: the T04 plan's Expected Output filenames (`price-history-catalog-sparklines-1-mobile-linux.png`, etc.) are heuristic — Playwright derives snapshot filenames from the actual test title. The committed snapshots use the canonical Playwright slug (e.g. `-parts-catalog-renders-sparklines-delta-lines-1-desktop-linux.png`). Functionally equivalent; only the filename is different from the plan's guess.

## Verification

Ran the slice verification command from the task plan: `cd frontend && npm run test:e2e`. All 15 tests passed in 6.0s across mobile/tablet/desktop projects — including all 3 new price-history tests, smoke.spec.ts, and components.spec.ts (no regression). The catalog test's network-call-counter assertion (`counters.batchPriceHistoryPostCount === 1` AND `observedBatchPosts === 1`) confirms the catalog uses exactly ONE POST `/parts/price-history` per displayed page, satisfying the slice plan's "exactly one POST /parts/price-history per displayed catalog page" runtime signal. Visual baselines are stable (maxDiffPixelRatio 0.002).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd frontend && npm run test:e2e` | 0 | ✅ pass | 6000ms |

## Deviations

Snapshot filenames diverge from the plan's Expected Output names (the plan listed `price-history-catalog-sparklines-1-mobile-linux.png` etc., but Playwright slugs the actual test title, producing `-parts-catalog-renders-sparklines-delta-lines-1-mobile-linux.png` etc.). Functionally equivalent — same 6 files, same coverage, same viewport projects.

## Known Issues

None.

## Files Created/Modified

- `frontend/e2e/price-history.spec.ts`
- `frontend/e2e/price-history.spec.ts-snapshots/-parts-catalog-renders-sparklines-delta-lines-1-mobile-linux.png`
- `frontend/e2e/price-history.spec.ts-snapshots/-parts-catalog-renders-sparklines-delta-lines-1-tablet-linux.png`
- `frontend/e2e/price-history.spec.ts-snapshots/-parts-catalog-renders-sparklines-delta-lines-1-desktop-linux.png`
- `frontend/e2e/price-history.spec.ts-snapshots/-parts-id-detail-renders-retailer-breakdown-stale-caveat-1-mobile-linux.png`
- `frontend/e2e/price-history.spec.ts-snapshots/-parts-id-detail-renders-retailer-breakdown-stale-caveat-1-tablet-linux.png`
- `frontend/e2e/price-history.spec.ts-snapshots/-parts-id-detail-renders-retailer-breakdown-stale-caveat-1-desktop-linux.png`
