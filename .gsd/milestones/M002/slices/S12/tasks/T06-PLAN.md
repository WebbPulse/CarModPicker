---
estimated_steps: 3
estimated_files: 9
skills_used: []
---

# T06: Add CI grep-guard test, refresh visual baselines, run final verification gauntlet

With the migration complete, R017's enforcement gate ('via lint rule or grep check') needs a committed test that fails the build if any future PR re-imports from components/common/ or components/buttons/. With every page reskinned, every Playwright spec that screenshots a touched page will produce pixel diffs vs the legacy baselines (per MEM113 / MEM115) — the baseline-refresh sweep is part of THIS slice, not a follow-up. The final gauntlet proves R017 is met and R020 is preserved.

Do: (a) Write frontend/src/__tests__/no-legacy-primitives.test.ts — a vitest test that walks frontend/src/ recursively (excluding components/common/, components/buttons/, __tests__/, node_modules/, dist/, coverage/), reads each .ts/.tsx file, and asserts no file matches the regex from\s+['\"](?:\\.\\.\\/)+(?:common|buttons)/. Document the WHY in a JSDoc block referencing R017 and the M002/S12 slice. (b) Augment frontend/eslint.config.js with a no-restricted-imports rule for components/common/* and components/buttons/* patterns (optional — redundant safety; only add if it doesn't introduce new errors against the MEM062 baseline). (c) Refresh visual baselines: cd frontend && npm run test:e2e -- --update-snapshots. Inspect the resulting PNG diffs to ensure they look correct (no overflow, no wrong color, no missing component); commit the refreshed baselines only after sanity-check. (d) Run the full gauntlet: npm run type-check (exit 0); npm test -- --run (exit 0, including the new no-legacy-primitives.test.ts); npm run test:e2e (exit 0, all 7 specs across 3 viewports); npm run lint (no NEW errors in S12-touched files vs MEM062 baseline of ~108); ! grep -rln 'components/common\\|components/buttons' frontend/src/ (zero hits); test ! -d frontend/src/components/buttons (true). (e) Write .gsd/milestones/M002/slices/S12/S12-UAT.md recording the manual smoke status — autonomous-mode entry: e2e suite served as evidence; if e2e doesn't cover a page (Tier A statics like ContactUs, Pricing, Checkout, Support), list it explicitly so S13 can pick it up.

Must-haves: no-legacy-primitives.test.ts is in npm test's output and is GREEN; full e2e suite green at all 3 viewports with refreshed baselines committed; type-check green; lint baseline preserved (no new errors in S12-touched files); grep returns zero hits; buttons/ directory gone; S12-UAT.md committed.

## Inputs

- ``frontend/src/components/common/` — directory; T06 verifies it contains only relocation-target stubs we intentionally keep (or is empty).`
- ``frontend/src/components/buttons/` — directory; T06 verifies it does not exist.`
- ``frontend/playwright.config.ts` — three-viewport projects + 0.2% threshold drive the baseline-refresh sweep.`
- ``frontend/e2e/components.spec.ts` — kitchen-sink visual regression (T01 already refreshed; verify still green).`
- ``frontend/e2e/build-list.spec.ts` — S09 build-list visual regression; baseline likely needs refresh after T04.`
- ``frontend/e2e/parts-catalog.spec.ts` — S10 parts-catalog visual regression; baseline likely needs refresh after T04.`
- ``frontend/e2e/price-history.spec.ts` — S06 price-history visual regression; refreshed in S10/T05; may need re-refresh after T04 PartList changes.`
- ``frontend/e2e/price-alerts.spec.ts` — S07 price-alerts visual regression; baseline likely needs refresh after T03 AccountAlerts migration.`
- ``frontend/e2e/admin.spec.ts` — S11 admin visual regression; baseline likely needs refresh after T05 admin sweep.`
- ``frontend/eslint.config.js` — existing eslint config; optional augmentation.`

## Expected Output

- ``frontend/src/__tests__/no-legacy-primitives.test.ts` — new vitest grep-guard test.`
- ``frontend/eslint.config.js` — optionally augmented with no-restricted-imports rule.`
- ``frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-mobile-linux.png` — possibly refreshed.`
- ``frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-tablet-linux.png` — possibly refreshed.`
- ``frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-desktop-linux.png` — possibly refreshed.`
- ``frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-mobile-linux.png` — refreshed.`
- ``frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-tablet-linux.png` — refreshed.`
- ``frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-desktop-linux.png` — refreshed.`
- ``frontend/e2e/parts-catalog.spec.ts-snapshots/parts-catalog-visual-regression-1-mobile-linux.png` — refreshed.`
- ``frontend/e2e/parts-catalog.spec.ts-snapshots/parts-catalog-visual-regression-1-tablet-linux.png` — refreshed.`
- ``frontend/e2e/parts-catalog.spec.ts-snapshots/parts-catalog-visual-regression-1-desktop-linux.png` — refreshed.`
- ``frontend/e2e/price-history.spec.ts-snapshots` — refreshed PNGs as needed.`
- ``frontend/e2e/price-alerts.spec.ts-snapshots` — refreshed PNGs as needed.`
- ``frontend/e2e/admin.spec.ts-snapshots` — refreshed PNGs as needed.`
- ``.gsd/milestones/M002/slices/S12/S12-UAT.md` — manual UAT record (autonomous-mode entry per slice plan).`

## Verification

cd frontend && npm run type-check && npm test -- --run && npm run test:e2e && ! grep -rln 'components/common\|components/buttons' src/ && test ! -d src/components/buttons && test -f ../.gsd/milestones/M002/slices/S12/S12-UAT.md
