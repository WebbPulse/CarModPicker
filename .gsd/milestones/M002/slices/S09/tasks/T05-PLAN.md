---
estimated_steps: 10
estimated_files: 1
skills_used: []
---

# T05: Slice-level verification sweep and evidence capture

Final cross-task verification that the slice goal is met. Run the full local test gauntlet from frontend/, capture exit codes, spot-check the page in dev, and make sure no regressions slipped into adjacent areas.

Steps:
  1. cd frontend && npm run type-check — must exit 0.
  2. cd frontend && npm run test -- ViewBuildlist BuildListParts confirm-dialog — must exit 0 (vitest passes for the directly-touched units).
  3. cd frontend && npm run test:e2e -- build-list components — must exit 0; build-list runs 3/3 + 1 desktop-only keyboard-focus test, components.spec still 3/3 (no token regression from confirm-dialog).
  4. cd frontend && npm run lint 2>&1 | tail -1 — capture the error count. MUST equal the existing 104-error baseline (MEM062). Any net-new error in src/components/ui/confirm-dialog.tsx, src/pages/builder/ViewBuildlist.tsx, src/components/buildListParts/BuildListParts.tsx, src/components/buildListParts/EditBuildListPartForm.tsx, or e2e/build-list.spec.ts is a fail.
  5. Manual smoke (1 minute, document the result in slice summary): start dev server (cd frontend && npm run dev), navigate to /build-lists/{any real id from local DB}, visually confirm the page renders on the new dark token palette, click Edit, press Escape, click Add Part, click Cancel, confirm focus rings visible on all action buttons under keyboard Tab.
  6. grep -r "from '../../components/common/Dialog'\|from '../../components/common/DeleteConfirmationDialog'\|from '../../components/buttons/ActionButton'" src/pages/builder/ViewBuildlist.tsx src/components/buildListParts/ — must return 0 hits (slice goal closure check).
  7. Confirm no new pre-commit lint errors introduced; if step 4 finds any, route them back to the originating task (T01–T03) for fix.

This task is verification-only — no source files modified.

## Inputs

- ``frontend/src/components/ui/confirm-dialog.tsx``
- ``frontend/src/pages/builder/ViewBuildlist.tsx``
- ``frontend/src/components/buildListParts/BuildListParts.tsx``
- ``frontend/src/components/buildListParts/EditBuildListPartForm.tsx``
- ``frontend/e2e/build-list.spec.ts``

## Expected Output

- ``.gsd/milestones/M002/slices/S09/S09-SUMMARY.md``

## Verification

cd frontend && npm run type-check && npm run test -- ViewBuildlist BuildListParts confirm-dialog && npm run test:e2e -- build-list components && grep -r "from '../../components/common/Dialog'\|from '../../components/common/DeleteConfirmationDialog'\|from '../../components/buttons/ActionButton'" src/pages/builder/ViewBuildlist.tsx src/components/buildListParts/ | wc -l | grep -q '^0$'

## Observability Impact

Verification evidence (exit codes, lint baseline delta, manual UAT note) captured into the slice summary so a future agent rebuilding the milestone audit can see what was actually run versus what was planned.
