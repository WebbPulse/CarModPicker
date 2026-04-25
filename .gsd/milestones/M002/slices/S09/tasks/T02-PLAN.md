---
estimated_steps: 6
estimated_files: 1
skills_used: []
---

# T02: Reskin ViewBuildlist.tsx page chrome and top-level dialogs onto ui/* primitives

Migrate frontend/src/pages/builder/ViewBuildlist.tsx from common/Dialog + DeleteConfirmationDialog + ActionButton to ui/dialog + ui/confirm-dialog (T01) + ui/button. Preserve every existing behavior: build-list info card, no-car-assigned warning, View Build Log button, Copy Build List button (with isCopyingBuildList loading state via Button loading prop), Edit/Delete affordances gated on canManage, EditBuildListForm in a ui/Dialog with title `Edit ${buildList.name}`, ConfirmDialog for delete, ui/Dialog for Create Build List Part with maxWidth equivalent to the existing 4xl (use sm:max-w-[64rem]).

Do NOT modify EditBuildListForm internals — it consumes common/Card and common/Input for the make/model/generation grids; those ride the S12 ripple. Only swap the OUTER dialog wrapper.

Keep PageHeader / SectionHeader / Card (from layout/ and common/) as-is for now — they are visual chrome and S12 will sweep them. The slice focus is replacing INTERACTIVE primitives (buttons, dialogs, dialog-confirm).

Add data-testid hooks: 'build-list-edit-trigger', 'build-list-delete-trigger', 'build-list-add-part-trigger', 'build-list-edit-dialog', 'build-list-delete-confirm', 'build-list-add-part-dialog'. T04's e2e spec targets these.

Failure modes: handleConfirmDelete navigates after success; if the parent forgets to close the dialog while processing, ConfirmDialog must keep the spinner visible — covered by ConfirmDialog from T01 (loading prop disables the button but does not auto-close). Negative tests: clicking Cancel while processing should be no-op (button disabled). Load profile: identical to current; no new fetches.

Threat surface: existing build-list ownership check (canManage = currentUser?.id === buildList.user_id) governs render of mutating triggers. Migration must NOT loosen the gate — verify by grep.

## Inputs

- ``frontend/src/pages/builder/ViewBuildlist.tsx``
- ``frontend/src/pages/builder/ViewBuildlist.test.tsx``
- ``frontend/src/components/ui/button.tsx``
- ``frontend/src/components/ui/dialog.tsx``
- ``frontend/src/components/ui/confirm-dialog.tsx``
- ``frontend/src/components/buildLists/EditBuildListForm.tsx``
- ``frontend/src/components/buildListParts/CreateBuildListPartForm.tsx``

## Expected Output

- ``frontend/src/pages/builder/ViewBuildlist.tsx``

## Verification

cd frontend && npm run type-check && npm test -- ViewBuildlist && grep -c "from '../../components/common/Dialog'\|from '../../components/common/DeleteConfirmationDialog'\|from '../../components/buttons/ActionButton'" src/pages/builder/ViewBuildlist.tsx | grep -q '^0$'

## Observability Impact

data-testid hooks above are the only public surfaces e2e targets. Each ui/Dialog uses Radix's built-in data-state attribute for open/closed transitions, which Playwright's toBeVisible/toBeHidden assertions read.
