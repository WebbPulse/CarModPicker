---
sliceId: S12
uatType: artifact-driven
verdict: PASS
date: 2026-04-26T04:12:50Z
---

# UAT Result — S12

## Checks

| Check | Mode | Result | Notes |
|-------|------|--------|-------|
| TC1: Kitchen-sink renders every primitive in every state at all 3 viewports | runtime | PASS | Automated equivalent (per UAT spec): `npm run test:e2e` covered `e2e/components.spec.ts` kitchen-sink visual regression at mobile/tablet/desktop. Full suite returned 35 passed / 10 skipped. Visual baselines present at `frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-{mobile,tablet,desktop}-linux.png`. Live in-browser viewport-by-viewport visual inspection of every primitive state matrix is `NEEDS-HUMAN` — the screenshot baseline diff covers it for autonomous mode. |
| TC2: Grep guard fails the build on a future legacy import | artifact + runtime | NEEDS-HUMAN | Created temporary probe `frontend/src/__uat_probe__.tsx` containing `import Card from './components/common/Card';` (the actual legacy import shape used historically — verified via `git show 76c5ae8:frontend/src/App.tsx`) and ran `npm test -- --run no-legacy-primitives`. **The guard test PASSED** — i.e. did NOT fail on the probe. Inspection of `frontend/src/__tests__/no-legacy-primitives.test.ts` line 28 reveals regex `/from\s+['"](?:\.\.\/)+(?:common\|buttons)\//` requires (a) one or more `../` path segments (not `./`), and (b) the segment immediately after the `../` chain to be `common` or `buttons` — NOT `components/common` or `components/buttons`. Real legacy imports were of the form `./components/common/X` or `../components/common/X`, which the regex never matches. Probe was removed. **Guard regex is over-narrow and would not catch the legacy import shape it claims to enforce.** Codebase remains clean today (zero importers, both directories deleted) and the redundant ESLint rule (TC3) does correctly catch the patterns, but TC2 as written cannot be honestly marked PASS. Filing a follow-up to fix the regex (suggested: `/from\s+['"]\.{1,2}\/(?:[^'"\n]*\/)*(?:components\/)?(?:common\|buttons)\//`). |
| TC3: ESLint no-restricted-imports rule fires | runtime | PASS | Same probe as TC2 (`./components/common/Card` + `./components/buttons/Button` imports). `npm run lint` reported `no-restricted-imports` errors on lines 3 and 4 of the probe with the documented S12 message. After probe removal, lint baseline returned to MEM062 (108 errors / 52 warnings). Rule is configured in `frontend/eslint.config.js` on patterns `**/components/common/*` and `**/components/buttons/*`. |
| TC4: Profile page (densest C1 surface) — full interaction smoke | human-follow-up | NEEDS-HUMAN | Full-stack interactive smoke (login, manage-security dialog, tab order, save-changes loading state) requires backend running, an authenticated user, and human visual judgment. Automatable signals all green: type-check exit 0, 597 unit tests pass (Profile.test.tsx covered), no broken imports, new Dialog parent-owned-state pattern documented and applied uniformly per S12 SUMMARY. Manual smoke deferred to S13 milestone validation per UAT "Surfaces deferred to S13" section. |
| TC5: ViewPart (978 LOC, heaviest C2 page) — list + dialogs | human-follow-up | NEEDS-HUMAN | Live full-stack page with parts in catalog. Type-check + 597 vitest pass cover import correctness; ConfirmDialog adapter pattern documented in SUMMARY and exercised at multiple callsites. Visual + interactive verification (delete flow, AddToBuildList dialog, error path) requires real backend + human eyes. Deferred to S13 manual smoke. |
| TC6: Admin extraction-health (Tier D) on new design system | runtime | PASS | Automated equivalent (per UAT): `npm run test:e2e -- admin.spec` covered `admin extraction-health visual regression` and `extraction-health: keyboard Tab lands visible focus on a control` at all 3 viewports. Suite green (35 passed / 10 skipped overall). Manual data-driven inspection (111/111 compliance, per-tier heatmap correctness) is data-validation, not S12 UI-migration scope — covered by S04. |
| TC7: Authentication flow on new design system | human-follow-up | NEEDS-HUMAN | Login + register pages migrated (verified by type-check + grep + lint baseline + Login/Register/ExtensionAuth vitest suites green). GoogleAuthFlow dialogs use parent-owned-state pattern (S09-derived, applied per SUMMARY). Live e2e auth flow is not in the Playwright suite (auth pages excluded by design — listed in "Surfaces deferred"). Manual smoke deferred to S13. |
| TC8: Build-list / parts-catalog priority pages | runtime | PASS | Automated equivalent: `npm run test:e2e` covered `build-list.spec` (build-list detail visual regression, edit-dialog Escape close, tab order focus) and `parts-catalog.spec` (visual regression, add-to-build-list dialog focus + Escape, tab traversal to search input) at all 3 viewports. Both spec files green within the 35-passed total. Sparkline + PriceDeltaLine S06 components preserved through the sweep (verified by file presence + green vitest suites). |

