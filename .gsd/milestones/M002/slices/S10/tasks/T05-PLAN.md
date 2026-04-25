---
estimated_steps: 11
estimated_files: 1
skills_used: []
---

# T05: Slice-level verification sweep and evidence capture

Final cross-task verification that the slice goal is met. Run the full local test gauntlet from frontend/, capture exit codes, spot-check the page in dev, and make sure no regressions slipped into adjacent areas.

Steps:
  1. cd frontend && npm run type-check — must exit 0.
  2. cd frontend && npm run test -- PartsCatalog PartList AddToBuildListDialog — must exit 0 (vitest passes for the directly-touched units).
  3. cd frontend && npm run test:e2e -- parts-catalog price-history components — must exit 0; parts-catalog runs 3 visual + 1 desktop dialog + 1 desktop keyboard test, price-history.spec.ts must STILL be 9/9 green (S06 invariant: row actions migration in T02 must not have broken sparkline integration), components.spec.ts must STILL be 3/3 green (no token regression).
  4. cd frontend && npm run lint 2>&1 | tail -1 — capture the error count. MUST equal the existing 104-error baseline (MEM062). Any net-new error in src/pages/parts/PartsCatalog.tsx, src/components/parts/PartsFilterSidebar.tsx, src/components/parts/PartsActiveFilterChips.tsx, src/components/parts/PartList.tsx, src/components/parts/AddToBuildListDialog.tsx, or e2e/parts-catalog.spec.ts is a fail — route back to T01–T04 for fix.
  5. Manual smoke (1–2 minutes, document the result in slice summary): start dev server (cd frontend && npm run dev) with a populated local DB, navigate to /parts, visually confirm the page renders on the new dark token palette, type into the search field and watch results filter, click the search-by-make / category checkboxes, click an 'Add to Build List' row button to open the dialog, press Escape to close, confirm focus rings visible on all action buttons under keyboard Tab, scroll to verify SparklineCell still renders for the multi-observation row.
  6. grep -r "from '../../components/common/Input'" src/pages/parts/PartsCatalog.tsx — must return 0.
  7. grep -r "from '../buttons/ActionButton'\|from '../buttons/SecondaryButton'\|from '../common/Dialog'" src/components/parts/PartList.tsx src/components/parts/AddToBuildListDialog.tsx — must return 0.
  8. Confirm no new pre-commit lint errors introduced; if step 4 finds any, route them back to the originating task (T01–T04) for fix.

This task is verification-only — no source files modified. The output is the slice summary doc and updated checkboxes on the slice plan.

## Inputs

- ``frontend/src/pages/parts/PartsCatalog.tsx``
- ``frontend/src/components/parts/PartsFilterSidebar.tsx``
- ``frontend/src/components/parts/PartsActiveFilterChips.tsx``
- ``frontend/src/components/parts/PartList.tsx``
- ``frontend/src/components/parts/AddToBuildListDialog.tsx``
- ``frontend/e2e/parts-catalog.spec.ts``

## Expected Output

- ``.gsd/milestones/M002/slices/S10/S10-SUMMARY.md``

## Verification

cd frontend && npm run type-check && npm run test -- PartsCatalog PartList AddToBuildListDialog && npm run test:e2e -- parts-catalog price-history components && grep -r "from '../../components/common/Input'" src/pages/parts/PartsCatalog.tsx; if [ $? -ne 1 ]; then exit 1; fi && grep -r "from '../buttons/ActionButton'\|from '../buttons/SecondaryButton'\|from '../common/Dialog'" src/components/parts/PartList.tsx src/components/parts/AddToBuildListDialog.tsx; if [ $? -ne 1 ]; then exit 1; fi
