---
id: T04
parent: S09
milestone: M002
key_files:
  - frontend/e2e/build-list.spec.ts
  - frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-mobile-linux.png
  - frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-tablet-linux.png
  - frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-desktop-linux.png
key_decisions:
  - Used testInfo.project.name !== 'desktop' in test.skip() rather than process.env to gate per-project tests — testInfo is reliable across local + CI runs and surfaces the skip reason in the HTML report.
  - Asserted R020's visible focus ring by checking matches(':focus-visible') AND (computed outline || boxShadow) is non-empty — works against ui/Button's Tailwind focus-visible:ring-* utilities without hard-coding ring color/width values that S12 might tune.
  - MOCK_USER.id === MOCK_BUILD_LIST.user_id so canManage evaluates true on the mocked page — required so the visual baseline includes the Edit/Delete affordances (R014) and the dialog test's trigger renders.
  - Mocked /car-generations/ (LARGE_FETCH_LIMIT cars list) and /categories/ + /part-manufacturers/ as empty arrays — slice-level concern is page chrome + dialogs, not parts list rendering, so empty fixtures keep the baseline lean and the spec maintainable.
duration: 
verification_result: passed
completed_at: 2026-04-25T23:18:25.840Z
blocker_discovered: false
---

# T04: test: Add Playwright e2e covering /build-lists/:id reskin — mobile/tablet/desktop visual regression + R020 keyboard assertions

**test: Add Playwright e2e covering /build-lists/:id reskin — mobile/tablet/desktop visual regression + R020 keyboard assertions**

## What Happened

Authored frontend/e2e/build-list.spec.ts mirroring the conventions established in price-alerts.spec.ts (S07/T06):

- page.route() URL matcher uses `/\/api\/(?!.*\.ts)/` (MEM082) so Vite's source modules at /src/api/*.ts aren't intercepted.
- Pre-accepts the cookie-consent banner via page.addInitScript (MEM098/MEM103) so the mobile (375px) viewport's bottom-pinned banner doesn't intercept clicks.
- Pins Date.now() to FIXED_NOW_ISO (2026-04-25T12:00:00Z) for deterministic rendering.
- page.on('pageerror') re-throws runtime React errors as hard test failures.
- Default route handler 404s with `Mock miss: {method} {path}` so any drift from the mock contract surfaces.

Mocked the full ViewBuildList + BuildListParts fetch graph: /users/me, /app-settings/, /build-lists/{id}, /build-lists/{id}/phases, /build-list-parts/{id}/parts, /car-generations/{carId}, /car-generations/ (LARGE_FETCH_LIMIT cars list), /categories/, /part-manufacturers/, /users/{userId}, /votes/build_list/{id}/summary. MOCK_USER.id matches MOCK_BUILD_LIST.user_id so `canManage` evaluates true and the Edit/Delete trigger buttons render — required for both the visual baseline and the dialog/keyboard tests.

Three tests:
1. 'build-list detail visual regression' — runs at all three projects (mobile/tablet/desktop). Asserts the edit trigger is visible (mock contract sanity) then takes a fullPage screenshot. Three baselines now live under e2e/build-list.spec.ts-snapshots/.
2. 'edit dialog opens, focuses, and Escape closes' — desktop-only via test.skip(testInfo.project.name !== 'desktop'). Clicks the edit trigger, asserts the dialog is visible, asserts document.activeElement is contained inside the dialog (Radix focus management), presses Escape, asserts the dialog hides.
3. 'tab order surfaces visible focus on first interactive control' — desktop-only. Forces focus to body (with tabindex=-1 if needed), then Tabs forward up to 30 times until activeElement.textContent matches 'View Build Log'. Then asserts the focused button matches `:focus-visible` AND has a non-empty outline OR boxShadow (R020 visible focus ring guarantee from ui/Button's Tailwind focus-visible:ring-* utilities).

Generated baselines with `npx playwright test build-list --update-snapshots` (5 active tests passed, 4 properly skipped on non-desktop projects). Re-ran without --update-snapshots to confirm second pass is green and stable: 5 passed, 4 skipped, 4.6s.

No deviations from the task plan. The screenshot test runs at all three viewports (no skip needed) — this matches the slice plan's intent that the visual baseline covers mobile/tablet/desktop while the keyboard tests run once on desktop.

## Verification

Ran the slice-level verification command twice from frontend/:
1. `npx playwright test build-list --update-snapshots` — 5 passed, 4 skipped, baselines written for mobile/tablet/desktop.
2. `npx playwright test build-list` — 5 passed, 4 skipped, 4.6s. Second pass confirms baselines are stable and the keyboard/dialog tests don't depend on snapshot generation side-effects.

Confirmed all three baseline PNGs exist at the paths specified in Expected Output:
- frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-mobile-linux.png
- frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-tablet-linux.png
- frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-desktop-linux.png

No pageerror was raised during either run, meaning every /api/* request the page issued was handled by the mock router (no 'Mock miss' fallback fired). The R020 assertions (focus moves into dialog on open, Escape closes it, Tab traversal reaches the first action button with a visible focus ring) all passed on desktop.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd frontend && npx playwright test build-list --update-snapshots` | 0 | ✅ pass | 4700ms |
| 2 | `cd frontend && npx playwright test build-list` | 0 | ✅ pass | 4600ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `frontend/e2e/build-list.spec.ts`
- `frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-mobile-linux.png`
- `frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-tablet-linux.png`
- `frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-desktop-linux.png`
