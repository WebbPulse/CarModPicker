---
estimated_steps: 10
estimated_files: 3
skills_used: []
---

# T02: Wrap two admin tables in `overflow-x-auto` per audit findings

Mechanical fix task acting on T01's `fixed-pending → T02` verdicts. Per MEM172, two admin tables lack horizontal-scroll wrappers and create page-level h-scroll at 360px:

1. **`frontend/src/pages/admin/CrawlerAdmin.tsx:322`** — wrap the rate-limit `<table>` in a `<div className="overflow-x-auto">`. The existing `rounded border border-gray-700/60 overflow-hidden` outer div does not allow horizontal scroll inside the rounded crop. Replace `overflow-hidden` → `overflow-x-auto` on that wrapper (preserves the rounded chrome), OR insert an inner `<div className="overflow-x-auto">` and keep the outer wrapper for the border. Choose whichever produces the cleaner diff — the simpler pattern is changing `overflow-hidden` → `overflow-x-auto` on line 322's div className.
2. **`frontend/src/pages/admin/ExtractionHealth.tsx:203`** — wrap the per-tier coverage `<table>` in `<div className="overflow-x-auto">`. The table is 2-column and likely fits at 360, but the audit may show it overflows under longer field names. If T01-SUMMARY.md verdict for this surface at 360 is `pass`, skip the wrapper add — only act on `fixed-pending → T02` verdicts. Document the decision in T02-SUMMARY.md.

## Constraints

- Do NOT touch other admin tables — UserManagement, PartsCuration scan-diff, and ExtractionHealth failure-rate are already wrapped (verdict from T01 should confirm this).
- Do NOT change column widths, row heights, or font sizes — wrapper-only fix.
- Do NOT add new tokens or design system primitives — `overflow-x-auto` is a Tailwind utility, no semantic-token impact.
- Run `npm --prefix frontend run type-check && npm --prefix frontend run lint` after the edit; both must remain green.

## Files Likely Touched

Only the two files named above.

## Inputs

- ``.gsd/milestones/M003/slices/S03/tasks/T01-SUMMARY.md` — verdict table identifying which surfaces need fixes`
- ``frontend/src/pages/admin/CrawlerAdmin.tsx` — rate-limit table wrapper at line 322`
- ``frontend/src/pages/admin/ExtractionHealth.tsx` — per-tier coverage table at line 203 (act only if T01 flagged fixed-pending)`

## Expected Output

- ``frontend/src/pages/admin/CrawlerAdmin.tsx` — wrapper at line 322 emits `overflow-x-auto``
- ``frontend/src/pages/admin/ExtractionHealth.tsx` — per-tier coverage table wrapped if T01 flagged it (otherwise unchanged with rationale)`
- ``.gsd/milestones/M003/slices/S03/tasks/T02-SUMMARY.md` — what changed and why`

## Verification

rg -q 'overflow-x-auto' frontend/src/pages/admin/CrawlerAdmin.tsx && (npm --prefix frontend run type-check) && (npm --prefix frontend run lint)
