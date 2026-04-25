---
estimated_steps: 15
estimated_files: 2
skills_used: []
---

# T03: Reskin BuildListParts.tsx child + EditBuildListPartForm dialog onto ui/* primitives

Migrate the BuildListParts component and its EditBuildListPartForm modal off common/Dialog + ActionButton + raw bare buttons + raw inputs onto ui/* primitives.

In BuildListParts.tsx:
  - Replace the View-mode toggle (the two raw <button> elements with conditional bg-blue-600/bg-gray-700 styling at lines ~390–413) with ui/Tabs (TabsList + TabsTrigger value='category'/'phase'). Keep state hook signature (viewMode setViewMode) unchanged so children still receive viewMode.
  - Replace the 'Add Part' ActionButton with ui/Button.
  - Replace the phase-row controls: the new-phase Input + Add phase ActionButton row, the per-row Edit/Cancel/Save SecondaryButton+ActionButton, and the per-row Delete bare button. Use ui/Input + ui/Button (variants: default, secondary, destructive, ghost as appropriate).
  - Replace DeleteConfirmationDialog (delete-phase + delete-part) with ConfirmDialog from T01.
  - Add data-testid='build-list-view-mode-tabs', 'build-list-add-phase-input', 'build-list-add-phase-submit', 'build-list-phase-row-${phase.id}'.
  - The car-mismatch warning banner stays as-is (presentational chrome, not interactive).

In EditBuildListPartForm.tsx:
  - Swap common/Dialog wrapper for ui/Dialog (preserve title='Edit Part', preserve isOpen/onClose contract). Inner form fields (the non-dialog-wrapper parts) can stay on legacy primitives — they'll ride S12 along with common/Input.
  - Replace the form's Cancel/Save ActionButton+SecondaryButton pair with ui/Button (variant='secondary' for Cancel, default for Save). Preserve the existing onSubmit/onClose contract.
  - Add data-testid='build-list-part-edit-dialog' and 'build-list-part-edit-submit'.

Do NOT touch BuildListPartList or BuildListPartListItem internals — they're row presentation that S12 will sweep. They are downstream of the parent and do not gate the slice goal.

Failure modes: optimistic purchased-toggle path uses no dialog; preserved as-is. Phase add/edit/delete error paths must still surface phaseError via the existing red text region. Negative tests: rapid double-click on Add phase must not duplicate (existing `disabled={!newPhaseName.trim() || isAddingPhase}` guard preserved). Load profile: same as before; no new fetches.

Threat surface: phase mutations gated on canManageParts (existing). Migration preserves the gate. The new-phase input value is sent verbatim to backend POST /api/build-lists/{id}/phases — backend already validates length and trims; no new XSS surface introduced (rendered as text in <span>, not dangerouslySetInnerHTML).

## Inputs

- ``frontend/src/components/buildListParts/BuildListParts.tsx``
- ``frontend/src/components/buildListParts/EditBuildListPartForm.tsx``
- ``frontend/src/components/ui/tabs.tsx``
- ``frontend/src/components/ui/button.tsx``
- ``frontend/src/components/ui/dialog.tsx``
- ``frontend/src/components/ui/input.tsx``
- ``frontend/src/components/ui/confirm-dialog.tsx``

## Expected Output

- ``frontend/src/components/buildListParts/BuildListParts.tsx``
- ``frontend/src/components/buildListParts/EditBuildListPartForm.tsx``

## Verification

cd frontend && npm run type-check && npm test -- BuildListParts ViewBuildlist && grep -c "from '../common/Dialog'\|from '../common/DeleteConfirmationDialog'\|from '../buttons/ActionButton'\|from '../buttons/SecondaryButton'" src/components/buildListParts/BuildListParts.tsx src/components/buildListParts/EditBuildListPartForm.tsx | awk -F: '{ sum += $2 } END { exit (sum > 0) }'

## Observability Impact

data-testid hooks listed above. The Tabs component emits data-state='active'/'inactive' on each TabsTrigger which Playwright assertions can read (page.getByTestId('build-list-view-mode-tabs').getByRole('tab', { name: 'By phase' }).click()) without depending on visual contrast cues.
