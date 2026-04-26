---
id: T04
parent: S11
milestone: M002
key_files:
  - frontend/e2e/admin.spec.ts
  - frontend/e2e/admin.spec.ts-snapshots/admin-dashboard-1-mobile-linux.png
  - frontend/e2e/admin.spec.ts-snapshots/admin-dashboard-1-tablet-linux.png
  - frontend/e2e/admin.spec.ts-snapshots/admin-dashboard-1-desktop-linux.png
  - frontend/e2e/admin.spec.ts-snapshots/admin-extraction-health-1-mobile-linux.png
  - frontend/e2e/admin.spec.ts-snapshots/admin-extraction-health-1-tablet-linux.png
  - frontend/e2e/admin.spec.ts-snapshots/admin-extraction-health-1-desktop-linux.png
key_decisions:
  - Used compliant: 108, total: 108 from the explicit task-plan fixture (matches MEM037's canonical 108-adapter count) rather than the slice-plan goal-text 111/111 which appears aspirational; the fixture is the contract the test asserts against and 108 is what the backend currently returns.
  - Made coverage.per_tier.browser an empty tier (parts_total: 0) and included a rate=1.0 failure-rate row to exercise the empty/full rendering paths (Q7 negative tests) the happy-path data wouldn't, on top of the typical mid-rate row.
  - Wrote the keyboard-focus assertion as 'class contains "ring" OR computed outline/box-shadow non-empty' rather than asserting a specific testid is focused — the first Tab target depends on header structure (skip-link, logo, nav, Refresh button) and R020 is concerned with focus-ring visibility, not element identity. ui/Button's class includes 'focus-visible:ring-2 focus-visible:ring-ring' so the fast-path className check succeeds on Refresh; the computed-style fallback covers anchor/link controls.
duration: 
verification_result: passed
completed_at: 2026-04-26T00:17:27.183Z
blocker_discovered: false
---

# T04: test: Add Playwright e2e admin.spec.ts — multi-viewport visual regression for /admin and /admin/extraction-health plus desktop keyboard-focus assertion

**test: Add Playwright e2e admin.spec.ts — multi-viewport visual regression for /admin and /admin/extraction-health plus desktop keyboard-focus assertion**

## What Happened

Created `frontend/e2e/admin.spec.ts` modelled on `parts-catalog.spec.ts` (S10/T04) and `build-list.spec.ts` (S09/T04). The spec defines `MOCK_ADMIN_USER` (admin variant of the standard MOCK_USER shape with `is_admin: true`) and `MOCK_EXTRACTION_HEALTH` matching the backend `ExtractionHealthResponse` exactly — compliance 108/108 (T0:83 / T1:15 / T2:10), per-tier coverage with 2-3 fields per tier including an empty `browser` tier (parts_total: 0) to exercise the "—" empty-summary path, and a 7d failure-rate table with three rows spanning a 100% rate (rate=1.0), a typical 5% rate, and a zero-failure row. `Date.now()` is pinned to `FIXED_NOW_ISO=2026-04-25T12:00:00.000Z`.

`setupPage()` follows the established conventions: `page.addInitScript` writes `cookie_consent_v1=accepted` (MEM098/MEM103) and `chrome_extension_promo_last_dismissed=YYYY-MM-DD` for today (MEM108/MEM109) into localStorage so the bottom-pinned cookie banner and the 2s-delayed chrome-extension promo can't intercept clicks or race the snapshot. The `page.route()` matcher is the regex `/\/api\/(?!.*\.ts)/` (MEM082) so Vite source modules at `/src/api/*.ts` are not swallowed. The mock router handles `/users/me` (MOCK_ADMIN_USER), `/app-settings/`, both `/admin/extraction-health` and `/admin/extraction-health/` (FastAPI redirects the no-slash form), a defensive `/admin/*` GET fallthrough returning `{}`, and a default 404 with `Mock miss: {method} {path}` for visibility. `page.on('pageerror')` re-throws.

Three tests:
1. **`/admin` visual regression** — navigates, awaits networkidle + fonts.ready + 300ms, asserts the new "Extraction Health" entry card is visible (so a route-registration regression fails loudly), then `expect(page).toHaveScreenshot('admin-dashboard-1.png', { fullPage: true })`. Runs on all 3 viewport projects → 3 PNG baselines.
2. **`/admin/extraction-health` visual regression** — same shape, asserts the three `compliance-pill-{tier}` testids and `failure-rate-table` testid are visible before snapshotting → 3 more PNG baselines.
3. **Keyboard focus on `/admin/extraction-health`** — gated to `desktop` project via `test.skip(testInfo.project.name !== 'desktop', …)` (MEM105). Pre-focuses `document.body`, presses Tab once, asserts `:focus` is visible, and verifies a focus ring is present either via class-string contains "ring" (ui/Button uses `focus-visible:ring-2 focus-visible:ring-ring` per `frontend/src/components/ui/button.tsx:9`) OR via non-empty computed `outline`/`box-shadow` when `:focus-visible` matches.

Generated baselines via `npx playwright test admin.spec.ts --update-snapshots` (6 PNGs written under `frontend/e2e/admin.spec.ts-snapshots/`), then re-ran `npm run test:e2e -- admin.spec.ts`: 7 passed, 2 skipped (expected — keyboard test is desktop-only). Total runtime 4.9s.

**Decisions documented:** Used `compliant: 108, total: 108` per the explicit task-plan fixture; the slice plan goal text mentions "111/111" but that appears to be aspirational (matches MEM037's canonical 108-adapter count and the fixture in the task plan body). Defensive fallthrough `/admin/* GET → {}` was added because AdminDashboard renders pure navigation cards and shouldn't actually call any admin endpoint at /admin itself, but a future addition shouldn't crash the bundle. The keyboard focus assertion uses an OR-of-class-or-computed-style check rather than asserting a specific testid: the first Tab target depends on header structure (skip-link, logo, nav items), and what matters for R020 is "a focus ring is visible somewhere", not a specific element identity.

**Failure modes mitigated (Q5):** Vite source-module swallow via the regex matcher (MEM082); cookie banner click-intercept via cookie_consent_v1 init script (MEM098); chrome-extension promo race via promo_last_dismissed init script (MEM108/MEM109). **Load profile (Q6):** N/A — fully mocked. **Negative tests (Q7):** the empty-coverage browser tier (parts_total=0) and the 100% failure-rate row exercise the empty/full ratio rendering paths that the happy-path data wouldn't.

## Verification

Slice-level verification check from S11-PLAN: `cd frontend && npm run test:e2e -- admin.spec.ts` → 7 passed, 2 skipped (mobile/tablet keyboard tests skipped by design via `testInfo.project.name !== 'desktop'`), 4.9s. Baselines for both pages exist on disk at all 3 viewport projects (6 PNGs under `frontend/e2e/admin.spec.ts-snapshots/`). The first `--update-snapshots` run wrote them; the second run consumed them and produced zero pixel diffs at the configured `maxDiffPixelRatio: 0.002`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd frontend && npx playwright test admin.spec.ts --update-snapshots` | 0 | ✅ pass | 4900ms |
| 2 | `cd frontend && npm run test:e2e -- admin.spec.ts` | 0 | ✅ pass | 4900ms |
| 3 | `ls frontend/e2e/admin.spec.ts-snapshots/ | wc -l` | 0 | ✅ pass — 6 baselines (admin-dashboard-1 × {mobile,tablet,desktop}-linux + admin-extraction-health-1 × {mobile,tablet,desktop}-linux) | 50ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `frontend/e2e/admin.spec.ts`
- `frontend/e2e/admin.spec.ts-snapshots/admin-dashboard-1-mobile-linux.png`
- `frontend/e2e/admin.spec.ts-snapshots/admin-dashboard-1-tablet-linux.png`
- `frontend/e2e/admin.spec.ts-snapshots/admin-dashboard-1-desktop-linux.png`
- `frontend/e2e/admin.spec.ts-snapshots/admin-extraction-health-1-mobile-linux.png`
- `frontend/e2e/admin.spec.ts-snapshots/admin-extraction-health-1-tablet-linux.png`
- `frontend/e2e/admin.spec.ts-snapshots/admin-extraction-health-1-desktop-linux.png`
