---
id: S09
parent: M002
milestone: M002
provides:
  - ["frontend/src/components/ui/confirm-dialog.tsx", "frontend/src/pages/builder/ViewBuildlist.tsx (reskinned)", "frontend/src/components/buildListParts/BuildListParts.tsx (reskinned)", "frontend/src/components/buildListParts/EditBuildListPartForm.tsx (reskinned)", "frontend/e2e/build-list.spec.ts (multi-viewport visual regression + keyboard assertions)", "frontend/e2e/build-list.spec.ts-snapshots/ (mobile/tablet/desktop baselines)", "data-testid hooks for downstream e2e: build-list-edit-trigger, build-list-edit-dialog, build-list-delete-trigger, build-list-delete-confirm, build-list-add-part-trigger, build-list-add-part-dialog, build-list-view-mode-tabs, build-list-add-phase-input, build-list-add-phase-submit, build-list-phase-row-{id}, build-list-phase-delete-confirm, build-list-part-delete-confirm, build-list-part-edit-dialog, build-list-part-edit-submit"]
requires:
  - slice: S08
    provides: components/ui/{button,dialog,input,tabs}.tsx, lib/utils.ts (cn), styles/tokens.css, playwright.config.ts (mobile/tablet/desktop projects + 0.2% threshold)
affects:
  - ["S10 (parts catalog redesign — consumes ConfirmDialog and reskin pattern)", "S11 (admin shell + extraction-health UI — consumes ConfirmDialog and reskin pattern)", "S12 (repo-wide ripple reskin — consumes ConfirmDialog, removes EditBuildListForm legacy Card/Input grids, removes BuildListPartList/BuildListPartListItem legacy primitives, removes components/common/Dialog + DeleteConfirmationDialog + ActionButton + SecondaryButton)", "S13 (milestone verification — consumes the deflake pattern for chrome-extension promo and build-list e2e baseline)"]
key_files:
  - ["frontend/src/components/ui/confirm-dialog.tsx", "frontend/src/pages/builder/ViewBuildlist.tsx", "frontend/src/components/buildListParts/BuildListParts.tsx", "frontend/src/components/buildListParts/EditBuildListPartForm.tsx", "frontend/e2e/build-list.spec.ts"]
key_decisions:
  - ["ConfirmDialog uses controlled open state — parent owns open/onOpenChange so async confirm handlers can keep the dialog visible during the await; component never calls onOpenChange in response to confirm clicks. Escape-during-loading still closes (Radix default) — accepted as documented behavior.", "Reused ui/Button's variant prop via buttonVariants instead of re-implementing destructive styling in ConfirmDialog — single-sourced design contract.", "Phase-row Delete affordance kept as ui/Button variant='ghost' with red text className override (not variant='destructive') — preserves the lightweight legacy visual; the actual destructive cue lives on ConfirmDialog's confirm button.", "Mapped legacy ActionButton color schemes (purple/indigo/yellow) to ui/Button via className passthrough rather than introducing new variants — preserves visual continuity for S09 demo while leaving consolidation for S12.", "Used `sm:max-w-[64rem]` for Add Part dialog matching plan-literal value over Tailwind 4xl alias (which is 56rem) — followed plan over framework default.", "Pre-dismissed chrome-extension promo via addInitScript in build-list.spec.ts to deflake the mobile baseline (promo's 2s detect-then-show timer was racing the snapshot capture); used the same chrome_extension_promo_last_dismissed localStorage key + YYYY-MM-DD format that dailyDismiss.ts reads.", "MOCK_USER.id matches MOCK_BUILD_LIST.user_id so canManage evaluates true on the mocked page — required so the visual baseline includes Edit/Delete affordances and the dialog test's trigger renders."]
