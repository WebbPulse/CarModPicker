---
id: T04
parent: S10
milestone: M002
key_files:
  - frontend/e2e/parts-catalog.spec.ts
  - frontend/e2e/parts-catalog.spec.ts-snapshots/parts-catalog-visual-regression-1-mobile-linux.png
  - frontend/e2e/parts-catalog.spec.ts-snapshots/parts-catalog-visual-regression-1-tablet-linux.png
  - frontend/e2e/parts-catalog.spec.ts-snapshots/parts-catalog-visual-regression-1-desktop-linux.png
key_decisions:
  - Used page.setViewportSize({ width: 2400, height: 900 }) BEFORE setupPage in the dialog test — the default 1280px desktop viewport's responsive table drops the actions column (priority 7) after sidebar+Tailwind container caps, so the AddToBuildList trigger is not in the DOM. Wider viewport keeps the column. Captured as gotcha memory for S12 ripple work.
  - Adapted the build-lists mock from the plan's /api/build-lists/?user_id=... to GET /build-lists/user/{userId} after reading frontend/src/api/build_lists.ts — buildListsApi.getBuildListsByUser hits the nested path, not the query-param flavor.
  - Mocked /api/users/me as MOCK_USER (200) — diverging from price-history.spec.ts which mocks anonymous (401). Authenticated mock is required so PartsCatalog renders the My Parts link AND PartList exposes parts-catalog-add-to-build-list-trigger via showAddToBuildListButton.
  - Per-project gating uses testInfo.project.name (MEM105) for the dialog and tab tests rather than process.env — keeps skip reasons in the HTML report and avoids env-coupling.
  - Tab test asserts via document.activeElement.dataset.testid === 'parts-catalog-search' (matching the test-id on the Input), not on element text — Inputs don't expose textContent reliably.
duration: 
verification_result: passed
completed_at: 2026-04-25T23:46:18.517Z
blocker_discovered: false
---

# T04: test: Add Playwright e2e parts-catalog.spec.ts — multi-viewport visual regression, AddToBuildList dialog focus/Escape, Tab keyboard test

**test: Add Playwright e2e parts-catalog.spec.ts — multi-viewport visual regression, AddToBuildList dialog focus/Escape, Tab keyboard test**

## What Happened

Authored frontend/e2e/parts-catalog.spec.ts modeled on frontend/e2e/price-history.spec.ts (S06/T04) and frontend/e2e/build-list.spec.ts (S09/T04). The spec mocks the full /api/* surface needed by /parts (auth → MOCK_USER, app-settings, categories, part-manufacturers, car-generations stats/by-ids, parts/with-votes returning a 3-part fixture mirroring the multi/single/zero-observation pattern from S06, parts/filter-options, parts/price-history GET (per-part lazy SparklineCell fetch), POST /parts/price-history (batch — counter-incremented), build-lists/user/{userId} for the AddToBuildList dialog's multi-select, votes summary), and any unmocked /api/* path falls through to a default-404 with Mock-miss detail to surface drift. Conventions enforced: page.route() regex /\\/api\\/(?!.*\\.ts)/ (MEM082), pre-accepted cookie-consent (MEM098), pre-dismissed chrome-extension promo for today (MEM108), pinned Date.now() to FIXED_NOW_ISO, page.on('pageerror') re-throws, MEM079 scrollIntoViewIfNeeded for the multi-observation row's IO-gated sparkline.\n\nThree tests authored:\n  1. parts catalog visual regression — runs at mobile/tablet/desktop, scrolls the MULTI_PART_ID container into view, asserts the [role='img'] sparkline visible, asserts exactly ONE batch POST to /parts/price-history (S06 invariant) via both the route counter and a request-listener witness, then page.toHaveScreenshot fullPage. Three baseline PNGs land under e2e/parts-catalog.spec.ts-snapshots/parts-catalog-visual-regression-1-{mobile,tablet,desktop}-linux.png.\n  2. add-to-build-list dialog opens, focus moves into it, Escape closes it — desktop-only via testInfo.project.name (MEM105). The default 1280px desktop viewport drops the table's `actions` column (priority 7) after sidebar+container caps; the test calls page.setViewportSize({ width: 2400, height: 900 }) BEFORE setupPage so the AddToBuildList trigger is in the DOM. Clicks parts-catalog-add-to-build-list-trigger.first(), expects parts-catalog-add-to-build-list-dialog visible, evaluates document.activeElement is contained by the dialog (Radix focus trap), presses Escape, expects dialog hidden.\n  3. tab traversal lands visible focus on search input — desktop-only. Focuses document.body, presses Tab up to 30 times until document.activeElement.dataset.testid === 'parts-catalog-search', then asserts the focused element matches :focus-visible AND has a non-empty outline OR boxShadow (R020 visible focus ring on ui/Input).\n\nGenerated baselines once with `npm run test:e2e -- parts-catalog --update-snapshots`. Final clean run: 5 passed (3 visual + 1 dialog desktop + 1 tab desktop) + 4 skipped (dialog/tab on mobile/tablet) in ~4s.\n\nDuring authoring, hit one local mismatch with the task plan: the plan said /api/build-lists/?user_id=... but buildListsApi.getBuildListsByUser hits /build-lists/user/{userId}. Adapted the mock router accordingly. Captured the responsive-table actions-column drop as a gotcha memory for future Playwright work on /parts.

## Verification

Ran `cd frontend && npm run test:e2e -- parts-catalog` (slice plan's Verification command). All 9 tests across 3 projects pass: 5 passed, 4 skipped (per-project skips on dialog and Tab tests), 0 failed. Baselines on disk under frontend/e2e/parts-catalog.spec.ts-snapshots/. Type-check clean (`npx tsc --noEmit -p e2e/tsconfig.json` — no output).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npx tsc --noEmit -p e2e/tsconfig.json` | 0 | ✅ pass | 4000ms |
| 2 | `cd frontend && npm run test:e2e -- parts-catalog --update-snapshots` | 0 | ✅ pass (baselines generated) | 9200ms |
| 3 | `cd frontend && npm run test:e2e -- parts-catalog --project=desktop -g dialog` | 0 | ✅ pass | 4200ms |
| 4 | `cd frontend && npm run test:e2e -- parts-catalog` | 0 | ✅ pass (5 passed, 4 skipped) | 4000ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `frontend/e2e/parts-catalog.spec.ts`
- `frontend/e2e/parts-catalog.spec.ts-snapshots/parts-catalog-visual-regression-1-mobile-linux.png`
- `frontend/e2e/parts-catalog.spec.ts-snapshots/parts-catalog-visual-regression-1-tablet-linux.png`
- `frontend/e2e/parts-catalog.spec.ts-snapshots/parts-catalog-visual-regression-1-desktop-linux.png`
