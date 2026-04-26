---
id: T06
parent: S05
milestone: M003
key_files:
  - frontend/e2e/polish-coverage.spec.ts
  - frontend/e2e/polish-coverage.spec.ts-snapshots/ (120 PNG baselines)
  - frontend/e2e/tsconfig.json
  - frontend/src/test/route-coverage-list.ts
  - frontend/src/App.coverage.test.tsx
  - .gsd/milestones/M003/slices/S05/S05-SUMMARY.md
key_decisions:
  - Extracted ALL_ROUTES + RouteGroup to frontend/src/test/route-coverage-list.ts as the single source of truth, and added '../src/test/route-coverage-list.ts' to frontend/e2e/tsconfig.json's include array so both vitest (App.coverage.test.tsx) and Playwright (polish-coverage.spec.ts) consume the same list. Cleaner than re-exporting from a .test.tsx file; preserves the App.coverage.test.tsx drift-guard semantics (vitest assertion ALL_ROUTES.length >= 38) with zero behavior change. Captured as MEM188.
  - polish-coverage.spec.ts uses one parametrized for-loop over ROUTES generating one test per route — Playwright runs each test under all 3 projects automatically, so 40 tests × 3 projects = 120 baselines. Avoids hand-rolling 120 test functions or coupling spec to project-name iteration.
  - mobile=375 (Playwright project) NOT 360 per MEM170/MEM179 — 360 is documented in the verdict table inline where it differs (UserManagement 11-col table, CrawlerAdmin tier-table) as the manual UAT signal only. The slice plan was explicit on this and called it out in T06's CRITICAL note.
  - Auth-guarded routes (builder group) visited as default unauthenticated user — the resulting redirect-to-login state is captured in the baseline. This locks the redirect behavior. The alternative (pre-authenticate via a fixture) was rejected to keep the spec stateless and avoid coupling to a backend test account. Routes with dynamic UUIDs render NotFound/error-boundary; baselines lock the error-state rendering per task plan Q5(b).
  - Setup pattern mirrors admin.spec.ts and price-alerts.spec.ts: pin Date.now() to fixed ISO + pre-accept cookie_consent_v1 + pre-dismiss chrome-extension promo BEFORE goto, networkidle capped at 8s with domcontentloaded fallback, document.fonts.ready + 300ms settle. Captured as MEM189.
  - Cascade-refresh outcome was zero non-polish-coverage baselines drifted (35 prior baselines all matched). Per MEM156/MEM160 this is the desired pixel-equivalent migration outcome — T02-T05's tokenized class swaps resolved through the existing semantic-token vocabulary to byte-identical screenshots within the existing spec coverage. Consistent with S04 smoke.spec.ts null-result and S02 MEM169 zero-baseline-drift expectation.
duration: 
verification_result: passed
completed_at: 2026-04-27T01:10:30.168Z
blocker_discovered: false
---

# T06: feat: Add polish-coverage.spec.ts with 120 PNG baselines (40 routes × 3 viewports), extract shared ROUTES module, write S05-SUMMARY.md verdict table

**feat: Add polish-coverage.spec.ts with 120 PNG baselines (40 routes × 3 viewports), extract shared ROUTES module, write S05-SUMMARY.md verdict table**

## What Happened

Wave C close for S05. Three deliverables landed atomically: (1) the new visual-regression spec, (2) the shared ROUTES module that backs both vitest and Playwright, (3) the per-page verdict table.

**Shared ROUTES module + tsconfig wiring:** The slice plan said "import the route list from frontend/src/App.coverage.test.tsx (re-export ROUTES if needed)". The cleaner shape was extracting `ALL_ROUTES` + `RouteGroup` to `frontend/src/test/route-coverage-list.ts` and updating `frontend/e2e/tsconfig.json`'s include array to add `../src/test/route-coverage-list.ts` (the e2e tsconfig only included `./**/*.ts` + `../playwright.config.ts` and excluded `src/**` by design). This preserves the App.coverage.test.tsx drift-guard semantics with zero behavior change while making the list importable from the e2e Playwright tsconfig. Captured as MEM188.

**polish-coverage.spec.ts:** Parametrized loop over the shared ROUTES list — for each route, one `test()` that runs across all 3 Playwright projects (mobile=375 / tablet=768 / desktop=1280 per playwright.config.ts), producing N×3 = 120 baselines per `--update-snapshots` seed run. Setup mirrors admin.spec.ts / price-alerts.spec.ts (MEM098/MEM103/MEM108/MEM109): pin Date.now() to a fixed ISO + addInitScript pre-accepts cookie_consent_v1 + addInitScript pre-dismisses chrome-extension promo for today, all BEFORE goto so the bottom-pinned banners don't pollute mobile baselines. Captured as MEM189. `networkidle` capped at 8s with a `domcontentloaded` fallback for routes that poll (admin pages with health checks). `document.fonts.ready` + 300ms tail for visual stability. fullPage screenshot with `maxDiffPixelRatio: 0.01` to absorb sub-pixel font/AA noise.

