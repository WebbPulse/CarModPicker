---
id: T04
parent: S12
milestone: M002
key_files:
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
  - frontend/src/components/forms/SearchableSelect.tsx
  - frontend/src/components/cars/CarModelMultiSelect.tsx
  - frontend/src/components/filters/VehicleFilterSection.tsx
  - frontend/src/components/filters/VehicleFilterChips.tsx
  - frontend/src/components/tables/ResponsiveTableWrapper.tsx
  - frontend/src/components/ui/card-info-item.tsx
key_decisions:
  - Used MEM124 re-export shim pattern for 6 of 7 future-relocated helpers (forms/SearchableSelect, cars/CarModelMultiSelect, filters/VehicleFilterSection, filters/VehicleFilterChips, tables/ResponsiveTableWrapper, ui/card-info-item) so type-check resolves their import paths during T04. Deliberately skipped the shim for buildLists/AddItemTile because the verify grep regex enumerates 'AddItemTile' as a banned legacy primitive name — a shim at components/buildLists/AddItemTile re-exporting from common/AddItemTile trips the grep (file lives in a scanned dir). Captured as MEM126.
  - Inlined ParentNavigationLink at 4 callsites (ViewBuildlist Associated Car + Owner, ViewBuildLog ← Back link, ViewPart Created by) using Link with `text-indigo-400 hover:text-indigo-300 underline` to match the legacy helper's exact styling. Lets T05 delete the helper file outright.
  - Removed legacy `interactive` prop from ui/Card swaps in CreateBuildListForm and EditBuildListForm; replaced with className equivalent `cursor-pointer hover:scale-105 hover:border-indigo-500 border-2 border-transparent transition-colors`. Captured as MEM125.
  - Refactored PartsFilterSidebar Card swap to wrap children in an inner div carrying the legacy `contentClassName` value, since ui/Card has no contentClassName prop. Set Card to `p-0` to strip the default md padding so the inner div controls layout.
duration: 
verification_result: passed
completed_at: 2026-04-26T03:00:26.186Z
blocker_discovered: false
---

# T04: Migrated Tier C2 (9 builder/parts/buildLists pages + 21 inner components in parts/buildListParts/buildLists/cars) onto ui/* primitives — zero legacy common/ or buttons/ imports remain in scope

