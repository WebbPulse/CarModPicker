import { test, expect, type Route, type Request } from '@playwright/test';

// ---------------------------------------------------------------------------
// Mock fixtures (M002/S11/T04)
// ---------------------------------------------------------------------------
//
// Slice this spec covers (S11): /admin (AdminDashboard) reskinned onto the
// S08 ui/Button design-system primitive AND the new /admin/extraction-health
// page that consumes GET /api/admin/extraction-health. The spec asserts:
//   1. /admin visual regression at mobile / tablet / desktop (3 baselines).
//   2. /admin/extraction-health visual regression at mobile / tablet / desktop
//      (3 baselines), exercising compliance pills, per-tier coverage heatmap,
//      and the 7d failure-rate table.
//   3. Keyboard focus on /admin/extraction-health: first Tab lands on a
//      focusable control whose computed style shows a focus ring (R020).
//
// Conventions inherited from frontend/e2e/parts-catalog.spec.ts (S10/T04)
// and frontend/e2e/build-list.spec.ts (S09/T04):
//   - MEM082: page.route() URL matcher MUST be `/\/api\/(?!.*\.ts)/` so it
//     does not swallow Vite's source modules at /src/api/*.ts.
//   - MEM098/MEM103: pre-accept the cookie-consent banner via addInitScript
//     so the mobile (375px) viewport doesn't have the bottom banner overlay
//     intercept clicks or move layout.
//   - MEM108/MEM109: pre-dismiss the chrome-extension promo for today (its 2s
//     detect-then-show timer can race the snapshot otherwise).
//   - MEM066/MEM068: every Playwright project uses Desktop Chrome (already
//     enforced in playwright.config.ts) so chromium-only baselines are stable.
//   - MEM105: gate per-project tests via `testInfo.project.name`, not env.
//   - Pin Date.now() to FIXED_NOW_ISO for deterministic rendering.
//   - page.on('pageerror') re-throws runtime React errors as hard failures.

const FIXED_NOW_ISO = '2026-04-25T12:00:00.000Z';
const ONE_DAY_MS = 24 * 60 * 60 * 1000;
const SEVEN_DAYS_AGO_ISO = new Date(
  Date.parse(FIXED_NOW_ISO) - 7 * ONE_DAY_MS,
).toISOString();

const USER_ID = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';

// Admin variant of the standard MOCK_USER shape (mirrors parts-catalog.spec.ts:68
// but with is_admin: true so AdminDashboard's redirect-on-non-admin path is
// satisfied and the dashboard renders).
const MOCK_ADMIN_USER = {
  id: USER_ID,
  username: 'admintester',
  email: 'admintester@example.com',
  disabled: false,
  email_verified: true,
  image_urls: null,
  is_superuser: false,
  is_admin: true,
  is_service_account: false,
  subscription_tier: 'free',
  subscription_status: 'inactive',
  totp_enabled: false,
};

// Mirrors the backend ExtractionHealthResponse shape exactly
// (`backend/app/api/endpoints/admin/extraction_health.py`). Fixture values
// chosen to exercise the empty / partial / full rendering paths:
//   - compliance shows the canonical 108/108 (T0:83 / T1:15 / T2:10).
//   - coverage.per_tier.browser is intentionally empty (parts_total: 0) to
//     exercise the "—" empty-summary path in ExtractionHealth.tsx.
//   - failure_rate_7d includes a 100% rate row (1.0) to exercise the full-ratio
//     rendering path alongside zero-failure rows.
const MOCK_EXTRACTION_HEALTH = {
  compliance: {
    compliant: 108,
    total: 108,
    per_tier: {
      http: '83/83',
      tls: '15/15',
      browser: '10/10',
    },
  },
  coverage: {
    per_tier: {
      http: {
        parts_with_specs: 4200,
        parts_total: 9000,
        per_field: {
          weight_grams: 0.42,
          material: 0.18,
          dimensions_mm: 0.31,
        },
      },
      tls: {
        parts_with_specs: 1100,
        parts_total: 2400,
        per_field: {
          weight_grams: 0.55,
          material: 0.22,
        },
      },
      browser: {
        parts_with_specs: 0,
        parts_total: 0,
        per_field: {
          weight_grams: 0,
          material: 0,
        },
      },
    },
  },
  failure_rate_7d: [
    {
      adapter: 'amazon_browser',
      failed: 12,
      parsed: 12,
      rate: 1.0,
      tier: 'browser',
    },
    {
      adapter: 'rockauto_http',
      failed: 5,
      parsed: 95,
      rate: 0.05,
      tier: 'http',
    },
    {
      adapter: 'tirerack_tls',
      failed: 0,
      parsed: 80,
      rate: 0.0,
      tier: 'tls',
    },
  ],
  window: {
    days: 7,
    since: SEVEN_DAYS_AGO_ISO,
  },
};

