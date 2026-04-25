---
estimated_steps: 25
estimated_files: 4
skills_used: []
---

# T04: Add frontend/e2e/build-list.spec.ts with mocked fixtures, multi-viewport screenshots, and keyboard assertions

Create a new Playwright spec for /build-lists/{id} that runs at mobile/tablet/desktop (already configured in playwright.config.ts) and asserts the slice's R014 + R020 success criteria.

Follow the conventions established in frontend/e2e/price-alerts.spec.ts (S07/T06):
  - page.route() URL matcher MUST be /\/api\/(?!.*\.ts)/ (MEM082) — never use **/api/** glob.
  - Pre-accept cookie-consent banner via page.addInitScript so the mobile (375px) viewport doesn't have the banner overlay obscure interactive controls (MEM098).
  - Pin Date.now via addInitScript to FIXED_NOW_ISO so any 'now'-dependent rendering is deterministic.
  - page.on('pageerror', err => { throw err }) so runtime React errors fail the test loudly.

Mock fixtures needed (from inspecting ViewBuildList + BuildListParts fetch paths):
  - GET /api/users/me → MOCK_USER
  - GET /api/app-settings/ → { premium_disabled: true, updated_at: FIXED_NOW_ISO }
  - GET /api/build-lists/{id} → MOCK_BUILD_LIST (with car_id set)
  - GET /api/car-generations/{carId} → MOCK_CAR
  - GET /api/users/{userId} → MOCK_USER
  - GET /api/votes/build_list/{id}/summary → MOCK_VOTE_SUMMARY
  - GET /api/build-list-parts/{id}/parts → []  (empty parts is fine — slice-level concern is page chrome + dialogs)
  - GET /api/build-lists/{id}/phases → []
  - GET /api/categories/ → []
  - GET /api/part-manufacturers/?active_only=true → []
  - GET /api/car-generations/?limit=... → []  (LARGE_FETCH_LIMIT cars list)
  - Default 404 with detail: 'Mock miss: {method} {path}' so unexpected calls surface in pageerror.

Tests to author:
  1. 'build-list detail visual regression' — goto /build-lists/{id}, waitForPageReady (networkidle + fonts.ready + 300ms), expect(page).toHaveScreenshot({ fullPage: true }). Three baseline PNGs land under e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-{mobile,tablet,desktop}-linux.png on first run.
  2. 'edit dialog opens, focuses, and Escape closes' — run only on the desktop project (use test.skip(project === 'mobile' || project === 'tablet') to keep the suite small) — click [data-testid="build-list-edit-trigger"], expect [data-testid="build-list-edit-dialog"] toBeVisible, expect locator(':focus') to be inside the dialog, press Escape, expect dialog toBeHidden.
  3. 'tab order surfaces visible focus on first interactive control' — desktop only — page.keyboard.press('Tab') a few times until reaching the first action (View Build Log button), assert it's the focused element via page.evaluate(() => document.activeElement?.dataset.testid).

Run npx playwright test build-list --update-snapshots for the first run to generate baselines, then commit baselines + spec.

Negative tests: the keyboard test guards against R020 regression; the Escape-closes test guards Radix focus management. Failure modes covered: a stray non-mocked /api/* request will trigger 404 + console error → pageerror → hard test failure.

## Inputs

- ``frontend/e2e/price-alerts.spec.ts``
- ``frontend/e2e/components.spec.ts``
- ``frontend/playwright.config.ts``
- ``frontend/src/pages/builder/ViewBuildlist.tsx``
- ``frontend/src/components/buildListParts/BuildListParts.tsx``

## Expected Output

- ``frontend/e2e/build-list.spec.ts``
- ``frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-mobile-linux.png``
- ``frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-tablet-linux.png``
- ``frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-desktop-linux.png``

## Verification

cd frontend && npm run test:e2e -- build-list

## Observability Impact

Playwright HTML reporter + per-test pageerror listener + per-viewport pixel diffs land under frontend/playwright-report/ and frontend/test-results/ on regression. Baseline PNGs under e2e/build-list.spec.ts-snapshots/ are the canonical reference; renaming or moving them must be deliberate.
