---
id: T05
parent: S12
milestone: M002
key_files:
  - frontend/src/pages/admin/AdminDashboard.tsx
  - frontend/src/pages/admin/ExtractionHealth.tsx
  - frontend/src/pages/admin/ReportReview.tsx
  - frontend/src/pages/admin/BugReportReview.tsx
  - frontend/src/pages/admin/UserManagement.tsx
  - frontend/src/pages/admin/PartsCuration.tsx
  - frontend/src/pages/admin/SystemAdmin.tsx
  - frontend/src/pages/admin/SystemStatistics.tsx
  - frontend/src/pages/admin/CrawlerAdmin.tsx
  - frontend/src/components/admin/ReportDialog.tsx
  - frontend/src/components/routes/RouteGroupBoundary.tsx
  - frontend/src/components/routes/RouteGroupBoundary.test.tsx
  - frontend/src/components/routes/EmailVerifiedRoute.tsx
  - frontend/src/components/routes/ProtectedRoute.tsx
  - frontend/src/components/routes/GuestRoute.tsx
  - frontend/src/components/shell/ErrorBoundary.tsx
  - frontend/src/components/shell/ErrorBoundary.test.tsx
  - frontend/src/components/shell/CookieConsentBanner.tsx
  - frontend/src/components/shell/ChromeExtensionPromo.tsx
  - frontend/src/components/shell/SubscriptionPromo.tsx
  - frontend/src/components/shell/BetaBanner.tsx
  - frontend/src/components/forms/ImageUpload.tsx
  - frontend/src/components/forms/SearchableSelect.tsx
  - frontend/src/components/cars/CarModelMultiSelect.tsx
  - frontend/src/components/images/ImageWithPlaceholder.tsx
  - frontend/src/components/filters/VehicleFilterSection.tsx
  - frontend/src/components/filters/VehicleFilterChips.tsx
  - frontend/src/components/buildLists/AddItemTile.tsx
  - frontend/src/components/tables/ResponsiveTableWrapper.tsx
  - frontend/src/components/ui/card-info-item.tsx
  - frontend/src/App.tsx
  - frontend/src/main.tsx
