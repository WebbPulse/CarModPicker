# S12: Repo-wide ripple reskin

**Goal:** Retire frontend/src/components/common/ and frontend/src/components/buttons/ from the app: every page and inner component is migrated onto the S08 design system (frontend/src/components/ui/*) or onto a relocated non-primitive home; legacy primitive files are deleted (or, for app-shell infrastructure, moved out of common/); CI enforces the boundary via a grep guard so regressions can't re-introduce the legacy palette.
**Demo:** Walk every page in dev — all on the new design system, all interactions use S08 primitives. Run npm run lint — passes. Run grep -r 'from .*components/common' frontend/src/ — returns nothing. components/common/ directory removed.

## Must-Haves

- grep -rln "components/common|components/buttons" frontend/src/ returns zero hits; frontend/src/components/buttons/ directory is deleted; frontend/src/components/common/ contains only relocation-target stubs we intentionally keep, or is empty; npm run type-check exit 0; npm run lint produces zero new errors in S12-touched files; npm run test:e2e exits 0 (full suite, refreshed baselines for any spec that captures a touched page); a CI grep-guard test fails the build if any future commit re-introduces components/common/ or components/buttons/ imports; R017 satisfied (all pages on the new component library, enforcement check committed); R020 preserved (keyboard nav, focus indicators, escape-on-dialog still work on S09/S10/S11 priority pages and on every page migrated this slice).

## Proof Level

- This slice proves: integration — every page renders correctly on the new design system end-to-end, the grep guard locks the boundary, the full Playwright e2e suite exercises the migration at three viewports against the dev server, and the existing per-page vitest suite verifies the import-path swaps did not break behavior. Real runtime required: yes (Playwright drives the dev server). Human/UAT: recommended in S13 milestone validation — autonomous-mode closure substitutes the e2e suite + per-page vitests.

## Integration Closure

Upstream surfaces consumed: components/ui/{button,input,select,tabs,combobox,dialog,dropdown-menu,sheet,toast,confirm-dialog}.tsx (S08/S09); styles/tokens.css (S08); playwright.config.ts mobile/tablet/desktop projects (S08); components/charts/Sparkline.tsx + components/parts/PriceDeltaLine.tsx (S06, preserved in the parts/builder ripple). New wiring: new ui/* primitive files (card, alert, spinner, pagination, card-info-item) compose every page sweep; relocated app-shell infra under components/shell/ and components/routes/ rewires App.tsx, main.tsx, and App.coverage.test.tsx; CI grep-guard test wiring under frontend/src/__tests__/no-legacy-primitives.test.ts. What remains before the milestone is end-to-end usable: S13 (final integration + milestone verification) — full live-flow exercise against real backend, S3, price-history, alert email; S12 itself is R017's completion gate but does not assert milestone-level integration.

## Verification

- No new runtime signals introduced. Pre-existing RouteGroupBoundary Sentry tagging continues to emit route_group on render-time crashes regardless of where the file is located after relocation. Inspection surfaces: npm run dev for visual smoke; frontend/playwright-report/ HTML reporter on failed e2e; pixel-diff PNGs at frontend/test-results/* on regression. Failure visibility: page-test stack traces surface broken imports at vitest runtime; type-check surfaces broken imports at compile-time; the new grep guard fires at CI time before merge. Redaction constraints: none — frontend visual migration only.

## Tasks

- [x] **T01: Build missing ui/* primitives — Card, Alert (with named-export wrappers), Spinner, Pagination** `est:1.5h`
  Every subsequent page sweep is mechanical only if the destination primitives already exist. Card has the largest blast radius (~30 importers); Alert second (~30 importers, three named-export variants — ErrorAlert / ConfirmationAlert / SuccessAlert — required so the page sweep is import-rename-only); Pagination has non-trivial ellipsis logic that must be preserved verbatim; Spinner standardizes the legacy 6-size × 3-color × inline matrix onto a Loader2-backed wrapper so the page sweep can drop legacy LoadingSpinner imports without per-call inlining.

Do: Implement Card with shadcn idiom (Card / CardHeader / CardTitle / CardDescription / CardContent / CardFooter); export cardVariants cva() so consumers can compose; map the legacy variant='glass'/'elevated' to className overrides if any callsite still wants them, but default to the simple shadcn Card. Implement Alert with variant: 'default' | 'destructive' | 'success' AND export the three named wrappers (ErrorAlert({message}) → <Alert variant='destructive'>{message}</Alert>, ConfirmationAlert and SuccessAlert → variant='success') so the page sweep is a pure import-path rename. Implement Spinner as a thin Loader2-backed wrapper exposing size: 'xs'|'sm'|'base'|'md'|'lg'|'xl' (mapped to tailwind h-/w- classes preserving the 6-size scale) + optional text + optional inline; default export to keep legacy import shape. Implement Pagination preserving the ellipsis logic from common/Pagination.tsx VERBATIM — accept currentPage/totalPages/onPageChange/itemsPerPage/totalItems, render the 'Showing X – Y of Z' summary, Previous/Next disabled states, ellipsis-start / ellipsis-end keys; restyle button visuals onto ui/Button under the hood for consistency. Add a section per new primitive to _KitchenSink.tsx so components.spec.ts covers them in regression. Re-baseline components.spec.ts via `npm run test:e2e -- components.spec --update-snapshots` and commit the 3 refreshed PNGs.

Must-haves: card.tsx exports {Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter, cardVariants}; alert.tsx exports {Alert, AlertTitle, AlertDescription, alertVariants, ErrorAlert, ConfirmationAlert, SuccessAlert}; spinner.tsx exports default Spinner with the 6-size scale; pagination.tsx exports default Pagination with the same prop shape as common/Pagination.tsx; _KitchenSink renders all four; type-check exits 0; components.spec passes at all 3 viewports.
  - Files: `frontend/src/components/ui/card.tsx`, `frontend/src/components/ui/alert.tsx`, `frontend/src/components/ui/spinner.tsx`, `frontend/src/components/ui/pagination.tsx`, `frontend/src/pages/_KitchenSink.tsx`, `frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-mobile-linux.png`, `frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-tablet-linux.png`, `frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-desktop-linux.png`
  - Verify: cd frontend && npm run type-check && npm run test:e2e -- components.spec

- [x] **T02: Sweep Tier A (trivial public statics) + Tier B (auth pages) onto ui/* primitives** `est:1.5h`
  Smallest, lowest-risk surface — ~14 files using only Card/Alerts/LoadingSpinner/Input + the buttons/* family. Knocking them out first establishes the swap pattern (formal variants over bespoke className per MEM116; no layout-chrome rewrites per MEM107/MEM115) before the heavier sweeps in T03–T05.

Swap rules (apply uniformly across this task and T03–T05): import Card from '../../components/common/Card' → import { Card } from '../../components/ui/card'; import { ErrorAlert, ConfirmationAlert, SuccessAlert } from '../../components/common/Alerts' → from '../../components/ui/alert' (T01 named wrappers); import LoadingSpinner from '../../components/common/LoadingSpinner' → import Spinner from '../../components/ui/spinner' (rename calls; preserve size/text/inline props); import Input from '../../components/common/Input' → import { Input } from '../../components/ui/input' (note: legacy Input has label/error/helperText/leftIcon/rightIcon props that ui/Input does NOT expose — for those callsites, render the label/icon as JSX siblings of <Input> rather than props); ButtonStretch → <Button className='w-full'>; Button from buttons/Button → ui/Button (default variant); LinkButton → <Button asChild><Link to='...'>...</Link></Button> (shadcn convention).

Apply MEM116 — formal variants (destructive/secondary/link/ghost) over bespoke color className overrides; className overrides only for layout shape (h-auto, p-0, w-full, justify-start). Preserve every existing data-testid hook. Preserve existing useEffect orderings, cancellation flags, and submit handlers — this is a styling migration, not a behavior refactor.

Must-haves: every file in the file list no longer imports from components/common/ or components/buttons/; npm run type-check exits 0; existing vitests for these pages still pass; no console errors when rendering each page in dev.
  - Files: `frontend/src/pages/About.tsx`, `frontend/src/pages/ContactUs.tsx`, `frontend/src/pages/Pricing.tsx`, `frontend/src/pages/Checkout.tsx`, `frontend/src/pages/Support.tsx`, `frontend/src/pages/BugReport.tsx`, `frontend/src/pages/authentication/Login.tsx`, `frontend/src/pages/authentication/Register.tsx`, `frontend/src/pages/authentication/ForgotPassword.tsx`, `frontend/src/pages/authentication/ForgotPasswordConfirm.tsx`, `frontend/src/pages/authentication/VerifyEmail.tsx`, `frontend/src/pages/authentication/VerifyEmailConfirm.tsx`, `frontend/src/pages/authentication/ExtensionAuth.tsx`, `frontend/src/components/authentication/GoogleAuthFlow.tsx`
  - Verify: cd frontend && npm run type-check && npm test -- --run Login Register ForgotPassword VerifyEmail BugReport About ContactUs Pricing Checkout Support GoogleAuthFlow ExtensionAuth && ! grep -ln 'components/common\|components/buttons' src/pages/About.tsx src/pages/ContactUs.tsx src/pages/Pricing.tsx src/pages/Checkout.tsx src/pages/Support.tsx src/pages/BugReport.tsx src/pages/authentication/*.tsx src/components/authentication/GoogleAuthFlow.tsx

- [x] **T03: Sweep Tier C1 (account/profile/user pages + profile inner components + global header) onto ui/* primitives** `est:2.5h`
  Profile is the densest single page in this tier (461 lines, 8 legacy primitives). The profile inner components (SecuritySettings, PasskeySettings, ConnectedAccountsSettings, ChangePasswordDialog, TwoFactorAuthDialog, SecuritySettingsDialog) all share the same legacy import set (ActionButton + SecondaryButton + Alerts + Input + LoadingSpinner + Dialog). Migrating Profile and its inner components together keeps the per-task context coherent — a Profile sweep that doesn't also migrate its inner forms would leave the page partly broken at runtime even though it compiles.

Same swap rules as T02. Specific notes: ActionButton → <Button> (default variant) or <Button variant='secondary'> per MEM116; SecondaryButton → <Button variant='secondary'>; legacy Dialog → ui/Dialog using the parent-owned-state pattern S09/T02 established in ViewBuildlist.tsx (open/onOpenChange API, sm:max-w-* sizing, no auto-close on confirm during async); legacy Alerts/LoadingSpinner/Input/Card swaps as in T02. Home.tsx uses LinkButton — replace with <Button asChild><Link to='...'>...</Link></Button>; Home/Profile may use StretchButton — replace with <Button className='w-full'>. Search.tsx is large (522 lines) but uses only Alerts + Card + LoadingSpinner + ActionButton. Header.tsx (layout/globalHeader) only imports LoadingSpinner — trivial.

Do NOT change behavior: useEffect orderings, cancellation flags, redirect logic, async-await patterns stay identical. Run page tests after each file (Profile.test.tsx, AccountAlerts.test.tsx exist; Search/Home/ViewUser may not).

Must-haves: every file in the file list no longer imports from components/common/ or components/buttons/; type-check exit 0; vitest green for Profile, AccountAlerts, ViewUser, UserCard tests if they exist.
  - Files: `frontend/src/pages/Profile.tsx`, `frontend/src/pages/Home.tsx`, `frontend/src/pages/Search.tsx`, `frontend/src/pages/ViewUser.tsx`, `frontend/src/pages/account/AccountAlerts.tsx`, `frontend/src/components/users/UserCard.tsx`, `frontend/src/components/profile/SecuritySettings.tsx`, `frontend/src/components/profile/PasskeySettings.tsx`, `frontend/src/components/profile/ConnectedAccountsSettings.tsx`, `frontend/src/components/profile/ChangePasswordDialog.tsx`, `frontend/src/components/profile/TwoFactorAuthDialog.tsx`, `frontend/src/components/profile/SecuritySettingsDialog.tsx`, `frontend/src/components/layout/globalHeader/Header.tsx`
  - Verify: cd frontend && npm run type-check && npm test -- --run Profile Home Search ViewUser AccountAlerts UserCard SecuritySettings PasskeySettings ConnectedAccountsSettings ChangePasswordDialog TwoFactorAuthDialog SecuritySettingsDialog Header && ! grep -ln 'components/common\|components/buttons' src/pages/Profile.tsx src/pages/Home.tsx src/pages/Search.tsx src/pages/ViewUser.tsx src/pages/account/AccountAlerts.tsx src/components/users/UserCard.tsx src/components/profile/*.tsx src/components/layout/globalHeader/Header.tsx

- [x] **T04: Sweep Tier C2 (builder + parts + buildLists pages + their inner components) onto ui/* primitives** `est:3h`
  The heaviest tier — 9 page files (one is 978 lines: ViewPart.tsx) plus ~20 inner components in buildLists/, buildListParts/, parts/, cars/. Bounded by what an executor can hold in one context, so the sweep is mechanical: every legacy primitive has a documented destination, no layout rewrites, no behavior changes. Pages partially migrated by S09 (ViewBuildlist) and S10 (PartsCatalog, PartsFilterSidebar, PartsActiveFilterChips, PartList, AddToBuildListDialog) only need the REMAINING legacy imports swept — Card, Alerts, LoadingSpinner, ImageWithPlaceholder, ResponsiveTableWrapper, Pagination, ParentNavigationLink — they already use the new buttons/dialogs.

Same swap rules as T02/T03. Specific notes: (a) DeleteConfirmationDialog → ui/confirm-dialog from S09 — use the parent-owned-state pattern, destructive variant, loadingLabel='Deleting...' preserved (see S09/T01 for the contract). (b) Pagination → ui/pagination from T01 — props are identical so it's a one-line import swap. (c) LinkButton (UserParts.tsx, PartsCatalog.tsx) → <Button asChild><Link to='...'>; if the legacy callsite used a stretch variant, add className='w-full'. (d) AddItemTile is a domain composite — at each callsite, update the import to its FUTURE relocated path '../buildLists/AddItemTile' (T05 performs the actual move). (e) ParentNavigationLink — at each of the 3 callsites (ViewBuildlist, ViewPart, ViewBuildLog), inline the <Link to={linkTo}>{linkText}</Link> JSX directly so we can delete the helper file in T05. (f) For forms (CreatePartForm, EditPartForm, CreateBuildListPartForm, EditBuildListForm, CreateBuildListForm) that compose SearchableSelect / CarModelMultiSelect / ImageUpload / ImageWithPlaceholder from common/, update the import paths to the FUTURE relocated paths: '../forms/SearchableSelect', '../forms/ImageUpload', '../images/ImageWithPlaceholder', '../cars/CarModelMultiSelect'. T05 performs the actual file moves; T04 leaves the imports pointing at the future paths so the diff in T05 is a pure file move + zero importer updates. Type-check WILL FAIL at the end of T04 because those relocated paths don't exist yet — this is expected and resolved by T05. (g) VehicleFilterSection / VehicleFilterChips (used by BuildListsCatalog, PartsFilterSidebar, PartsActiveFilterChips) — same: update imports to '../filters/VehicleFilterSection' and '../filters/VehicleFilterChips'; T05 moves the files. (h) ResponsiveTableWrapper (PartList, BuildListPartList) — update import to '../tables/ResponsiveTableWrapper'; T05 moves it. (i) CardInfoItem callsites in ViewBuildlist, ViewCar, ViewPart — update import to '../../components/ui/card-info-item' (T05 folds CardInfoItem into ui/).

The pattern: after T04, every file in the list has zero common/ or buttons/ imports — but several imports point at paths that don't exist until T05 lands. T04 is correct when the import statements are right; T05 makes them resolve.

Must-haves: every file in the file list no longer imports from components/common/Card / Alerts / LoadingSpinner / Pagination / Input / Dialog / DeleteConfirmationDialog / Button / DangerousActionDialog / ParentNavigationLink / ResponsiveTableWrapper / CardInfoItem / AddItemTile, or from components/buttons/*; imports of relocated helpers point at the future paths; behavior preserved.
  - Files: `frontend/src/pages/builder/ViewPart.tsx`, `frontend/src/pages/builder/ViewCar.tsx`, `frontend/src/pages/builder/Builder.tsx`, `frontend/src/pages/builder/ViewBuildlist.tsx`, `frontend/src/pages/buildLists/BuildListsCatalog.tsx`, `frontend/src/pages/buildLists/ViewBuildLog.tsx`, `frontend/src/pages/parts/PartsCatalog.tsx`, `frontend/src/pages/parts/UserParts.tsx`, `frontend/src/pages/parts/EditPart.tsx`, `frontend/src/components/parts/PartList.tsx`, `frontend/src/components/parts/PartListItem.tsx`, `frontend/src/components/parts/PartsFilterSidebar.tsx`, `frontend/src/components/parts/PartsActiveFilterChips.tsx`, `frontend/src/components/parts/AddToBuildListDialog.tsx`, `frontend/src/components/parts/CreatePartForm.tsx`, `frontend/src/components/parts/EditPartForm.tsx`, `frontend/src/components/parts/ImageGallery.tsx`, `frontend/src/components/parts/ImageGalleryManage.tsx`, `frontend/src/components/buildListParts/BuildListPartList.tsx`, `frontend/src/components/buildListParts/BuildListPartListItem.tsx`, `frontend/src/components/buildListParts/BuildListParts.tsx`, `frontend/src/components/buildListParts/CreateBuildListPartForm.tsx`, `frontend/src/components/buildLists/CreateBuildListForm.tsx`, `frontend/src/components/buildLists/EditBuildListForm.tsx`, `frontend/src/components/buildLists/BuildListItem.tsx`, `frontend/src/components/buildLists/BuildListList.tsx`, `frontend/src/components/buildLists/BuildListCard.tsx`, `frontend/src/components/buildLists/BuildListCatalogList.tsx`, `frontend/src/components/cars/CarList.tsx`, `frontend/src/components/cars/CarListItem.tsx`
  - Verify: cd frontend && ! grep -lE "from '(\\.\\./)+(common|buttons)/(Card|Alerts|LoadingSpinner|Pagination|Input|Dialog|DeleteConfirmationDialog|Button|DangerousActionDialog|ParentNavigationLink|ResponsiveTableWrapper|CardInfoItem|AddItemTile|ActionButton|SecondaryButton|StretchButton|LinkButton)'" src/pages/builder/*.tsx src/pages/buildLists/*.tsx src/pages/parts/*.tsx src/components/parts/*.tsx src/components/buildListParts/*.tsx src/components/buildLists/*.tsx src/components/cars/*.tsx

- [x] **T05: Sweep Tier D (admin pages) + relocate structural infra and non-primitive helpers + delete legacy primitives** `est:3h`
  Three closely-coupled chunks of work that must land atomically: (a) the admin tier (9 pages including the 2,665-line CrawlerAdmin.tsx + 1 inner component ReportDialog) is the last page-importer cluster and shares the same legacy import set as Tier C; (b) structural infra (RouteGroupBoundary + test, ErrorBoundary + test, CookieConsentBanner, ChromeExtensionPromo, SubscriptionPromo, BetaBanner) plus non-primitive helpers (SearchableSelect, CarModelMultiSelect, ImageUpload, ImageWithPlaceholder, VehicleFilterSection, VehicleFilterChips, AddItemTile, ResponsiveTableWrapper, CardInfoItem) need to move out of components/common/ so the grep guard in T06 can pass; (c) legacy primitive files must be deleted. Bundling them in one task lets the executor verify everything compiles + tests pass at one consistent end state, instead of leaving the tree in a half-relocated half-deleted state between tasks.

Do (a) Admin sweep first: same swap rules as T03/T04. Admin pages predominantly use Card + Alerts + LoadingSpinner + Pagination + ActionButton + SecondaryButton + Dialog + DeleteConfirmationDialog. AdminDashboard already uses ui/Button (S11); finish off Card + Alerts. ExtractionHealth already uses ui/Button (S11); finish off Card + Alerts + LoadingSpinner. CrawlerAdmin is large but mechanical. ReportDialog (admin/) swaps Dialog + ActionButton + SecondaryButton.

Do (b) Structural-infra relocation: read each source file, write it to its new path, delete old. Update imports in App.tsx ('./components/common/RouteGroupBoundary' → './components/routes/RouteGroupBoundary'; same pattern for ErrorBoundary → ./components/shell/ErrorBoundary, CookieConsentBanner → ./components/shell/CookieConsentBanner, ChromeExtensionPromo → ./components/shell/ChromeExtensionPromo, SubscriptionPromo → ./components/shell/SubscriptionPromo, BetaBanner → ./components/shell/BetaBanner). Update main.tsx for ErrorBoundary import. Update App.coverage.test.tsx if it references the old paths in comments. RouteGroupBoundary.test.tsx and ErrorBoundary.test.tsx — only their location changes; their internal 'from ./RouteGroupBoundary' imports stay relative-to-self.

Do (c) Non-primitive helper relocation: move SearchableSelect → forms/, ImageUpload → forms/, CarModelMultiSelect → cars/, ImageWithPlaceholder → images/, VehicleFilterSection → filters/, VehicleFilterChips → filters/, AddItemTile → buildLists/, ResponsiveTableWrapper → tables/, CardInfoItem → ui/card-info-item.tsx (fold into ui/). T04 already updated every importer to point at these new paths, so the move alone resolves the broken imports. Verify with grep that no remaining importer points at the old path.

Do (d) Legacy primitive delete: delete components/common/{Card,Alerts,LoadingSpinner,Pagination,Input,Dialog,DeleteConfirmationDialog,Button,DangerousActionDialog,ParentNavigationLink}.tsx and the entire components/buttons/ directory. After delete, components/common/ should be empty — if any file remains, an importer was missed; chase it down.

Run the full type-check + vitest gauntlet at the end of the task to verify everything resolves and behaves identically. Type-check should now exit 0 (T04's pending failures resolved by the relocations).

Must-haves: admin pages have no legacy imports; relocated files exist at new paths and are imported correctly everywhere; legacy primitive files deleted; full vitest + type-check green; components/buttons/ directory does not exist; components/common/ contains no Card/Alerts/LoadingSpinner/Pagination/Input/Dialog/DeleteConfirmationDialog/Button/DangerousActionDialog/ParentNavigationLink files.
  - Files: `frontend/src/pages/admin/AdminDashboard.tsx`, `frontend/src/pages/admin/ExtractionHealth.tsx`, `frontend/src/pages/admin/ReportReview.tsx`, `frontend/src/pages/admin/BugReportReview.tsx`, `frontend/src/pages/admin/UserManagement.tsx`, `frontend/src/pages/admin/PartsCuration.tsx`, `frontend/src/pages/admin/SystemAdmin.tsx`, `frontend/src/pages/admin/SystemStatistics.tsx`, `frontend/src/pages/admin/CrawlerAdmin.tsx`, `frontend/src/components/admin/ReportDialog.tsx`, `frontend/src/components/routes/RouteGroupBoundary.tsx`, `frontend/src/components/routes/RouteGroupBoundary.test.tsx`, `frontend/src/components/shell/ErrorBoundary.tsx`, `frontend/src/components/shell/ErrorBoundary.test.tsx`, `frontend/src/components/shell/CookieConsentBanner.tsx`, `frontend/src/components/shell/ChromeExtensionPromo.tsx`, `frontend/src/components/shell/SubscriptionPromo.tsx`, `frontend/src/components/shell/BetaBanner.tsx`, `frontend/src/components/forms/SearchableSelect.tsx`, `frontend/src/components/forms/ImageUpload.tsx`, `frontend/src/components/cars/CarModelMultiSelect.tsx`, `frontend/src/components/images/ImageWithPlaceholder.tsx`, `frontend/src/components/filters/VehicleFilterSection.tsx`, `frontend/src/components/filters/VehicleFilterChips.tsx`, `frontend/src/components/buildLists/AddItemTile.tsx`, `frontend/src/components/tables/ResponsiveTableWrapper.tsx`, `frontend/src/components/ui/card-info-item.tsx`, `frontend/src/App.tsx`, `frontend/src/main.tsx`, `frontend/src/App.coverage.test.tsx`
  - Verify: cd frontend && npm run type-check && npm test -- --run && test ! -d src/components/buttons && test ! -f src/components/common/Card.tsx && test ! -f src/components/common/Alerts.tsx && test ! -f src/components/common/LoadingSpinner.tsx && test ! -f src/components/common/Pagination.tsx && test ! -f src/components/common/Input.tsx && test ! -f src/components/common/Dialog.tsx && test ! -f src/components/common/DeleteConfirmationDialog.tsx && test ! -f src/components/common/Button.tsx && test ! -f src/components/common/DangerousActionDialog.tsx && test ! -f src/components/common/ParentNavigationLink.tsx

- [x] **T06: Add CI grep-guard test, refresh visual baselines, run final verification gauntlet** `est:1.5h`
  With the migration complete, R017's enforcement gate ('via lint rule or grep check') needs a committed test that fails the build if any future PR re-imports from components/common/ or components/buttons/. With every page reskinned, every Playwright spec that screenshots a touched page will produce pixel diffs vs the legacy baselines (per MEM113 / MEM115) — the baseline-refresh sweep is part of THIS slice, not a follow-up. The final gauntlet proves R017 is met and R020 is preserved.

Do: (a) Write frontend/src/__tests__/no-legacy-primitives.test.ts — a vitest test that walks frontend/src/ recursively (excluding components/common/, components/buttons/, __tests__/, node_modules/, dist/, coverage/), reads each .ts/.tsx file, and asserts no file matches the regex from\s+['\"](?:\\.\\.\\/)+(?:common|buttons)/. Document the WHY in a JSDoc block referencing R017 and the M002/S12 slice. (b) Augment frontend/eslint.config.js with a no-restricted-imports rule for components/common/* and components/buttons/* patterns (optional — redundant safety; only add if it doesn't introduce new errors against the MEM062 baseline). (c) Refresh visual baselines: cd frontend && npm run test:e2e -- --update-snapshots. Inspect the resulting PNG diffs to ensure they look correct (no overflow, no wrong color, no missing component); commit the refreshed baselines only after sanity-check. (d) Run the full gauntlet: npm run type-check (exit 0); npm test -- --run (exit 0, including the new no-legacy-primitives.test.ts); npm run test:e2e (exit 0, all 7 specs across 3 viewports); npm run lint (no NEW errors in S12-touched files vs MEM062 baseline of ~108); ! grep -rln 'components/common\\|components/buttons' frontend/src/ (zero hits); test ! -d frontend/src/components/buttons (true). (e) Write .gsd/milestones/M002/slices/S12/S12-UAT.md recording the manual smoke status — autonomous-mode entry: e2e suite served as evidence; if e2e doesn't cover a page (Tier A statics like ContactUs, Pricing, Checkout, Support), list it explicitly so S13 can pick it up.

Must-haves: no-legacy-primitives.test.ts is in npm test's output and is GREEN; full e2e suite green at all 3 viewports with refreshed baselines committed; type-check green; lint baseline preserved (no new errors in S12-touched files); grep returns zero hits; buttons/ directory gone; S12-UAT.md committed.
  - Files: `frontend/src/__tests__/no-legacy-primitives.test.ts`, `frontend/eslint.config.js`, `frontend/e2e/components.spec.ts-snapshots`, `frontend/e2e/build-list.spec.ts-snapshots`, `frontend/e2e/parts-catalog.spec.ts-snapshots`, `frontend/e2e/price-history.spec.ts-snapshots`, `frontend/e2e/price-alerts.spec.ts-snapshots`, `frontend/e2e/admin.spec.ts-snapshots`, `.gsd/milestones/M002/slices/S12/S12-UAT.md`
  - Verify: cd frontend && npm run type-check && npm test -- --run && npm run test:e2e && ! grep -rln 'components/common\|components/buttons' src/ && test ! -d src/components/buttons && test -f ../.gsd/milestones/M002/slices/S12/S12-UAT.md

## Files Likely Touched

- frontend/src/components/ui/card.tsx
- frontend/src/components/ui/alert.tsx
- frontend/src/components/ui/spinner.tsx
- frontend/src/components/ui/pagination.tsx
- frontend/src/pages/_KitchenSink.tsx
- frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-mobile-linux.png
- frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-tablet-linux.png
- frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-desktop-linux.png
- frontend/src/pages/About.tsx
- frontend/src/pages/ContactUs.tsx
- frontend/src/pages/Pricing.tsx
- frontend/src/pages/Checkout.tsx
- frontend/src/pages/Support.tsx
- frontend/src/pages/BugReport.tsx
- frontend/src/pages/authentication/Login.tsx
- frontend/src/pages/authentication/Register.tsx
- frontend/src/pages/authentication/ForgotPassword.tsx
- frontend/src/pages/authentication/ForgotPasswordConfirm.tsx
- frontend/src/pages/authentication/VerifyEmail.tsx
- frontend/src/pages/authentication/VerifyEmailConfirm.tsx
- frontend/src/pages/authentication/ExtensionAuth.tsx
- frontend/src/components/authentication/GoogleAuthFlow.tsx
- frontend/src/pages/Profile.tsx
- frontend/src/pages/Home.tsx
- frontend/src/pages/Search.tsx
- frontend/src/pages/ViewUser.tsx
- frontend/src/pages/account/AccountAlerts.tsx
- frontend/src/components/users/UserCard.tsx
- frontend/src/components/profile/SecuritySettings.tsx
- frontend/src/components/profile/PasskeySettings.tsx
- frontend/src/components/profile/ConnectedAccountsSettings.tsx
- frontend/src/components/profile/ChangePasswordDialog.tsx
- frontend/src/components/profile/TwoFactorAuthDialog.tsx
- frontend/src/components/profile/SecuritySettingsDialog.tsx
- frontend/src/components/layout/globalHeader/Header.tsx
- frontend/src/pages/builder/ViewPart.tsx
- frontend/src/pages/builder/ViewCar.tsx
- frontend/src/pages/builder/Builder.tsx
- frontend/src/pages/builder/ViewBuildlist.tsx
- frontend/src/pages/buildLists/BuildListsCatalog.tsx
- frontend/src/pages/buildLists/ViewBuildLog.tsx
- frontend/src/pages/parts/PartsCatalog.tsx
- frontend/src/pages/parts/UserParts.tsx
- frontend/src/pages/parts/EditPart.tsx
- frontend/src/components/parts/PartList.tsx
- frontend/src/components/parts/PartListItem.tsx
- frontend/src/components/parts/PartsFilterSidebar.tsx
- frontend/src/components/parts/PartsActiveFilterChips.tsx
- frontend/src/components/parts/AddToBuildListDialog.tsx
- frontend/src/components/parts/CreatePartForm.tsx
- frontend/src/components/parts/EditPartForm.tsx
- frontend/src/components/parts/ImageGallery.tsx
- frontend/src/components/parts/ImageGalleryManage.tsx
- frontend/src/components/buildListParts/BuildListPartList.tsx
- frontend/src/components/buildListParts/BuildListPartListItem.tsx
- frontend/src/components/buildListParts/BuildListParts.tsx
- frontend/src/components/buildListParts/CreateBuildListPartForm.tsx
- frontend/src/components/buildLists/CreateBuildListForm.tsx
- frontend/src/components/buildLists/EditBuildListForm.tsx
- frontend/src/components/buildLists/BuildListItem.tsx
- frontend/src/components/buildLists/BuildListList.tsx
- frontend/src/components/buildLists/BuildListCard.tsx
- frontend/src/components/buildLists/BuildListCatalogList.tsx
- frontend/src/components/cars/CarList.tsx
- frontend/src/components/cars/CarListItem.tsx
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
- frontend/src/components/shell/ErrorBoundary.tsx
- frontend/src/components/shell/ErrorBoundary.test.tsx
- frontend/src/components/shell/CookieConsentBanner.tsx
- frontend/src/components/shell/ChromeExtensionPromo.tsx
- frontend/src/components/shell/SubscriptionPromo.tsx
- frontend/src/components/shell/BetaBanner.tsx
- frontend/src/components/forms/SearchableSelect.tsx
- frontend/src/components/forms/ImageUpload.tsx
- frontend/src/components/cars/CarModelMultiSelect.tsx
- frontend/src/components/images/ImageWithPlaceholder.tsx
- frontend/src/components/filters/VehicleFilterSection.tsx
- frontend/src/components/filters/VehicleFilterChips.tsx
- frontend/src/components/buildLists/AddItemTile.tsx
- frontend/src/components/tables/ResponsiveTableWrapper.tsx
- frontend/src/components/ui/card-info-item.tsx
- frontend/src/App.tsx
- frontend/src/main.tsx
- frontend/src/App.coverage.test.tsx
- frontend/src/__tests__/no-legacy-primitives.test.ts
- frontend/eslint.config.js
- frontend/e2e/components.spec.ts-snapshots
- frontend/e2e/build-list.spec.ts-snapshots
- frontend/e2e/parts-catalog.spec.ts-snapshots
- frontend/e2e/price-history.spec.ts-snapshots
- frontend/e2e/price-alerts.spec.ts-snapshots
- frontend/e2e/admin.spec.ts-snapshots
- .gsd/milestones/M002/slices/S12/S12-UAT.md
