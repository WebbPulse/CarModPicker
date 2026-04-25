---
estimated_steps: 11
estimated_files: 1
skills_used: []
---

# T02: Reskin PartList row action buttons (Add to Build List / Edit / Delete) onto ui/Button — table + card layouts

Migrate the four row-action <ActionButton>/<SecondaryButton> usages in PartList.tsx (two per layout × table + card) to ui/Button while preserving the sparkline + delta-line integration (S06) and the responsive column-priority logic untouched.

In frontend/src/components/parts/PartList.tsx:
- Drop `import ActionButton from '../buttons/ActionButton'` and `import SecondaryButton from '../buttons/SecondaryButton'`.
- Add `import { Button } from '../ui/button'`.
- Table layout (lines ~847–869): the `actions` td renders three optional buttons. Replace `<ActionButton onClick={() => onAddToBuildList(part)} className='text-xs px-2 py-1 whitespace-nowrap shrink-0'>` with `<Button size='sm' className='text-xs px-2 py-1 whitespace-nowrap shrink-0' onClick={...}>`. Replace `<SecondaryButton onClick={() => onEdit(part)} className='text-xs px-2 py-1'>` with `<Button variant='secondary' size='sm' className='text-xs px-2 py-1' onClick={...}>`. Replace the destructive `<ActionButton ... className='text-xs px-2 py-1 bg-red-600 hover:bg-red-700'>` with `<Button variant='destructive' size='sm' className='text-xs px-2 py-1' onClick={...}>` — drop the bespoke red Tailwind classes since the destructive variant from buttonVariants already encodes them.
- Card layout (lines ~991–1014): same three substitutions, preserving the `text-xs px-3 py-1` size override. Keep the leading 📋 emoji prefix on Add-to-Build-List in the card layout.
- Add `data-testid='parts-catalog-add-to-build-list-trigger'` to the Add-to-Build-List Button in the TABLE layout only (T04's e2e clicks via this selector; the card layout is only used in non-catalog contexts so no testid needed there).
- DO NOT touch SortableTh, the surrounding ResponsiveTableWrapper, the LoadingSpinner / ErrorAlert / Card containers, or the price-cell SparklineCell + PriceDeltaLine integration. Those stay on legacy primitives — S12 sweep handles SortableTh, Card, ErrorAlert. The S06 invariant (one batch POST per page, multi-observation lazy-load) MUST remain intact — verified by T04's network counter.
- DO NOT change column-priority logic, sort logic, cache logic, or the providedData/providedPagination prop contract — they're consumed by other surfaces (UserParts, build-list views) outside this slice.

Failure modes: button onClick handlers MUST keep the same arity (`() => onAddToBuildList(part)` etc.) — Vitest's existing PartList.priceHistory.test.tsx exercises these via fireEvent.click. The destructive variant must still trigger onDelete with the part as a single argument. Negative tests: with onAddToBuildList undefined OR showAddToBuildListButton false, the button must NOT render (existing && short-circuit preserved). Load profile: rendered N×3 times per page where N is row count; no extra reflow.

Threat surface: row actions are currently gated by canEdit/canDelete predicates and showAddToBuildListButton; migration preserves all three gates. No new authorization surface introduced.

## Inputs

- ``frontend/src/components/parts/PartList.tsx``
- ``frontend/src/components/ui/button.tsx``

## Expected Output

- ``frontend/src/components/parts/PartList.tsx``

## Verification

cd frontend && npm run type-check && npm test -- PartList && grep -c "from '../buttons/ActionButton'\|from '../buttons/SecondaryButton'" src/components/parts/PartList.tsx | grep -q '^0$'

## Observability Impact

No runtime-boundary changes — Button is presentational. The sparkline/delta integration (S06) is untouched; T04's network-counter assertion (1 batch POST per page) still holds. data-testid='parts-catalog-add-to-build-list-trigger' enables T04 dialog targeting.
