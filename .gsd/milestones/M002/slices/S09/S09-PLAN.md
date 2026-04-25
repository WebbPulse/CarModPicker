# S09: Build-list view redesign

**Goal:** Reskin /build-lists/:buildListId on the S08 design system. Replace common/Dialog + DeleteConfirmationDialog + ActionButton + Card + Input usages on ViewBuildList and its BuildListParts child with components/ui/* (button, dialog, input, tabs) and a new ui/confirm-dialog primitive. Preserve R014 (build-list-detail surface), R020 (tab order, focus rings, escape closes dialogs), and existing semantics (vote buttons, copy/edit/delete affordances, phase management, optimistic purchased toggle). Land Playwright build-list.spec.ts at mobile/tablet/desktop with mocked API fixtures and keyboard assertions, plus baseline PNGs.
**Demo:** Visit /build-lists/{id} in dev — page is on the new design system, all interactions use S08 primitives. Run npm run test:e2e -- build-list.spec.ts — green at mobile/tablet/desktop. Tab through the page — focus indicators visible, escape on dialogs works.

## Must-Haves

- /build-lists/{id} renders on the new design system in dev (no imports from components/common/Dialog, components/common/DeleteConfirmationDialog, or components/buttons/ActionButton inside ViewBuildlist.tsx and components used exclusively from it).
- New components/ui/confirm-dialog.tsx wraps ui/dialog with destructive/default variants, exposes loading + error props, traps focus, and closes on Escape.
- All five Dialog instances (Edit Build List, Delete Build List Confirm, Create Build List Part, Edit Build List Part, Delete Phase Confirm, Delete Part Confirm) consume ui/dialog or ui/confirm-dialog with token-driven styling.
- Phase view-mode toggle uses ui/tabs (or ui/button variants) with focus-visible ring; phase-list inputs use ui/input.
- ViewBuildlist.test.tsx still passes (mocks unchanged, semantic queries unchanged).
- frontend/e2e/build-list.spec.ts navigates with mocked fixtures, runs at mobile/tablet/desktop, asserts toHaveScreenshot fullPage, asserts dialog-Escape closes the Edit dialog, asserts focus is visible on the first interactive element after Tab. Three baseline PNGs committed under e2e/build-list.spec.ts-snapshots/.
- npm run type-check exits 0; npm run test:e2e -- build-list exits 0 with 3/3 passing; npm run test -- ViewBuildlist passes; npm run lint produces no NEW errors beyond the existing 104-error baseline (MEM062).

## Proof Level

- This slice proves: integration — page-level reskin proven by Playwright multi-viewport visual regression + keyboard assertions and unchanged unit tests; real runtime required (Vite dev server + mocked API fixtures); no human UAT required for the automated portion, but a brief manual keyboard pass is documented in the slice summary follow-ups.

## Integration Closure

- Upstream surfaces consumed: frontend/src/components/ui/{button,dialog,input,tabs}.tsx, frontend/src/lib/utils.ts (cn), frontend/src/styles/tokens.css, frontend/playwright.config.ts (mobile/tablet/desktop projects + 0.2% threshold).
- New wiring introduced in this slice: components/ui/confirm-dialog.tsx (new shadcn primitive), ViewBuildlist.tsx + BuildListParts.tsx + EditBuildListPartForm.tsx rewired onto ui/* primitives, frontend/e2e/build-list.spec.ts + 3 baseline PNGs.
- What remains before the milestone is truly usable end-to-end: S10 (parts catalog reskin onto same primitives), S11 (admin shell + extraction-health UI), S12 (ripple reskin of remaining ~17 pages and removal of components/common/), S13 (final integration + milestone verification). EditBuildListForm internals (car-make/model/generation Card grids) stay on legacy Card/Input in S09 — they will ride the S12 ripple along with components/common/Card and components/common/Input.

## Verification

- Runtime signals: ui/dialog onOpenChange transitions, dialog-data-state attributes from Radix
- Inspection surfaces: /build-lists/{id} in dev with React DevTools; e2e Playwright HTML report at frontend/playwright-report/ on failed runs; pixel-diff PNGs at frontend/test-results/build-list-* on regression
- Failure visibility: pageerror listener in build-list.spec.ts re-throws runtime React errors as hard test failures; data-testid hooks (build-list-edit-trigger, build-list-edit-dialog, build-list-delete-trigger, build-list-delete-confirm, build-list-add-part-trigger, build-list-add-part-dialog) make focused targeting deterministic
- Redaction constraints: none (page is public-readable; no PII in fixtures)

## Tasks

- [x] **T01: Add components/ui/confirm-dialog.tsx and unit-test it** `est:45m`
  Create a new shadcn-style ConfirmDialog primitive on top of ui/dialog that replaces the deprecated common/DeleteConfirmationDialog pattern across the app. Used by S09 in three places (Delete Build List, Delete Phase, Delete Part) and by S10/S11/S12 thereafter. Must support destructive vs default variants, processing/loading state on the confirm button, an inline error region, and an optional warning slot for the existing 'in N build lists' notice that DeleteConfirmationDialog accepts.

Failure modes: dialog must NOT close on confirm-click while processing (parent controls open state via async handler). Negative tests: pressing Escape while processing still closes (matches Radix default; document this as accepted behavior). Load profile: rendered at most once per page, no perf concerns. No external deps reached — pure presentational.

No Threat-Surface concern (no user input persisted; dialog is presentational).
  - Files: `frontend/src/components/ui/confirm-dialog.tsx`, `frontend/src/components/ui/confirm-dialog.test.tsx`
  - Verify: cd frontend && npm run type-check && npm test -- confirm-dialog

- [x] **T02: Reskin ViewBuildlist.tsx page chrome and top-level dialogs onto ui/* primitives** `est:1h`
  Migrate frontend/src/pages/builder/ViewBuildlist.tsx from common/Dialog + DeleteConfirmationDialog + ActionButton to ui/dialog + ui/confirm-dialog (T01) + ui/button. Preserve every existing behavior: build-list info card, no-car-assigned warning, View Build Log button, Copy Build List button (with isCopyingBuildList loading state via Button loading prop), Edit/Delete affordances gated on canManage, EditBuildListForm in a ui/Dialog with title `Edit ${buildList.name}`, ConfirmDialog for delete, ui/Dialog for Create Build List Part with maxWidth equivalent to the existing 4xl (use sm:max-w-[64rem]).

Do NOT modify EditBuildListForm internals — it consumes common/Card and common/Input for the make/model/generation grids; those ride the S12 ripple. Only swap the OUTER dialog wrapper.

Keep PageHeader / SectionHeader / Card (from layout/ and common/) as-is for now — they are visual chrome and S12 will sweep them. The slice focus is replacing INTERACTIVE primitives (buttons, dialogs, dialog-confirm).

Add data-testid hooks: 'build-list-edit-trigger', 'build-list-delete-trigger', 'build-list-add-part-trigger', 'build-list-edit-dialog', 'build-list-delete-confirm', 'build-list-add-part-dialog'. T04's e2e spec targets these.

Failure modes: handleConfirmDelete navigates after success; if the parent forgets to close the dialog while processing, ConfirmDialog must keep the spinner visible — covered by ConfirmDialog from T01 (loading prop disables the button but does not auto-close). Negative tests: clicking Cancel while processing should be no-op (button disabled). Load profile: identical to current; no new fetches.

Threat surface: existing build-list ownership check (canManage = currentUser?.id === buildList.user_id) governs render of mutating triggers. Migration must NOT loosen the gate — verify by grep.
  - Files: `frontend/src/pages/builder/ViewBuildlist.tsx`
  - Verify: cd frontend && npm run type-check && npm test -- ViewBuildlist && grep -c "from '../../components/common/Dialog'\|from '../../components/common/DeleteConfirmationDialog'\|from '../../components/buttons/ActionButton'" src/pages/builder/ViewBuildlist.tsx | grep -q '^0$'

- [x] **T03: Reskin BuildListParts.tsx child + EditBuildListPartForm dialog onto ui/* primitives** `est:1.5h`
  Migrate the BuildListParts component and its EditBuildListPartForm modal off common/Dialog + ActionButton + raw bare buttons + raw inputs onto ui/* primitives.

In BuildListParts.tsx:
  - Replace the View-mode toggle (the two raw <button> elements with conditional bg-blue-600/bg-gray-700 styling at lines ~390–413) with ui/Tabs (TabsList + TabsTrigger value='category'/'phase'). Keep state hook signature (viewMode setViewMode) unchanged so children still receive viewMode.
  - Replace the 'Add Part' ActionButton with ui/Button.
  - Replace the phase-row controls: the new-phase Input + Add phase ActionButton row, the per-row Edit/Cancel/Save SecondaryButton+ActionButton, and the per-row Delete bare button. Use ui/Input + ui/Button (variants: default, secondary, destructive, ghost as appropriate).
  - Replace DeleteConfirmationDialog (delete-phase + delete-part) with ConfirmDialog from T01.
  - Add data-testid='build-list-view-mode-tabs', 'build-list-add-phase-input', 'build-list-add-phase-submit', 'build-list-phase-row-${phase.id}'.
  - The car-mismatch warning banner stays as-is (presentational chrome, not interactive).

In EditBuildListPartForm.tsx:
  - Swap common/Dialog wrapper for ui/Dialog (preserve title='Edit Part', preserve isOpen/onClose contract). Inner form fields (the non-dialog-wrapper parts) can stay on legacy primitives — they'll ride S12 along with common/Input.
  - Replace the form's Cancel/Save ActionButton+SecondaryButton pair with ui/Button (variant='secondary' for Cancel, default for Save). Preserve the existing onSubmit/onClose contract.
  - Add data-testid='build-list-part-edit-dialog' and 'build-list-part-edit-submit'.

Do NOT touch BuildListPartList or BuildListPartListItem internals — they're row presentation that S12 will sweep. They are downstream of the parent and do not gate the slice goal.

Failure modes: optimistic purchased-toggle path uses no dialog; preserved as-is. Phase add/edit/delete error paths must still surface phaseError via the existing red text region. Negative tests: rapid double-click on Add phase must not duplicate (existing `disabled={!newPhaseName.trim() || isAddingPhase}` guard preserved). Load profile: same as before; no new fetches.

Threat surface: phase mutations gated on canManageParts (existing). Migration preserves the gate. The new-phase input value is sent verbatim to backend POST /api/build-lists/{id}/phases — backend already validates length and trims; no new XSS surface introduced (rendered as text in <span>, not dangerouslySetInnerHTML).
  - Files: `frontend/src/components/buildListParts/BuildListParts.tsx`, `frontend/src/components/buildListParts/EditBuildListPartForm.tsx`
  - Verify: cd frontend && npm run type-check && npm test -- BuildListParts ViewBuildlist && grep -c "from '../common/Dialog'\|from '../common/DeleteConfirmationDialog'\|from '../buttons/ActionButton'\|from '../buttons/SecondaryButton'" src/components/buildListParts/BuildListParts.tsx src/components/buildListParts/EditBuildListPartForm.tsx | awk -F: '{ sum += $2 } END { exit (sum > 0) }'

- [ ] **T04: Add frontend/e2e/build-list.spec.ts with mocked fixtures, multi-viewport screenshots, and keyboard assertions** `est:1h`
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
  - Files: `frontend/e2e/build-list.spec.ts`, `frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-mobile-linux.png`, `frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-tablet-linux.png`, `frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-desktop-linux.png`
  - Verify: cd frontend && npm run test:e2e -- build-list

- [ ] **T05: Slice-level verification sweep and evidence capture** `est:30m`
  Final cross-task verification that the slice goal is met. Run the full local test gauntlet from frontend/, capture exit codes, spot-check the page in dev, and make sure no regressions slipped into adjacent areas.

Steps:
  1. cd frontend && npm run type-check — must exit 0.
  2. cd frontend && npm run test -- ViewBuildlist BuildListParts confirm-dialog — must exit 0 (vitest passes for the directly-touched units).
  3. cd frontend && npm run test:e2e -- build-list components — must exit 0; build-list runs 3/3 + 1 desktop-only keyboard-focus test, components.spec still 3/3 (no token regression from confirm-dialog).
  4. cd frontend && npm run lint 2>&1 | tail -1 — capture the error count. MUST equal the existing 104-error baseline (MEM062). Any net-new error in src/components/ui/confirm-dialog.tsx, src/pages/builder/ViewBuildlist.tsx, src/components/buildListParts/BuildListParts.tsx, src/components/buildListParts/EditBuildListPartForm.tsx, or e2e/build-list.spec.ts is a fail.
  5. Manual smoke (1 minute, document the result in slice summary): start dev server (cd frontend && npm run dev), navigate to /build-lists/{any real id from local DB}, visually confirm the page renders on the new dark token palette, click Edit, press Escape, click Add Part, click Cancel, confirm focus rings visible on all action buttons under keyboard Tab.
  6. grep -r "from '../../components/common/Dialog'\|from '../../components/common/DeleteConfirmationDialog'\|from '../../components/buttons/ActionButton'" src/pages/builder/ViewBuildlist.tsx src/components/buildListParts/ — must return 0 hits (slice goal closure check).
  7. Confirm no new pre-commit lint errors introduced; if step 4 finds any, route them back to the originating task (T01–T03) for fix.

This task is verification-only — no source files modified.
  - Verify: cd frontend && npm run type-check && npm run test -- ViewBuildlist BuildListParts confirm-dialog && npm run test:e2e -- build-list components && grep -r "from '../../components/common/Dialog'\|from '../../components/common/DeleteConfirmationDialog'\|from '../../components/buttons/ActionButton'" src/pages/builder/ViewBuildlist.tsx src/components/buildListParts/ | wc -l | grep -q '^0$'

## Files Likely Touched

- frontend/src/components/ui/confirm-dialog.tsx
- frontend/src/components/ui/confirm-dialog.test.tsx
- frontend/src/pages/builder/ViewBuildlist.tsx
- frontend/src/components/buildListParts/BuildListParts.tsx
- frontend/src/components/buildListParts/EditBuildListPartForm.tsx
- frontend/e2e/build-list.spec.ts
- frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-mobile-linux.png
- frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-tablet-linux.png
- frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-desktop-linux.png