patterns_established:
  - ["ConfirmDialog primitive: parent owns open state, never auto-closes during async confirm — consumers wire onOpenChange to swallow dismiss while loading=true. Reusable across S10/S11/S12.", "Page-reskin scope discipline: migrate INTERACTIVE primitives only (buttons, dialogs, inputs, tabs); leave layout chrome (PageHeader/SectionHeader/Card) for the S12 ripple sweep. Keeps slice diffs reviewable.", "Color-scheme passthrough on ui/Button via className: legacy purple/indigo/yellow color schemes preserved during reskin without inventing new variants — leaves consolidation room for S12.", "Playwright spec template (mirrors S07/T06 price-alerts.spec.ts): page.route() URL matcher /\\/api\\/(?!.*\\.ts)/ (MEM082), pre-accept cookie consent + chrome-extension promo via addInitScript (MEM098/MEM103), pin Date.now to FIXED_NOW_ISO, page.on('pageerror') re-throws, default 404 with 'Mock miss' for visibility, MOCK_USER.id matches MOCK_BUILD_LIST.user_id so canManage evaluates true, multi-viewport visual regression + desktop-only keyboard assertions.", "Visible-focus assertion pattern: matches(':focus-visible') AND (computed outline || boxShadow) is non-empty — works against ui/Button's Tailwind focus-visible:ring-* utilities without hard-coding ring color/width values."]
observability_surfaces:
  - ["Runtime signals: ui/dialog onOpenChange transitions, dialog data-state attributes from Radix", "Inspection surfaces: /build-lists/{id} in dev with React DevTools; e2e Playwright HTML report at frontend/playwright-report/ on failed runs; pixel-diff PNGs at frontend/test-results/build-list-* on regression", "Failure visibility: pageerror listener in build-list.spec.ts re-throws runtime React errors as hard test failures; 14 data-testid hooks make focused targeting deterministic; default mock-route 404 with 'Mock miss: {method} {path}' surfaces unexpected calls in pageerror"]
drill_down_paths:
  []
duration: ""
verification_result: passed
completed_at: 2026-04-25T23:26:59.007Z
blocker_discovered: false
---

# S09: Build-list view redesign

**/build-lists/:id reskinned onto S08 design system primitives with new ConfirmDialog primitive and multi-viewport Playwright coverage.**

## What Happened

S09 reskinned the /build-lists/:buildListId page surface onto the S08 design system, replacing every interactive primitive that ViewBuildlist + BuildListParts owned. Five tasks landed end to end:

T01 introduced `frontend/src/components/ui/confirm-dialog.tsx` — a controlled, parent-owns-open-state primitive layered on ui/dialog + ui/button. It supports default/destructive variants, loading + loadingLabel, an inline error region (role="alert"), an optional warning slot for the legacy "in N build lists" notice, and five data-testid hooks. The critical contract — "no auto-close on confirm during loading" — is enforced by the parent owning open state; ConfirmDialog never calls onOpenChange in response to confirm clicks. 14 unit tests cover variant switching, loading states, error/warning slots, and the no-auto-close guarantee.

T02 migrated `frontend/src/pages/builder/ViewBuildlist.tsx` off common/Dialog + DeleteConfirmationDialog + buttons/ActionButton onto ui/dialog + ui/confirm-dialog + ui/button. The Edit Build List dialog and Add Part dialog moved to ui/Dialog (sm:max-w-2xl and sm:max-w-[64rem] respectively); the Delete Build List confirmation moved to ConfirmDialog with destructive variant + loadingLabel="Deleting..."; legacy purple/indigo/yellow color schemes preserved via className passthrough on ui/Button so visual continuity holds for the demo while leaving consolidation room for S12. handleDeleteOpenChange was wired to swallow outside-click/escape dismiss while the delete is in flight, preserving the parent-controlled-while-loading contract. canManage gates remained intact at all four mutating-affordance sites.

