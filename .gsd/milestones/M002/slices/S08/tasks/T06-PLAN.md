---
estimated_steps: 19
estimated_files: 3
skills_used: []
---

# T06: Configure Playwright multi-viewport projects and ship components.spec.ts visual-regression suite

Slice's objective stopping condition (R013, D006). Updates `playwright.config.ts` to declare three viewport projects, then writes `e2e/components.spec.ts` that visits the kitchen sink at each breakpoint, settles state, and runs `toHaveScreenshot()`.

**playwright.config.ts changes:**
- Replace the single `chromium` project with three: `mobile` (375×667, iPhone SE), `tablet` (768×1024, iPad), `desktop` (1280×800, Desktop Chrome). Each entry uses `...devices['<name>']` overrides only where needed; viewport explicitly set to the listed dimensions.
- Add `expect.toHaveScreenshot.maxDiffPixelRatio: 0.002` (0.2%, per R013) and `expect.toHaveScreenshot.animations: 'disabled'`.
- Keep `webServer` block (already present) and `baseURL` (already present).
- Bump `timeout` per test to 30_000ms to absorb slow first-paint on cold dev server.

**e2e/components.spec.ts:**
- Single test: `'kitchen-sink visual regression'` per project.
- `await page.goto('/_kitchen-sink')`.
- `await page.waitForLoadState('networkidle')`.
- `await page.evaluate(() => document.fonts.ready)` so font metric is stable across runs.
- A small `await page.waitForTimeout(300)` to let toast/dropdown/dialog enter animations settle (animations are disabled in expect, but mount-time effects need a tick).
- `await expect(page).toHaveScreenshot({ fullPage: true })` — Playwright auto-keys snapshot by project name, producing `components.spec.ts-snapshots/kitchen-sink-visual-regression-1-{mobile,tablet,desktop}-linux.png`.
- Listen for `pageerror`: `page.on('pageerror', err => { throw err; })` at top of test so any runtime React error surfaces.

**Baseline generation:** First task run will fail with 'no baseline'. Re-run with `--update-snapshots` to capture. Commit the resulting PNGs.

**Threat-surface considerations:** N/A — dev tooling.
**Failure modes:** flake from animations/fonts/network → mitigated above. Snapshot drift from minor anti-aliasing → 0.2% threshold.
**Negative tests:** Run with the kitchen sink intentionally broken (e.g. delete a primitive import) and confirm test fails with a clear error — not in CI but verified manually before shipping.
**Load profile:** Playwright runs serially per project; `webServer.reuseExistingServer` keeps dev startup amortized.

## Inputs

- ``frontend/playwright.config.ts``
- ``frontend/e2e/smoke.spec.ts``
- ``frontend/src/pages/_KitchenSink.tsx``
- ``frontend/src/App.tsx``

## Expected Output

- ``frontend/playwright.config.ts` (three projects, screenshot threshold, disabled animations)`
- ``frontend/e2e/components.spec.ts``
- ``frontend/e2e/components.spec.ts-snapshots/` (three baseline PNGs, one per project)`

## Verification

cd frontend && grep -q "name: 'mobile'" playwright.config.ts && grep -q "name: 'tablet'" playwright.config.ts && grep -q "name: 'desktop'" playwright.config.ts && grep -q 'maxDiffPixelRatio' playwright.config.ts && grep -q '_kitchen-sink' e2e/components.spec.ts && grep -q 'toHaveScreenshot' e2e/components.spec.ts && npm run test:e2e -- --update-snapshots > /tmp/s08-t06-snap.log 2>&1 && npm run test:e2e > /tmp/s08-t06-run.log 2>&1

## Observability Impact

On regression: Playwright writes `test-results/<test>-<project>/` with diff PNG, expected PNG, actual PNG, and trace.zip. `npm run test:e2e:ui` opens the trace viewer for interactive inspection. Any kitchen-sink runtime error surfaces via `pageerror` listener as a hard test failure with stack trace, not a silent screenshot mismatch.
