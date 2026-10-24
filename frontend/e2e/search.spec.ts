import { test, expect, type Route, type Request } from './fixtures';

const FIXED_NOW_ISO = '2026-04-25T12:00:00.000Z';

const USER_ID = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
const BUILD_LIST_ID = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';
const PART_ID = 'cccccccc-cccc-cccc-cccc-cccccccccccc';
const SECOND_PART_ID = 'dddddddd-dddd-dddd-dddd-dddddddddddd';

const MOCK_USER = {
  id: USER_ID,
  username: 'supradriver',
  image_urls: null,
  created_at: FIXED_NOW_ISO,
};

const MOCK_BUILD_LIST = {
  id: BUILD_LIST_ID,
  name: 'Supra Street Build',
  description: 'Fixture build list for the search spec.',
  car_id: null,
  user_id: USER_ID,
  image_urls: null,
  created_at: FIXED_NOW_ISO,
  updated_at: FIXED_NOW_ISO,
};

/**
 * Build a part fixture with the shared defaults.
 */
function makePart(id: string, name: string) {
  return {
    id,
    name,
    description: 'Fixture part for the search spec.',
    best_price_cents: 12999,
    image_urls: null,
    category_id: null,
    user_id: USER_ID,
    car_ids: [],
    is_universal: true,
    part_manufacturer_id: null,
    part_manufacturer: null,
    part_number: 'SUPRA-001',
    specifications: null,
    canonical_part_id: null,
    is_verified: true,
    source: 'user',
    edit_count: 0,
    created_at: FIXED_NOW_ISO,
    updated_at: FIXED_NOW_ISO,
  };
}

const FIRST_PAGE = {
  query: 'supra',
  build_lists: { items: [MOCK_BUILD_LIST], next_cursor: null, has_next: false },
  users: { items: [MOCK_USER], next_cursor: null, has_next: false },
  parts: {
    items: [makePart(PART_ID, 'Supra Turbo Manifold')],
    next_cursor: 'parts-cursor-1',
    has_next: true,
  },
};

const SECOND_PARTS_PAGE = {
  ...FIRST_PAGE,
  parts: {
    items: [makePart(SECOND_PART_ID, 'Supra Intercooler Kit')],
    next_cursor: null,
    has_next: false,
  },
};

/**
 * Fulfil a mocked route with a JSON body.
 */
function jsonResponse(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

/**
 * Serve the search page's API contract from fixtures as an anonymous viewer,
 * returning the second parts page when the parts cursor is sent.
 */
async function mockApi(page: import('@playwright/test').Page): Promise<void> {
  await page.route(
    /\/api\/(?!.*\.ts)/,
    async (route: Route, request: Request) => {
      const url = new URL(request.url());
      const path = url.pathname.replace(/^\/api/, '');
      const method = request.method();

      if (path === '/users/me' && method === 'GET') {
        return jsonResponse(route, { detail: 'Not authenticated' }, 401);
      }
      if (path === '/app-settings/' && method === 'GET') {
        return jsonResponse(route, {
          premium_disabled: true,
          updated_at: FIXED_NOW_ISO,
        });
      }
      if (path === '/search' && method === 'GET') {
        const partsCursor = url.searchParams.get('parts_cursor');
        return jsonResponse(
          route,
          partsCursor === 'parts-cursor-1' ? SECOND_PARTS_PAGE : FIRST_PAGE
        );
      }
      const voteMatch = path.match(/^\/votes\/([^/]+)\/([^/]+)\/summary$/);
      if (voteMatch && method === 'GET') {
        return jsonResponse(route, {
          entity_id: voteMatch[2],
          entity_type: voteMatch[1],
          upvotes: 0,
          downvotes: 0,
          total_votes: 0,
          vote_score: 0,
          user_vote: null,
        });
      }
      return jsonResponse(route, { detail: 'Not mocked' }, 404);
    }
  );
}

test.describe('search', () => {
  test('renders build lists, parts and users from the cursor paged response', async ({
    page,
  }) => {
    await mockApi(page);
    await page.goto('/search?q=supra');

    await expect(page.getByText('Supra Street Build')).toBeVisible();
    await expect(page.getByText('Supra Turbo Manifold')).toBeVisible();
    await expect(page.getByText('supradriver').first()).toBeVisible();
    await expect(page.getByText('Parts (1+)')).toBeVisible();
  });

  test('loads the next page of parts with its cursor', async ({ page }) => {
    await mockApi(page);
    await page.goto('/search?q=supra');

    await page.getByRole('button', { name: /load more parts/i }).click();

    await expect(page.getByText('Supra Intercooler Kit')).toBeVisible();
    await expect(page.getByText('Supra Turbo Manifold')).toBeVisible();
    await expect(page.getByText('Parts (2)')).toBeVisible();
    await expect(
      page.getByRole('button', { name: /load more parts/i })
    ).toHaveCount(0);
  });
});