**Migrated Tier C2 (9 builder/parts/buildLists pages + 21 inner components in parts/buildListParts/buildLists/cars) onto ui/* primitives — zero legacy common/ or buttons/ imports remain in scope**

## What Happened

Swept the heaviest tier of the S12 ripple — 30 files spanning the builder/parts/buildLists page surface plus all their domain-composite inner components — off legacy common/ + buttons/ primitives onto the S08 ui/* design system.

**Page sweep (9 files):** ViewBuildlist (S09 partial → finished off Card/CardInfoItem/ParentNavigationLink/LoadingSpinner/ErrorAlert), ViewCar, Builder, ViewPart (978 LOC, full primitive set), BuildListsCatalog (660 LOC), ViewBuildLog (664 LOC, 2 dialogs + delete confirm), PartsCatalog (S10 partial → LinkButton + Pagination), UserParts (LinkButton + DeleteConfirmationDialog), EditPart (4× SecondaryButton).

**Inner-component sweep (21 files):** parts/ → PartList, PartListItem, PartsFilterSidebar, PartsActiveFilterChips, AddToBuildListDialog, CreatePartForm, EditPartForm, ImageGallery, ImageGalleryManage. buildListParts/ → BuildListPartList, BuildListPartListItem, BuildListParts, CreateBuildListPartForm. buildLists/ → CreateBuildListForm, EditBuildListForm, BuildListItem, BuildListList, BuildListCard, BuildListCatalogList. cars/ → CarList, CarListItem.

**Swap rules applied uniformly per S12 plan + MEM116/MEM124:**
- Card/Alerts/LoadingSpinner/Pagination/Input/Dialog → ui/* primitive equivalents (formal variants over bespoke className overrides per MEM116; preserved every data-testid + useEffect ordering + cancellation flag).
- DeleteConfirmationDialog → ui/ConfirmDialog with parent-owned-state pattern, destructive variant, loadingLabel='Deleting...', warning rendered via the warning prop (preserved buildListCount tally for ViewPart and UserParts).
- legacy Dialog (isOpen/onClose/title API) → Radix-style Dialog/DialogContent/DialogHeader/DialogTitle with sm:max-w-* sizing.
- ActionButton → Button (default), SecondaryButton → Button variant='secondary', ButtonStretch → Button className='w-full', LinkButton → Button asChild + Link.
- legacy Input with label/leftIcon/rightIcon props → ui/Input wrapped in <div> + sibling <label htmlFor> per the swap rule.
- ParentNavigationLink → inlined `<Link to={linkTo} className="text-indigo-400 hover:text-indigo-300 underline">{linkText}</Link>` at the 3 callsites (ViewBuildlist x2, ViewBuildLog x1, ViewPart x1) so T05 can delete the helper.

**Future-path imports (per plan + MEM124):** SearchableSelect/CarModelMultiSelect/ImageUpload/ImageWithPlaceholder/VehicleFilterSection/VehicleFilterChips/ResponsiveTableWrapper/CardInfoItem/AddItemTile importers updated to point at the future relocated paths (`forms/`, `cars/`, `images/`, `filters/`, `tables/`, `ui/card-info-item`). Created re-export shims at those paths so type-check resolves at T04 — except for `buildLists/AddItemTile` (see Known issues below).

**PartsFilterSidebar Card swap:** legacy `contentClassName` prop on Card had no equivalent on ui/Card; refactored by wrapping children in an inner `<div className="lg:absolute lg:inset-0 flex flex-col">` and stripping `padding-md` via `p-0` className. Preserves the sticky-sidebar layout.

Verification grep (the must-pass slice gate) returns zero hits across all 30 files in scope.

## Verification

Ran the canonical T04 verify grep: `! grep -lE "from '(\\.\\./)+(common|buttons)/(Card|Alerts|LoadingSpinner|Pagination|Input|Dialog|DeleteConfirmationDialog|Button|DangerousActionDialog|ParentNavigationLink|ResponsiveTableWrapper|CardInfoItem|AddItemTile|ActionButton|SecondaryButton|StretchButton|LinkButton)'" src/pages/builder/*.tsx src/pages/buildLists/*.tsx src/pages/parts/*.tsx src/components/parts/*.tsx src/components/buildListParts/*.tsx src/components/buildLists/*.tsx src/components/cars/*.tsx` → exit 0 (zero hits, inverted exit 0 ⇒ pass). Also ran `npm run type-check` to confirm the failure shape matches the plan's expected outcome: 3 errors, all `Cannot find module ... AddItemTile` from Builder.tsx, BuildListList.tsx, CarList.tsx — exactly the importers waiting for T05's file move. No other type errors. Slice-level verification (e2e + visual baseline refresh) is T06's responsibility.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `! grep -lE "from '(\\.\\./)+(common|buttons)/(Card|Alerts|LoadingSpinner|Pagination|Input|Dialog|DeleteConfirmationDialog|Button|DangerousActionDialog|ParentNavigationLink|ResponsiveTableWrapper|CardInfoItem|AddItemTile|ActionButton|SecondaryButton|StretchButton|LinkButton)'" src/pages/builder/*.tsx src/pages/buildLists/*.tsx src/pages/parts/*.tsx src/components/parts/*.tsx src/components/buildListParts/*.tsx src/components/buildLists/*.tsx src/components/cars/*.tsx` | 0 | ✅ pass | 50ms |
| 2 | `npm run type-check` | 1 | ✅ pass (expected 3 AddItemTile module-not-found errors, resolved by T05 file move) | 12000ms |

## Deviations

None.

## Known Issues

npm run type-check exits 1 with exactly 3 expected errors: `Cannot find module './AddItemTile'` from BuildListList.tsx, `Cannot find module '../buildLists/AddItemTile'` from CarList.tsx and Builder.tsx. Per the slice plan: "Type-check WILL FAIL at the end of T04 because those relocated paths don't exist yet — this is expected and resolved by T05." T05's wholesale move of components/common/AddItemTile.tsx → components/buildLists/AddItemTile.tsx will resolve all three. No other deviations from the plan.

## Files Created/Modified

- `frontend/src/pages/builder/ViewPart.tsx`
- `frontend/src/pages/builder/ViewCar.tsx`
- `frontend/src/pages/builder/Builder.tsx`
- `frontend/src/pages/builder/ViewBuildlist.tsx`
- `frontend/src/pages/buildLists/BuildListsCatalog.tsx`
- `frontend/src/pages/buildLists/ViewBuildLog.tsx`
- `frontend/src/pages/parts/PartsCatalog.tsx`
- `frontend/src/pages/parts/UserParts.tsx`
- `frontend/src/pages/parts/EditPart.tsx`
- `frontend/src/components/parts/PartList.tsx`
- `frontend/src/components/parts/PartListItem.tsx`
- `frontend/src/components/parts/PartsFilterSidebar.tsx`
- `frontend/src/components/parts/PartsActiveFilterChips.tsx`
- `frontend/src/components/parts/AddToBuildListDialog.tsx`
- `frontend/src/components/parts/CreatePartForm.tsx`
- `frontend/src/components/parts/EditPartForm.tsx`
- `frontend/src/components/parts/ImageGallery.tsx`
- `frontend/src/components/parts/ImageGalleryManage.tsx`
- `frontend/src/components/buildListParts/BuildListPartList.tsx`
- `frontend/src/components/buildListParts/BuildListPartListItem.tsx`
- `frontend/src/components/buildListParts/BuildListParts.tsx`
- `frontend/src/components/buildListParts/CreateBuildListPartForm.tsx`
- `frontend/src/components/buildLists/CreateBuildListForm.tsx`
- `frontend/src/components/buildLists/EditBuildListForm.tsx`
- `frontend/src/components/buildLists/BuildListItem.tsx`
- `frontend/src/components/buildLists/BuildListList.tsx`
- `frontend/src/components/buildLists/BuildListCard.tsx`
- `frontend/src/components/buildLists/BuildListCatalogList.tsx`
- `frontend/src/components/cars/CarList.tsx`
- `frontend/src/components/cars/CarListItem.tsx`
- `frontend/src/components/forms/SearchableSelect.tsx`
- `frontend/src/components/cars/CarModelMultiSelect.tsx`
- `frontend/src/components/filters/VehicleFilterSection.tsx`
- `frontend/src/components/filters/VehicleFilterChips.tsx`
- `frontend/src/components/tables/ResponsiveTableWrapper.tsx`
- `frontend/src/components/ui/card-info-item.tsx`
