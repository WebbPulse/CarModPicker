---
estimated_steps: 4
estimated_files: 30
skills_used: []
---

# T04: Sweep Tier C2 (builder + parts + buildLists pages + their inner components) onto ui/* primitives

The heaviest tier — 9 page files (one is 978 lines: ViewPart.tsx) plus ~20 inner components in buildLists/, buildListParts/, parts/, cars/. Bounded by what an executor can hold in one context, so the sweep is mechanical: every legacy primitive has a documented destination, no layout rewrites, no behavior changes. Pages partially migrated by S09 (ViewBuildlist) and S10 (PartsCatalog, PartsFilterSidebar, PartsActiveFilterChips, PartList, AddToBuildListDialog) only need the REMAINING legacy imports swept — Card, Alerts, LoadingSpinner, ImageWithPlaceholder, ResponsiveTableWrapper, Pagination, ParentNavigationLink — they already use the new buttons/dialogs.

Same swap rules as T02/T03. Specific notes: (a) DeleteConfirmationDialog → ui/confirm-dialog from S09 — use the parent-owned-state pattern, destructive variant, loadingLabel='Deleting...' preserved (see S09/T01 for the contract). (b) Pagination → ui/pagination from T01 — props are identical so it's a one-line import swap. (c) LinkButton (UserParts.tsx, PartsCatalog.tsx) → <Button asChild><Link to='...'>; if the legacy callsite used a stretch variant, add className='w-full'. (d) AddItemTile is a domain composite — at each callsite, update the import to its FUTURE relocated path '../buildLists/AddItemTile' (T05 performs the actual move). (e) ParentNavigationLink — at each of the 3 callsites (ViewBuildlist, ViewPart, ViewBuildLog), inline the <Link to={linkTo}>{linkText}</Link> JSX directly so we can delete the helper file in T05. (f) For forms (CreatePartForm, EditPartForm, CreateBuildListPartForm, EditBuildListForm, CreateBuildListForm) that compose SearchableSelect / CarModelMultiSelect / ImageUpload / ImageWithPlaceholder from common/, update the import paths to the FUTURE relocated paths: '../forms/SearchableSelect', '../forms/ImageUpload', '../images/ImageWithPlaceholder', '../cars/CarModelMultiSelect'. T05 performs the actual file moves; T04 leaves the imports pointing at the future paths so the diff in T05 is a pure file move + zero importer updates. Type-check WILL FAIL at the end of T04 because those relocated paths don't exist yet — this is expected and resolved by T05. (g) VehicleFilterSection / VehicleFilterChips (used by BuildListsCatalog, PartsFilterSidebar, PartsActiveFilterChips) — same: update imports to '../filters/VehicleFilterSection' and '../filters/VehicleFilterChips'; T05 moves the files. (h) ResponsiveTableWrapper (PartList, BuildListPartList) — update import to '../tables/ResponsiveTableWrapper'; T05 moves it. (i) CardInfoItem callsites in ViewBuildlist, ViewCar, ViewPart — update import to '../../components/ui/card-info-item' (T05 folds CardInfoItem into ui/).

The pattern: after T04, every file in the list has zero common/ or buttons/ imports — but several imports point at paths that don't exist until T05 lands. T04 is correct when the import statements are right; T05 makes them resolve.