## Additional verification gauntlet (per SUMMARY's Verification section)

| Gate | Mode | Result | Notes |
|------|------|--------|-------|
| Type-check | runtime | PASS | `cd frontend && npm run type-check` exit 0 (`tsc -b --noEmit` clean). |
| Unit/integration tests | runtime | PASS | `cd frontend && npm test -- --run` → 90 files / 597 tests pass / 0 failed in 6.21s. Includes `no-legacy-primitives.test.ts` (1 test pass). |
| E2E suite | runtime | PASS | `cd frontend && npm run test:e2e` → 35 passed / 10 skipped across mobile/tablet/desktop. All 7 spec files (components, build-list, parts-catalog, price-history, price-alerts, admin, smoke) green. |
| Lint baseline (MEM062) | runtime | PASS | `cd frontend && npm run lint` → 108 errors / 52 warnings = MEM062 baseline. Lint exits 1 because of pre-existing baseline; S12 introduced 0 new errors. 0 `no-restricted-imports` violations means the rule fired on nothing in real code. |
| Grep guard (raw shell) | artifact | PASS | `grep -rln 'components/common\|components/buttons' frontend/src/` returns only `frontend/src/__tests__/no-legacy-primitives.test.ts` (the self-referential allowlisted match). Zero real importers. |
| Legacy directory deletion | artifact | PASS | `test ! -d frontend/src/components/common` and `test ! -d frontend/src/components/buttons` both true. Confirmed via `ls frontend/src/components/` — neither directory exists. |
| Vitest grep-guard test correctness | artifact | FLAG (filed below) | The vitest test passes today only because no importers exist. The regex `/from\s+['"](?:\.\.\/)+(?:common\|buttons)\//` does not match the actual legacy import shape used historically (`./components/common/X` or `../components/common/X`), so TC2's "fail-the-build-on-a-future-legacy-import" guarantee is not honored by this layer. The ESLint rule (eslint.config.js no-restricted-imports) correctly catches both shapes — that is the layer that actually enforces R017. |

## Overall Verdict

PASS — All automatable surface checks (type-check, 597 vitests, 35 e2e, lint baseline, raw-grep guard, legacy directory deletion, ESLint TC3) pass. TC1/TC6/TC8 are PASS via their UAT-spec'd automated equivalents (Playwright at 3 viewports). TC4/TC5/TC7 are objectively NEEDS-HUMAN (deferred to S13 per the UAT's own "Surfaces deferred to S13" clause and the human-experience portions of the manual smoke). TC2 surfaces a real defect in the vitest grep-guard regex but does not compromise the codebase state today (ESLint TC3 covers, zero importers verified by raw-shell grep). R017 enforcement is intact at the ESLint layer; the vitest guard layer needs a regex fix as a follow-up. R020 accessibility patterns preserved (verified by Playwright keyboard/focus tests at 3 viewports).

## Notes

**TC2 follow-up filed:** The vitest grep guard at `frontend/src/__tests__/no-legacy-primitives.test.ts:28` uses regex `/from\s+['"](?:\.\.\/)+(?:common\|buttons)\//` which over-narrows on two axes: (1) requires `../` repeated (not `./`), and (2) requires `common`/`buttons` to appear immediately after the relative-path segments without an intervening `components/` directory. Historical legacy imports always had the form `./components/common/X` (verified via `git show 76c5ae8:frontend/src/App.tsx`). Recommended fix: extend the regex to `/from\s+['"]\.{1,2}\/(?:[^'"\n]*\/)*(?:common\|buttons)\//` or, more cleanly, key off the `components/(common|buttons)/` segment specifically. This is a defect in the secondary safety net only — the ESLint no-restricted-imports rule (verified PASS in TC3) is the primary enforcement and correctly catches both `./components/common/*` and `./components/buttons/*` patterns at PR-time. R017 remains satisfied operationally because (a) zero legacy importers exist today, (b) both directories are deleted, (c) ESLint catches future regressions.

**Surfaces explicitly deferred per UAT spec:** Tier A statics, Tier B auth (other than smoke-tested ones), Tier C1/C2 inner forms not screenshot-asserted, Tier D admin sub-pages other than AdminDashboard + ExtractionHealth. UAT itself documents these as "S13 milestone validation should pick up a manual smoke pass over these — type-check + lint + grep prove imports are correct; visual polish verification benefits from human eyeball." Marking those test cases as NEEDS-HUMAN is consistent with that spec.

**Evidence captured:**
- type-check stdout: empty (clean exit 0).
- vitest stdout final: `Test Files  90 passed (90) / Tests  597 passed (597) / Duration 6.21s`.
- e2e stdout final: `10 skipped / 35 passed (17.1s)` — full per-spec-per-viewport list captured in background job log.
- lint final: `✖ 160 problems (108 errors, 52 warnings)` = MEM062 baseline; exit 1 expected.
- ESLint TC3 probe: 2 `no-restricted-imports` errors fired with documented S12 message; cleared after probe removal.
- Raw shell grep: only self-referential match in guard test file.
- Legacy directories: both confirmed absent on disk.
