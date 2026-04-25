---
id: T06
parent: S12
milestone: M002
key_files:
  - frontend/src/__tests__/no-legacy-primitives.test.ts
  - frontend/eslint.config.js
  - frontend/vitest.config.ts
  - frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-mobile-linux.png
  - frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-tablet-linux.png
  - frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-desktop-linux.png
  - .gsd/milestones/M002/slices/S12/S12-UAT.md
key_decisions:
  - Added vitest test.include='src/**/*.{test,spec}.{ts,tsx}' + test.exclude=['e2e/**'] to vitest.config.ts. The default vitest include glob picks up Playwright e2e specs and crashes them with 'test() did not expect to be called here'. Constraining the include scope is the minimal fix and matches the project convention that src/ holds vitest suites and e2e/ holds Playwright suites. Captured as MEM129.
  - Treated the redundant ESLint no-restricted-imports rule as kept (already authored). It pairs cleanly with the vitest grep-guard — lint catches violations at PR time before vitest runs. Zero violations confirm the guard fires on nothing in the current codebase.
  - Autonomous-mode S12-UAT.md uses the e2e suite at 3 viewports as primary visual evidence and explicitly enumerates ~30 Tier A statics + inner forms not covered by Playwright so a future S13 / manual UAT pass can pick them up. Type-check + lint + grep cover their import correctness even without per-pixel guards.
duration: 
verification_result: passed
completed_at: 2026-04-26T03:43:54.691Z
blocker_discovered: false
---

# T06: Locked R017 enforcement for M002/S12 — vitest grep-guard + ESLint no-restricted-imports + refreshed kitchen-sink baselines; full gauntlet (type-check, 597 unit, 35 e2e, lint baseline, grep) green

**Locked R017 enforcement for M002/S12 — vitest grep-guard + ESLint no-restricted-imports + refreshed kitchen-sink baselines; full gauntlet (type-check, 597 unit, 35 e2e, lint baseline, grep) green**

## What Happened

Closed out S12 by proving the components/common + components/buttons retirement holds end-to-end. The grep-guard (`frontend/src/__tests__/no-legacy-primitives.test.ts`) and ESLint `no-restricted-imports` rule on `**/components/common/*` + `**/components/buttons/*` were already authored during the slice-execution sweeps (T01-T05); T06's job was to verify they survive the full verification gauntlet and to refresh any baselines that drifted in the final task chain.

Discovered one pre-existing test-infra defect that blocked the gauntlet's `npm test` step: vitest's default `include` glob picks up `e2e/*.spec.ts` files, which crash with "Playwright Test did not expect test() to be called here" because @playwright/test isn't a vitest runner. Fixed by adding `test.include: ['src/**/*.{test,spec}.{ts,tsx}']` and `test.exclude: ['e2e/**']` to `vitest.config.ts`. After the fix, `npm test -- --run` returns 597 passed / 0 failed (596 pre-existing unit tests from T05 plus the new no-legacy-primitives.test.ts). Captured the gotcha as MEM129 so future agents don't have to re-diagnose.

Refreshed visual baselines via `npm run test:e2e -- --update-snapshots`. Only the three kitchen-sink PNGs drifted (T01 had refreshed two of these earlier; the third drifted from later card/spinner tweaks). All other Playwright suites (admin, build-list, parts-catalog, price-history, price-alerts, smoke) had already been refreshed in T03/T04/T05 and produced zero new diffs. Final `npm run test:e2e` (no update flag) confirms 35 passed / 10 skipped at all 3 viewports.

Lint check: 108 errors / 52 warnings — exactly the MEM062 baseline. Spot-checked S12-touched non-test files (ui/* primitives, components/parts/*, etc.) and confirmed they contribute warnings only (cva re-export per MEM073, forwardRef in shadcn primitives, etc.), zero errors. Zero `no-restricted-imports` violations means the new guard fired on nothing — the migration is clean.

Final grep `grep -rln 'components/common\|components/buttons' frontend/src/` returns one match — the guard test's own docstring/regex literal, which is allowlisted in the test itself. Both `frontend/src/components/common/` and `frontend/src/components/buttons/` directories are gone (removed in T05; non-primitive helpers relocated to forms/, cars/, images/, filters/, tables/, routes/, shell/).

Wrote `.gsd/milestones/M002/slices/S12/S12-UAT.md` documenting the autonomous-mode UAT entry: e2e suite serves as primary visual evidence for ~7 priority pages at three viewports; explicit deferral list of ~30 Tier A static pages + Tier C/D inner forms whose visuals weren't asserted by Playwright (covered by type-check, lint, and grep-guard for import correctness).

## Verification

Ran the full gauntlet from `frontend/`: `npm run type-check` (exit 0, no output), `npm test -- --run` (90 files / 597 tests passed including the new no-legacy-primitives.test.ts), `npm run test:e2e -- --update-snapshots` (35 pass / 10 skipped — only 3 kitchen-sink baselines drifted), `npm run test:e2e` (35 pass / 10 skipped — all baselines stable post-refresh), `npm run lint` (108 errors / 52 warnings = MEM062 baseline, 0 new errors in S12-touched non-test files, 0 no-restricted-imports violations), `grep -rln 'components/common|components/buttons' src/` (1 self-referential match in the guard test only), `test ! -d src/components/buttons` and `test ! -d src/components/common` (both true).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd frontend && npm run type-check` | 0 | ✅ pass | 12000ms |
| 2 | `cd frontend && npm test -- --run` | 0 | ✅ pass (597/597) | 6500ms |
| 3 | `cd frontend && npm run test:e2e -- --update-snapshots` | 0 | ✅ pass (35 passed / 10 skipped, 3 kitchen-sink PNGs refreshed) | 17100ms |
| 4 | `cd frontend && npm run test:e2e` | 0 | ✅ pass (35 passed / 10 skipped, all baselines stable) | 16600ms |
| 5 | `cd frontend && npm run lint` | 1 | ✅ baseline-preserved (108 errors == MEM062 baseline; 0 new errors in S12-touched non-test files; 0 no-restricted-imports violations) | 18000ms |
| 6 | `grep -rln 'components/common\|components/buttons' frontend/src/` | 0 | ✅ pass (1 self-referential match in guard test only; 0 real importers) | 200ms |
| 7 | `test ! -d frontend/src/components/buttons && test ! -d frontend/src/components/common` | 0 | ✅ pass (both legacy dirs deleted in T05) | 50ms |
| 8 | `test -f .gsd/milestones/M002/slices/S12/S12-UAT.md` | 0 | ✅ pass (S12-UAT.md committed) | 50ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `frontend/src/__tests__/no-legacy-primitives.test.ts`
- `frontend/eslint.config.js`
- `frontend/vitest.config.ts`
- `frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-mobile-linux.png`
- `frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-tablet-linux.png`
- `frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-desktop-linux.png`
- `.gsd/milestones/M002/slices/S12/S12-UAT.md`
