---
estimated_steps: 11
estimated_files: 1
skills_used: []
---

# T03: Reskin AddToBuildListDialog onto ui/Dialog + ui/Button while preserving form-submit semantics

Replace the common/Dialog wrapper, ActionButton, and SecondaryButton in AddToBuildListDialog.tsx with ui/Dialog (+ DialogContent/DialogHeader/DialogTitle/DialogFooter) and ui/Button. Preserve the form contract (handleSubmit, error/loading states, build-list multi-select, car-mismatch warning) — only swap the outer dialog primitive and the two footer buttons.

In frontend/src/components/parts/AddToBuildListDialog.tsx:
- Drop `import Dialog from '../common/Dialog'`, `import ActionButton from '../buttons/ActionButton'`, `import SecondaryButton from '../buttons/SecondaryButton'`.
- Add: `import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog'` and `import { Button } from '../ui/button'`.
- Replace `<Dialog isOpen={isOpen} onClose={onClose} title={...}>` with `<Dialog open={isOpen} onOpenChange={(open) => { if (!open) onClose(); }}>` wrapping `<DialogContent data-testid='parts-catalog-add-to-build-list-dialog' className='sm:max-w-3xl max-h-[90vh] overflow-y-auto'>` containing `<DialogHeader><DialogTitle>{`Add ${part.name} to Build List`}</DialogTitle></DialogHeader>` followed by the existing form. The S08 DialogContent default max width is `max-w-lg` — override to `sm:max-w-3xl` to roughly preserve the legacy width that fit the part-preview Card + build-list multi-select UI without horizontal cramp. Keep `max-h-[90vh] overflow-y-auto` so the scroll behavior on tall content survives.
- Replace the footer pair: `<SecondaryButton type='button' onClick={onClose} disabled={isAdding}>Cancel</SecondaryButton><ActionButton type='submit' disabled={isAdding || selectedBuildListIds.size === 0}>{...}</ActionButton>` with `<Button type='button' variant='secondary' onClick={onClose} disabled={isAdding}>Cancel</Button><Button type='submit' loading={isAdding} disabled={selectedBuildListIds.size === 0} data-testid='parts-catalog-add-to-build-list-submit'>{selectedBuildListIds.size === 1 ? 'Add to Build List' : `Add to ${selectedBuildListIds.size} Build Lists`}</Button>`. Drop the inline `<LoadingSpinner/>` ternary — Button's `loading` prop renders the spinner via lucide Loader2. Note: ui/Button auto-disables when `loading=true` (see button.tsx line ~59), so keep the redundant `disabled={selectedBuildListIds.size === 0}` only for the empty-selection guard, not the loading guard.
- DO NOT touch the inner Cards (part preview, build-list rows), the quantity raw `<input type='number'/>`, the car-mismatch banner, the ErrorAlert message, or the LoadingSpinner used during build-list fetch — those are nested chrome that S12 will sweep. The form's onSubmit handler stays exactly as-is.
- The existing 4xl-equivalent width is purely aesthetic; sm:max-w-3xl is close enough and keeps the diff minimal. Document the slight width change in the slice summary.

Failure modes: handleSubmit awaits buildListPartsApi.addPartToBuildList in a loop; if any iteration throws, the catch block sets error and isAdding=false. The Button's `loading` prop must NOT auto-close the dialog (DialogContent doesn't auto-dismiss on loading), so the existing flow (success → onPartAdded() + onClose()) is preserved. Negative tests: clicking Cancel while isAdding=true must be a no-op (Cancel button disabled). Pressing Escape while isAdding=true: Radix Dialog's default behavior closes — accept this as documented in S09's confirm-dialog gotchas.

Threat surface: the dialog adds a part to user-owned build-lists by calling buildListPartsApi.addPartToBuildList(buildListId, partId, {quantity, notes:null}). Ownership is enforced server-side; quantity is clamped to >=1 in handleSubmit (`Math.max(1, quantity)`). Migration preserves both gates. No new XSS surface — part.name and buildList.name render as text.

Load profile: dialog opens on demand; no autoload. The build-list fetch fires once on isOpen=true (existing behavior).

## Inputs

- ``frontend/src/components/parts/AddToBuildListDialog.tsx``
- ``frontend/src/components/ui/dialog.tsx``
- ``frontend/src/components/ui/button.tsx``

## Expected Output

- ``frontend/src/components/parts/AddToBuildListDialog.tsx``

## Verification

cd frontend && npm run type-check && npm test -- PartsCatalog && grep -c "from '../common/Dialog'\|from '../buttons/ActionButton'\|from '../buttons/SecondaryButton'" src/components/parts/AddToBuildListDialog.tsx | grep -q '^0$'

## Observability Impact

Dialog open/close transitions surface via Radix data-state attributes on DialogContent. data-testid='parts-catalog-add-to-build-list-dialog' on the DialogContent + 'parts-catalog-add-to-build-list-submit' on the submit Button enable T04 to assert dialog visibility, focus management, and Escape-closes.
