---
estimated_steps: 7
estimated_files: 30
skills_used: []
---

# T05: Sweep Tier D (admin pages) + relocate structural infra and non-primitive helpers + delete legacy primitives

Three closely-coupled chunks of work that must land atomically: (a) the admin tier (9 pages including the 2,665-line CrawlerAdmin.tsx + 1 inner component ReportDialog) is the last page-importer cluster and shares the same legacy import set as Tier C; (b) structural infra (RouteGroupBoundary + test, ErrorBoundary + test, CookieConsentBanner, ChromeExtensionPromo, SubscriptionPromo, BetaBanner) plus non-primitive helpers (SearchableSelect, CarModelMultiSelect, ImageUpload, ImageWithPlaceholder, VehicleFilterSection, VehicleFilterChips, AddItemTile, ResponsiveTableWrapper, CardInfoItem) need to move out of components/common/ so the grep guard in T06 can pass; (c) legacy primitive files must be deleted. Bundling them in one task lets the executor verify everything compiles + tests pass at one consistent end state, instead of leaving the tree in a half-relocated half-deleted state between tasks.

Do (a) Admin sweep first: same swap rules as T03/T04. Admin pages predominantly use Card + Alerts + LoadingSpinner + Pagination + ActionButton + SecondaryButton + Dialog + DeleteConfirmationDialog. AdminDashboard already uses ui/Button (S11); finish off Card + Alerts. ExtractionHealth already uses ui/Button (S11); finish off Card + Alerts + LoadingSpinner. CrawlerAdmin is large but mechanical. ReportDialog (admin/) swaps Dialog + ActionButton + SecondaryButton.

Do (b) Structural-infra relocation: read each source file, write it to its new path, delete old. Update imports in App.tsx ('./components/common/RouteGroupBoundary' → './components/routes/RouteGroupBoundary'; same pattern for ErrorBoundary → ./components/shell/ErrorBoundary, CookieConsentBanner → ./components/shell/CookieConsentBanner, ChromeExtensionPromo → ./components/shell/ChromeExtensionPromo, SubscriptionPromo → ./components/shell/SubscriptionPromo, BetaBanner → ./components/shell/BetaBanner). Update main.tsx for ErrorBoundary import. Update App.coverage.test.tsx if it references the old paths in comments. RouteGroupBoundary.test.tsx and ErrorBoundary.test.tsx — only their location changes; their internal 'from ./RouteGroupBoundary' imports stay relative-to-self.

Do (c) Non-primitive helper relocation: move SearchableSelect → forms/, ImageUpload → forms/, CarModelMultiSelect → cars/, ImageWithPlaceholder → images/, VehicleFilterSection → filters/, VehicleFilterChips → filters/, AddItemTile → buildLists/, ResponsiveTableWrapper → tables/, CardInfoItem → ui/card-info-item.tsx (fold into ui/). T04 already updated every importer to point at these new paths, so the move alone resolves the broken imports. Verify with grep that no remaining importer points at the old path.

Do (d) Legacy primitive delete: delete components/common/{Card,Alerts,LoadingSpinner,Pagination,Input,Dialog,DeleteConfirmationDialog,Button,DangerousActionDialog,ParentNavigationLink}.tsx and the entire components/buttons/ directory. After delete, components/common/ should be empty — if any file remains, an importer was missed; chase it down.

