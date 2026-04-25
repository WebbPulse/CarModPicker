---
estimated_steps: 9
estimated_files: 7
skills_used: []
---

# T04: Playwright admin.spec.ts — multi-viewport visual regression + keyboard focus

Create `frontend/e2e/admin.spec.ts` modelled on `frontend/e2e/parts-catalog.spec.ts`:

1. **Mock fixtures** — define `MOCK_ADMIN_USER` (same shape as MOCK_USER in parts-catalog.spec.ts but `is_admin: true, email_verified: true, subscription_tier: 'free'`), `MOCK_EXTRACTION_HEALTH` matching the backend `ExtractionHealthResponse` exactly: `compliance: { compliant: 108, total: 108, per_tier: { http: '83/83', tls: '15/15', browser: '10/10' } }`, `coverage.per_tier.{http,tls,browser}` with 2-3 sample fields each (e.g. `weight_grams: 0.42, material: 0.18`), `failure_rate_7d` with 3 sample rows across tiers, `window: { days: 7, since: FIXED_NOW_ISO_MINUS_7D }`. Pin `Date.now()` to `FIXED_NOW_ISO`.
2. **Setup helper** — `setupPage(page)`: `page.addInitScript` to pre-accept cookie consent (MEM098) AND pre-dismiss chrome-extension promo (MEM108 / parts-catalog.spec.ts:30 pattern); `page.route` matcher MUST be `/\/api\/(?!.*\.ts)/` (MEM082); handle paths `/users/me` (return MOCK_ADMIN_USER), `/app-settings` (existing pattern from other specs), `/admin/extraction-health` (return MOCK_EXTRACTION_HEALTH), and a fallthrough that fulfils 200 with `{}` for any unexpected admin endpoint hit (defensive). `page.on('pageerror')` re-throw.
3. **Test 1: `/admin` visual regression** — navigate, await networkidle + fonts.ready + 300ms, `expect(page).toHaveScreenshot({ fullPage: true })`. Will produce one baseline per viewport project (3 PNGs). Use `testInfo.project.name` in the snapshot identifier (auto-handled by `toHaveScreenshot`).
4. **Test 2: `/admin/extraction-health` visual regression** — same shape as Test 1 but on `/admin/extraction-health`. 3 more baseline PNGs.
5. **Test 3: keyboard focus on `/admin/extraction-health`** — `await page.keyboard.press('Tab')` once, assert focused element has a visible focus ring via `expect(page.locator(':focus')).toBeVisible()` and `expect(await page.locator(':focus').getAttribute('class')).toContain('ring')` (or use `evaluate` to read computed `outline`/`box-shadow`). Run on `desktop` project only (gate via `test.skip(testInfo.project.name !== 'desktop', 'keyboard test desktop-only')`).

**Generate baselines** — run `cd frontend && npx playwright test admin.spec.ts --update-snapshots` once, then `npm run test:e2e -- admin.spec.ts` to confirm green. Commit baselines under `frontend/e2e/admin.spec.ts-snapshots/`.

Mirror parts-catalog.spec.ts conventions: spread of MOCK_USER admin variant, animations:disabled (already in playwright.config.ts), no DB.

**Failure modes (Q5):** mock route swallowing /src/api/*.ts (MEM082) → page bundle crash; cookie banner overlay (MEM098); chrome-extension promo race (MEM108). All mitigated in setupPage. **Load profile (Q6):** N/A — fully mocked. **Negative tests (Q7):** the MOCK_EXTRACTION_HEALTH includes an empty-coverage tier and an adapter with rate=1.0 to exercise the empty/full ratio rendering paths.

## Inputs

- ``frontend/e2e/admin.spec.ts``
- ``frontend/e2e/parts-catalog.spec.ts``
- ``frontend/e2e/build-list.spec.ts``
- ``frontend/e2e/price-alerts.spec.ts``
- ``frontend/playwright.config.ts``
- ``frontend/src/pages/admin/AdminDashboard.tsx``
- ``frontend/src/pages/admin/ExtractionHealth.tsx``
- ``backend/app/api/endpoints/admin/extraction_health.py``

## Expected Output

- ``frontend/e2e/admin.spec.ts``
- ``frontend/e2e/admin.spec.ts-snapshots/admin-dashboard-1-mobile-linux.png``
- ``frontend/e2e/admin.spec.ts-snapshots/admin-dashboard-1-tablet-linux.png``
- ``frontend/e2e/admin.spec.ts-snapshots/admin-dashboard-1-desktop-linux.png``
- ``frontend/e2e/admin.spec.ts-snapshots/admin-extraction-health-1-mobile-linux.png``
- ``frontend/e2e/admin.spec.ts-snapshots/admin-extraction-health-1-tablet-linux.png``
- ``frontend/e2e/admin.spec.ts-snapshots/admin-extraction-health-1-desktop-linux.png``

## Verification

cd frontend && npm run test:e2e -- admin.spec.ts