T03 migrated `frontend/src/components/buildListParts/BuildListParts.tsx` and `frontend/src/components/buildListParts/EditBuildListPartForm.tsx`. The view-mode toggle became a ui/Tabs (TabsList + TabsTrigger value="category"/"phase") wired through onValueChange; both Add Part triggers (error-path + happy-path) became ui/Button; the new-phase row became ui/Input + ui/Button with the existing trim+isAddingPhase guard preserved; per-row phase Edit/Cancel/Save became ui/Button (secondary/default), and the Delete affordance became ui/Button variant="ghost" with red text classes (preserving the lightweight legacy visual while letting ConfirmDialog's destructive variant carry the actual destructive cue). Both DeleteConfirmationDialog instances (delete-phase, delete-part) consolidated onto ConfirmDialog. EditBuildListPartForm's outer wrapper moved to ui/Dialog while inner form fields stayed on legacy primitives (they ride S12 with common/Input). Required testids landed: build-list-view-mode-tabs, build-list-add-phase-input, build-list-add-phase-submit, build-list-phase-row-${id}, build-list-phase-delete-confirm, build-list-part-delete-confirm, build-list-part-edit-dialog, build-list-part-edit-submit.

T04 authored `frontend/e2e/build-list.spec.ts` mirroring the S07/T06 price-alerts.spec.ts conventions: page.route() URL matcher uses `/\/api\/(?!.*\.ts)/` (MEM082), pre-accepts cookie-consent banner via addInitScript (MEM098), pins Date.now() to FIXED_NOW_ISO, and re-throws pageerror as hard test failures. Mocked the full ViewBuildList + BuildListParts fetch graph including /users/me, /app-settings, /build-lists/{id}, /build-lists/{id}/phases, /build-list-parts/{id}/parts, /car-generations/{carId}, /car-generations/, /categories/, /part-manufacturers/, /users/{userId}, /votes/build_list/{id}/summary. MOCK_USER.id matches MOCK_BUILD_LIST.user_id so canManage evaluates true and Edit/Delete trigger buttons render. Three tests landed: (1) build-list detail visual regression at all three projects with three baseline PNGs committed; (2) edit dialog opens, focuses, and Escape closes (desktop-only); (3) tab order surfaces visible focus on first interactive control (desktop-only) — asserts :focus-visible AND non-empty outline OR boxShadow against ui/Button's Tailwind focus-visible:ring-* utilities.

T05 ran the slice gauntlet end-to-end. Type-check exit 0. Vitest 17/17 (confirm-dialog 14 + ViewBuildlist 3). E2E first run failed on the mobile baseline (21,295 px diff, 0.03 ratio > 0.2% threshold) due to ChromeExtensionPromo's 2s timer racing the snapshot capture; deflaked by extending the spec's addInitScript to pre-dismiss the promo for today via the chrome_extension_promo_last_dismissed localStorage key in YYYY-MM-DD format that dailyDismiss.ts reads. Regenerated the mobile baseline; re-ran full suite: 8 passed / 4 skipped / 0 failed (the 4 skips are the desktop-only keyboard tests skipping on mobile/tablet, as designed). Lint reports 108 errors / 44 warnings (+4 vs MEM062's 104 baseline) but all 4 net-new errors live in unrelated pre-existing test files (reports/votes/bug_reports api tests dominate at 38/36/19); zero errors in the five S09 touched files. Manual UAT smoke substituted by the desktop edit-dialog Escape and tab-focus e2e assertions (autonomous mode, no human available). Import-closure grep across ViewBuildlist + buildListParts/ for legacy common/Dialog, common/DeleteConfirmationDialog, buttons/ActionButton sources returns 0 hits.

Re-verified at slice closure: type-check exit 0; vitest 17/17; e2e build-list + components 8 passed / 4 skipped; legacy-import grep 0 hits.

## Verification

All slice-level must-haves verified at closure.

Type-check: `npm run type-check` exit 0.

Unit tests: `npm run test -- ViewBuildlist BuildListParts confirm-dialog` exit 0, 17/17 passing (confirm-dialog 14 + ViewBuildlist 3).

E2E: `npm run test:e2e -- build-list components` exit 0, 8 passed / 4 skipped / 0 failed. Three viewport baselines (mobile/tablet/desktop) pass with 0.2% pixel threshold; desktop-only edit-dialog Escape + tab-focus tests pass; components.spec kitchen-sink screenshots still green (no token regression from confirm-dialog).

Import closure: `grep -rn "from '../../components/common/Dialog'|from '../../components/common/DeleteConfirmationDialog'|from '../../components/buttons/ActionButton'" src/pages/builder/ViewBuildlist.tsx src/components/buildListParts/` returns 0 hits.

Lint: 108 errors / 44 warnings — +4 vs MEM062 baseline of 104, but all 4 net-new errors live in unrelated pre-existing test files (reports/votes/bug_reports api tests). Zero errors in confirm-dialog.tsx, ViewBuildlist.tsx, BuildListParts.tsx, EditBuildListPartForm.tsx, or e2e/build-list.spec.ts. Slice intent (zero net-new errors in S09 touched files) is satisfied; recommend re-baselining MEM062 to 108 in a separate maintenance task.

Manual smoke: substituted by Playwright assertions (autonomous mode, no human available). The desktop e2e tests cover: page renders on the new dark token palette across mobile/tablet/desktop (visual regression), Edit dialog opens via testid trigger and Escape closes it, focus rings visible after Tab. Recommend a follow-up human pass on real local DB data when S13 milestone validation runs.

Three baseline PNGs exist under e2e/build-list.spec.ts-snapshots/ for mobile, tablet, desktop.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

"T05 modified frontend/e2e/build-list.spec.ts (8-line addInitScript extension to pre-dismiss the chrome-extension promo) and regenerated frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-mobile-linux.png — plan said 'no source files modified' for T05 but the verification gate surfaced a flake (promo's 2s timer racing the snapshot) that needed an in-scope fix. Treated as verification-driven fix rather than scope creep; the alternative (re-baseline mobile every CI run when timing wobbles) would have left the slice in a knowingly-flaky state."

## Known Limitations

"S09 only migrated INTERACTIVE primitives (buttons, dialogs, inputs, tabs) on ViewBuildlist + BuildListParts + EditBuildListPartForm. Layout chrome (PageHeader, SectionHeader, Card, CardInfoItem, Divider from layout/ and common/) and EditBuildListForm internals (car make/model/generation Card grids), plus BuildListPartList/BuildListPartListItem row internals, all stay on legacy primitives — they ride the S12 ripple sweep. The Add Part dialog's inner CreateBuildListPartForm fields are also untouched. The slice goal scope was the OUTER dialog wrappers and INTERACTIVE button/input primitives only."

## Follow-ups

["Update MEM062 lint baseline from 104 → 108 (or hunt down the +4 net-new errors in reports/votes/bug_reports api test files) in a separate maintenance task — drift is from unrelated pre-existing test files outside S09 scope.", "Run a 1-minute manual UAT smoke on real local DB data during S13 milestone validation — the autonomous-mode closure substituted Playwright e2e assertions for the human pass.", "S12 will sweep the remaining EditBuildListForm internals (car-make/model/generation Card grids), PageHeader/SectionHeader/Card layout chrome, BuildListPartList/BuildListPartListItem internals, and remove components/common/Dialog + DeleteConfirmationDialog + buttons/ActionButton + buttons/SecondaryButton."]

## Files Created/Modified

- `frontend/src/components/ui/confirm-dialog.tsx` — New shadcn primitive: destructive/default variants, loading + loadingLabel, error region, warning slot, controlled open state, dataTestid override (default 'confirm-dialog')
- `frontend/src/components/ui/confirm-dialog.test.tsx` — 14 unit tests covering variant switching, loading state UI, error/warning slots, no-auto-close-on-confirm contract
- `frontend/src/pages/builder/ViewBuildlist.tsx` — Reskinned: ActionButton→ui/Button (variants + className passthrough), common/Dialog→ui/Dialog for Edit + Add Part, DeleteConfirmationDialog→ConfirmDialog destructive, handleDeleteOpenChange swallows dismiss while loading, six new data-testid hooks
- `frontend/src/components/buildListParts/BuildListParts.tsx` — Reskinned: view-mode toggle→ui/Tabs, Add Part→ui/Button, new-phase row→ui/Input+ui/Button, per-row Edit/Cancel/Save→ui/Button (secondary/default), Delete→ui/Button ghost+red, both DeleteConfirmationDialog instances→ConfirmDialog, eight new data-testid hooks
- `frontend/src/components/buildListParts/EditBuildListPartForm.tsx` — Reskinned outer wrapper: common/Dialog→ui/Dialog, Cancel/Save→ui/Button (secondary/default), handleOpenChange refuses close while loading, two new data-testid hooks. Inner form fields stay on legacy primitives (S12 ripple).
- `frontend/e2e/build-list.spec.ts` — New Playwright spec: full ViewBuildList+BuildListParts mock graph, three tests (multi-viewport visual regression + desktop edit-dialog Escape + desktop tab-focus), pre-accepts cookie consent + chrome-extension promo, FIXED_NOW_ISO pinning, pageerror re-throw
- `frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-mobile-linux.png` — Mobile (375×812) baseline
- `frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-tablet-linux.png` — Tablet (768×1024) baseline
- `frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-desktop-linux.png` — Desktop (1280×800) baseline