Run the full type-check + vitest gauntlet at the end of the task to verify everything resolves and behaves identically. Type-check should now exit 0 (T04's pending failures resolved by the relocations).

Must-haves: admin pages have no legacy imports; relocated files exist at new paths and are imported correctly everywhere; legacy primitive files deleted; full vitest + type-check green; components/buttons/ directory does not exist; components/common/ contains no Card/Alerts/LoadingSpinner/Pagination/Input/Dialog/DeleteConfirmationDialog/Button/DangerousActionDialog/ParentNavigationLink files.

## Inputs

- ``frontend/src/components/ui/card.tsx` — destination for Card swap.`
- ``frontend/src/components/ui/alert.tsx` — destination for Alerts swap.`
- ``frontend/src/components/ui/spinner.tsx` — destination for LoadingSpinner swap.`
- ``frontend/src/components/ui/pagination.tsx` — destination for Pagination swap.`
- ``frontend/src/components/ui/button.tsx` — destination for ActionButton/SecondaryButton swaps.`
- ``frontend/src/components/ui/dialog.tsx` — destination for Dialog swap.`
- ``frontend/src/components/ui/confirm-dialog.tsx` — destination for DeleteConfirmationDialog swap.`
- ``frontend/src/pages/admin/AdminDashboard.tsx` — partial S11 migration; finish off legacy imports.`
- ``frontend/src/pages/admin/ExtractionHealth.tsx` — partial S11 migration; finish off legacy imports.`
- ``frontend/src/pages/admin/ReportReview.tsx` — Card + Alerts + LoadingSpinner + Pagination + ActionButton + SecondaryButton + Dialog.`
- ``frontend/src/pages/admin/BugReportReview.tsx` — same set.`
- ``frontend/src/pages/admin/UserManagement.tsx` — same set.`
- ``frontend/src/pages/admin/PartsCuration.tsx` — same set.`
- ``frontend/src/pages/admin/SystemAdmin.tsx` — same set.`
- ``frontend/src/pages/admin/SystemStatistics.tsx` — same set.`
- ``frontend/src/pages/admin/CrawlerAdmin.tsx` — 2,665 lines; same legacy import set.`
- ``frontend/src/components/admin/ReportDialog.tsx` — Dialog + ActionButton + SecondaryButton.`
- ``frontend/src/components/common/RouteGroupBoundary.tsx` — relocate source.`
- ``frontend/src/components/common/RouteGroupBoundary.test.tsx` — relocate source.`
- ``frontend/src/components/common/ErrorBoundary.tsx` — relocate source.`
- ``frontend/src/components/common/ErrorBoundary.test.tsx` — relocate source.`
- ``frontend/src/components/common/CookieConsentBanner.tsx` — relocate source.`
- ``frontend/src/components/common/ChromeExtensionPromo.tsx` — relocate source.`
- ``frontend/src/components/common/SubscriptionPromo.tsx` — relocate source.`
- ``frontend/src/components/common/BetaBanner.tsx` — relocate source.`
- ``frontend/src/components/common/SearchableSelect.tsx` — relocate source.`
- ``frontend/src/components/common/CarModelMultiSelect.tsx` — relocate source.`
- ``frontend/src/components/common/ImageUpload.tsx` — relocate source.`
- ``frontend/src/components/common/ImageWithPlaceholder.tsx` — relocate source.`
- ``frontend/src/components/common/VehicleFilterSection.tsx` — relocate source.`
- ``frontend/src/components/common/VehicleFilterChips.tsx` — relocate source.`
- ``frontend/src/components/common/AddItemTile.tsx` — relocate source.`
- ``frontend/src/components/common/ResponsiveTableWrapper.tsx` — relocate source.`
- ``frontend/src/components/common/CardInfoItem.tsx` — relocate source (folds into ui/).`
- ``frontend/src/App.tsx` — rewires structural-infra imports after relocation.`
- ``frontend/src/main.tsx` — rewires ErrorBoundary import after relocation.`
- ``frontend/src/App.coverage.test.tsx` — drift-guard test; update if comments reference old paths.`

## Expected Output

- ``frontend/src/pages/admin/AdminDashboard.tsx` — modified, no legacy imports.`
- ``frontend/src/pages/admin/ExtractionHealth.tsx` — modified, no legacy imports.`
- ``frontend/src/pages/admin/ReportReview.tsx` — modified, no legacy imports.`
- ``frontend/src/pages/admin/BugReportReview.tsx` — modified, no legacy imports.`
- ``frontend/src/pages/admin/UserManagement.tsx` — modified, no legacy imports.`
- ``frontend/src/pages/admin/PartsCuration.tsx` — modified, no legacy imports.`
- ``frontend/src/pages/admin/SystemAdmin.tsx` — modified, no legacy imports.`
- ``frontend/src/pages/admin/SystemStatistics.tsx` — modified, no legacy imports.`
- ``frontend/src/pages/admin/CrawlerAdmin.tsx` — modified, no legacy imports.`
- ``frontend/src/components/admin/ReportDialog.tsx` — modified, no legacy imports.`
- ``frontend/src/components/routes/RouteGroupBoundary.tsx` — relocated from common/.`
- ``frontend/src/components/routes/RouteGroupBoundary.test.tsx` — relocated from common/.`
- ``frontend/src/components/shell/ErrorBoundary.tsx` — relocated from common/.`
- ``frontend/src/components/shell/ErrorBoundary.test.tsx` — relocated from common/.`
- ``frontend/src/components/shell/CookieConsentBanner.tsx` — relocated from common/.`
- ``frontend/src/components/shell/ChromeExtensionPromo.tsx` — relocated from common/.`
- ``frontend/src/components/shell/SubscriptionPromo.tsx` — relocated from common/.`
- ``frontend/src/components/shell/BetaBanner.tsx` — relocated from common/.`
- ``frontend/src/components/forms/SearchableSelect.tsx` — relocated from common/.`
- ``frontend/src/components/forms/ImageUpload.tsx` — relocated from common/.`
- ``frontend/src/components/cars/CarModelMultiSelect.tsx` — relocated from common/.`
- ``frontend/src/components/images/ImageWithPlaceholder.tsx` — relocated from common/.`
- ``frontend/src/components/filters/VehicleFilterSection.tsx` — relocated from common/.`
- ``frontend/src/components/filters/VehicleFilterChips.tsx` — relocated from common/.`
- ``frontend/src/components/buildLists/AddItemTile.tsx` — relocated from common/.`
- ``frontend/src/components/tables/ResponsiveTableWrapper.tsx` — relocated from common/.`
- ``frontend/src/components/ui/card-info-item.tsx` — folded from common/CardInfoItem.tsx into ui/.`
- ``frontend/src/App.tsx` — modified imports for structural infra.`
- ``frontend/src/main.tsx` — modified ErrorBoundary import.`
- ``frontend/src/App.coverage.test.tsx` — modified if comments referenced old paths.`

## Verification

cd frontend && npm run type-check && npm test -- --run && test ! -d src/components/buttons && test ! -f src/components/common/Card.tsx && test ! -f src/components/common/Alerts.tsx && test ! -f src/components/common/LoadingSpinner.tsx && test ! -f src/components/common/Pagination.tsx && test ! -f src/components/common/Input.tsx && test ! -f src/components/common/Dialog.tsx && test ! -f src/components/common/DeleteConfirmationDialog.tsx && test ! -f src/components/common/Button.tsx && test ! -f src/components/common/DangerousActionDialog.tsx && test ! -f src/components/common/ParentNavigationLink.tsx
