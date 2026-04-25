import { test, expect, type Route, type Request } from '@playwright/test';

// ---------------------------------------------------------------------------
// Mock fixtures (M002/S07/T06)
// ---------------------------------------------------------------------------
//
// Demo flow this spec covers (from S07-PLAN.md):
//   (1) /parts/<id>: click "Notify me on price drop", set threshold, submit;
//       button label flips to "Manage alert ($X.XX)" and POST hit recorded.
//   (2) /account/alerts: new alert listed.
//   (3) Click "Unsubscribe" on the row; DELETE hit recorded and row disappears.
// The "mocked observation fires email" assertion lives in the unit-test layer
// (T03 service tests). Playwright covers UI flow only.
//
// MEM082: page.route() must NOT match Vite's source modules at /src/api/*.ts.
// MEM079/MEM066/MEM068: pin Date.now() and only ever use Desktop Chrome
// (already enforced by playwright.config.ts).

const PART_ID = '11111111-1111-1111-1111-111111111111';
const USER_ID = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
const CREATED_ALERT_ID = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';

const FIXED_NOW_ISO = '2026-04-25T12:00:00.000Z';

const MOCK_CATEGORY_ID = 'cat-1';
const MOCK_CATEGORY = {
  id: MOCK_CATEGORY_ID,
  name: 'brakes',
  display_name: 'Brakes',
  description: null,
  icon: null,
  is_active: true,
  sort_order: 0,
  created_at: FIXED_NOW_ISO,
  updated_at: FIXED_NOW_ISO,
};

const MOCK_PART_MANUFACTURER_ID = 'pm-1';
const MOCK_PART_MANUFACTURER = {
  id: MOCK_PART_MANUFACTURER_ID,
  name: 'Acme Performance',
  description: null,
  is_active: true,
  created_at: FIXED_NOW_ISO,
  updated_at: FIXED_NOW_ISO,
};