CRITICAL: per MEM170/MEM179, polish-coverage.spec.ts uses the mobile=375 Playwright project (NOT 360); 360 is documented in the verdict table as the manual UAT signal only. Slug helper makes snapshot filenames readable (`/admin/extraction-health` → `admin-extraction-health.png`).

**Auth-guarded routes:** builder group (/profile, /builder, /my-parts, /checkout, /account/alerts, /verify-email) is visited as the default unauthenticated user and the resulting redirect-to-login state is captured in the baseline. This locks the redirect behavior; a regression that breaks the redirect surfaces as a PNG diff. The alternative (pre-authenticate via a fixture) was rejected to keep the spec stateless and avoid coupling to a backend test account. Routes with dynamic UUIDs (/parts/some-part, /build-lists/00000000-..., /user/00000000-..., /car-generations/some-car) are not real records; the API returns 404 and the page renders its NotFound / error-boundary state — baselines lock that error-state rendering per task plan Q5(b).

**Cascade refresh per MEM176:** Ran the full Playwright suite with `--update-snapshots` once at end-of-slice. Per MEM156/MEM160 default `=changed` mode, only baselines that pixel-differ from the on-disk snapshots are rewritten. Outcome: zero non-polish-coverage baselines drifted. Polish-coverage produced 120 new baselines (none existed prior); the 35 prior baselines across admin / build-list / components / parts-catalog / price-alerts / price-history / smoke specs all matched their on-disk snapshots after T02-T05's polish edits. This is the desired pixel-equivalent migration outcome (consistent with S04's smoke.spec.ts null-result and S02's MEM169 zero-baseline-drift expectation): T02-T05's tokenized class swaps resolved through the existing semantic-token vocabulary to byte-identical screenshots within the existing spec coverage. Final clean Playwright pass (no `--update-snapshots`): 155 passed / 10 skipped / 0 failed across 6 specs at 3 viewports.

**S05-SUMMARY.md:** Per-route × per-viewport verdict table with 40 rows × 3 viewport columns covering every production route. Verdict legend: pass / fixed / acceptable-as-scroll / deferred-to-S06. Explicit Deferrals section listing the 6 high-impact IA decisions punted to S06 UAT (auth-shell unification, ContactUs 3-card collapse, BuildListsCatalog sidebar drawer, ViewBuildLog markdown-prose plugin, UserManagement 11-col table responsive strategy, SystemAdmin DangerActionPanel extraction) with file paths and 1-2 sentence rationale per decision. 12 S04 standing gates (7 grep + 5 toolchain) re-verified at zero hits and exit 0 in a dedicated table. Cascade-refresh review note per MEM148. Files Created/Modified section enumerates all 40+ files touched across T01-T06.

**Verification:** type-check exit 0, lint exit 0 (zero errors, well under MEM062 baseline of 108), vitest 594/594 across 90 files in 5.35s, vite build 4.37s + prerender 7 routes 11.0s, polish-coverage.spec.ts 120/120 passed in 42s, full Playwright suite 155 passed / 10 skipped / 0 failed in ~49s. App.coverage.test.tsx vitest 41 tests passed after the import refactor.

