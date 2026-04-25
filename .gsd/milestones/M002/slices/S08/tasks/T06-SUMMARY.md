---
id: T06
parent: S08
milestone: M002
key_files:
  - frontend/playwright.config.ts
  - frontend/e2e/components.spec.ts
  - frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-mobile-linux.png
  - frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-tablet-linux.png
  - frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-desktop-linux.png
key_decisions:
  - Used `...devices['Desktop Chrome']` for all three projects with explicit viewport overrides instead of the iPhone SE / iPad presets. The mobile/tablet device descriptors default to webkit, which would have rendered cross-engine pixel diffs vs the chromium desktop baseline. All three projects now share the chromium engine — the only variable is viewport. Captured as MEM066.
  - Added `timeout: 30_000` at the top-level config (not just per-test) to absorb cold-start latency on the dev server's first paint. The plan called for 30s 'per test'; setting it at the config level applies to every test in every project, which matches the intent.
  - Kept the existing `smoke.spec.ts` in the suite. It now runs across all three viewport projects (3 extra runs), but the homepage check is cheap and gives free smoke coverage at every breakpoint.
duration: 
verification_result: passed
completed_at: 2026-04-25T19:42:30.520Z
blocker_discovered: false
---

# T06: Configure Playwright multi-viewport projects and ship components.spec.ts visual-regression suite with three baseline PNGs.

**Configure Playwright multi-viewport projects and ship components.spec.ts visual-regression suite with three baseline PNGs.**

## What Happened

Replaced the single `chromium` project in `frontend/playwright.config.ts` with three viewport projects — `mobile` (375×667), `tablet` (768×1024), and `desktop` (1280×800) — each spreading `devices['Desktop Chrome']` and overriding only `viewport`. Added `expect.toHaveScreenshot.maxDiffPixelRatio: 0.002` (R013's 0.2% bar) and `animations: 'disabled'`, plus a per-test `timeout: 30_000` to absorb cold-start flake. The `webServer` and `baseURL` blocks were preserved.

Created `frontend/e2e/components.spec.ts` with a single `kitchen-sink visual regression` test that navigates to `/_kitchen-sink`, awaits `networkidle` and `document.fonts.ready`, sleeps 300ms for mount-time effects, then asserts `toHaveScreenshot({ fullPage: true })`. A `pageerror` listener at the top of the test re-throws any runtime React error so silent regressions surface as hard failures rather than pixel drift.

Generated baselines via `npm run test:e2e -- --update-snapshots`, then re-ran `npm run test:e2e` and confirmed all 6 tests pass (3 components.spec runs + 3 smoke.spec runs across the three projects). Three PNG baselines landed in `frontend/e2e/components.spec.ts-snapshots/` keyed by project name as expected.

Local adaptation: the task plan suggested `...devices['iPhone SE']` and `...devices['iPad']` overrides, but those device descriptors set `defaultBrowserType: 'webkit'`. Mixing webkit baselines for mobile/tablet with chromium for desktop would have produced cross-engine pixel diffs that no `maxDiffPixelRatio` could absorb. Used `Desktop Chrome` for all three projects with explicit `viewport` overrides — same chromium engine, just different sizes. Captured this as MEM066. Vite proxy errors for `/api/*` in the run logs are expected (no backend running) and do not affect the kitchen-sink page.

## Verification

Verified the chained grep + double `npm run test:e2e` invocation specified in the task plan: all six grep markers (`name: 'mobile'`, `name: 'tablet'`, `name: 'desktop'`, `maxDiffPixelRatio`, `_kitchen-sink`, `toHaveScreenshot`) match. `npm run test:e2e -- --update-snapshots` wrote three baseline PNGs and exited 0; the follow-up `npm run test:e2e` re-ran against those baselines and exited 0 with `6 passed (4.4s)`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `grep -q "name: 'mobile'" playwright.config.ts && grep -q "name: 'tablet'" playwright.config.ts && grep -q "name: 'desktop'" playwright.config.ts && grep -q 'maxDiffPixelRatio' playwright.config.ts && grep -q '_kitchen-sink' e2e/components.spec.ts && grep -q 'toHaveScreenshot' e2e/components.spec.ts` | 0 | ✅ pass | 50ms |
| 2 | `npm run test:e2e -- --update-snapshots` | 0 | ✅ pass | 16500ms |
| 3 | `npm run test:e2e` | 0 | ✅ pass | 9300ms |

## Deviations

Substituted `Desktop Chrome` for the suggested `iPhone SE` / `iPad` device presets on the mobile and tablet projects to avoid mixing webkit and chromium engines in one snapshot suite. Viewport dimensions match the plan exactly; only the engine selection changed.

## Known Issues

Vite proxy spams `ECONNREFUSED 127.0.0.1:8000` for `/api/app-settings/` and `/api/users/me` during the e2e run because no backend is running. These are visible in the test logs but do not affect the kitchen-sink page or the snapshots. If the noise becomes an issue in CI, the e2e harness could mock those routes via `page.route()` in a fixture; not pursued here because the kitchen-sink doesn't depend on backend data.

## Files Created/Modified

- `frontend/playwright.config.ts`
- `frontend/e2e/components.spec.ts`
- `frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-mobile-linux.png`
- `frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-tablet-linux.png`
- `frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-desktop-linux.png`
