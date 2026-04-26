/* eslint-disable @typescript-eslint/unbound-method, @typescript-eslint/no-unsafe-assignment --
 * vi.mocked(apiClient.get) is the canonical Phase 8 mocking pattern.
 * `expect.objectContaining(...)` returns `any` and trips no-unsafe-assignment
 * when nested as a property value — false positive in this matcher pattern.
 */

// Phase 8 plan 08-14 (D-11) — Search page render + URL-driven API round-trip.
//
// Search imports `searchApi` from `../services/Api`. The global setup.ts mock
// provides only `default: mockApiClient`; we extend via a local vi.mock that
// forwards searchApi.search through the already-mocked apiClient.
//
// NOTE: we bypass test-utils.tsx's customRender — that helper registers its
// own vi.mock('../../services/Api', ...) with ONLY `default`, which would
// shadow the test-file mock and drop `searchApi`. We render manually with
// MemoryRouter at the `/search?q=...` route.

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { apiClient } from '../api/client';
import { mockBuildList, mockPart, mockUser } from '../test/mocks/api';
import { mockUseAuth } from '../test/utils/test-mocks';

vi.mock('../services/Api', async () => {
  const clientMod = await import('../api/client');
  const client = clientMod.apiClient;
  return {
    default: client,
    apiClient: client,
    searchApi: {
      search: (params: { q: string; skip?: number; limit?: number }) =>
        client.get('/search/', { params }),
    },
  };
});

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

import Search from './Search';

const searchResultsFixture = {
  data: {
    query: 'honda',
    build_lists: {
      data: [mockBuildList],
      total: 1,
      has_next: false,
      skip: 0,
      limit: 10,
    },
    users: {
      data: [mockUser],
      total: 1,
      has_next: false,
      skip: 0,
      limit: 10,
    },
    parts: {
      data: [mockPart],
      total: 1,
      has_next: false,
      skip: 0,
      limit: 10,
    },
  },
};

const emptyResultsFixture = {
  data: {
    query: 'missing',
    build_lists: { data: [], total: 0, has_next: false, skip: 0, limit: 10 },
    users: { data: [], total: 0, has_next: false, skip: 0, limit: 10 },
    parts: { data: [], total: 0, has_next: false, skip: 0, limit: 10 },
  },
};

describe('Search page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      checkAuthStatus: vi.fn(),
    });
  });

  it('renders the initial empty state when no query is in the URL', () => {
    render(
      <MemoryRouter initialEntries={['/search']}>
        <Search />
      </MemoryRouter>
    );
    expect(
      screen.getByRole('heading', { name: /^search$/i })
    ).toBeInTheDocument();
    expect(
      screen.getByText(/enter a search term to find build lists/i)
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/search build lists, users, and parts/i)
    ).toBeInTheDocument();
  });

  it('renders search results from the API when query param is present', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(searchResultsFixture);

    render(
      <MemoryRouter initialEntries={['/search?q=honda']}>
        <Search />
      </MemoryRouter>
    );

    await waitFor(() =>
      expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
        '/search/',
        expect.objectContaining({
          params: expect.objectContaining({ q: 'honda' }),
        })
      )
    );
  });

  it('shows a no-results message when the API returns empty result sets', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(emptyResultsFixture);

    render(
      <MemoryRouter initialEntries={['/search?q=missing']}>
        <Search />
      </MemoryRouter>
    );

    await waitFor(() =>
      expect(
        screen.getByText(/no results found for "missing"/i)
      ).toBeInTheDocument()
    );
  });
});
