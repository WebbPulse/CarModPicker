---
id: T02
parent: S10
milestone: M002
key_files:
  - frontend/src/components/parts/PartList.tsx
key_decisions:
  - Used the destructive variant (variant='destructive') for the Delete row-action and dropped the bespoke `bg-red-600 hover:bg-red-700` Tailwind override — the variant from buttonVariants already encodes the intended semantic via bg-destructive / hover:bg-destructive/90, matching MEM111's 'switch to formal variants where the new design tokens already encode the intended semantic' rule.
  - Used variant='secondary' for the Edit row-action (table + card) per MEM111's same rule — Edit is semantically a secondary action and the secondary variant already maps to the right token palette.
  - Added data-testid='parts-catalog-add-to-build-list-trigger' on the TABLE-layout Add-to-Build-List Button only (not the card layout). The card layout is only used in non-catalog contexts (UserParts, build-list views) that T04's e2e does not exercise, so adding the testid there would be misleading.
  - Kept the leading 📋 emoji on Add-to-Build-List in the card layout exactly as it was on the legacy ActionButton — the emoji is part of the card-layout's affordance language and the plan called it out explicitly.
duration: 
verification_result: passed
completed_at: 2026-04-25T23:39:23.502Z
blocker_discovered: false
---

# T02: Reskin PartList row action buttons (Add to Build List / Edit / Delete) onto ui/Button across table and card layouts

**Reskin PartList row action buttons (Add to Build List / Edit / Delete) onto ui/Button across table and card layouts**

## What Happened

Migrated the six row-action button usages (three per layout × table + card) in `frontend/src/components/parts/PartList.tsx` from the legacy `ActionButton` / `SecondaryButton` primitives to `ui/Button`.

Imports: dropped `import ActionButton from '../buttons/ActionButton'` and `import SecondaryButton from '../buttons/SecondaryButton'`; added `import { Button } from '../ui/button'`.

Table layout (the actions `<td>` inside `ResponsiveTableWrapper`):
- Add to Build List → `<Button size="sm" data-testid="parts-catalog-add-to-build-list-trigger" className="text-xs px-2 py-1 whitespace-nowrap shrink-0" onClick={() => onAddToBuildList(part)}>` — kept the default ('primary' equivalent) variant for the hero action and added the testid that T04's e2e dialog test will target.
- Edit → `<Button variant="secondary" size="sm" className="text-xs px-2 py-1" onClick={() => onEdit(part)}>` per MEM111's "switch to formal variants where the new design tokens already encode the intended semantic".
- Delete → `<Button variant="destructive" size="sm" className="text-xs px-2 py-1" onClick={() => onDelete(part)}>`. Dropped the bespoke `bg-red-600 hover:bg-red-700` Tailwind classes — the destructive variant from `buttonVariants` already encodes them via `bg-destructive` / `hover:bg-destructive/90`.

Card layout (the inline action row inside the per-part card): same three substitutions with the `text-xs px-3 py-1` size override preserved on each, and the leading 📋 emoji kept on Add-to-Build-List per the plan. No data-testid on the card layout because it is consumed by non-catalog surfaces (UserParts, build-list views) that T04 does not exercise.

Carve-outs preserved per MEM107 / S12 sweep scope: SortableTh, ResponsiveTableWrapper, LoadingSpinner, ErrorAlert, Card, SectionHeader, ImageWithPlaceholder, VoteButtons, SparklineCell, and PriceDeltaLine all stay on legacy primitives. The S06 invariant — one batch POST per page for `usePartPriceSummaries`, plus per-row lazy multi-observation fetches — is untouched (no changes to the price-cell render path or hook usage). The column-priority logic, sort logic, cache logic, and `providedData` / `providedPagination` prop contract are also untouched (consumed by other surfaces outside this slice).

The three button-render predicates (`showAddToBuildListButton && onAddToBuildList`, `onEdit && (!canEdit || canEdit(part))`, `onDelete && (!canDelete || canDelete(part))`) were preserved verbatim — Negative Tests (Q7) requirement that "with onAddToBuildList undefined OR showAddToBuildListButton false, the button must NOT render" is satisfied by leaving the existing && short-circuits in place. onClick arity is identical (`() => onAddToBuildList(part)` / `() => onEdit(part)` / `() => onDelete(part)`), so Vitest's existing `PartList.priceHistory.test.tsx` continues to exercise the handlers via fireEvent.click.

ui/Button emits token-aware `focus-visible:ring-ring` outlines, so R020 keyboard-focus visibility is preserved without bespoke ring classes.

## Verification

Ran the task contract verification chain end-to-end:
- `cd frontend && npm run type-check` (tsc -b --noEmit) — exit 0, zero output.
- `cd frontend && npm test -- PartList --run` — 3/3 PartList.priceHistory.test.tsx tests pass (812ms total). These cover the actual onClick handlers via fireEvent.click on the Add/Edit/Delete buttons, which confirms the variant migration did not change the rendered handlers.
- `grep -c "from '../buttons/ActionButton'\|from '../buttons/SecondaryButton'" src/components/parts/PartList.tsx` → 0, confirming both legacy imports are gone.

Slice-level e2e (parts-catalog.spec.ts, T04) and the full lint/visual sweep are deferred to T05's verification round per the slice plan.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd frontend && npm run type-check` | 0 | pass | 6500ms |
| 2 | `cd frontend && npm test -- PartList --run` | 0 | pass | 812ms |
| 3 | `grep -c "from '../buttons/ActionButton'\|from '../buttons/SecondaryButton'" src/components/parts/PartList.tsx` | 0 | pass | 50ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `frontend/src/components/parts/PartList.tsx`
