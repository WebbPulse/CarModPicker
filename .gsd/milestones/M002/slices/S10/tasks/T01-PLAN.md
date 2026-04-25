---
estimated_steps: 17
estimated_files: 3
skills_used: []
---

# T01: Reskin PartsCatalog search Input + PartsFilterSidebar inputs/checkboxes + PartsActiveFilterChips onto ui/* primitives

Migrate the catalog page-level chrome and filter UI onto S08 primitives. Three files, all interactive primitives only — leave VehicleFilterSection (legacy common/) and Pagination untouched per MEM107.

In frontend/src/pages/parts/PartsCatalog.tsx:
- Replace `import Input from '../../components/common/Input'` with `import { Input } from '../../components/ui/input'`.
- The search Input has props `type='text' placeholder value onChange className='w-full max-w-md'` — the S08 Input forwards all standard HTMLInputAttributes, so pass props directly. Add `data-testid='parts-catalog-search'` for T04.
- DO NOT touch the Pagination import or call site; that's S12 layout-chrome.
- DO NOT touch the LinkButton 'My Parts' import (it's a layout-tier link); S12 sweep.

In frontend/src/components/parts/PartsFilterSidebar.tsx:
- Replace the four raw `<input type='checkbox'/>` rows (Source / Categories / PartManufacturers) with raw `<input>` elements styled to use the new design tokens. The S08 ui/input is a single-line text input only — there is no ui/checkbox primitive yet, and adding one is out of scope (S12 will introduce it if needed). Instead, retire the `checkboxInputClass` Tailwind blob in favor of token-driven utility classes: `accent-primary border-input bg-background focus-visible:ring-2 focus-visible:ring-ring`.
- Replace the two price-range raw `<input type='number'/>` instances and the part-manufacturer search raw `<input type='text'/>` with `<Input>` from ui/input — pass `id`, `min`, `step`, `placeholder`, `value`, `onChange`. Use `<Input>` directly; do not introduce wrappers.
- Replace the 'Clear all' raw `<button>` and the 'Clear categories' / 'Clear part manufacturers' raw `<button>` elements with `<Button variant='ghost' size='sm' className='...preserved layout classes...'>` from ui/button. Preserve original alignment (block w-full text-left for inline section clears; inline link-style for the top-right Clear all — use `variant='link' size='sm'` for that one).
- Keep the outer Card wrapper and the section title <h2>/<h3> markup as-is — they are layout chrome (S12 sweep). The aside's `lg:w-64 flex-shrink-0` layout container is also untouched.
- Keep VehicleFilterSection's legacy import — it stays on legacy primitives until S12.

In frontend/src/components/parts/PartsActiveFilterChips.tsx:
- The chip itself uses `filterChipClass` from common/VehicleFilterChips (a shared style constant). Retain the import but move the per-chip remove `<button>` to `<Button variant='ghost' size='icon' className='h-5 w-5 ...preserved classes...'>` from ui/button so focus rings inherit ring tokens. Pass `aria-label` through unchanged.

Failure modes: filter-state callbacks (toggleCategory / togglePartManufacturer / clearVehicleFilter / clearPriceRange / setSelectedCategoryIds / setSelectedPartManufacturerIds / setPriceMin / setPriceMax) MUST stay wired identically — the test that proves they still work is the existing PartsCatalog.test.tsx + the new e2e spec exercising the search input. Negative tests: typing into the search field must trigger setSearchTerm without losing keystrokes (no debounce regression).

Threat surface: search-term value flows into the URL via usePartsFilters({syncToUrl:true}) and into a backend query param. No new XSS surface — value is rendered as text and used as a search filter. Existing rate-limit/sanitize behavior preserved.

Load profile: identical to before; no new fetches or re-renders introduced.

## Inputs

- ``frontend/src/pages/parts/PartsCatalog.tsx``
- ``frontend/src/components/parts/PartsFilterSidebar.tsx``
- ``frontend/src/components/parts/PartsActiveFilterChips.tsx``
- ``frontend/src/components/ui/input.tsx``
- ``frontend/src/components/ui/button.tsx``

## Expected Output

- ``frontend/src/pages/parts/PartsCatalog.tsx``
- ``frontend/src/components/parts/PartsFilterSidebar.tsx``
- ``frontend/src/components/parts/PartsActiveFilterChips.tsx``

## Verification

cd frontend && npm run type-check && npm test -- PartsCatalog && grep -c "from '../../components/common/Input'\|from '../components/common/Input'" src/pages/parts/PartsCatalog.tsx | grep -q '^0$'

## Observability Impact

No new runtime boundaries — ui/Input and ui/Button are presentational primitives. data-testid='parts-catalog-search' added on the search input gives T04 a deterministic selector.