Must-haves: every file in the file list no longer imports from components/common/Card / Alerts / LoadingSpinner / Pagination / Input / Dialog / DeleteConfirmationDialog / Button / DangerousActionDialog / ParentNavigationLink / ResponsiveTableWrapper / CardInfoItem / AddItemTile, or from components/buttons/*; imports of relocated helpers point at the future paths; behavior preserved.

## Inputs

- ``frontend/src/components/ui/card.tsx` — destination for Card swap.`
- ``frontend/src/components/ui/alert.tsx` — destination for Alerts swap.`
- ``frontend/src/components/ui/spinner.tsx` — destination for LoadingSpinner swap.`
- ``frontend/src/components/ui/pagination.tsx` — destination for Pagination swap.`
- ``frontend/src/components/ui/input.tsx` — destination for Input swap.`
- ``frontend/src/components/ui/button.tsx` — destination for button-family swaps.`
- ``frontend/src/components/ui/dialog.tsx` — destination for Dialog swap.`
- ``frontend/src/components/ui/confirm-dialog.tsx` — destination for DeleteConfirmationDialog swap (S09 contract).`
- ``frontend/src/pages/builder/ViewPart.tsx` — 978 LOC, ActionButton + Alerts + Card + CardInfoItem + DeleteConfirmationDialog + Dialog + LoadingSpinner + ParentNavigationLink.`
- ``frontend/src/pages/builder/ViewCar.tsx` — 303 LOC, Alerts + Card + CardInfoItem + Dialog + Input + LoadingSpinner.`
- ``frontend/src/pages/builder/Builder.tsx` — 176 LOC, AddItemTile + Alerts + Dialog + LoadingSpinner + Pagination.`
- ``frontend/src/pages/builder/ViewBuildlist.tsx` — partially migrated by S09; finish off Card + CardInfoItem + ParentNavigationLink + LoadingSpinner.`
- ``frontend/src/pages/buildLists/BuildListsCatalog.tsx` — 660 LOC, Alerts + Card + Input + LoadingSpinner + Pagination + VehicleFilterChips + VehicleFilterSection.`
- ``frontend/src/pages/buildLists/ViewBuildLog.tsx` — 664 LOC, ActionButton + Alerts + Card + DeleteConfirmationDialog + Dialog + ImageUpload + LoadingSpinner + Pagination + ParentNavigationLink.`
- ``frontend/src/pages/parts/PartsCatalog.tsx` — partially migrated by S10; finish off LinkButton + Pagination.`
- ``frontend/src/pages/parts/UserParts.tsx` — LinkButton + Alerts + Card + DeleteConfirmationDialog + Input + Pagination.`
- ``frontend/src/pages/parts/EditPart.tsx` — SecondaryButton + Alerts + Card + LoadingSpinner.`
- ``frontend/src/components/parts/PartList.tsx` — partially migrated by S10; finish off Card + Alerts + LoadingSpinner + ResponsiveTableWrapper + ImageWithPlaceholder.`
- ``frontend/src/components/parts/PartListItem.tsx` — Card + ImageWithPlaceholder.`
- ``frontend/src/components/parts/PartsFilterSidebar.tsx` — partially migrated by S10; finish off Card + VehicleFilterSection import path.`
- ``frontend/src/components/parts/PartsActiveFilterChips.tsx` — partially migrated by S10; finish off filterChipClass import (move with VehicleFilterChips).`
- ``frontend/src/components/parts/AddToBuildListDialog.tsx` — partially migrated by S10; finish off Card + Alerts + LoadingSpinner + ImageWithPlaceholder.`
- ``frontend/src/components/parts/CreatePartForm.tsx` — ActionButton + SecondaryButton + Alerts + ImageUpload + Input + LoadingSpinner + CarModelMultiSelect + SearchableSelect.`
- ``frontend/src/components/parts/EditPartForm.tsx` — same set.`
- ``frontend/src/components/parts/ImageGallery.tsx` — ImageWithPlaceholder.`
- ``frontend/src/components/parts/ImageGalleryManage.tsx` — Alerts + DeleteConfirmationDialog + ImageWithPlaceholder.`
- ``frontend/src/components/buildListParts/BuildListPartList.tsx` — ResponsiveTableWrapper + ActionButton + SecondaryButton + Card + ImageWithPlaceholder + LoadingSpinner.`
- ``frontend/src/components/buildListParts/BuildListPartListItem.tsx` — ActionButton + SecondaryButton + Card.`
- ``frontend/src/components/buildListParts/BuildListParts.tsx` — partially migrated by S09; finish off Alerts + Card.`
- ``frontend/src/components/buildListParts/CreateBuildListPartForm.tsx` — ActionButton + SecondaryButton + Alerts + CarModelMultiSelect + ImageUpload + ImageWithPlaceholder + Input + LoadingSpinner + SearchableSelect.`
- ``frontend/src/components/buildLists/CreateBuildListForm.tsx` — Alerts + Input + LoadingSpinner.`
- ``frontend/src/components/buildLists/EditBuildListForm.tsx` — Alerts + Input + LoadingSpinner.`
- ``frontend/src/components/buildLists/BuildListItem.tsx` — Card.`
- ``frontend/src/components/buildLists/BuildListList.tsx` — Alerts + Card + LoadingSpinner.`
- ``frontend/src/components/buildLists/BuildListCard.tsx` — Card.`
- ``frontend/src/components/buildLists/BuildListCatalogList.tsx` — Alerts + Card + LoadingSpinner.`
- ``frontend/src/components/cars/CarList.tsx` — AddItemTile + Alerts + LoadingSpinner.`
- ``frontend/src/components/cars/CarListItem.tsx` — Card + CardInfoItem.`
- ``frontend/src/pages/builder/ViewBuildlist.tsx` — S09 pattern reference for ui/Dialog parent-owned state.`
- ``frontend/src/components/common/SearchableSelect.tsx` — relocates in T05; T04 updates importer paths only.`
- ``frontend/src/components/common/CarModelMultiSelect.tsx` — relocates in T05.`
- ``frontend/src/components/common/ImageUpload.tsx` — relocates in T05.`
- ``frontend/src/components/common/ImageWithPlaceholder.tsx` — relocates in T05.`
- ``frontend/src/components/common/VehicleFilterSection.tsx` — relocates in T05.`
- ``frontend/src/components/common/VehicleFilterChips.tsx` — relocates in T05.`
- ``frontend/src/components/common/ResponsiveTableWrapper.tsx` — relocates in T05.`
- ``frontend/src/components/common/CardInfoItem.tsx` — relocates in T05 (folds into ui/).`
- ``frontend/src/components/common/AddItemTile.tsx` — relocates in T05.`
- ``frontend/src/components/common/ParentNavigationLink.tsx` — DELETED in T05; T04 inlines its 3 callsites.`

## Expected Output

- ``frontend/src/pages/builder/ViewPart.tsx` — modified, no legacy primitive imports; helper imports point at future relocated paths.`
- ``frontend/src/pages/builder/ViewCar.tsx` — modified.`
- ``frontend/src/pages/builder/Builder.tsx` — modified.`
- ``frontend/src/pages/builder/ViewBuildlist.tsx` — modified.`
- ``frontend/src/pages/buildLists/BuildListsCatalog.tsx` — modified.`
- ``frontend/src/pages/buildLists/ViewBuildLog.tsx` — modified.`
- ``frontend/src/pages/parts/PartsCatalog.tsx` — modified.`
- ``frontend/src/pages/parts/UserParts.tsx` — modified.`
- ``frontend/src/pages/parts/EditPart.tsx` — modified.`
- ``frontend/src/components/parts/PartList.tsx` — modified.`
- ``frontend/src/components/parts/PartListItem.tsx` — modified.`
- ``frontend/src/components/parts/PartsFilterSidebar.tsx` — modified.`
- ``frontend/src/components/parts/PartsActiveFilterChips.tsx` — modified.`
- ``frontend/src/components/parts/AddToBuildListDialog.tsx` — modified.`
- ``frontend/src/components/parts/CreatePartForm.tsx` — modified.`
- ``frontend/src/components/parts/EditPartForm.tsx` — modified.`
- ``frontend/src/components/parts/ImageGallery.tsx` — modified.`
- ``frontend/src/components/parts/ImageGalleryManage.tsx` — modified.`
- ``frontend/src/components/buildListParts/BuildListPartList.tsx` — modified.`
- ``frontend/src/components/buildListParts/BuildListPartListItem.tsx` — modified.`
- ``frontend/src/components/buildListParts/BuildListParts.tsx` — modified.`
- ``frontend/src/components/buildListParts/CreateBuildListPartForm.tsx` — modified.`
- ``frontend/src/components/buildLists/CreateBuildListForm.tsx` — modified.`
- ``frontend/src/components/buildLists/EditBuildListForm.tsx` — modified.`
- ``frontend/src/components/buildLists/BuildListItem.tsx` — modified.`
- ``frontend/src/components/buildLists/BuildListList.tsx` — modified.`
- ``frontend/src/components/buildLists/BuildListCard.tsx` — modified.`
- ``frontend/src/components/buildLists/BuildListCatalogList.tsx` — modified.`
- ``frontend/src/components/cars/CarList.tsx` — modified.`
- ``frontend/src/components/cars/CarListItem.tsx` — modified.`

## Verification

cd frontend && ! grep -lE "from '(\\.\\./)+(common|buttons)/(Card|Alerts|LoadingSpinner|Pagination|Input|Dialog|DeleteConfirmationDialog|Button|DangerousActionDialog|ParentNavigationLink|ResponsiveTableWrapper|CardInfoItem|AddItemTile|ActionButton|SecondaryButton|StretchButton|LinkButton)'" src/pages/builder/*.tsx src/pages/buildLists/*.tsx src/pages/parts/*.tsx src/components/parts/*.tsx src/components/buildListParts/*.tsx src/components/buildLists/*.tsx src/components/cars/*.tsx
