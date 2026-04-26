---
slice: S12
parent: M002
title: Repo-wide ripple reskin
depth: targeted
---

# S12: Repo-wide ripple reskin — Research

## Summary

S12 finishes M002's design-system migration: every page that wasn't touched by S09/S10/S11 needs to land on `components/ui/*`, the legacy `components/common/` and `components/buttons/` directories need to be retired (or at least cease being imported from `pages/*`), and a CI grep/lint guard needs to lock the migration in. Three structural realities planning needs to absorb up front:

1. **Surface size is bigger than "17 pages."** 38 page-level files (.tsx) currently import from `components/common` or `components/buttons`, plus 35 inner-component files (forms, list items, dialogs) under `components/{admin,authentication,buildLists,buildListParts,cars,parts,profile,routes,users,layout}/`. The grep guard the slice wants ("no `from .*components/common`") would fail today against all 73 files. Total page LOC: ~23,200; the heaviest single file is `admin/CrawlerAdmin.tsx` at 2,665 lines.
2. **The `ui/*` library is missing primitives the legacy library has.** `components/ui/` ships button, input, select, tabs, combobox, dialog, dropdown-menu, sheet, toast, confirm-dialog. It does **not** ship `card`, `alert`, `pagination`, `spinner`, `image-upload`, `searchable-select`, `responsive-table`, `card-info-item`, `add-item-tile`, `image-with-placeholder`, or anything to replace `CarModelMultiSelect` / `VehicleFilterSection` / `VehicleFilterChips`. Any planning that says "just swap the import" misses ~10 new shadcn-style primitives that have to land first.
3. **Some of `common/*` is structural infrastructure, not legacy primitives.** `RouteGroupBoundary.tsx` (Phase 6 FE-03 sentry pattern, used by App.tsx + has its own test), `ErrorBoundary.tsx` (used by App.tsx + main.tsx), `CookieConsentBanner.tsx`, `ChromeExtensionPromo.tsx`, `SubscriptionPromo.tsx`, `BetaBanner.tsx` are app-shell concerns, not visual primitives. They should be **moved out of `common/` into a different home** (e.g. `components/shell/`, `components/layout/`, or `components/routes/`) — not rewritten on top of shadcn.

The pragmatic shape is: build the missing `ui/*` primitives first (T01–T03), do the page sweeps in tier-grouped tasks (T04–T08), relocate the structural infra (T09), retire/deprecate the legacy shells (T10), add the grep guard (T11), refresh visual baselines (T12). Manual UAT smoke per page (R017 says "Manual UAT smoke pass documented per page") becomes one consolidated checklist in S12-UAT.md, executed against the Playwright suite + a single live-server walkthrough.

## Recommendation

**Approach:** Build missing `ui/*` primitives first → page sweep grouped by route domain (admin / authentication / public / builder/parts/buildLists) → relocate non-primitive `common/*` files (RouteGroupBoundary, ErrorBoundary, CookieConsentBanner, ChromeExtensionPromo, SubscriptionPromo, BetaBanner) → delete the now-unused legacy primitives → land grep guard → refresh visual baselines.