const MOCK_USER = {
  id: USER_ID,
  username: 'alerttester',
  email: 'alerttester@example.com',
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

const MOCK_PART = {
  id: PART_ID,
  name: 'Demo Brake Pad',
  description: 'Mocked part for the price-alerts e2e demo flow.',
  best_price_cents: 12999,
  image_urls: null,
  category_id: MOCK_CATEGORY_ID,
  user_id: USER_ID,
  car_ids: [],
  is_universal: true,
  part_manufacturer_id: MOCK_PART_MANUFACTURER_ID,
  part_manufacturer: MOCK_PART_MANUFACTURER.name,
  part_number: 'DEMO-001',
  specifications: null,
  canonical_part_id: null,
  is_verified: true,
  source: 'crawler',
  edit_count: 0,
  created_at: FIXED_NOW_ISO,
  updated_at: FIXED_NOW_ISO,
  upvotes: 0,
  downvotes: 0,
  total_votes: 0,
  user_vote: null,
};

const MOCK_LISTINGS = [
  {
    id: 'listing-1',
    part_id: PART_ID,
    retailer_id: 'r1',
    product_url: 'https://retailer-one.example.com/product/demo-001',
    last_known_price_cents: 12999,
    last_price_updated_at: FIXED_NOW_ISO,
    created_at: FIXED_NOW_ISO,
    updated_at: FIXED_NOW_ISO,
    retailer: {
      id: 'r1',
      name: 'RetailerOne',
      domain: 'retailer-one.example.com',
      base_url: 'https://retailer-one.example.com',
      is_active: true,
      created_at: FIXED_NOW_ISO,
      updated_at: FIXED_NOW_ISO,
    },
  },
];

const MOCK_PRICE_SUMMARY = {
  summary: {
    min_cents: 12999,
    max_cents: 14999,
    last_cents: 12999,
    last_observed_at: FIXED_NOW_ISO,
    trend: 'down',
    observation_count: 3,
  },
  retailers: [
    {
      retailer_id: 'r1',
      retailer_name: 'RetailerOne',
      min_cents: 12999,
      max_cents: 14999,
      last_cents: 12999,
      last_observed_at: FIXED_NOW_ISO,
      observation_count: 3,
    },
  ],
  history: [
    {
      id: 'h1',
      part_listing_id: 'listing-1',
      price_cents: 14999,
      observed_at: '2026-02-01T00:00:00.000Z',
      retailer_id: 'r1',
      retailer_name: 'RetailerOne',
    },
    {
      id: 'h2',
      part_listing_id: 'listing-1',
      price_cents: 13999,
      observed_at: '2026-03-01T00:00:00.000Z',
      retailer_id: 'r1',
      retailer_name: 'RetailerOne',
    },
    {
      id: 'h3',
      part_listing_id: 'listing-1',
      price_cents: 12999,
      observed_at: '2026-04-15T00:00:00.000Z',
      retailer_id: 'r1',
      retailer_name: 'RetailerOne',
    },
  ],
  window: '90d',
};

const MOCK_VOTE_SUMMARY = {
  entity_id: PART_ID,
  entity_type: 'part',
  upvotes: 0,
  downvotes: 0,
  total_votes: 0,
  vote_score: 0,
  user_vote: null,
};

interface CapturedRequest {
  method: string;
  path: string;
  body: unknown;
}

interface AlertState {
  alerts: Array<{
    id: string;
    user_id: string;
    part_id: string;
    threshold_cents: number;
    active: boolean;
    last_fired_at: string | null;
    created_at: string;
    updated_at: string;
  }>;
  captured: CapturedRequest[];
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
  state: AlertState,
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

    // ---------- Categories / part-manufacturers / car generations ----------
    if (path === '/categories/' && method === 'GET') {
      return jsonResponse(route, [MOCK_CATEGORY]);
    }
    if (path.startsWith('/categories/') && method === 'GET') {
      return jsonResponse(route, MOCK_CATEGORY);
    }
    if (path === '/part-manufacturers/' && method === 'GET') {
      return jsonResponse(route, [MOCK_PART_MANUFACTURER]);
    }
    if (path.startsWith('/part-manufacturers/') && method === 'GET') {
      return jsonResponse(route, MOCK_PART_MANUFACTURER);
    }
    if (path === '/car-generations/by-ids' && method === 'GET') {
      return jsonResponse(route, []);
    }
    if (path === '/car-generations/stats/car-makes' && method === 'GET') {
      return jsonResponse(route, {});
    }
    if (path.startsWith('/car-generations/') && method === 'GET') {
      return jsonResponse(route, []);
    }

    // ---------- Part-price-alerts (the surface under test) ----------
    if (path === '/part-price-alerts/me' && method === 'GET') {
      // Return only the active alerts so the button mount-time prefill
      // matches the post-subscribe state.
      return jsonResponse(
        route,
        state.alerts.filter((a) => a.active),
      );
    }
    if (path === '/part-price-alerts/' && method === 'POST') {
      const bodyText = request.postData() ?? '{}';
      let body: { part_id?: string; threshold_cents?: number };
      try {
        body = JSON.parse(bodyText);
      } catch {
        body = {};
      }
      state.captured.push({ method, path, body });

      const threshold =
        typeof body.threshold_cents === 'number' ? body.threshold_cents : 0;
      const partIdFromBody =
        typeof body.part_id === 'string' ? body.part_id : PART_ID;

      // Idempotent upsert: if an alert exists for this user+part, update it
      // and resurrect from inactive. Otherwise create a new row.
      const existing = state.alerts.find(
        (a) => a.user_id === USER_ID && a.part_id === partIdFromBody,
      );
      let saved;
      if (existing) {
        existing.threshold_cents = threshold;
        existing.active = true;
        existing.updated_at = FIXED_NOW_ISO;
        saved = existing;
      } else {
        saved = {
          id: CREATED_ALERT_ID,
          user_id: USER_ID,
          part_id: partIdFromBody,
          threshold_cents: threshold,
          active: true,
          last_fired_at: null,
          created_at: FIXED_NOW_ISO,
          updated_at: FIXED_NOW_ISO,
        };
        state.alerts.push(saved);
      }
      return jsonResponse(route, saved, 201);
    }
    const alertDeleteMatch = path.match(/^\/part-price-alerts\/([^/]+)$/);
    if (alertDeleteMatch && method === 'DELETE') {
      const alertId = alertDeleteMatch[1]!;
      state.captured.push({ method, path, body: null });
      const target = state.alerts.find((a) => a.id === alertId && a.active);
      if (!target) {
        return jsonResponse(route, { detail: 'Not found' }, 404);
      }
      target.active = false;
      target.updated_at = FIXED_NOW_ISO;
      return route.fulfill({ status: 204, body: '' });
    }

    // ---------- Parts ----------
    if (path === '/parts/with-votes' && method === 'GET') {
      return jsonResponse(route, {
        data: [MOCK_PART],
        pagination: {
          current_page: 1,
          total_pages: 1,
          total_items: 1,
          items_per_page: 100,
          has_next: false,
          has_previous: false,
        },
      });
    }
    if (path === '/parts/filter-options' && method === 'GET') {
      return jsonResponse(route, {
        category_ids: [MOCK_CATEGORY_ID],
        part_manufacturer_ids: [MOCK_PART_MANUFACTURER_ID],
        car_ids: [],
        make_names: [],
      });
    }
    if (path === '/parts/price-history' && method === 'POST') {
      return jsonResponse(route, {
        summaries: { [PART_ID]: MOCK_PRICE_SUMMARY.summary },
        window: '90d',
        requested_count: 1,
        found_count: 1,
      });
    }
    const priceHistoryMatch = path.match(/^\/parts\/([^/]+)\/price-history$/);
    if (priceHistoryMatch && method === 'GET') {
      const partId = priceHistoryMatch[1];
      const isLegacy = url.searchParams.get('legacy') === 'true';
      if (isLegacy) {
        return jsonResponse(
          route,
          partId === PART_ID ? MOCK_PRICE_SUMMARY.history : [],
        );
      }
      return jsonResponse(route, MOCK_PRICE_SUMMARY);
    }
    const listingsMatch = path.match(/^\/parts\/([^/]+)\/listings$/);
    if (listingsMatch && method === 'GET') {
      return jsonResponse(
        route,
        listingsMatch[1] === PART_ID ? MOCK_LISTINGS : [],
      );
    }
    const partMatch = path.match(/^\/parts\/([^/]+)$/);
    if (partMatch && method === 'GET') {
      const partId = partMatch[1];
      if (partId === PART_ID) {
        return jsonResponse(route, MOCK_PART);
      }
      return jsonResponse(route, { detail: 'Not found' }, 404);
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

    // ---------- Users ----------
    const userMatch = path.match(/^\/users\/([^/]+)$/);
    if (userMatch && method === 'GET') {
      return jsonResponse(route, MOCK_USER);
    }

    // Default: 404 — surface unexpected calls so the test (and the pageerror
    // listener) flag any drift from the mock contract.
    return jsonResponse(route, { detail: `Mock miss: ${method} ${path}` }, 404);
  });
}

