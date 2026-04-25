---
id: T01
parent: S10
milestone: M002
key_files:
  - frontend/src/pages/parts/PartsCatalog.tsx
  - frontend/src/components/parts/PartsFilterSidebar.tsx
  - frontend/src/components/parts/PartsActiveFilterChips.tsx
key_decisions:
  - Used variant='link' size='sm' with h-auto/p-0 overrides for the top-right 'Clear all' button to preserve inline link styling against the size variant's h-9 default — matches MEM111's pattern of overriding via className rather than introducing new variants.
  - Used variant='ghost' size='sm' with 'block w-full text-left justify-start h-auto px-3 py-2' for the per-section clear buttons to preserve the legacy left-aligned full-width layout (the ghost variant defaults to inline-flex justify-center, which would have re-centered the label).
  - Used variant='ghost' size='icon' with 'h-5 w-5 p-0' overrides for the per-chip remove buttons in PartsActiveFilterChips so they remain compact inside the chip span (icon variant defaults to h-10 w-10).
  - Retired checkboxInputClass (legacy bg-gray-800/border-gray-500/indigo palette) for token-driven 'accent-primary border-input bg-background focus-visible:ring-2 focus-visible:ring-ring' since no ui/checkbox primitive exists yet (S12 will introduce one if needed).
duration: 
verification_result: passed
completed_at: 2026-04-25T23:37:23.670Z
blocker_discovered: false
---

# T01: Reskin PartsCatalog search input, PartsFilterSidebar inputs/clear-buttons, and PartsActiveFilterChips remove buttons onto ui/* primitives

**Reskin PartsCatalog search input, PartsFilterSidebar inputs/clear-buttons, and PartsActiveFilterChips remove buttons onto ui/* primitives**

## What Happened

Migrated three catalog files onto S08 design-system primitives while preserving all filter-state callbacks and visible behavior.

PartsCatalog.tsx: swapped `import Input from '../../components/common/Input'` for `import { Input } from '../../components/ui/input'` and added `data-testid='parts-catalog-search'` on the search field for T04's e2e selector. Pagination, LinkButton 'My Parts', and PageHeader left untouched per MEM107 (S12 layout-chrome sweep).

PartsFilterSidebar.tsx: replaced the bespoke `inputClass` blob on the price-min/price-max number inputs and the part-manufacturer search text input with the ui/Input primitive (props pass through unchanged: id, type, min, step, placeholder, value, onChange). Replaced the four checkbox rows' `checkboxInputClass` (which used legacy `border-gray-500 bg-gray-800 text-indigo-500 focus:ring-indigo-500/...` palette) with token-driven utilities `accent-primary border-input bg-background focus-visible:ring-2 focus-visible:ring-ring`. Replaced the top-right 'Clear all' raw `<button>` with `<Button variant='link' size='sm' className='h-auto p-0 text-sm'>` so the inline link styling survives the size override. Replaced the per-section 'Clear categories' / 'Clear part manufacturers' raw `<button>`s with `<Button variant='ghost' size='sm' className='block w-full text-left justify-start h-auto px-3 py-2 text-sm text-gray-500 hover:text-gray-300'>` — `justify-start` and `h-auto` overrides preserve the original block-left layout against the ghost variant's default centered/h-9 sizing. Kept the outer Card, section <h2>/<h3> markup, and VehicleFilterSection import on legacy primitives per the plan's S12 carve-out.

PartsActiveFilterChips.tsx: kept the shared `filterChipClass` import (S12 will retire it) and converted the four per-chip remove `<button>` elements (category / manufacturer / vehicle / price) to `<Button variant='ghost' size='icon' className='h-5 w-5 p-0 rounded-full ...'>` with `h-5 w-5 p-0` overriding the icon variant's default 10×10 size. The aria-label on each is preserved verbatim.

Both ui/Button and ui/Input emit token-aware `focus-visible:ring-ring` outlines, so R020 keyboard-focus visibility is preserved without adding bespoke ring classes.

## Verification

Ran the task contract verification chain end-to-end:
- `npm run type-check` (tsc -b --noEmit) — exit 0, no errors.
- `npm test -- PartsCatalog --run` — 3/3 PartsCatalog page tests pass (renders title + fetches, empty state, My Parts gating). The two `[usePartPriceSummaries]` console.warn lines in stderr are pre-existing S06 mock-miss handling (no `/parts/price-history` mock in PartsCatalog.test.tsx), not regressions from this task.
- grep for `from '../../components/common/Input'` in PartsCatalog.tsx returned 0; same import variants in PartsFilterSidebar.tsx and PartsActiveFilterChips.tsx also returned 0.

Filter-state callbacks (toggleCategory / togglePartManufacturer / clearVehicleFilter / clearPriceRange / setSelectedCategoryIds / setSelectedPartManufacturerIds / setPriceMin / setPriceMax / setHideUgc / setSearchTerm) are wired identically — only the underlying button/input element changed. Slice-level e2e (parts-catalog.spec.ts, T04) and full lint baseline check are deferred to T05's verification sweep per the slice plan.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd frontend && npm run type-check` | 0 | pass | 6500ms |
| 2 | `cd frontend && npm test -- PartsCatalog --run` | 0 | pass | 880ms |
| 3 | `grep -c "from '../../components/common/Input'\|from '../components/common/Input'" src/pages/parts/PartsCatalog.tsx` | 0 | pass | 50ms |

## Deviations

None material. Inline-utility tweaks on Button className were necessary to preserve the legacy layouts (left-aligned full-width clears, compact chip-remove icons) — these are anticipated by MEM111 ("override via className, don't invent variants") and stay within the slice plan's text.

## Known Issues

PartsCatalog.test.tsx still emits two `[usePartPriceSummaries] TypeError: Cannot read properties of null (reading 'summaries')` console.warn lines in stderr because the test does not mock `/parts/price-history` — pre-existing S06 behavior, unchanged by this task.

## Files Created/Modified

- `frontend/src/pages/parts/PartsCatalog.tsx`
- `frontend/src/components/parts/PartsFilterSidebar.tsx`
- `frontend/src/components/parts/PartsActiveFilterChips.tsx`
