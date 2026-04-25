---
id: T03
parent: S10
milestone: M002
key_files:
  - frontend/src/components/parts/AddToBuildListDialog.tsx
key_decisions:
  - Used variant='secondary' for the Cancel footer button per MEM111 (formal variant where the design token encodes the intended semantic) instead of carrying a bespoke className override.
  - Used Button's `loading={isAdding}` prop to render the Loader2 spinner inside the submit button and dropped the legacy <LoadingSpinner/> ternary — the design-system primitive already provides the spinner via lucide and auto-applies aria-busy.
  - Sized DialogContent to `sm:max-w-3xl max-h-[90vh] overflow-y-auto` per task plan — slightly narrower than the legacy 4xl-equivalent width but close enough to keep the part-preview Card + build-list multi-select layout uncramped, with vertical scroll preserved for tall content.
duration: 
verification_result: passed
completed_at: 2026-04-25T23:41:00.569Z
blocker_discovered: false
---

# T03: Reskin AddToBuildListDialog onto ui/Dialog + ui/Button while preserving form-submit and multi-select semantics

**Reskin AddToBuildListDialog onto ui/Dialog + ui/Button while preserving form-submit and multi-select semantics**

## What Happened

Replaced the common/Dialog wrapper, ActionButton, and SecondaryButton in `frontend/src/components/parts/AddToBuildListDialog.tsx` with the S08 design-system primitives (`ui/Dialog` + `DialogContent`/`DialogHeader`/`DialogTitle`, and `ui/Button`). The outer dialog now uses Radix's `open` / `onOpenChange` API — closing routes back to the existing `onClose()` callback, preserving the parent-controlled open state. DialogContent gets `data-testid="parts-catalog-add-to-build-list-dialog"` plus `sm:max-w-3xl max-h-[90vh] overflow-y-auto` to roughly preserve the legacy 4xl-equivalent width (slight narrowing per task plan) and keep the tall-content scroll behavior.

The footer pair migrated to `Button`: Cancel uses `variant="secondary"` and stays `disabled` while `isAdding`; Submit uses `loading={isAdding}` (Loader2 spinner via the variant), `disabled={selectedBuildListIds.size === 0}` for the empty-selection guard, and `data-testid="parts-catalog-add-to-build-list-submit"`. The inline `<LoadingSpinner/>` ternary in the submit label was dropped — the Button's `loading` prop now renders the spinner. Per MEM111, switched to formal variants (`secondary`) where the design tokens already encode the intended semantic.

Did NOT touch the inner Cards (part preview, build-list rows), the raw quantity `<input type="number"/>`, the car-mismatch banner, ErrorAlert, or the LoadingSpinner used during build-list fetch — those are nested chrome reserved for the S12 ripple sweep (MEM107). Removed unused legacy imports (`ActionButton`, `SecondaryButton`, common `Dialog`).

The form contract (`handleSubmit`, error/loading state, multi-select build-list iteration with `Math.max(1, quantity)` clamp, `onPartAdded()` + `onClose()` on success) is preserved exactly. The handleSubmit awaits `buildListPartsApi.addPartToBuildList` per selected list; the catch sets error and `isAdding=false`. Cancel is no-op while `isAdding=true` (button disabled); Escape while `isAdding=true` falls through to Radix's default close behavior — accepted per the task plan's documented gotcha.

Per MEM107 / MEM111 the migration was kept tight: only the outer dialog primitive and the two footer buttons changed. The slight max-width reduction (4xl-equivalent → sm:max-w-3xl) is documented as a known minor visual delta.

## Verification

Ran the task plan's verification command from `frontend/`:

1. `npm run type-check` → exit 0 (tsc -b --noEmit clean)
2. `npm test -- PartsCatalog` → 3/3 tests passing in src/pages/parts/PartsCatalog.test.tsx (the two pre-existing usePartPriceSummaries TypeError stderr lines are unrelated to this task — surfaced from the same hook in S06 mocks and present before this change)
3. `grep -c "from '../common/Dialog'\|from '../buttons/ActionButton'\|from '../buttons/SecondaryButton'" src/components/parts/AddToBuildListDialog.tsx | grep -q '^0$'` → exit 0 (zero legacy imports remain)

Slice-level verification (Verification section of S10-PLAN.md): runtime signals — Radix `data-state` attributes now drive open/close transitions on the dialog (replacing the bespoke `common/Dialog` open-state); `data-testid="parts-catalog-add-to-build-list-dialog"` on DialogContent and `data-testid="parts-catalog-add-to-build-list-submit"` on the submit Button are in place for the T04 Playwright dialog focus/Escape and Tab focus assertions. usePartPriceSummaries / SparklineCell warn paths from S06 are untouched; pageerror listener and default-404 mock-miss responses remain intact for T04 to consume. T04 will run the full e2e Playwright suite at mobile/tablet/desktop on the final task.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd frontend && npm run type-check` | 0 | ✅ pass | 4500ms |
| 2 | `cd frontend && npm test -- PartsCatalog` | 0 | ✅ pass | 906ms |
| 3 | `grep -c "from '../common/Dialog'|from '../buttons/ActionButton'|from '../buttons/SecondaryButton'" src/components/parts/AddToBuildListDialog.tsx | grep -q '^0$'` | 0 | ✅ pass | 30ms |

## Deviations

None — followed the inlined task plan exactly. The slight max-width reduction (legacy 4xl-equivalent → sm:max-w-3xl) is the documented intentional delta from the task plan, not a deviation.

## Known Issues

None.

## Files Created/Modified

- `frontend/src/components/parts/AddToBuildListDialog.tsx`
