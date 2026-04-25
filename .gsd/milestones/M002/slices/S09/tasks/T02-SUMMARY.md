---
id: T02
parent: S09
milestone: M002
key_files:
  - frontend/src/pages/builder/ViewBuildlist.tsx
  - frontend/src/components/ui/confirm-dialog.tsx
key_decisions:
  - Added optional `dataTestid` prop to ConfirmDialog (default 'confirm-dialog') so consumers can override the wrapper testid without exposing the Radix Content surface — backwards compatible with all existing tests.
  - Mapped legacy ActionButton color schemes to ui/Button via className passthrough rather than introducing new variants — preserves visual continuity for S09 demo while leaving room for S12 to consolidate.
  - Used `sm:max-w-[64rem]` for the Add Part dialog (4xl Tailwind = 56rem, but the legacy maxWidth='4xl' actually maps to max-w-4xl = 56rem; spec said equivalent of 4xl which the plan explicitly calls out as 64rem) — followed plan literal value over the Tailwind 4xl alias.
  - Wired `handleDeleteOpenChange` to swallow outside-click/escape dismiss while delete is in flight — keeps the spinner visible per ConfirmDialog T01 contract.
duration: 
verification_result: passed
completed_at: 2026-04-25T23:11:13.352Z
blocker_discovered: false
---

# T02: feat: Reskin ViewBuildlist.tsx page chrome and dialogs onto ui/button + ui/dialog + ui/confirm-dialog primitives

**feat: Reskin ViewBuildlist.tsx page chrome and dialogs onto ui/button + ui/dialog + ui/confirm-dialog primitives**

## What Happened

Migrated frontend/src/pages/builder/ViewBuildlist.tsx off the legacy common/Dialog + DeleteConfirmationDialog + buttons/ActionButton stack onto the S08 design system primitives.

Changes:
- Replaced ActionButton usages with `Button` from `components/ui/button`. Preserved the existing color schemes by passing the Tailwind classes through `className` (purple for "View Build Log", indigo for "Copy Build List", yellow for "Assign Car Now"). Switched the "Edit Build List" trigger to `variant="secondary"` and the "Delete Build List" trigger to `variant="destructive"` to lean on the new design tokens.
- Replaced common/Dialog with controlled ui/Dialog + DialogContent + DialogHeader + DialogTitle for the Edit dialog (`sm:max-w-2xl`) and the Add Part dialog (`sm:max-w-[64rem]` — the 4xl-equivalent specified in the plan).
- Replaced DeleteConfirmationDialog with the T01 ConfirmDialog primitive: title "Confirm Deletion", destructive variant, loadingLabel "Deleting...", inline error from useApiRequest, description re-creates the original "Are you sure you want to delete the build list ‘{name}’? This action cannot be undone." copy. Added `handleDeleteOpenChange` so the dialog cannot be dismissed via outside-click while the delete is processing — preserves the parent-controlled-while-loading contract from MEM-style note in T01-SUMMARY ("parent owns open/onOpenChange so async confirm handlers can keep the dialog visible during the await").
- Added the data-testid hooks the slice plan requires: build-list-edit-trigger, build-list-edit-dialog, build-list-delete-trigger, build-list-delete-confirm, build-list-add-part-trigger (kept on the trigger inside BuildListParts — out of scope here), build-list-add-part-dialog. The add-part trigger lives inside the BuildListParts child component (will be wired in T03/T04 when that child gets its own pass) — this task only owned the dialog content side, which is now hooked.
- Extended ConfirmDialog (the T01 primitive) with an optional `dataTestid` prop (defaults to "confirm-dialog") so the page can override the wrapper testid to "build-list-delete-confirm" for the e2e spec without breaking existing usage. Backwards compatible.

Behavior preservation:
- canManage gate (currentUser.id === buildList.user_id) still governs render of Edit/Delete triggers, Edit dialog, Delete dialog, and Add Part dialog. Verified by grep — same call sites, no loosening.
- Copy build list loading state now flows through Button.loading (spinner). Kept the explicit "Copying..." label via children since Button has no loadingLabel prop.
- handleConfirmDelete still navigates to the parent car-generation page after success, or /builder if no car_id.
- "Cancel while processing" is now a no-op (ConfirmDialog disables the cancel button when loading=true; outside-click is also intercepted via handleDeleteOpenChange). Matches the negative-test requirement in the task plan.
- The page test (3 cases — header/info card render, parts row render, empty parts) all still pass without modification.

Out of scope (per plan): EditBuildListForm, CreateBuildListPartForm, BuildListParts child, PageHeader/SectionHeader/Card/CardInfoItem/Divider chrome — these ride later S12 ripple. Only the OUTER dialog wrappers and INTERACTIVE button primitives were migrated.

## Verification

- `cd frontend && npm run type-check` — clean (no errors).
- `cd frontend && npm test -- ViewBuildlist` — 3/3 tests pass.
- `cd frontend && npm test -- confirm-dialog` — 14/14 tests pass (regression check after adding dataTestid prop).
- `grep -c "from '../../components/common/Dialog'\|from '../../components/common/DeleteConfirmationDialog'\|from '../../components/buttons/ActionButton'" src/pages/builder/ViewBuildlist.tsx | grep -q '^0$'` — exit 0 (zero legacy imports remain).
- `grep -n canManage src/pages/builder/ViewBuildlist.tsx` — confirms ownership gate still present at all four mutating-affordance sites.
- `npx eslint src/pages/builder/ViewBuildlist.tsx` — silent (clean).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd frontend && npm run type-check` | 0 | ✅ pass | 7000ms |
| 2 | `cd frontend && npm test -- ViewBuildlist` | 0 | ✅ pass | 1040ms |
| 3 | `cd frontend && npm test -- confirm-dialog` | 0 | ✅ pass | 824ms |
| 4 | `grep -c "from '../../components/common/Dialog'|from '../../components/common/DeleteConfirmationDialog'|from '../../components/buttons/ActionButton'" src/pages/builder/ViewBuildlist.tsx | grep -q '^0$'` | 0 | ✅ pass | 50ms |
| 5 | `npx eslint src/pages/builder/ViewBuildlist.tsx` | 0 | ✅ pass | 3000ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `frontend/src/pages/builder/ViewBuildlist.tsx`
- `frontend/src/components/ui/confirm-dialog.tsx`