Slice S05 closes the M003 polish-pass surface against the clean post-S04 substrate. Downstream slice S06 (close gauntlet + UAT) inherits 33 newly-baselined routes via polish-coverage.spec.ts (giving R061's close gauntlet visual signal across all routes, not just the 6 with prior coverage), the structured per-page verdict list, the 4 new ui/* primitives as canonical-import targets, and 6 explicitly-punted IA decisions ready for human resolution.

## Verification

All slice-level verification gates green from /home/tyler-webb/Documents/Github/CarModPicker/.gsd/worktrees/M003/frontend:

1. polish-coverage.spec.ts seed: `npx playwright test polish-coverage.spec.ts --update-snapshots` → exit 0, 120 passed in 42s, 120 PNG baselines created under e2e/polish-coverage.spec.ts-snapshots/ (verified `ls e2e/polish-coverage.spec.ts-snapshots/ | wc -l` = 120).
2. Cascade refresh: `npx playwright test --update-snapshots` → exit 0, 155 passed / 10 skipped / 0 failed across 6 specs in 48.6s; only the 120 polish-coverage baselines were written, the 35 prior baselines were unchanged (per MEM156/MEM160 default `=changed` mode).
3. Final clean Playwright pass: `npx playwright test` → exit 0, 155 passed / 10 skipped / 0 failed in 49.2s — proves all baselines match.
4. Type-check: `npm run type-check` → exit 0 (tsc -b --noEmit clean, including the e2e tsconfig with the new ../src/test/route-coverage-list.ts include).
5. Lint: `npm run lint` → exit 0 (zero ESLint errors, well under MEM062 baseline of 108).
6. Vitest: `npm test -- --run` → exit 0, 594/594 tests across 90 files in 5.35s. App.coverage.test.tsx (41 tests) passes after the ALL_ROUTES import refactor.
7. Vite build: `npm run build` → exit 0, vite built in 4.37s + prerender 7 routes in 11.0s.
8. 7 grep gates re-run from the worktree root, all exit 1 (zero hits, the desired outcome): S01 raw-palette, S01 text-accent, S02 glass class, S02 className glass, S02 var legacy, S04 consumer-class, S04 index.css self-inspection.
9. S05-SUMMARY.md exists at .gsd/milestones/M003/slices/S05/S05-SUMMARY.md with the 40-row × 3-viewport verdict table, the Deferrals section listing 6 IA decisions with file paths, the 12-gate close-gauntlet table, the cascade-refresh review note per MEM148, and Files Created/Modified covering all 40+ files touched across T01-T06.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npx playwright test polish-coverage.spec.ts --update-snapshots` | 0 | ✅ pass | 42000ms |
| 2 | `npx playwright test --update-snapshots` | 0 | ✅ pass | 48600ms |
| 3 | `npx playwright test` | 0 | ✅ pass | 49200ms |
| 4 | `npm run type-check` | 0 | ✅ pass | 15000ms |
| 5 | `npm run lint` | 0 | ✅ pass | 10000ms |
| 6 | `npm test -- --run` | 0 | ✅ pass | 5350ms |
| 7 | `npm run build` | 0 | ✅ pass | 15400ms |
| 8 | `rg '(text|bg|border|ring|from|to|via)-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` | 1 | ✅ pass (zero hits) | 300ms |
| 9 | `rg 'text-accent-(emerald|amber|rose|purple)' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` | 1 | ✅ pass (zero hits) | 300ms |
| 10 | `rg 'glass-(card|button)?' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` | 1 | ✅ pass (zero hits) | 300ms |
| 11 | `rg 'className=.*\bglass\b' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` | 1 | ✅ pass (zero hits) | 300ms |
| 12 | `rg 'var\(--(primary|neutral|accent|gradient)-' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` | 1 | ✅ pass (zero hits) | 300ms |
| 13 | `rg '\b(btn-primary|btn-secondary|btn-outline|input-modern|card-interactive|card-table-container|skeleton|hero-gradient|shadow-glow|border-gradient)\b' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` | 1 | ✅ pass (zero hits) | 300ms |
| 14 | `rg -c '@theme|--primary-[0-9]|\.glass-card|\.btn-primary|\.card-interactive|\.input-modern|\.text-gradient|\.shadow-glow|\.border-gradient|\.skeleton|\.hero-gradient' frontend/src/index.css` | 1 | ✅ pass (zero hits) | 50ms |
| 15 | `ls e2e/polish-coverage.spec.ts-snapshots/ | wc -l` | 0 | ✅ pass (120 baselines) | 50ms |

## Deviations

"Extracted ROUTES to a dedicated shared module (frontend/src/test/route-coverage-list.ts) instead of re-exporting from App.coverage.test.tsx. The slice plan said 're-export ROUTES if needed' but importing from a `.test.tsx` file (which is excluded from production bundles) is a smell, and the e2e tsconfig didn't include `src/**` so a direct cross-tsconfig import wouldn't compile. The cleaner shape is one shared module + one explicit include entry in frontend/e2e/tsconfig.json. Captured as MEM188 for future cross-tsconfig sharing needs."

## Known Issues

"Auth-guarded route coverage is the redirect target (typically /login), not the protected page itself — by design, since the spec is stateless. Domain-specific specs (admin.spec.ts) and existing vitest cover the protected-page render under authenticated state. Routes with dynamic UUIDs render their NotFound/error-boundary state; baselines lock that. Mobile=375 vs 360 manual UAT (MEM170/MEM179) — Playwright at 375 is not a substitute for the 360px overflow check; verdict table flags `acceptable-as-scroll` for known cases. Total disk footprint is 120 PNG baselines (~low single-digit MB) — meaningful but acceptable per slice plan. Future spec consolidation (e.g. dedupe with admin.spec.ts coverage of /admin and /admin/extraction-health) listed as a follow-up in S05-SUMMARY.md."

## Files Created/Modified

- `frontend/e2e/polish-coverage.spec.ts`
- `frontend/e2e/polish-coverage.spec.ts-snapshots/ (120 PNG baselines)`
- `frontend/e2e/tsconfig.json`
- `frontend/src/test/route-coverage-list.ts`
- `frontend/src/App.coverage.test.tsx`
- `.gsd/milestones/M003/slices/S05/S05-SUMMARY.md`
