import { test, expect, type Route, type Request } from '@playwright/test';

// ---------------------------------------------------------------------------
// Mock fixtures (M002/S10/T04)
// ---------------------------------------------------------------------------
//
// Slice this spec covers (S10): /parts (Parts Catalog) reskinned onto the
// S08 design system. Asserts:
//   1. Visual regression at mobile / tablet / desktop (R014/R015) — including
//      the S06 sparkline + delta integration on the multi-observation row
//      and exactly ONE batch POST per page (S06 invariant).
//   2. AddToBuildList dialog opens, focus moves into it, Escape closes it
//      (R020 / Radix focus management).
//   3. Tab traversal lands visible focus on the search input (R020).
//
// Conventions inherited from frontend/e2e/price-history.spec.ts (S06/T04)
// and frontend/e2e/build-list.spec.ts (S09/T04):
//   - MEM082: page.route() URL matcher MUST be `/\/api\/(?!.*\.ts)/` so it
//     does not swallow Vite's source modules at /src/api/*.ts.
//   - MEM098: pre-accept the cookie-consent banner via addInitScript so the
//     mobile (375px) viewport doesn't have the bottom banner overlay
//     intercept clicks.
//   - MEM108: pre-dismiss the chrome-extension promo (its 2s detect-then-show
//     timer can race the snapshot otherwise).
//   - MEM066/MEM068: every Playwright project uses Desktop Chrome (already
//     enforced in playwright.config.ts) so chromium-only baselines are stable.
//   - MEM079: SparklineCell IO observer fires deterministically only after
//     scrollIntoViewIfNeeded() — tablet/mobile horizontally scroll the
//     responsive table and push the price column past the viewport.
//   - MEM105: gate per-project tests via `testInfo.project.name`, not env.
//   - Pin Date.now() to FIXED_NOW_ISO for deterministic rendering.
//   - page.on('pageerror') re-throws runtime React errors as hard failures.

const MULTI_PART_ID = '11111111-1111-1111-1111-111111111111';
const SINGLE_PART_ID = '22222222-2222-2222-2222-222222222222';
const ZERO_PART_ID = '33333333-3333-3333-3333-333333333333';

const FIXED_NOW_ISO = '2026-04-25T12:00:00.000Z';
const ONE_DAY_MS = 24 * 60 * 60 * 1000;
const FRESH_LISTING_OBSERVED_AT = new Date(
  Date.parse(FIXED_NOW_ISO) - 5 * ONE_DAY_MS,
).toISOString();

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

