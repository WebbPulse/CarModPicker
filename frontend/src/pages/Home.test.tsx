/* eslint-disable @typescript-eslint/unbound-method --
 * vi.mocked(apiClient.get) is the canonical Phase 8 mocking pattern.
 */

// Phase 8 plan 08-14 (D-11) — Home page happy-path + auth-branch tests.
//
// Home pulls named domain APIs (buildListsApi/partsApi/retailersApi/
// partManufacturersApi) from `../services/Api`. Per PATTERNS.md §7+§8 and the
// usePartsFilters.test.tsx precedent, the global setup.ts mock only exposes
// `default: mockApiClient` on services/Api — it does NOT replicate the named
// domain APIs that services/Api re-exports from api/<domain>. We install a
// local services/Api mock that forwards through the already-mocked apiClient.
//
// NOTE: we deliberately bypass test-utils.tsx's customRender because that
// helper also registers `vi.mock('../../services/Api', ...)` with ONLY
// `default: apiClient`, and Vitest prefers the mock hoisted from a loaded
// module over the test-file mock. We render manually with BrowserRouter +
// TestProviders-style mockUseAuth setup inline.

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';

import { apiClient } from '../api/client';
import { mockUser } from '../test/mocks/api';
import { mockUseAuth } from '../test/utils/test-mocks';

vi.mock('../services/Api', async () => {
  const clientMod = await import('../api/client');
  const client = clientMod.apiClient;
  return {
    default: client,
    apiClient: client,
    buildListsApi: {
      getBuildListsWithVotes: (params?: unknown) =>
        client.get('/build-lists/with-votes', { params }),
      countBuildLists: () => client.get('/build-lists/count'),
    },
    partsApi: {
      countParts: () => client.get('/parts/count'),
    },
    retailersApi: {
      countRetailers: () => client.get('/retailers/count'),
    },
    partManufacturersApi: {
      countPartManufacturers: () => client.get('/part-manufacturers/count'),
    },
  };
});

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

import Home from './Home';

describe('Home page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.get).mockResolvedValue({ data: [] });
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      checkAuthStatus: vi.fn(),
    });
  });

  it('renders the CarModPicker hero + unauthenticated CTAs (Get Started + Sign In)', () => {
    render(
      <BrowserRouter>
        <Home />
      </BrowserRouter>
    );

    expect(
      screen.getByRole('heading', { name: /carmodpicker/i })
    ).toBeInTheDocument();
    const getStarted = screen.getByRole('link', { name: /get started/i });
    expect(getStarted).toHaveAttribute('href', '/register');
    const signIn = screen.getByRole('link', { name: /sign in/i });
    expect(signIn).toHaveAttribute('href', '/login');
  });

  it('renders authenticated hero CTA (Create Build) when user is logged in', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: mockUser,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      checkAuthStatus: vi.fn(),
    });

    render(
      <BrowserRouter>
        <Home />
      </BrowserRouter>
    );

    // Hero "Create Build" CTA links to /builder.
    const createBuildLinks = screen.getAllByRole('link', {
      name: /create build/i,
    });
    expect(createBuildLinks.length).toBeGreaterThan(0);
    expect(createBuildLinks[0]).toHaveAttribute('href', '/builder');
  });

  it('renders Featured Builds section heading', () => {
    render(
      <BrowserRouter>
        <Home />
      </BrowserRouter>
    );

    expect(
      screen.getByRole('heading', { name: /featured builds/i })
    ).toBeInTheDocument();
  });

  it('fires off the initial API fetches on mount', async () => {
    render(
      <BrowserRouter>
        <Home />
      </BrowserRouter>
    );
    await waitFor(() => expect(vi.mocked(apiClient.get)).toHaveBeenCalled());
  });
});
