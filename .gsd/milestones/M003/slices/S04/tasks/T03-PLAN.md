---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T03: Drop trailing `input-modern` class from EditPartForm `<select>` and SearchableSelect `<input>`

Two consumer sites confirmed by `rg -n 'input-modern' frontend/src/`: `frontend/src/components/parts/EditPartForm.tsx:349` (`<select>` element) and `frontend/src/components/forms/SearchableSelect.tsx:294` (`<input>` element). Both currently spell out tokenized utilities BEFORE the trailing `input-modern` class — the explicit utilities cover the look entirely and `input-modern` is additive decorative chrome that doesn't change observable rendering. Drop only the trailing `input-modern` token from each className string. Keep all preceding utilities intact. Single atomic commit. Narrative explains why dropping is safe (the `.input-modern` rule at index.css:584-616 only sets `padding`/`border`/`border-radius`/`background-color`/`color`/`font-size`/`transition` — all already covered by the preceding tokenized utilities at each site).

## Inputs

- `frontend/src/components/parts/EditPartForm.tsx`
- `frontend/src/components/forms/SearchableSelect.tsx`

## Expected Output

- `frontend/src/components/parts/EditPartForm.tsx`
- `frontend/src/components/forms/SearchableSelect.tsx`

## Verification

cd frontend && rg 'input-modern' src/{components,pages,contexts,hooks,api,lib,__tests__}/; test $? -eq 1 && npm run type-check && npm test -- --run