const USER_ID = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
const MOCK_USER = {
  id: USER_ID,
  username: 'partshopper',
  email: 'partshopper@example.com',
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

const BUILD_LIST_ID = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';
const MOCK_BUILD_LIST = {
  id: BUILD_LIST_ID,
  name: 'My Build',
  description: 'Demo build list — fixture-only.',
  car_id: null,
  user_id: USER_ID,
  image_urls: null,
  created_at: FIXED_NOW_ISO,
  updated_at: FIXED_NOW_ISO,
};

interface MockPart {
  id: string;
  name: string;
  description: string;
  best_price_cents: number | null;
  image_urls: null;
  category_id: string;
  user_id: string;
  car_ids: string[];
  is_universal: boolean;
  part_manufacturer_id: string;
  part_manufacturer: string;
  part_number: string;
  specifications: null;
  canonical_part_id: null;
  is_verified: boolean;
  source: string;
  edit_count: number;
  created_at: string;
  updated_at: string;
  upvotes: number;
  downvotes: number;
  total_votes: number;
  user_vote: null;
}

function makeMockPart(
  overrides: Partial<MockPart> & Pick<MockPart, 'id' | 'name'>,
): MockPart {
  return {
    description: 'Mocked part for e2e parts-catalog spec.',
    best_price_cents: 12999,
    image_urls: null,
    category_id: MOCK_CATEGORY_ID,
    user_id: USER_ID,
    car_ids: [],
    is_universal: true,
    part_manufacturer_id: MOCK_PART_MANUFACTURER_ID,
    part_manufacturer: MOCK_PART_MANUFACTURER.name,
    part_number: 'PN-0001',
    specifications: null,
    canonical_part_id: null,
    is_verified: true,
    source: 'crawler',
    edit_count: 0,
    created_at: FIXED_NOW_ISO,
    updated_at: FIXED_NOW_ISO,
    upvotes: 5,
    downvotes: 1,
    total_votes: 6,
    user_vote: null,
    ...overrides,
  };
}

const MOCK_PARTS: Record<string, MockPart> = {
  [MULTI_PART_ID]: makeMockPart({
    id: MULTI_PART_ID,
    name: 'Multi-Observation Brake Pad',
    part_number: 'MULTI-001',
    best_price_cents: 12999,
  }),
  [SINGLE_PART_ID]: makeMockPart({
    id: SINGLE_PART_ID,
    name: 'Single-Observation Coilover',
    part_number: 'SINGLE-001',
    best_price_cents: 49999,
  }),
  [ZERO_PART_ID]: makeMockPart({
    id: ZERO_PART_ID,
    name: 'Zero-Observation Turbo',
    part_number: 'ZERO-001',
    best_price_cents: null,
  }),
};

const MOCK_PARTS_LIST: MockPart[] = [
  MOCK_PARTS[MULTI_PART_ID],
  MOCK_PARTS[SINGLE_PART_ID],
  MOCK_PARTS[ZERO_PART_ID],
];

const MOCK_PAGINATED_PARTS = {
  data: MOCK_PARTS_LIST,
  pagination: {
    current_page: 1,
    total_pages: 1,
    total_items: MOCK_PARTS_LIST.length,
    items_per_page: 100,
    has_next: false,
    has_previous: false,
  },
};

const MOCK_BATCH_RESPONSE = {
  summaries: {
    [MULTI_PART_ID]: {
      min_cents: 11999,
      max_cents: 14999,
      last_cents: 12999,
      last_observed_at: FRESH_LISTING_OBSERVED_AT,
      trend: 'down',
      observation_count: 6,
    },
    [SINGLE_PART_ID]: {
      min_cents: 49999,
      max_cents: 49999,
      last_cents: 49999,
      last_observed_at: FRESH_LISTING_OBSERVED_AT,
      trend: 'flat',
      observation_count: 1,
    },
    [ZERO_PART_ID]: {
      min_cents: null,
      max_cents: null,
      last_cents: null,
      last_observed_at: null,
      trend: 'flat',
      observation_count: 0,
    },
  },
  window: '90d',
  requested_count: 3,
  found_count: 3,
};

// PartPriceHistoryReadWithRetailer[] — used by the SparklineCell lazy fetch
// for the multi-observation row scrolled into view.
const MOCK_PRICE_HISTORY_ARRAY = [
  { id: 'h1', part_listing_id: 'l1', price_cents: 14999, observed_at: '2026-02-01T00:00:00.000Z', retailer_id: 'r1', retailer_name: 'RetailerOne' },
  { id: 'h2', part_listing_id: 'l1', price_cents: 13999, observed_at: '2026-02-15T00:00:00.000Z', retailer_id: 'r1', retailer_name: 'RetailerOne' },
  { id: 'h3', part_listing_id: 'l1', price_cents: 13499, observed_at: '2026-03-01T00:00:00.000Z', retailer_id: 'r1', retailer_name: 'RetailerOne' },
  { id: 'h4', part_listing_id: 'l2', price_cents: 12999, observed_at: '2026-03-15T00:00:00.000Z', retailer_id: 'r2', retailer_name: 'RetailerTwo' },
  { id: 'h5', part_listing_id: 'l2', price_cents: 12499, observed_at: '2026-04-01T00:00:00.000Z', retailer_id: 'r2', retailer_name: 'RetailerTwo' },
  { id: 'h6', part_listing_id: 'l1', price_cents: 11999, observed_at: '2026-04-20T00:00:00.000Z', retailer_id: 'r1', retailer_name: 'RetailerOne' },
];

const MOCK_SINGLE_SUMMARY = {
  summary: MOCK_BATCH_RESPONSE.summaries[MULTI_PART_ID],
  retailers: [
    {
      retailer_id: 'r1',
      retailer_name: 'RetailerOne',
      min_cents: 11999,
      max_cents: 14999,
      last_cents: 11999,
      last_observed_at: FRESH_LISTING_OBSERVED_AT,
      observation_count: 4,
    },
  ],
  history: MOCK_PRICE_HISTORY_ARRAY,
  window: '90d',
};

const MOCK_VOTE_SUMMARY_DEFAULT = {
  entity_id: '',
  entity_type: 'part',
  upvotes: 0,
  downvotes: 0,
  total_votes: 0,
  vote_score: 0,
  user_vote: null,
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

interface NetworkCounters {
  batchPriceHistoryPostCount: number;
}

async function mockApi(
  page: import('@playwright/test').Page,
  counters: NetworkCounters,
): Promise<void> {
  await page.route(/\/api\/(?!.*\.ts)/, async (route: Route, request: Request) => {
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api/, '');
    const method = request.method();

    // ---------- Auth + global settings ----------
    if (path === '/users/me' && method === 'GET') {
      // Authenticated viewer — diverges from price-history.spec.ts's anonymous
      // mock so the "My Parts" link renders and AddToBuildList trigger flips
      // canManage=true on the row actions.
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

    // ---------- Parts: catalog + filter options ----------
    if (path === '/parts/with-votes' && method === 'GET') {
      return jsonResponse(route, MOCK_PAGINATED_PARTS);
    }
    if (path === '/parts/filter-options' && method === 'GET') {
      return jsonResponse(route, {
        category_ids: [MOCK_CATEGORY_ID],
        part_manufacturer_ids: [MOCK_PART_MANUFACTURER_ID],
        car_ids: [],
        make_names: [],
      });
    }

    // ---------- Parts: batch price history (POST) ----------
    if (path === '/parts/price-history' && method === 'POST') {
      counters.batchPriceHistoryPostCount += 1;
      return jsonResponse(route, MOCK_BATCH_RESPONSE);
    }

    // ---------- Parts: single-part price history (SparklineCell lazy fetch) ----------
    const priceHistoryMatch = path.match(/^\/parts\/([^/]+)\/price-history$/);
    if (priceHistoryMatch && method === 'GET') {
      const partId = priceHistoryMatch[1];
      if (partId === MULTI_PART_ID) {
        return jsonResponse(route, MOCK_SINGLE_SUMMARY);
      }
      return jsonResponse(route, {
        summary: {
          min_cents: null,
          max_cents: null,
          last_cents: null,
          last_observed_at: null,
          trend: 'flat',
          observation_count: 0,
        },
        retailers: [],
        history: [],
        window: '90d',
      });
    }

    // ---------- Build lists by user (drives AddToBuildList dialog) ----------
    // The dialog calls buildListsApi.getBuildListsByUser(user.id), which hits
    // GET /build-lists/user/{userId} (not ?user_id=). Match that exact path.
    const buildListsByUserMatch = path.match(/^\/build-lists\/user\/([^/]+)$/);
    if (buildListsByUserMatch && method === 'GET') {
      return jsonResponse(route, [MOCK_BUILD_LIST]);
    }

    // ---------- Votes ----------
    const voteSummaryMatch = path.match(
      /^\/votes\/([^/]+)\/([^/]+)\/summary$/,
    );
    if (voteSummaryMatch && method === 'GET') {
      const [, entityType, entityId] = voteSummaryMatch;
      return jsonResponse(route, {
        ...MOCK_VOTE_SUMMARY_DEFAULT,
        entity_id: entityId,
        entity_type: entityType,
      });
    }

    // Default: 404 — surface unexpected calls so the test (via the
    // pageerror listener / network-default-404) flags drift from the contract.
    return jsonResponse(route, { detail: `Mock miss: ${method} ${path}` }, 404);
  });
}

// ---------------------------------------------------------------------------
// Deterministic page setup helpers
// ---------------------------------------------------------------------------

async function setupPage(
  page: import('@playwright/test').Page,
): Promise<NetworkCounters> {
  // Pin Date.now() so any rendering that depends on "now" is deterministic.
  await page.addInitScript((nowIso: string) => {
    const fixed = new Date(nowIso).getTime();
    const realNow = Date.now.bind(Date);
    Date.now = () => fixed;
    (globalThis as unknown as Record<string, unknown>).__REAL_DATE_NOW__ =
      realNow;
  }, FIXED_NOW_ISO);

  // MEM098: pre-accept cookie-consent + MEM108: pre-dismiss the chrome-extension
  // promo for today so its 2s detect-then-show timer can't race the snapshot.
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

  const counters: NetworkCounters = { batchPriceHistoryPostCount: 0 };
  await mockApi(page, counters);

  page.on('pageerror', (err) => {
    throw err;
  });

  return counters;
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

test('parts catalog visual regression', async ({ page }) => {
  const counters = await setupPage(page);

  // Belt-and-braces witness: count POST /parts/price-history independently
  // of the route counter, so a mock-bypass would still fail the assertion.
  let observedBatchPosts = 0;
  page.on('request', (req: Request) => {
    if (req.method() === 'POST' && req.url().includes('/parts/price-history')) {
      observedBatchPosts += 1;
    }
  });

  await page.goto('/parts');
  await waitForPageReady(page);

  // Multi-observation row sparkline: SparklineCell is IO-gated (rootMargin
  // '100px'). On tablet/mobile the responsive table can scroll horizontally
  // so the price column may be off-viewport — scroll the container into view
  // first (MEM079) so the observer fires deterministically across all 3
  // viewport projects.
  const multiSparkContainer = page
    .locator(`[data-part-id="${MULTI_PART_ID}"]`)
    .first();
  await multiSparkContainer.scrollIntoViewIfNeeded();
  await expect(multiSparkContainer).toBeVisible();
  const multiSparkline = multiSparkContainer.locator('[role="img"]').first();
  await expect(multiSparkline).toBeVisible({ timeout: 10_000 });

  // S06 invariant: ONE batch POST per displayed catalog page. Both the route
  // counter and the request listener should agree.
  expect(counters.batchPriceHistoryPostCount).toBe(1);
  expect(observedBatchPosts).toBe(1);

  await expect(page).toHaveScreenshot({ fullPage: true });
});

test('add-to-build-list dialog opens, focus moves into it, Escape closes it', async ({
  page,
}, testInfo) => {
  test.skip(
    testInfo.project.name !== 'desktop',
    'Dialog keyboard interaction is asserted once on desktop',
  );

  // The responsive parts table drops the `actions` column (priority 7) at the
  // default 1280px desktop viewport once the sidebar + Tailwind container
  // caps are subtracted — the trigger button is not rendered there. Widen to
  // 2400px so all columns (including actions) fit and the AddToBuildList
  // trigger is in the DOM. Viewport-specific layout is asserted by the
  // visual-regression test, which keeps the configured per-project viewport.
  await page.setViewportSize({ width: 2400, height: 900 });
  await setupPage(page);

  await page.goto('/parts');
  await waitForPageReady(page);

  // useContainerWidth is a ResizeObserver-driven hook — give it a tick to
  // settle after the post-load layout pass before asserting the action
  // column dropped back in.
  const trigger = page
    .getByTestId('parts-catalog-add-to-build-list-trigger')
    .first();
  await expect(trigger).toBeVisible({ timeout: 15_000 });
  await trigger.click();

  const dialog = page.getByTestId('parts-catalog-add-to-build-list-dialog');
  await expect(dialog).toBeVisible();

  // Radix moves focus into the dialog on open. Assert the focused element is
  // a descendant of the dialog content surface.
  const focusInsideDialog = await page.evaluate(() => {
    const dialogEl = document.querySelector(
      '[data-testid="parts-catalog-add-to-build-list-dialog"]',
    );
    const focused = document.activeElement;
    return !!(dialogEl && focused && dialogEl.contains(focused));
  });
  expect(focusInsideDialog).toBe(true);

  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
});

test('tab traversal lands visible focus on search input', async ({
  page,
}, testInfo) => {
  test.skip(
    testInfo.project.name !== 'desktop',
    'Tab order is asserted once on desktop',
  );

  await setupPage(page);

  await page.goto('/parts');
  await waitForPageReady(page);

  // Wait for the search input to be ready so the page is interactive before
  // we start traversing focus.
  const searchInput = page.getByTestId('parts-catalog-search');
  await expect(searchInput).toBeVisible();

  // Move focus to the page body so Tab progresses from the start of the
  // document, then Tab forward until the active element is the search input.
  // The header/nav contributes a known number of focusable nodes (skip-link,
  // logo, nav links, "My Parts" outlined link) — bail out as soon as we land.
  await page.evaluate(() => {
    document.body.focus();
    if (document.activeElement !== document.body) {
      document.body.setAttribute('tabindex', '-1');
      document.body.focus();
    }
  });

  let foundOnTab = -1;
  for (let i = 1; i <= 30; i++) {
    await page.keyboard.press('Tab');
    const isSearch = await page.evaluate(
      () =>
        (document.activeElement as HTMLElement | null)?.dataset.testid ===
        'parts-catalog-search',
    );
    if (isSearch) {
      foundOnTab = i;
      break;
    }
  }

  expect(
    foundOnTab,
    'Tab traversal never reached the parts-catalog search input within 30 presses',
  ).toBeGreaterThan(0);

  // R020: the focused control must have a visible focus ring. ui/Input uses
  // Tailwind's focus-visible:ring-* utilities — assert the computed outline
  // or box-shadow is non-empty when focus-visible matches.
  const hasFocusRing = await searchInput.evaluate((el) => {
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
