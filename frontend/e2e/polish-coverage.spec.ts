import { test, expect } from '@playwright/test';

import { ALL_ROUTES } from '../src/test/route-coverage-list';

// ---------------------------------------------------------------------------
// M003/S05/T06: visual-regression coverage for every <Route path> in App.tsx.
//
// The 33 routes that had zero Playwright baseline coverage post-S04 get one
// here, so the M003/S06 close gauntlet has visual signal across the entire
// production surface — not just the 6 routes covered by admin/build-list/
// parts-catalog/price-alerts/price-history specs.
//
// Important behavioral notes (cross-referenced with the slice plan T06 Q5):
//   - Auth-guarded routes (builder group: /profile, /builder, /my-parts,
//     /checkout, /account/alerts, /verify-email; authentication group:
//     /login, /register, /forgot-password) are visited as the default
//     unauthenticated user. Builder routes will redirect to /login;
//     authentication routes render the requested page directly. The
//     baseline locks whichever state the user actually sees (the redirect
//     target for builder, the page itself for authentication).
//   - Routes with dynamic UUIDs (`/parts/some-part`, `/build-lists/00000...`,
//     `/user/00000...`, `/car-generations/some-car`) are not real records;
//     the API returns 404 and the page renders its NotFound / error-boundary
//     state. Baselines lock that error-state rendering — useful per task
//     plan Q5(b).
//   - `/nonexistent-route-for-404-test` exercises the App.tsx `*` route.
//   - `/_kitchen-sink` is dev-only; the Playwright `npm run dev` webServer
//     sets DEV=true so the route mounts. components.spec.ts also covers it
//     at a single viewport — the cascade-aware --update-snapshots run will
//     keep both spec's baselines in sync.
//
// Memory references this implementation depends on:
//   - MEM170/MEM179: mobile project = 375 (NOT 360); 360 is the manual UAT
//     target only. Documented in S05-SUMMARY.md verdict table.
//   - MEM098/MEM103: pre-accept cookie_consent_v1 via addInitScript so the
//     bottom-pinned banner does not occlude the mobile viewport screenshot.
//   - MEM108/MEM109: pre-dismiss the chrome-extension promo so its 2s
//     detect-then-show timer cannot race fullPage screenshots.
//   - MEM156/MEM160: `--update-snapshots` (no value) defaults to `changed`
//     mode — only rewrites baselines that actually drift. T06's cascade
//     refresh relies on this default.
//   - MEM175: positional spec args go BEFORE `--update-snapshots` when no
//     mode value is supplied.
// ---------------------------------------------------------------------------

const FIXED_NOW_ISO = '2026-04-25T12:00:00.000Z';

// Slugify a route path so snapshot filenames are readable and stable.
//   '/'                          -> 'root'
//   '/admin/extraction-health'   -> 'admin-extraction-health'
//   '/parts/some-part/edit'      -> 'parts-some-part-edit'
function slugForRoute(path: string): string {
  if (path === '/') return 'root';
  return path
    .replace(/^\//, '')
    .replace(/\//g, '-')
    .replace(/[^a-zA-Z0-9-]/g, '_');
}

async function setupPage(
  page: import('@playwright/test').Page,
): Promise<void> {
  // Pin Date.now() so any rendering that depends on "now" (header date
  // pickers, last-updated formatters, subscription expiry comparisons) is
  // deterministic across snapshot runs.
  await page.addInitScript((nowIso: string) => {
    const fixed = new Date(nowIso).getTime();
    const realNow = Date.now.bind(Date);
    Date.now = () => fixed;
    (globalThis as unknown as Record<string, unknown>).__REAL_DATE_NOW__ =
      realNow;
  }, FIXED_NOW_ISO);

  // Pre-accept cookie consent and pre-dismiss the chrome-extension promo for
  // today (MEM098/MEM103/MEM108/MEM109). Both overlay the bottom region of
  // the mobile viewport and would otherwise be in every fullPage baseline.
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
      // localStorage may be unavailable (private mode); banners stay.
    }
  });
}

async function waitForPageReady(
  page: import('@playwright/test').Page,
): Promise<void> {
  // networkidle can hang on routes that poll, so cap with a try/catch and
  // fall back to domcontentloaded + a fixed settle window. Fonts.ready and
  // a 300ms tail match admin.spec.ts / price-alerts.spec.ts.
  try {
    await page.waitForLoadState('networkidle', { timeout: 8000 });
  } catch {
    // Fall through; some pages have ongoing requests (admin polling) and
    // never quiesce. The fixed 300ms settle below is enough for the visual
    // surface to stabilize.
    await page.waitForLoadState('domcontentloaded');
  }
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(300);
}

// One test per (route × project). Each project (mobile/tablet/desktop) is
// configured in playwright.config.ts; Playwright runs the full describe block
// once per project, so a single test() per route generates 3 baselines.
for (const { path } of ALL_ROUTES) {
  const slug = slugForRoute(path);

  test(`polish-coverage: ${path}`, async ({ page }) => {
    await setupPage(page);

    page.on('pageerror', (err) => {
      // Surface unexpected page errors so a regression that crashes the page
      // fails this spec loudly instead of silently producing a blank baseline.
      throw err;
    });

    await page.goto(path);
    await waitForPageReady(page);

    await expect(page).toHaveScreenshot(`${slug}.png`, {
      fullPage: true,
      // Absorb sub-pixel font/AA noise without weakening the geometry signal.
      maxDiffPixelRatio: 0.01,
    });
  });
}
