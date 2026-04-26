---
estimated_steps: 17
estimated_files: 10
skills_used: []
---

# T01: Responsive audit pass — record per-viewport verdict for every dense table + card-grid view at 360/768/1280

Read-only audit pass producing a verdict table consumed by T02 and T03. Visit each surface with realistic densest data at 360, 768, and 1280; record `pass` (no overflow, content readable), `fixed-pending` (overflow surfaced — fix scheduled in T02 or T03), or `acceptable-as-scroll` (table is dense by design and lives inside `overflow-x-auto` — horizontal scroll is the intended UX) per viewport. Output goes into `tasks/T01-SUMMARY.md` as a markdown table — no source code changes in this task.

## What to audit

Dense `<table>` views (4 admin + 2 ResponsiveTableWrapper consumers):
- `frontend/src/pages/admin/UserManagement.tsx:346-484` — 11-column user-management table inside `overflow-x-auto` (verdict-only; expected `acceptable-as-scroll` at 360/768, `pass` at 1280).
- `frontend/src/pages/admin/CrawlerAdmin.tsx:321-380` — 5-column rate-limit table inside `rounded border` div with NO horizontal scroll wrapper (expected `fixed-pending` at 360 — flag for T02; verdict at 768 / 1280).
- `frontend/src/pages/admin/ExtractionHealth.tsx:203-230` — 2-column per-tier coverage table inside per-tier card with NO horizontal scroll wrapper (probably narrow enough to `pass` at 360; if not, flag `fixed-pending` for T02). Also audit `failure-rate` table at lines 248-285 (already inside `overflow-x-auto` — `acceptable-as-scroll`).
- `frontend/src/pages/admin/PartsCuration.tsx:697-746` — 4-column scan-diff table inside `overflow-x-auto` (expected `acceptable-as-scroll`).
- `frontend/src/components/parts/PartList.tsx` — uses `useResponsiveColumns` + `ResponsiveTableWrapper`. Container is `frontend/src/pages/parts/PartsCatalog.tsx`. Verdict-only.
- `frontend/src/components/buildListParts/BuildListPartList.tsx` — uses `useResponsiveColumns` + `ResponsiveTableWrapper`. Container is `frontend/src/pages/buildLists/ViewBuildList.tsx`. Verdict-only.

Dense card-grid views (Tailwind responsive grid):
- `frontend/src/pages/parts/PartsCatalog.tsx` (table layout via PartList — overlaps with PartList audit row).
- `frontend/src/pages/buildLists/BuildListsCatalog.tsx:625` (`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4`).
- `frontend/src/pages/Search.tsx:464` (`<PartList layout="table" />` for parts; `tile-grid-compact` CSS class for users + build lists).

## How to audit

Locally serve the app (`npm --prefix frontend run dev`), navigate to each surface with seeded sample data (run `python scripts/populate_sample_data.py` from `backend/` first if the local DB is empty), and use Chrome DevTools device toolbar to set viewport to 360, 768, then 1280. Record what you see in a one-row-per-(surface × viewport) table. Per MEM170: 360 is the manual UAT target only; Playwright `toHaveScreenshot()` runs at 375 (mobile project default) — note this in the summary if it changes the verdict at 360 vs 375.

## Out of scope

No code changes — this is read-only. If a surface needs a fix, write the fix into the verdict cell as `fixed-pending → T02` or `fixed-pending → T03` and let the next task act on it. Resist the urge to fold in the fix here — keeping audit and repair separate avoids thrash.

## Inputs

- ``frontend/src/pages/admin/UserManagement.tsx` — 11-col user table`
- ``frontend/src/pages/admin/CrawlerAdmin.tsx` — 5-col rate-limit table (no overflow wrapper at line 322)`
- ``frontend/src/pages/admin/ExtractionHealth.tsx` — per-tier coverage table (no wrapper at line 203) + failure-rate table`
- ``frontend/src/pages/admin/PartsCuration.tsx` — 4-col scan-diff table`
- ``frontend/src/components/parts/PartList.tsx` — ResponsiveTableWrapper consumer`
- ``frontend/src/components/buildListParts/BuildListPartList.tsx` — ResponsiveTableWrapper consumer`
- ``frontend/src/pages/parts/PartsCatalog.tsx` — PartList container`
- ``frontend/src/pages/buildLists/BuildListsCatalog.tsx` — Tailwind responsive grid (line 625)`
- ``frontend/src/pages/Search.tsx` — mixed grid + table (line 464)`

## Expected Output

- ``.gsd/milestones/M003/slices/S03/tasks/T01-SUMMARY.md` — verdict table with 8 audit rows × 3 viewports = 24+ data rows; per-row verdict ∈ {pass, fixed-pending → T02, fixed-pending → T03, acceptable-as-scroll}; per-row one-sentence justification; closing section noting any cross-cutting findings`

## Verification

test -f .gsd/milestones/M003/slices/S03/tasks/T01-SUMMARY.md && grep -c '^|' .gsd/milestones/M003/slices/S03/tasks/T01-SUMMARY.md | awk '$1 >= 24'