key_decisions:
  - Used the MEM127 sequence (rm shim → git mv original → fix sibling imports) for all 9 helper relocations so git history follows the file rather than a delete+create churn. AddItemTile's `from './Card'`, ImageUpload's `from './Alerts'/./LoadingSpinner'/'./ImageWithPlaceholder'`, CarModelMultiSelect's `from './SearchableSelect'`, and VehicleFilterSection's `from './LoadingSpinner'` all required path rewrites because they were sibling refs in the original common/ home that no longer resolve from the new locations.
  - ConfirmDialog adapter pattern for DeleteConfirmationDialog→ui/ConfirmDialog: built a destructure-friendly wrapper with `description={<>...{name}...</>}`, `confirmLabel='Confirm Delete'`, `loadingLabel='Deleting...'`, `variant='destructive'`, and `error={raw ? `Failed to delete ${type}: ${raw}` : null}` so each callsite's existing error/loading/itemName/itemType state plugs in without re-wiring.
  - SystemAdmin's many `<ActionButton>` wrappers around `<Spinner inline /> + text` patterns collapsed to the Button `loading` prop. Eliminates ~30 LOC and matches the established ui/Button convention; the Loader2 spinner inside the Button is consistent with Submit-button patterns elsewhere.
  - Captured MEM128 to flag that the 7 vitest e2e-spec discovery failures are pre-existing (vitest config doesn't exclude `e2e/**`), so future test gauntlets won't get treated as a regression. Fix is one-line in vitest.config.ts but out of scope for S12.
duration: 
verification_result: passed
completed_at: 2026-04-26T03:33:00.472Z
blocker_discovered: false
---

# T05: Swept Tier D admin pages onto ui/* primitives, relocated structural infra (routes/, shell/) and helpers, deleted components/common/ and components/buttons/ — type-check 0, 596 unit/integration tests pass, slice grep guard returns nothing

**Swept Tier D admin pages onto ui/* primitives, relocated structural infra (routes/, shell/) and helpers, deleted components/common/ and components/buttons/ — type-check 0, 596 unit/integration tests pass, slice grep guard returns nothing**

## What Happened

Closed out the S12 ripple in three coordinated chunks per the task plan:

**(a) Admin tier sweep (9 pages + ReportDialog):**
- AdminDashboard, ExtractionHealth: finished off legacy Card/Alerts/LoadingSpinner imports (S11 had already migrated their Buttons).
- ReportReview, BugReportReview: full set — Card→ui/Card, Alerts→ui/alert, LoadingSpinner→ui/Spinner, Pagination→ui/pagination, ActionButton→Button(variant secondary/default), Dialog→Radix-style ui/Dialog+DialogContent+DialogHeader+DialogTitle. Tab navigation buttons swapped to `variant={selected ? 'default' : 'secondary'}` instead of bespoke className overrides per MEM116.
- UserManagement: same set + DeleteConfirmationDialog→ConfirmDialog (with description prop holding the wrap-with-em-tag JSX, destructive variant, loadingLabel), Input legacy `label=` prop expanded into wrapped `<div className="space-y-1"><label htmlFor={id}>...</label><Input id={id}/></div>` per the swap rule.
- PartsCuration: same set + manual Dialog confirmation rebuild as Radix Dialog/DialogContent. ConfirmDialog form pattern (label→Input wrap) applied to 4 lookup inputs.
- SystemAdmin: 4× DeleteConfirmationDialog→ConfirmDialog conversions, Button `loading` prop replaces the manual `<Spinner inline/> + text` pattern at every disabled action site.
- SystemStatistics: refresh + bucket buttons → Button variant=secondary size=sm.
- CrawlerAdmin (2,665 lines): mechanical replace-all on imports + ActionButton→Button + LoadingSpinner→Spinner. No `label=` props on any Input so the Input swap was direct.
- ReportDialog (admin/): Dialog→Radix Dialog stack, ActionButton→Button, SecondaryButton→Button variant=outline.

**(b) Structural infra relocation:**
- `git mv` RouteGroupBoundary[.test].tsx common/→routes/, ErrorBoundary[.test].tsx + CookieConsentBanner.tsx + ChromeExtensionPromo.tsx + SubscriptionPromo.tsx + BetaBanner.tsx common/→shell/ (created shell/ directory).
- App.tsx imports rewired to `./components/routes/RouteGroupBoundary` and `./components/shell/{ErrorBoundary,CookieConsentBanner,ChromeExtensionPromo,SubscriptionPromo,BetaBanner}`. Bonus: App.tsx still had a legacy LoadingSpinner import — swapped to ui/Spinner.
- main.tsx ErrorBoundary import rewired to `./components/shell/ErrorBoundary`.
- Test file relative imports (`from './RouteGroupBoundary'`) were already location-independent — no changes needed.

**(c) Shim collapse + legacy deletion:**
Per MEM127 pattern (captured this task): for each T03/T04 shim, `rm` the shim file at the new path, then `git mv` the original from `common/X.tsx` to the new path so git tracks the move. Applied to: ImageUpload, SearchableSelect, CarModelMultiSelect, ImageWithPlaceholder, VehicleFilterSection, VehicleFilterChips, ResponsiveTableWrapper, CardInfoItem, AddItemTile.

Fixed broken sibling imports inside the moved files: ImageUpload referenced `./Alerts`/`./LoadingSpinner`/`./ImageWithPlaceholder` (rewired to `../ui/alert`, `../ui/spinner`, `../images/ImageWithPlaceholder`); CarModelMultiSelect referenced `./SearchableSelect` (rewired to `../forms/SearchableSelect`); VehicleFilterSection referenced `./LoadingSpinner` (rewired to `../ui/spinner`); AddItemTile referenced `./Card` (rewired to `../ui/card`).

Three remaining route guards (EmailVerifiedRoute/ProtectedRoute/GuestRoute) still imported `../common/LoadingSpinner` — swapped to `../ui/spinner` so the legacy delete wouldn't strand them.

Final delete: `git rm` Card/Alerts/LoadingSpinner/Pagination/Input/Dialog/DeleteConfirmationDialog/Button/DangerousActionDialog/ParentNavigationLink from common/ + `git rm -r components/buttons`. components/common/ and components/buttons/ no longer exist on disk.

**Verification:** `npm run type-check` exits 0 (T04's 3 expected AddItemTile module-not-found errors now resolved by the file move). `npm test -- --run` reports 596 tests pass; the 7 e2e/*.spec.ts files trip vitest discovery because vitest's config doesn't exclude e2e (Playwright tests). This is pre-existing noise unrelated to S12 — captured as MEM128. Slice grep guard returns zero hits across `src/`. All 10 must-have file-deletion checks pass via `test ! -f`.

The slice goal (retire components/common/ and components/buttons/, every importer migrated to ui/* design system or relocated non-primitive home, CI grep guard installable) is achieved at end of T05; T06 will install the CI grep guard.

## Verification

Ran the slice's verification command: `cd frontend && npm run type-check` exits 0; `npm test -- --run` reports 596 unit/integration tests pass (Vitest exit 0); all 10 `test ! -f src/components/common/X.tsx` and `test ! -d src/components/buttons` checks pass; full-tree grep `from '...common/' or '...buttons/'` returns zero matches across src/. T04's 3 expected module-not-found errors (AddItemTile) are resolved by the relocation. The 7 vitest "test file failed" reports are pre-existing e2e-discovery noise (Playwright-runner conflict) — vitest still exits 0 and the actual test count holds at 596 passing.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm run type-check` | 0 | ✅ pass | 11000ms |
| 2 | `npm test -- --run` | 0 | ✅ pass (596 unit/integration tests pass; 7 pre-existing e2e-discovery file failures are not test-result regressions) | 7370ms |
| 3 | `test ! -d src/components/buttons && test ! -f src/components/common/Card.tsx && test ! -f src/components/common/Alerts.tsx && test ! -f src/components/common/LoadingSpinner.tsx && test ! -f src/components/common/Pagination.tsx && test ! -f src/components/common/Input.tsx && test ! -f src/components/common/Dialog.tsx && test ! -f src/components/common/DeleteConfirmationDialog.tsx && test ! -f src/components/common/Button.tsx && test ! -f src/components/common/DangerousActionDialog.tsx && test ! -f src/components/common/ParentNavigationLink.tsx` | 0 | ✅ pass | 40ms |
| 4 | `grep -rnE "from ['\"][^'\"]*(common|buttons)/" src/ --include="*.tsx" --include="*.ts"` | 1 | ✅ pass (no matches — exit 1 is grep's no-match signal, the desired outcome) | 80ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `frontend/src/pages/admin/AdminDashboard.tsx`
- `frontend/src/pages/admin/ExtractionHealth.tsx`
- `frontend/src/pages/admin/ReportReview.tsx`
- `frontend/src/pages/admin/BugReportReview.tsx`
- `frontend/src/pages/admin/UserManagement.tsx`
- `frontend/src/pages/admin/PartsCuration.tsx`
- `frontend/src/pages/admin/SystemAdmin.tsx`
- `frontend/src/pages/admin/SystemStatistics.tsx`
- `frontend/src/pages/admin/CrawlerAdmin.tsx`
- `frontend/src/components/admin/ReportDialog.tsx`
- `frontend/src/components/routes/RouteGroupBoundary.tsx`
- `frontend/src/components/routes/RouteGroupBoundary.test.tsx`
- `frontend/src/components/routes/EmailVerifiedRoute.tsx`
- `frontend/src/components/routes/ProtectedRoute.tsx`
- `frontend/src/components/routes/GuestRoute.tsx`
- `frontend/src/components/shell/ErrorBoundary.tsx`
- `frontend/src/components/shell/ErrorBoundary.test.tsx`
- `frontend/src/components/shell/CookieConsentBanner.tsx`
- `frontend/src/components/shell/ChromeExtensionPromo.tsx`
- `frontend/src/components/shell/SubscriptionPromo.tsx`
- `frontend/src/components/shell/BetaBanner.tsx`
- `frontend/src/components/forms/ImageUpload.tsx`
- `frontend/src/components/forms/SearchableSelect.tsx`
- `frontend/src/components/cars/CarModelMultiSelect.tsx`
- `frontend/src/components/images/ImageWithPlaceholder.tsx`
- `frontend/src/components/filters/VehicleFilterSection.tsx`
- `frontend/src/components/filters/VehicleFilterChips.tsx`
- `frontend/src/components/buildLists/AddItemTile.tsx`
- `frontend/src/components/tables/ResponsiveTableWrapper.tsx`
- `frontend/src/components/ui/card-info-item.tsx`
- `frontend/src/App.tsx`
- `frontend/src/main.tsx`