// ---------------------------------------------------------------------------
// API mock router
// ---------------------------------------------------------------------------

function jsonResponse(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function mockApi(page: import('@playwright/test').Page): Promise<void> {
  // MEM082: regex matcher excludes Vite source modules at /src/api/*.ts.
  await page.route(
    /\/api\/(?!.*\.ts)/,
    async (route: Route, request: Request) => {
      const url = new URL(request.url());
      const path = url.pathname.replace(/^\/api/, '');
      const method = request.method();

      // ---------- Auth + global settings ----------
      if (path === '/users/me' && method === 'GET') {
        return jsonResponse(route, MOCK_ADMIN_USER);
      }
      if (path === '/app-settings/' && method === 'GET') {
        return jsonResponse(route, {
          premium_disabled: true,
          updated_at: FIXED_NOW_ISO,
        });
      }

      // ---------- Extraction health ----------
      // adminApi.getExtractionHealth() targets `/admin/extraction-health` (no
      // trailing slash); FastAPI redirects to the trailing-slash form mounted
      // by the router. Match both shapes defensively.
      if (
        (path === '/admin/extraction-health' ||
          path === '/admin/extraction-health/') &&
        method === 'GET'
      ) {
        return jsonResponse(route, MOCK_EXTRACTION_HEALTH);
      }

      // Defensive fallthrough for any unexpected admin endpoint hit during
      // dashboard render (most are not called from /admin itself, which is
      // pure navigation cards). Return an empty object to keep the bundle
      // alive rather than crashing on a 404 axios reject.
      if (path.startsWith('/admin/') && method === 'GET') {
        return jsonResponse(route, {});
      }

      // Default: 404 — surface unexpected calls so the test (via the
      // pageerror listener) flags drift from the contract.
      return jsonResponse(
        route,
        { detail: `Mock miss: ${method} ${path}` },
        404,
      );
    },
  );
}

// ---------------------------------------------------------------------------
// Deterministic page setup helpers
// ---------------------------------------------------------------------------

async function setupPage(
  page: import('@playwright/test').Page,
): Promise<void> {
  // Pin Date.now() so any rendering that depends on "now" is deterministic.
  await page.addInitScript((nowIso: string) => {
    const fixed = new Date(nowIso).getTime();
    const realNow = Date.now.bind(Date);
    Date.now = () => fixed;
    (globalThis as unknown as Record<string, unknown>).__REAL_DATE_NOW__ =
      realNow;
  }, FIXED_NOW_ISO);

  // MEM098: pre-accept cookie-consent + MEM108/MEM109: pre-dismiss the
  // chrome-extension promo for today so its 2s detect-then-show timer can't
  // race the full-page snapshot.
  await page.addInitScript(() => {
    try {
      localStorage.setItem('cookie_consent_v1', 'accepted');
      const today = new Date();
      const y = today.getFullYear();
      const m = String(today.getMonth() + 1).padStart(2, '0');
      const d = String(today.getDate()).padStart(2, '0');
      localStorage.setItem(
        'chrome_extension_promo_last_dismissed',
        `${y}-${m}-${d}`,
      );
    } catch {
      // localStorage unavailable (private mode); banner stays.
    }
  });

  await mockApi(page);

  page.on('pageerror', (err) => {
    throw err;
  });
}

async function waitForPageReady(
  page: import('@playwright/test').Page,
): Promise<void> {
  await page.waitForLoadState('networkidle');
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(300);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test('admin dashboard visual regression', async ({ page }) => {
  await setupPage(page);

  await page.goto('/admin');
  await waitForPageReady(page);

  // Spot-check that the dashboard rendered the new /admin/extraction-health
  // entry card (added in S11/T02) so a route/registration regression fails
  // here loudly rather than silently producing a stale baseline.
  await expect(
    page.getByRole('heading', { name: 'Extraction Health' }),
  ).toBeVisible();

  await expect(page).toHaveScreenshot('admin-dashboard-1.png', {
    fullPage: true,
  });
});

test('admin extraction-health visual regression', async ({ page }) => {
  await setupPage(page);

  await page.goto('/admin/extraction-health');
  await waitForPageReady(page);

  // Compliance pills are the headline signal — assert they rendered before
  // taking the snapshot so a fetch failure can't masquerade as a layout-only
  // diff. Pills come from data-testid="compliance-pill-{tier}" in
  // ExtractionHealth.tsx.
  await expect(page.getByTestId('compliance-pill-http')).toBeVisible();
  await expect(page.getByTestId('compliance-pill-tls')).toBeVisible();
  await expect(page.getByTestId('compliance-pill-browser')).toBeVisible();
  await expect(page.getByTestId('failure-rate-table')).toBeVisible();

  await expect(page).toHaveScreenshot('admin-extraction-health-1.png', {
    fullPage: true,
  });
});

test('extraction-health: keyboard Tab lands visible focus on a control', async ({
  page,
}, testInfo) => {
  test.skip(
    testInfo.project.name !== 'desktop',
    'Keyboard focus is asserted once on desktop',
  );

  await setupPage(page);

  await page.goto('/admin/extraction-health');
  await waitForPageReady(page);

  // Wait for the page to be interactive (Refresh button is the first
  // page-local control after the global header).
  await expect(
    page.getByRole('button', { name: /Refresh extraction health/i }),
  ).toBeVisible();

  // Move focus to the document start so Tab progresses from the top of the
  // page rather than from whatever element happened to be focused after
  // navigation.
  await page.evaluate(() => {
    document.body.focus();
    if (document.activeElement !== document.body) {
      document.body.setAttribute('tabindex', '-1');
      document.body.focus();
    }
  });

  await page.keyboard.press('Tab');

  // R020: the focused control must exist and be visible.
  const focused = page.locator(':focus');
  await expect(focused).toBeVisible();

  // ui/Button uses `focus-visible:ring-2 focus-visible:ring-ring` (see
  // frontend/src/components/ui/button.tsx). Most focusable controls on this
  // page are either Buttons (Refresh) or links/anchors (skip-link, header
  // nav) — all of which use Tailwind ring/outline focus utilities. Verify
  // either the class string contains "ring" OR the computed style applies
  // a non-empty outline/box-shadow when focus-visible matches.
  const focusRingPresent = await focused.evaluate((el) => {
    const cls = el.className;
    if (typeof cls === 'string' && cls.includes('ring')) {
      return true;
    }
    if (!el.matches(':focus-visible')) {
      return false;
    }
    const styles = window.getComputedStyle(el);
    const outline = styles.outlineStyle;
    const boxShadow = styles.boxShadow;
    return (
      (outline !== 'none' && outline !== '') ||
      (boxShadow !== 'none' && boxShadow !== '')
    );
  });
  expect(focusRingPresent).toBe(true);
});
