import { test, expect, type Route, type Request } from '@playwright/test';

// ---------------------------------------------------------------------------
// Mock fixtures (M002/S09/T04)
// ---------------------------------------------------------------------------
//
// Slice this spec covers (S09): /build-lists/:buildListId reskinned onto the
// S08 design system (ui/button + ui/dialog + ui/confirm-dialog + ui/tabs +
// ui/input). The spec asserts:
//   1. Visual regression at mobile / tablet / desktop (R014).
//   2. Edit dialog opens, focus moves into it, Escape closes it (R020).
//   3. Tab traversal lands visible focus on the first interactive control
//      ("View Build Log" — see ViewBuildlist.tsx) (R020).
//
// Shared Playwright conventions (S07/T06):
//   - MEM082: page.route() URL matcher MUST be `/\/api\/(?!.*\.ts)/` so it
//     does not swallow Vite's source modules at /src/api/*.ts.
//   - MEM098/MEM103: pre-accept the cookie-consent banner via addInitScript
//     so the mobile (375px) viewport doesn't have the bottom banner overlay
//     intercept clicks.
//   - MEM066/MEM068: every Playwright project uses Desktop Chrome (already
//     enforced in playwright.config.ts) so chromium-only baselines are stable.
//   - Pin Date.now() to FIXED_NOW_ISO for deterministic rendering.
//   - page.on('pageerror') re-throws runtime React errors as hard failures.

const BUILD_LIST_ID = 'cccccccc-cccc-cccc-cccc-cccccccccccc';
const CAR_ID = 'dddddddd-dddd-dddd-dddd-dddddddddddd';
const USER_ID = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';

const FIXED_NOW_ISO = '2026-04-25T12:00:00.000Z';

const MOCK_USER = {
  id: USER_ID,
  username: 'buildtester',
  email: 'buildtester@example.com',
  disabled: false,
  email_verified: true,
  image_urls: null,
  is_superuser: false,
  is_admin: false,
  is_service_account: false,
  subscription_tier: 'free',
  subscription_status: 'inactive',
  totp_enabled: false,
};

const MOCK_BUILD_LIST = {
  id: BUILD_LIST_ID,
  name: 'Demo Build List',
  description: 'Mocked build list for the S09 e2e demo flow.',
  car_id: CAR_ID,
  user_id: USER_ID,
  image_urls: null,
  created_at: FIXED_NOW_ISO,
  updated_at: FIXED_NOW_ISO,
};

const MOCK_CAR = {
  id: CAR_ID,
  car_make_name: 'Honda',
  car_model_name: 'Civic',
  car_model_display_name: 'Civic',
  generation_name: 'EK',
  display_name: null,
  display_label: 'Honda Civic EK',
  car_model_display_label: 'Civic',
  start_year: 1996,
  end_year: 2000,
  description: null,
  image_urls: null,
};

const MOCK_VOTE_SUMMARY = {
  entity_id: BUILD_LIST_ID,
  entity_type: 'build_list',
  upvotes: 0,
  downvotes: 0,
  total_votes: 0,
  vote_score: 0,
  user_vote: null,
};

interface MockState {
  unexpected: Array<{ method: string; path: string }>;
}

function jsonResponse(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function mockApi(
  page: import('@playwright/test').Page,
  state: MockState,
): Promise<void> {
  // MEM082: regex matches `/api/...` paths but excludes Vite source modules
  // at `/src/api/*.ts`. The negative lookahead `(?!.*\.ts)` is the lever.
  await page.route(/\/api\/(?!.*\.ts)/, async (route: Route, request: Request) => {
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api/, '');
    const method = request.method();

    // ---------- Auth + global settings ----------
    if (path === '/users/me' && method === 'GET') {
      return jsonResponse(route, MOCK_USER);
    }
    if (path === '/app-settings/' && method === 'GET') {
      return jsonResponse(route, {
        premium_disabled: true,
        updated_at: FIXED_NOW_ISO,
      });
    }

    // ---------- Build list + related lookups ----------
    if (path === `/build-lists/${BUILD_LIST_ID}` && method === 'GET') {
      return jsonResponse(route, MOCK_BUILD_LIST);
    }
    if (path === `/build-lists/${BUILD_LIST_ID}/phases` && method === 'GET') {
      return jsonResponse(route, []);
    }
    if (path === `/build-list-parts/${BUILD_LIST_ID}/parts` && method === 'GET') {
      return jsonResponse(route, []);
    }

    // ---------- Car generations ----------
    if (path === `/car-generations/${CAR_ID}` && method === 'GET') {
      return jsonResponse(route, MOCK_CAR);
    }
    if (path === '/car-generations/' && method === 'GET') {
      // BuildListParts.fetchCars() — LARGE_FETCH_LIMIT, used to populate
      // the carsById map for compatibility warnings. Empty list is fine.
      return jsonResponse(route, []);
    }

    // ---------- Categories / part-manufacturers ----------
    if (path === '/categories/' && method === 'GET') {
      return jsonResponse(route, []);
    }
    if (path === '/part-manufacturers/' && method === 'GET') {
      // active_only=true is sent as a query param; matched via path-only here.
      return jsonResponse(route, []);
    }

    // ---------- Users (build list owner hydration) ----------
    const userMatch = path.match(/^\/users\/([^/]+)$/);
    if (userMatch && method === 'GET') {
      return jsonResponse(route, MOCK_USER);
    }

    // ---------- Votes ----------
    const voteSummaryMatch = path.match(
      /^\/votes\/([^/]+)\/([^/]+)\/summary$/,
    );
    if (voteSummaryMatch && method === 'GET') {
      const [, entityType, entityId] = voteSummaryMatch;
      return jsonResponse(route, {
        ...MOCK_VOTE_SUMMARY,
        entity_id: entityId,
        entity_type: entityType,
      });
    }

    // Default: 404 — surface unexpected calls so the test (and the pageerror
    // listener via console error) flag any drift from the mock contract.
    state.unexpected.push({ method, path });
    return jsonResponse(route, { detail: `Mock miss: ${method} ${path}` }, 404);
  });
}