**Why this shape:** Trying to swap imports page-by-page without first landing the missing primitives forces planners to inline ad-hoc styles per page (regressing on the design-system goal). Doing the ui/* primitive work in one wave first (T01–T03) means every page sweep becomes a mechanical import swap. The structural-infra relocate (T09) is the cleanest way to satisfy the literal "no `components/common/` imports" guard without rewriting working app-shell code.

**Risks to budget:** Visual baseline refresh blast radius is large — every spec that screenshots any reskinned page will drift (MEM113/MEM115 confirmed this from S10). Plan to refresh `build-list.spec.ts`, `parts-catalog.spec.ts`, `admin.spec.ts`, `price-history.spec.ts`, `price-alerts.spec.ts`, `components.spec.ts` baselines — and any new spec that captures a reskinned page. Don't try to make S12 zero-baseline-drift.

## Implementation Landscape

### Files that exist today and need to change

**Missing ui/* primitives that must land first** (T01–T03):

| New primitive | Replaces | Notes |
|---|---|---|
| `ui/card.tsx` | `common/Card.tsx` (62 lines, 3 variants × 4 padding × interactive) | Shadcn Card pattern: Card / CardHeader / CardTitle / CardDescription / CardContent / CardFooter. Map legacy `variant='glass'` to a `className` override; `interactive` becomes a `cn()`-driven hover state. |
| `ui/alert.tsx` | `common/Alerts.tsx` exporting `ErrorAlert` / `ConfirmationAlert` / `SuccessAlert` (63 lines) | Shadcn Alert with `variant='default' \| 'destructive' \| 'success'`. Keep the `ErrorAlert`/`SuccessAlert` named exports as thin wrappers so the page sweep is import-rename only. |
| `ui/spinner.tsx` (or use Loader2 directly) | `common/LoadingSpinner.tsx` (116 lines, 6 sizes × 3 colors × inline/block/text) | Many usages just need `Loader2` from lucide. The slice could replace LoadingSpinner with `<Loader2 className="animate-spin" />` everywhere and skip a primitive. Alternative: a thin `Spinner` wrapper exposing `size` + `text` + `inline` to keep page diffs minimal. |
| `ui/pagination.tsx` | `common/Pagination.tsx` (164 lines, ellipsis-aware) | Shadcn ships an idiomatic Pagination. Used by 6+ files. Worth porting properly because the ellipsis behavior is non-trivial. |
| `ui/card-info-item.tsx` (optional) | `common/CardInfoItem.tsx` (22 lines) | Trivial. Could fold into Card subcomponents or keep as a small wrapper. |
| `ui/responsive-table.tsx` (optional) | `common/ResponsiveTableWrapper.tsx` (43 lines) | Small wrapper; could move into `ui/` or leave as `components/tables/`. |

**Primitives that should NOT be reimplemented in S12 — keep them, just relocate:**

| Legacy file | Why keep | Suggested new home |
|---|---|---|
| `common/SearchableSelect.tsx` (429 lines, create-new flow + custom filter) | Behavior is non-trivial; ui/Combobox doesn't cover create-new flow. Replacing it would fight 4 forms. | Move to `components/forms/SearchableSelect.tsx` or restyle in place using ui/Input + ui/Popover (out of scope for S12). |
| `common/CarModelMultiSelect.tsx` (162 lines, multi-select chips on top of SearchableSelect) | Domain-specific; pulls SearchableSelect as a dep. | Move to `components/cars/CarModelMultiSelect.tsx`. |
| `common/ImageUpload.tsx` (212 lines, S3 presigned-URL flow) | Backend integration; not a primitive. | Move to `components/forms/ImageUpload.tsx`. |
| `common/ImageWithPlaceholder.tsx` (61 lines) | Domain helper, not styling. | Move to `components/images/ImageWithPlaceholder.tsx`. |
| `common/RouteGroupBoundary.tsx` (91 lines) + test | Phase 6 FE-03 Sentry pattern; mounted from App.tsx. | Move to `components/routes/RouteGroupBoundary.tsx` (sibling of GuestRoute/ProtectedRoute). |
| `common/ErrorBoundary.tsx` (70 lines) + test | App-root catch; mounted from main.tsx + App.tsx. | Move to `components/shell/ErrorBoundary.tsx` or `components/routes/`. |
| `common/CookieConsentBanner.tsx` (71 lines) | App-shell, not a page primitive. | Move to `components/shell/CookieConsentBanner.tsx`. |
| `common/ChromeExtensionPromo.tsx` (125 lines) | App-shell promo. | Move to `components/shell/ChromeExtensionPromo.tsx`. |
| `common/SubscriptionPromo.tsx` (86 lines) | App-shell promo. | Move to `components/shell/SubscriptionPromo.tsx`. |
| `common/BetaBanner.tsx` (43 lines) | App-shell banner. | Move to `components/shell/BetaBanner.tsx`. |
| `common/VehicleFilterSection.tsx` (165 lines) + `VehicleFilterChips.tsx` (99 lines) | Domain filter UI for parts/build-lists catalogs. | Move to `components/parts/` or `components/filters/`. Restyle is optional in S12 — can ride later. |
| `common/AddItemTile.tsx` (35 lines) | Domain UI built on Card. | Move to `components/buildLists/` or fold into a Card variant. |
| `common/DangerousActionDialog.tsx` (122 lines) | If still used; `ConfirmDialog` may already cover it. Verify. | Replace with `ui/confirm-dialog.tsx` or fold the variant in. |

**Legacy primitives that DELETE after sweep:**

| Delete target | Replacement | Files to update |
|---|---|---|
| `common/Card.tsx` | `ui/card.tsx` | ~30 importers (page + component) |
| `common/Alerts.tsx` | `ui/alert.tsx` (re-exporting ErrorAlert/SuccessAlert/ConfirmationAlert names) | ~30 importers |
| `common/LoadingSpinner.tsx` | `ui/spinner.tsx` (or inline Loader2) | ~25 importers |
| `common/Input.tsx` | `ui/input.tsx` (already exists; just swap) | ~10 importers |
| `common/Dialog.tsx` | `ui/dialog.tsx` (already exists) | ~7 importers |
| `common/DeleteConfirmationDialog.tsx` | `ui/confirm-dialog.tsx` (already exists) | ~5 importers |
| `common/Button.tsx` | `ui/button.tsx` (already exists) | 2 importers (BugReport, About) |
| `common/Pagination.tsx` | `ui/pagination.tsx` | ~6 importers |
| `common/CardInfoItem.tsx` | `ui/card-info-item.tsx` or fold into ui/card | ~5 importers |
| `common/ResponsiveTableWrapper.tsx` | `ui/responsive-table.tsx` or relocate | 2 importers (PartList, BuildListPartList) |
| `common/ParentNavigationLink.tsx` | inline `<Link>` + arrow, or relocate to `components/layout/` | 3 importers |
| `buttons/ActionButton.tsx` | `ui/Button` (default variant) | ~12 importers |
| `buttons/SecondaryButton.tsx` | `ui/Button` variant='secondary' | ~10 importers |
| `buttons/StretchButton.tsx` | `ui/Button` className='w-full' | ~6 importers (auth pages) |
| `buttons/Button.tsx` | `ui/Button` (note: this is a different file from common/Button!) | 2 importers (auth Login/Register) |
| `buttons/LinkButton.tsx` | `ui/Button asChild` wrapping `<Link>` | ~3 importers (Home, PartsCatalog, UserParts) |

### Page importers — count by origin

Generated by `grep -r 'from.*components/(common|buttons)/' frontend/src` then deduped:

- `frontend/src/main.tsx` — 1 import (ErrorBoundary)
- `frontend/src/App.tsx` — 7 imports (BetaBanner, ChromeExtensionPromo, CookieConsentBanner, ErrorBoundary, LoadingSpinner, RouteGroupBoundary, SubscriptionPromo)
- `frontend/src/pages/*` (page level) — 38 distinct files
- `frontend/src/components/*` (inner components) — 35 distinct files

Total: 73 files importing legacy primitives. This count drops dramatically after relocating the structural infra (App.tsx → 0; main.tsx → 0; routes/* → 0).

### Tier-grouping for the page sweep (planner can use this directly)

Group by relative LOC + shared context. Each group is one task; each group should land + commit independently.

**Tier A — trivial swaps (≤200 LOC, 1–3 imports):**
- `pages/About.tsx` (244, Button + Card)
- `pages/ContactUs.tsx` (114, Card)
- `pages/Pricing.tsx` (275, Card)
- `pages/Checkout.tsx` (161, Card)
- `pages/Support.tsx` (237, ActionButton + Card)
- `pages/NotFound.tsx` (27, no legacy imports — verify)
- `pages/PrivacyPolicy.tsx` (414, no legacy imports — verify)
- `pages/TermsOfService.tsx` (401, no legacy imports — verify)

**Tier B — auth pages (legacy ButtonStretch + Input + Alerts + LoadingSpinner):**
- `authentication/Login.tsx` (360)
- `authentication/Register.tsx` (253)
- `authentication/ForgotPassword.tsx` (82)
- `authentication/ForgotPasswordConfirm.tsx` (134)
- `authentication/VerifyEmail.tsx` (90)
- `authentication/VerifyEmailConfirm.tsx` (45)
- `authentication/ExtensionAuth.tsx` (212)

**Tier C — user-facing complex pages:**
- `pages/Home.tsx` (414, LinkButton + Alerts + Card + ImageWithPlaceholder + LoadingSpinner)
- `pages/Profile.tsx` (461, ActionButton + SecondaryButton + StretchButton + Alerts + Card + CardInfoItem + ImageUpload + Input + LoadingSpinner)
- `pages/ViewUser.tsx` (149, Alerts + Card + CardInfoItem + LoadingSpinner)
- `pages/Search.tsx` (522, ActionButton + Alerts + Card + LoadingSpinner)
- `pages/BugReport.tsx` (368, Alerts + Button + Card + Input + LoadingSpinner)
- `pages/account/AccountAlerts.tsx` (299, Alerts + Card + LoadingSpinner) — also fold MEM102 useEffect bug fix here
- `pages/buildLists/BuildListsCatalog.tsx` (660, Alerts + Card + Input + LoadingSpinner + Pagination + VehicleFilterChips + VehicleFilterSection)
- `pages/buildLists/ViewBuildLog.tsx` (664, ActionButton + Alerts + Card + DeleteConfirmationDialog + Dialog + ImageUpload + LoadingSpinner + Pagination + ParentNavigationLink)
- `pages/builder/Builder.tsx` (176, AddItemTile + Alerts + Dialog + LoadingSpinner + Pagination)
- `pages/builder/ViewCar.tsx` (303, Alerts + Card + CardInfoItem + Dialog + Input + LoadingSpinner)
- `pages/builder/ViewPart.tsx` (978, ActionButton + Alerts + Card + CardInfoItem + DeleteConfirmationDialog + Dialog + LoadingSpinner + ParentNavigationLink)
- `pages/parts/UserParts.tsx` (211, LinkButton + Alerts + Card + DeleteConfirmationDialog + Input + Pagination)
- `pages/parts/EditPart.tsx` (141, SecondaryButton + Alerts + Card + LoadingSpinner)

**Tier D — admin pages (8 files, Alerts + Card + Dialog + LoadingSpinner + Pagination + ActionButton patterns):**
- `admin/AdminDashboard.tsx` (137 — already partly reskinned in S11; finish chrome retirement)
- `admin/ExtractionHealth.tsx` (296 — already partly reskinned in S11; finish chrome retirement)
- `admin/ReportReview.tsx` (451)
- `admin/BugReportReview.tsx` (608)
- `admin/UserManagement.tsx` (721)
- `admin/PartsCuration.tsx` (762)
- `admin/SystemAdmin.tsx` (828)
- `admin/SystemStatistics.tsx` (755)
- `admin/CrawlerAdmin.tsx` (2665) **← largest single file**

**Tier E — inner components (35 files in `frontend/src/components/{admin,authentication,buildLists,buildListParts,cars,parts,profile,routes,users,layout}/`):**
Importers list (from grep):
- `admin/ReportDialog.tsx`
- `authentication/GoogleAuthFlow.tsx`
- `buildLists/{CreateBuildListForm, EditBuildListForm, BuildListCatalogList, BuildListItem, BuildListList, BuildListCard}.tsx`
- `buildListParts/{CreateBuildListPartForm, BuildListParts, BuildListPartListItem, BuildListPartList}.tsx`
- `cars/{CarList, CarListItem}.tsx`
- `parts/{ImageGallery, ImageGalleryManage, CreatePartForm, EditPartForm, AddToBuildListDialog, PartList, PartListItem, PartsFilterSidebar, PartsActiveFilterChips}.tsx`
- `profile/{SecuritySettings, SecuritySettingsDialog, TwoFactorAuthDialog, ConnectedAccountsSettings, PasskeySettings, ChangePasswordDialog}.tsx`
- `routes/{GuestRoute, ProtectedRoute, EmailVerifiedRoute}.tsx` (each just imports LoadingSpinner — trivial)
- `users/UserCard.tsx`
- `layout/globalHeader/Header.tsx` (just LoadingSpinner)
- `buttons/Button.tsx` (only imports LoadingSpinner; deletes when buttons/Button is deleted)

These ride alongside their owning page-tier task — e.g. `pages/Profile.tsx` sweep updates `components/profile/*.tsx`; `pages/buildLists/*.tsx` sweep updates `components/buildLists/*.tsx`.

### Where the natural seams are

- **Seam 1: ui primitive substrate** — T01 (Card), T02 (Alert), T03 (Pagination + Spinner). Land before any page sweep so swaps are mechanical.
- **Seam 2: page sweeps grouped by domain** — T04 admin, T05 authentication, T06 user-facing public/builder/parts/buildLists/account. Tier A trivials can fold into one of these or be a quick T-prefix task.
- **Seam 3: structural infra relocation** — T09 moves RouteGroupBoundary/ErrorBoundary/CookieConsentBanner/ChromeExtensionPromo/SubscriptionPromo/BetaBanner out of `common/` into proper homes. Requires updating App.tsx + main.tsx + tests.
- **Seam 4: legacy primitive deletion** — T10 deletes the now-unused `common/{Card,Alerts,LoadingSpinner,Pagination,Input,Dialog,DeleteConfirmationDialog,Button,CardInfoItem,ResponsiveTableWrapper,ParentNavigationLink,AddItemTile,DangerousActionDialog}.tsx` plus all of `buttons/`. Pure delete — no consumers should remain after T04–T08.
- **Seam 5: enforcement** — T11 grep CI guard (or eslint `no-restricted-imports` rule).
- **Seam 6: visual baseline refresh** — T12 final `--update-snapshots` sweep + verify gauntlet.

### What to build/prove first

1. **Audit `common/DangerousActionDialog.tsx` consumers** — determine if it's still used; may be replaceable by `ui/confirm-dialog.tsx` already.
2. **Build `ui/card.tsx`** — biggest blast radius (~30 importers); shadcn pattern is well-known so this is mostly mechanical.
3. **Build `ui/alert.tsx`** — second biggest (~30 importers); the wrapper-export pattern (`ErrorAlert`/`SuccessAlert`/`ConfirmationAlert` named exports keeping legacy call signature) is what makes the page sweep mechanical.
4. **Build `ui/pagination.tsx`** — non-trivial ellipsis logic to preserve.
5. **Decide spinner story** — either build `ui/spinner.tsx` or inline Loader2 (recommend the wrapper to keep page diffs small; the legacy `LoadingSpinner` API has 6 sizes × 3 colors × inline/text — most callers use the defaults).
6. **Then sweep pages by domain**, each task running its own type-check + vitest + e2e for the touched specs.

### How to verify the result

**Per-task verification:**
- `cd frontend && npm run type-check` exit 0
- `cd frontend && npm test -- --run <touched-files>` passes
- For pages with e2e specs: `cd frontend && npm run test:e2e -- <spec>` passes (refresh baseline if drift caused by ui/* substitution)
- `grep -r 'from.*components/(common|buttons)/' frontend/src/pages/<area>/` returns nothing for the swept area

**Slice-close verification (T11/T12):**
- `grep -r 'from.*components/common\|from.*components/buttons' frontend/src/pages/` returns 0 hits
- `grep -r 'from.*components/common\|from.*components/buttons' frontend/src/components/` returns 0 hits (or only allow-listed structural-infra survivors if relocation is partial)
- `cd frontend && npm run test:e2e` passes (35+ tests at 3 viewports)
- `cd frontend && npm test -- --run` passes (596+ tests as of S11 close)
- `cd frontend && npm run type-check` exit 0
- `cd frontend && npm run lint` produces ≤108 errors (MEM062 baseline) — no new errors introduced
- Manual UAT: walk every page in dev (per R017 "Manual UAT smoke pass documented per page"); doc lives in `S12-UAT.md`. Scope: visual sanity-check, focus-rings on Tab, Escape closes any dialogs.

## Pitfalls to Avoid

- **Don't try to retire structural infra by rewriting it.** RouteGroupBoundary/ErrorBoundary are working code with their own tests — the `common/` import path is what needs to die, not the file. Move them, update imports, done.
- **Don't reimplement SearchableSelect / CarModelMultiSelect / ImageUpload in shadcn during S12.** Behavior is non-trivial (create-new flow, S3 presigned-URL upload, multi-select chips). Relocate them out of `common/` and tackle visual restyle later. R017 only requires "no `components/common/` imports" — relocation satisfies that.
- **Don't expect one PR-sized diff.** 73 files × hundreds of LOC each = 4–6 commits at minimum. Plan for tier-grouped commits per task.
- **Don't skip baseline refresh.** MEM113/MEM115: every spec that screenshots a reskinned page will drift. `--update-snapshots` is the routine path — confirmed in S10/T05.
- **Don't start with the page sweep.** The new ui/* primitives must land first or every page sweep regresses on the design-system goal by inlining ad-hoc styles. Tasks T01–T03 strictly precede T04+.
- **Don't forget legacy palette retirement.** MEM072: legacy `--primary-*/--neutral-*/--accent-*` token blocks were left intact for additive coexistence "until S12 retires the old palette." When the last `common/Card` consumer dies, sweep through `tokens.css` and `index.css` and remove the legacy color blocks if no consumers remain. Verify with grep against the legacy token names before deleting.
- **Don't break MEM102 by sweeping AccountAlerts.tsx blindly.** The self-cancelling useEffect bug is still open; either fix it as part of the sweep or carry it forward as a known-issue ride-along.
- **Don't try to sweep all 73 files in one task.** Each tier (A/B/C/D/E) needs to be its own commit so reviewers can read the diff.

## Don't Hand-Roll

- **shadcn Card** — copy the canonical shadcn-ui Card pattern (CardHeader/CardTitle/CardDescription/CardContent/CardFooter). Don't invent a new card API just because legacy Card had `variant='glass'`.
- **shadcn Alert** — same. The named-export wrapper pattern (`export const ErrorAlert = (props) => <Alert variant='destructive'>{...}</Alert>`) is how to make page sweeps a 1-line import-rename instead of a hundred call-site changes.
- **shadcn Pagination** — port the official pattern; the ellipsis logic in legacy `Pagination.tsx` is custom but shadcn's Pagination Item/Link/Ellipsis primitives are a clean home for it.
- **lucide Loader2** — the substrate for any spinner; don't write your own SVG.

## Sources

- `.gsd/milestones/M002/M002-ROADMAP.md` — S12 boundary map (reads only S08/S09/S10/S11; produces "all ~17 remaining pages reskinned" + "lint rule or grep CI check" + "frontend/src/components/common/ removed or stubbed-as-deprecated").
- `.gsd/milestones/M002/M002-CONTEXT.md` — "shadcn-style copy-into-repo Radix primitives ... replaces hand-rolled `components/common/` over the course of M002."
- `.gsd/REQUIREMENTS.md` R017 — "All ~17 remaining pages migrated onto the new component library and tokens. Manual UAT smoke pass documented per page. No page imports from deprecated `components/common/`; enforcement via lint rule or grep check."
- `.gsd/REQUIREMENTS.md` R020 — "Tab order, focus indicators, escape handling on dialogs, and screen-reader-friendly labels validated on each redesigned page. Light pass."
- S08-SUMMARY (`.gsd/milestones/M002/slices/S08/S08-SUMMARY.md`) — primitive list shipped: button, input, select, tabs, combobox, dialog, dropdown-menu, sheet, toast.
- S09-SUMMARY — confirm-dialog primitive established; reskin scope discipline (interactive only).
- S10-SUMMARY (T05) — visual baseline drift after page reskin is expected; --update-snapshots is the routine.
- S11-SUMMARY — admin priority slice; reskin pattern locked in; AdminDashboard + ExtractionHealth still have legacy chrome (Card/PageHeader/SectionHeader/Alerts/LoadingSpinner) waiting for S12.
- MEM003, MEM006, MEM072, MEM107, MEM113, MEM115, MEM116, MEM119, MEM121 — design-system architecture, scope discipline, baseline-refresh expectation, formal-variants convention, admin sub-page idiom.
- MEM062 — frontend lint baseline (104 + drift to 108 in S11); 0-error-introduced is the pass bar, not 0-total.
- MEM102 — AccountAlerts self-cancelling useEffect bug, still open, flagged for S10/S12 reskin.
- `frontend/src/components/ui/*` — 10 primitives shipped (button, combobox, confirm-dialog, dialog, dropdown-menu, input, select, sheet, tabs, toast).
- `frontend/src/components/common/*` — 25 files, 2,883 LOC; subset is structural infra (~10 files) and the rest are visual primitives (~15 files).
- `frontend/src/components/buttons/*` — 5 files (ActionButton, SecondaryButton, StretchButton, Button, LinkButton); all retire to ui/Button.
- `frontend/src/App.tsx` — 7 legacy imports; route group / suspense fallback / shell promos all still on `common/`.
- `frontend/src/components/layout/{PageHeader,SectionHeader,Divider}.tsx` — already live outside `common/`; left untouched.
