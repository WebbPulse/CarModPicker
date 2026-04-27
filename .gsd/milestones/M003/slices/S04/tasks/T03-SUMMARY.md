---
id: T03
parent: S04
milestone: M003
key_files:
  - frontend/src/components/parts/EditPartForm.tsx
  - frontend/src/components/forms/SearchableSelect.tsx
key_decisions:
  - Dropped only the trailing `input-modern` token at each site, leaving all preceding tokenized utilities (bg/border/rounded/text/focus-ring/transition) intact — preserves sizing, color, focus, and transition without relying on the soon-to-be-deleted legacy `.input-modern` rule.
  - Accepted the visual delta from `.input-modern`'s glass background + backdrop-filter + focus translateY/box-shadow chrome, because S04's slice goal (MEM144) explicitly retires that glassmorphism substrate — surviving inputs render in flat tokenized form by design.
duration: 
verification_result: passed
completed_at: 2026-04-26T23:00:11.426Z
blocker_discovered: false
---

# T03: Drop trailing input-modern class from EditPartForm select and SearchableSelect input

**Drop trailing input-modern class from EditPartForm select and SearchableSelect input**

## What Happened

Removed the trailing `input-modern` token from the two remaining consumer sites — `frontend/src/components/parts/EditPartForm.tsx:349` (the category `<select>`) and `frontend/src/components/forms/SearchableSelect.tsx:294` (the search `<input>`). Both className strings already spell out the tokenized utilities that drive their look (`bg-gray-800 border border-white/20 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all duration-300 ease-out`), so removing the trailing `input-modern` token leaves the structural sizing, color, focus ring, and transition intact through the explicit utilities.

Per the task plan and the slice intent (S04 hard-deletes the `.input-modern` rule at index.css:584-616 in pass-1), the surrounding tokenized utilities are intended to be authoritative. The legacy `.input-modern` rule does add some decorative chrome that the preceding utilities don't strictly cover (a glass-gradient `background` that overrides `bg-gray-800`, `backdrop-filter: blur(15px)`, a focus `translateY(-1px)`, and a slightly larger `box-shadow` than `focus:ring-2`), but per slice goal MEM144 this glass/lift chrome is exactly the substrate being retired — the surviving inputs render in flat tokenized form, which is the post-S04 design contract.

This was a 2-edit surgical change with no test changes needed; the existing test suite continues to pass.

## Verification

Ran the task plan's exact verification chain from `frontend/`:
1. `rg 'input-modern' src/{components,pages,contexts,hooks,api,lib,__tests__}/` → exit 1 (no matches in consumer dirs).
2. `npm run type-check` → exit 0 (tsc -b --noEmit clean).
3. `npm test -- --run` → exit 0; 594 tests across 90 files all pass, including the FE-03 drift guard suite, no-legacy-gradient guard, and the App route coverage.

Slice-level grep gates: the new `input-modern` gate is now satisfied for the consumer dirs (only the 4 self-references inside `index.css:586-615` remain, which S04 pass-1 will delete in a later task).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg 'input-modern' src/{components,pages,contexts,hooks,api,lib,__tests__}/` | 1 | pass | 50ms |
| 2 | `npm run type-check` | 0 | pass | 8000ms |
| 3 | `npm test -- --run` | 0 | pass | 5680ms |

## Deviations

None — task plan executed exactly as specified.

## Known Issues

None.

## Files Created/Modified

- `frontend/src/components/parts/EditPartForm.tsx`
- `frontend/src/components/forms/SearchableSelect.tsx`