async function setupPage(
  page: import('@playwright/test').Page,
): Promise<AlertState> {
  // MEM079: pin Date.now() so any rendering that depends on "now" (e.g.
  // last_fired_at "today" formatting, subscription_expires_at comparisons)
  // is deterministic. Only Date.now() is overridden — `new Date(iso)` still
  // works as expected.
  await page.addInitScript((nowIso: string) => {
    const fixed = new Date(nowIso).getTime();
    const realNow = Date.now.bind(Date);
    Date.now = () => fixed;
    (globalThis as unknown as Record<string, unknown>).__REAL_DATE_NOW__ =
      realNow;
  }, FIXED_NOW_ISO);

  // Pre-accept the cookie-consent banner. On the mobile viewport (375px) the
  // banner overlays the bottom of the page and intercepts pointer events on
  // the subscribe button; pre-seeding localStorage suppresses it before any
  // page bundle code runs.
  await page.addInitScript(() => {
    try {
      localStorage.setItem('cookie_consent_v1', 'accepted');
    } catch {
      // localStorage may be unavailable (private mode); banner stays.
    }
  });

  const state: AlertState = { alerts: [], captured: [] };
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

test('subscribe → manage → unsubscribe demo flow', async ({ page }) => {
  const state = await setupPage(page);

  // ---- Step 1: Subscribe on /parts/:id ----
  await page.goto(`/parts/${PART_ID}`);
  await waitForPageReady(page);

  const trigger = page.getByTestId('price-alert-subscribe-trigger');
  await trigger.scrollIntoViewIfNeeded();
  await expect(trigger).toBeVisible();
  await expect(trigger).toHaveText('Notify me on price drop');

  await trigger.click();

  const dialog = page.getByTestId('price-alert-subscribe-dialog');
  await expect(dialog).toBeVisible();

  // Replace the prefilled best-price value with the demo threshold of $99.
  const thresholdInput = page.getByTestId('price-alert-threshold-input');
  await thresholdInput.fill('99');

  // Submitting fires POST /api/part-price-alerts/. Wait for the request so we
  // can assert on its body before the optimistic close races us.
  const [subscribeRequest] = await Promise.all([
    page.waitForRequest(
      (req) =>
        req.method() === 'POST' &&
        new URL(req.url()).pathname === '/api/part-price-alerts/',
    ),
    page.getByTestId('price-alert-subscribe-submit').click(),
  ]);

  expect(subscribeRequest.postDataJSON()).toEqual({
    part_id: PART_ID,
    threshold_cents: 9900,
  });

  // Mock router recorded the call with the right body too (belt-and-braces).
  expect(state.captured).toContainEqual({
    method: 'POST',
    path: '/part-price-alerts/',
    body: { part_id: PART_ID, threshold_cents: 9900 },
  });

  // Dialog closes; trigger label flips to "Manage alert ($99.00)".
  await expect(dialog).toBeHidden();
  await expect(trigger).toHaveText('Manage alert ($99.00)');

  // One screenshot per viewport — captured here (post-subscribe, pre-unsubscribe)
  // to keep the snapshot count bounded as the task plan requires.
  await expect(page).toHaveScreenshot({ fullPage: true });

  // ---- Step 2: /account/alerts lists the new alert ----
  await page.goto('/account/alerts');
  await waitForPageReady(page);

  const alertRow = page.locator(
    `[data-testid="alert-row"][data-alert-id="${CREATED_ALERT_ID}"]`,
  );
  await expect(alertRow).toBeVisible();
  await expect(alertRow.getByTestId('alert-row-threshold')).toHaveText(
    'Threshold: $99.00',
  );
  // The row links back to the part. (Part-name hydration happens lazily via
  // partsApi.getPart and is asserted at the unit-test layer in
  // AccountAlerts.test.tsx; here we just confirm the row points at the right
  // part.)
  await expect(alertRow.getByTestId('alert-row-part-link')).toHaveAttribute(
    'href',
    `/parts/${PART_ID}`,
  );

  // ---- Step 3: Unsubscribe — DELETE fires and the row disappears ----
  const [deleteRequest] = await Promise.all([
    page.waitForRequest(
      (req) =>
        req.method() === 'DELETE' &&
        new URL(req.url()).pathname ===
          `/api/part-price-alerts/${CREATED_ALERT_ID}`,
    ),
    alertRow.getByTestId('alert-row-unsubscribe').click(),
  ]);

  expect(new URL(deleteRequest.url()).pathname).toBe(
    `/api/part-price-alerts/${CREATED_ALERT_ID}`,
  );
  expect(state.captured).toContainEqual({
    method: 'DELETE',
    path: `/part-price-alerts/${CREATED_ALERT_ID}`,
    body: null,
  });

  // Optimistic remove: the row goes away without a refetch.
  await expect(alertRow).toHaveCount(0);
  await expect(page.getByTestId('alerts-empty')).toBeVisible();
});