async function setupPage(
  page: import('@playwright/test').Page,
): Promise<MockState> {
  // Pin Date.now() so any rendering that depends on "now" is deterministic.
  // Only Date.now() is overridden — `new Date(iso)` still works as expected.
  await page.addInitScript((nowIso: string) => {
    const fixed = new Date(nowIso).getTime();
    const realNow = Date.now.bind(Date);
    Date.now = () => fixed;
    (globalThis as unknown as Record<string, unknown>).__REAL_DATE_NOW__ =
      realNow;
  }, FIXED_NOW_ISO);

  // MEM098/MEM103: pre-accept the cookie-consent banner. On the mobile
  // viewport (375px) the bottom-pinned banner overlays bottom-region controls
  // and Playwright's auto-retry click loop times out trying to find a
  // non-intercepted target. Pre-seeding localStorage suppresses it before
  // any page bundle code runs.
  await page.addInitScript(() => {
    try {
      localStorage.setItem('cookie_consent_v1', 'accepted');
      // Pre-dismiss the chrome-extension promo for today so its 2s
      // detect-then-show timer does not race the snapshot — flaked the
      // mobile baseline once already (S09/T05).
      const today = new Date();
      const y = today.getFullYear();
      const m = String(today.getMonth() + 1).padStart(2, '0');
      const d = String(today.getDate()).padStart(2, '0');
      localStorage.setItem(
        'chrome_extension_promo_last_dismissed',
        `${y}-${m}-${d}`,
      );
    } catch {
      // localStorage may be unavailable (private mode); banner stays.
    }
  });

  const state: MockState = { unexpected: [] };
  await mockApi(page, state);

  page.on('pageerror', (err) => {
    throw err;
  });

  return state;
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

test('build-list detail visual regression', async ({ page }) => {
  await setupPage(page);

  await page.goto(`/build-lists/${BUILD_LIST_ID}`);
  await waitForPageReady(page);

  // Sanity: edit trigger is rendered (canManage block reached) — confirms the
  // mock contract held end-to-end before we snapshot.
  await expect(page.getByTestId('build-list-edit-trigger')).toBeVisible();

  await expect(page).toHaveScreenshot({ fullPage: true });
});

test('edit dialog opens, focuses, and Escape closes', async ({ page }, testInfo) => {
  test.skip(
    testInfo.project.name !== 'desktop',
    'Dialog keyboard interaction is asserted once on desktop',
  );

  await setupPage(page);

  await page.goto(`/build-lists/${BUILD_LIST_ID}`);
  await waitForPageReady(page);

  const trigger = page.getByTestId('build-list-edit-trigger');
  await expect(trigger).toBeVisible();
  await trigger.click();

  const dialog = page.getByTestId('build-list-edit-dialog');
  await expect(dialog).toBeVisible();

  // Radix moves focus into the dialog on open. Assert the focused element is
  // a descendant of the dialog content surface.
  const focusInsideDialog = await page.evaluate(() => {
    const dialogEl = document.querySelector(
      '[data-testid="build-list-edit-dialog"]',
    );
    const focused = document.activeElement;
    return !!(dialogEl && focused && dialogEl.contains(focused));
  });
  expect(focusInsideDialog).toBe(true);

  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
});

test('tab order surfaces visible focus on first interactive control', async ({ page }, testInfo) => {
  test.skip(
    testInfo.project.name !== 'desktop',
    'Tab order is asserted once on desktop',
  );

  await setupPage(page);

  await page.goto(`/build-lists/${BUILD_LIST_ID}`);
  await waitForPageReady(page);

  // Wait for the first action button (View Build Log) to be in the DOM so the
  // page is interactive before we start traversing focus.
  const viewBuildLogBtn = page.getByRole('button', { name: 'View Build Log' });
  await expect(viewBuildLogBtn).toBeVisible();

  // Move focus to the page body so Tab progresses from the start of the
  // document, then Tab forward until we hit the first action button. The
  // header/nav contributes a known number of focusable nodes, but we don't
  // want to hard-code that count — bail out as soon as we find the target.
  await page.evaluate(() => {
    document.body.focus();
    if (document.activeElement !== document.body) {
      // Some browsers won't focus body without a tabindex; force it.
      document.body.setAttribute('tabindex', '-1');
      document.body.focus();
    }
  });

  let foundOnTab = -1;
  for (let i = 1; i <= 30; i++) {
    await page.keyboard.press('Tab');
    const activeText = await page.evaluate(
      () => document.activeElement?.textContent?.trim() ?? '',
    );
    if (activeText === 'View Build Log') {
      foundOnTab = i;
      break;
    }
  }

  expect(
    foundOnTab,
    'Tab traversal never reached the View Build Log button within 30 presses',
  ).toBeGreaterThan(0);

  // R020: the focused control must have a visible focus ring. ui/Button uses
  // Tailwind's focus-visible:ring-* utilities — assert the computed outline
  // or box-shadow is non-empty when focus-visible matches.
  const hasFocusRing = await viewBuildLogBtn.evaluate((el) => {
    if (!el.matches(':focus-visible')) return false;
    const styles = window.getComputedStyle(el);
    const outline = styles.outlineStyle;
    const boxShadow = styles.boxShadow;
    return (
      (outline !== 'none' && outline !== '') ||
      (boxShadow !== 'none' && boxShadow !== '')
    );
  });
  expect(hasFocusRing).toBe(true);
});
