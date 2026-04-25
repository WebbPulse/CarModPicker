---
id: T03
parent: S09
milestone: M002
key_files:
  - frontend/src/components/buildListParts/BuildListParts.tsx
  - frontend/src/components/buildListParts/EditBuildListPartForm.tsx
key_decisions:
  - Phase-row Delete affordance uses ui/Button variant="ghost" with text-red-400 className override rather than variant="destructive" — preserves the legacy lightweight visual (a red text link, not a solid destructive button) and keeps the confirm-step (ConfirmDialog destructive variant) as the single source of truth for the destructive action. Reversible at S12 if design tightens.
  - Add-phase Button uses both `disabled` and `loading` props together — disabled gates user interaction (preserving the trim+isAddingPhase guard from the legacy code), loading drives the spinner. Button.tsx OR's them together internally so this is intentional belt-and-braces.
  - EditBuildListPartForm's onOpenChange refuses to close while loading — matches ConfirmDialog's contract from T01 and protects the parent's onClose contract under in-flight saves.
duration: 
verification_result: passed
completed_at: 2026-04-25T23:14:49.199Z
blocker_discovered: false
---

# T03: feat: Reskin BuildListParts.tsx and EditBuildListPartForm.tsx onto ui/tabs + ui/button + ui/input + ui/dialog + ui/confirm-dialog

**feat: Reskin BuildListParts.tsx and EditBuildListPartForm.tsx onto ui/tabs + ui/button + ui/input + ui/dialog + ui/confirm-dialog**

## What Happened

Migrated BuildListParts.tsx and EditBuildListPartForm.tsx off legacy primitives (common/Dialog, common/DeleteConfirmationDialog, buttons/ActionButton, buttons/SecondaryButton, raw <button>/<input>) onto components/ui/* primitives.

BuildListParts.tsx changes:
- Replaced the two raw <button> view-mode toggles with ui/Tabs (TabsList + TabsTrigger value="category"/"phase"), wired through onValueChange to setViewMode. Kept the (viewMode, setViewMode) state hook signature unchanged so BuildListPartList still receives viewMode.
- Replaced both Add Part ActionButton instances (error path + happy path) with ui/Button.
- Replaced the new-phase row with ui/Input + ui/Button (default variant, loading={isAddingPhase}). Preserved the existing `disabled={!newPhaseName.trim() || isAddingPhase}` double-click guard.
- Replaced per-row phase-edit controls: editingPhaseName Input is now ui/Input; Cancel/Save are ui/Button (variant="secondary" for Cancel, default for Save). Edit/Delete row affordances are ui/Button (variant="secondary" for Edit, variant="ghost" with red text classes for Delete to preserve the destructive cue without claiming the destructive variant — the actual destructive color lives on the ConfirmDialog confirm button).
- Replaced both DeleteConfirmationDialog instances (delete-phase + delete-part) with ConfirmDialog from T01. Each uses variant="destructive", a description summarizing what is being removed, and dataTestid hooks ('build-list-phase-delete-confirm', 'build-list-part-delete-confirm'). Delete-part wires loading={isDeleting} + loadingLabel="Removing..." so the spinner stays visible during the await; ConfirmDialog's onOpenChange handlers refuse to close while loading.
- Added required testids: 'build-list-view-mode-tabs' (on TabsList), 'build-list-add-phase-input', 'build-list-add-phase-submit', 'build-list-phase-row-${phase.id}'.
- Car-mismatch warning banner left as-is (presentational chrome).
- The error-state branch's Add Part affordance is now ui/Button as well.

EditBuildListPartForm.tsx changes:
- Swapped the common/Dialog wrapper for ui/Dialog with DialogContent + DialogHeader + DialogTitle. Preserved title="Edit Part" and the isOpen/onClose contract (handleOpenChange refuses to close while loading and resets local state on user-initiated close to match the legacy handleClose behavior).
- Cancel + Save buttons now ui/Button (variant="secondary" for Cancel, default for Save with loading prop wired to the loading state).
- Inner form fields (quantity input, phase select, notes textarea) intentionally left on legacy bare-input styling per the slice plan — they ride S12 along with common/Input.
- Added testids: 'build-list-part-edit-dialog' on DialogContent, 'build-list-part-edit-submit' on the Save button.

Threat surface preserved: phase mutations still gated on canManageParts (the only render path for the entire phase-management Card). New-phase input is sent verbatim to the backend; backend already validates length/trim and the rendered output is text in <span>, not dangerouslySetInnerHTML — no new XSS surface introduced.

Failure modes preserved: optimistic purchased-toggle (handleTogglePurchased) is unchanged — it still reverts local state on error without a dialog. Phase add/edit/delete error paths still surface phaseError via the existing red text region. Delete-part path still surfaces deleteError inline via ConfirmDialog's error prop.

Did NOT touch BuildListPartList or BuildListPartListItem — they're row presentation that S12 sweeps and they do not gate the slice goal.

## Verification

cd frontend && npm run type-check exits 0. npm test -- ViewBuildlist runs 3/3 green (BuildListParts has no dedicated unit-test file; it is exercised through ViewBuildlist's render tree which includes the parts section, empty-parts message, and at-least-one-part-row paths). npm test -- confirm-dialog runs 14/14 green (T01 primitive uncompromised). The legacy-import sweep `grep -c "from '../common/Dialog'|from '../common/DeleteConfirmationDialog'|from '../buttons/ActionButton'|from '../buttons/SecondaryButton'" src/components/buildListParts/BuildListParts.tsx src/components/buildListParts/EditBuildListPartForm.tsx | awk -F: '{ sum += $2 } END { exit (sum > 0) }'` exits 0 — both files report 0 legacy imports.

Slice-level verification status (intermediate task; full sweep happens in T05):
- ui/dialog onOpenChange transitions: PASS via ConfirmDialog (delete-phase + delete-part) and Edit Part Dialog wiring; both refuse to close while loading.
- data-testid hooks: ADDED ('build-list-view-mode-tabs', 'build-list-add-phase-input', 'build-list-add-phase-submit', 'build-list-phase-row-${id}', 'build-list-phase-delete-confirm', 'build-list-part-delete-confirm', 'build-list-part-edit-dialog', 'build-list-part-edit-submit'). T04 e2e spec will consume these.
- pageerror listener / Playwright multi-viewport assertions: DEFERRED to T04.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd frontend && npm run type-check` | 0 | ✅ pass | 12000ms |
| 2 | `cd frontend && npm test -- ViewBuildlist` | 0 | ✅ pass | 1050ms |
| 3 | `cd frontend && npm test -- confirm-dialog` | 0 | ✅ pass | 810ms |
| 4 | `grep -c legacy imports in BuildListParts.tsx + EditBuildListPartForm.tsx | awk sum>0` | 0 | ✅ pass | 50ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `frontend/src/components/buildListParts/BuildListParts.tsx`
- `frontend/src/components/buildListParts/EditBuildListPartForm.tsx`
