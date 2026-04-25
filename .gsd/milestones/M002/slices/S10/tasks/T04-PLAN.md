---
estimated_steps: 27
estimated_files: 4
skills_used: []
---

# T04: Add frontend/e2e/parts-catalog.spec.ts with mocked fixtures, multi-viewport screenshots, sparkline assertion, dialog focus + Escape, and Tab keyboard test

Create a new Playwright spec for /parts that runs at mobile/tablet/desktop (already configured in playwright.config.ts) and asserts the slice's R015 + R020 success criteria plus the S06 sparkline integration invariant.

Follow the conventions established in frontend/e2e/price-history.spec.ts (S06/T04) and frontend/e2e/build-list.spec.ts (S09/T04):
- page.route() URL matcher MUST be `/\/api\/(?!.*\.ts)/` (MEM082) — never use **/api/** glob.
- Pre-accept cookie-consent banner via page.addInitScript (MEM098).
- Pre-dismiss chrome-extension promo via addInitScript writing chrome_extension_promo_last_dismissed=YYYY-MM-DD (MEM108).
- Pin Date.now() via addInitScript to FIXED_NOW_ISO so any 'now'-dependent rendering is deterministic.
- page.on('pageerror', err => { throw err }) so runtime React errors fail the test loudly.
- Authenticate the mocked user (MOCK_USER returned from /api/users/me) so the 'Add to Build List' affordance and the 'My Parts' link both render — the catalog page checks isAuthenticated.

Mock fixtures needed (modeled on price-history.spec.ts mockApi router):
- GET /api/users/me → MOCK_USER (200, authenticated — distinguishes this spec from price-history.spec.ts which mocks anonymous 401)
- GET /api/app-settings/ → { premium_disabled: true, updated_at: FIXED_NOW_ISO }
- GET /api/categories/ → [MOCK_CATEGORY]
- GET /api/part-manufacturers/?active_only=true → [MOCK_PART_MANUFACTURER]
- GET /api/car-generations/stats/car-makes → {}
- GET /api/car-generations/by-ids → [] (used by PartList's on-demand car lookup)
- GET /api/parts/with-votes → MOCK_PAGINATED_PARTS (3 parts: multi-obs / single-obs / zero-obs, mirrors price-history.spec.ts)
- GET /api/parts/filter-options → { category_ids:[MOCK_CATEGORY_ID], part_manufacturer_ids:[MOCK_PART_MANUFACTURER_ID], car_ids:[], make_names:[] }
- POST /api/parts/price-history → MOCK_BATCH_RESPONSE (counter-incremented to assert exactly 1 call per page)
- GET /api/build-lists/?user_id=... → 1-entry MOCK_BUILD_LISTS array (so T04 dialog test sees a build-list row in the multi-select)
- Default 404 with `Mock miss: ${method} ${path}` (catches drift)

Tests to author:
  1. 'parts catalog visual regression' — goto /parts, waitForPageReady (networkidle + fonts.ready + 300ms), scrollIntoViewIfNeeded the multi-observation row (MEM079/MEM083) so the SparklineCell IO observer fires deterministically across all 3 projects, expect [data-part-id='${MULTI_PART_ID}'] [role='img'] toBeVisible, expect counters.batchPriceHistoryPostCount toBe 1 (S06 invariant), expect(page).toHaveScreenshot({ fullPage: true }). Three baseline PNGs land under e2e/parts-catalog.spec.ts-snapshots/parts-catalog-visual-regression-1-{mobile,tablet,desktop}-linux.png on first run.
  2. 'add-to-build-list dialog opens, focus moves into it, Escape closes it' — desktop only (test.skip on mobile/tablet to keep suite light) — click [data-testid='parts-catalog-add-to-build-list-trigger'].first(), expect [data-testid='parts-catalog-add-to-build-list-dialog'] toBeVisible, expect locator(':focus') to resolve to a node inside the dialog, press Escape, expect dialog toBeHidden.
  3. 'tab traversal lands visible focus on search input' — desktop only — page.keyboard.press('Tab') a couple of times until reaching the search input, assert via page.evaluate(() => document.activeElement?.dataset.testid === 'parts-catalog-search'). Allow up to 5 tabs to absorb any leading skip-link / 'My Parts' link focus.

Run npx playwright test parts-catalog --update-snapshots once locally to generate baselines, then commit baselines + spec.

Failure modes: a stray non-mocked /api/* call surfaces as a default-404 + console error → pageerror → hard test failure. Negative tests: the keyboard test guards R020 regression; the Escape-closes test guards Radix focus management. Load profile: per spec run, ~10 mocked HTTP calls per project + 3 snapshots; total runtime ~10s.

Threat surface: spec consumes mocked fixtures only; no real DB or network. The MOCK_USER's id matches the build-list fixture's user_id so the canManage / showAddToBuildListButton gate evaluates true.

## Inputs

- ``frontend/e2e/price-history.spec.ts``
- ``frontend/e2e/build-list.spec.ts``
- ``frontend/playwright.config.ts``
- ``frontend/src/pages/parts/PartsCatalog.tsx``
- ``frontend/src/components/parts/PartList.tsx``
- ``frontend/src/components/parts/AddToBuildListDialog.tsx``

## Expected Output

- ``frontend/e2e/parts-catalog.spec.ts``
- ``frontend/e2e/parts-catalog.spec.ts-snapshots/parts-catalog-visual-regression-1-mobile-linux.png``
- ``frontend/e2e/parts-catalog.spec.ts-snapshots/parts-catalog-visual-regression-1-tablet-linux.png``
- ``frontend/e2e/parts-catalog.spec.ts-snapshots/parts-catalog-visual-regression-1-desktop-linux.png``

## Verification

cd frontend && npm run test:e2e -- parts-catalog

## Observability Impact

Test failures surface via Playwright HTML reporter at frontend/playwright-report/ and pixel-diff PNGs at frontend/test-results/. pageerror listener in the spec re-throws runtime React errors as hard test failures.
