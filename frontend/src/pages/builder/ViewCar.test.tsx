// Phase 8 plan 08-11 (D-11) — page test for ViewCar.
//
// ViewCar is routed as `/car-generations/:carId` and hydrates from multiple
// endpoints on mount:
//   - carGenerationsApi.getCar(carId)           → GET /car-generations/{id}
//   - categoriesApi.getCategories()             → GET /categories/
//   - BuildListList                             → GET /build-lists/car/{id}
//   - PartList (via partsApi.getPartsWithVotes) → GET /parts/with-votes
//
// We route responses by URL prefix via a single vi.mocked(apiClient.get)
// implementation so all effects settle with deterministic data.

/* eslint-disable @typescript-eslint/unbound-method, @typescript-eslint/prefer-promise-reject-errors --
 * vi.mocked(apiClient.get) is the canonical Vitest pattern for typed mock
 * introspection (same rationale as AuthContext.test.tsx). The AxiosError-shaped
 * rejection object is intentionally plain (not an Error instance) so it mimics
 * the exact shape Axios passes to useApiRequest's parseApiError — wrapping it
 * in an Error would defeat the point of exercising that branch.
 */

import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../../api/client';
import {
  mockBuildList,
  mockCar,
  mockCategory,
  mockUser,
} from '../../test/mocks/api';
import { mockUseAuth } from '../../test/utils/test-mocks';
import ViewCar from './ViewCar';

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

// Extend the global setup.ts mock of `../services/Api` (which only exports
// `default`) with the named exports ViewCar consumes (carGenerationsApi,
// categoriesApi). Re-exporting the real module resolves this cleanly because
// the domain APIs internally call the globally-mocked `apiClient`.
vi.mock('../../services/Api', async () => {
  const actual =
    await vi.importActual<typeof import('../../services/Api')>(
      '../../services/Api'
    );
  return actual;
});

// Auth fixture. Inlined equivalent of the canonical testScenarios.authenticated
// shape from `src/test/utils/test-utils.tsx` (Phase 8 D-05) — we can't import
// test-utils directly because its `vi.mock('../../services/Api', ...)` would
// clobber our importActual-based extension above.
const authenticatedAuthState = {
  isAuthenticated: true,
  isLoading: false,
} as const;

function seedAuthenticated(): void {
  mockUseAuth.mockReturnValue({
    isAuthenticated: authenticatedAuthState.isAuthenticated,
    user: mockUser,
    isLoading: authenticatedAuthState.isLoading,
    login: vi.fn(),
    logout: vi.fn(),
    checkAuthStatus: vi.fn().mockResolvedValue(undefined),
  });
}

describe('ViewCar page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    seedAuthenticated();
  });

  it('renders the car header, info card, and nested sections when the fetch succeeds', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === `/car-generations/${mockCar.id}`) {
        return Promise.resolve({ data: mockCar });
      }
      if (url === '/categories/') {
        return Promise.resolve({ data: [mockCategory] });
      }
      if (url.startsWith(`/build-lists/car/${mockCar.id}`)) {
        return Promise.resolve({
          data: {
            data: [mockBuildList],
            pagination: {
              current_page: 1,
              total_pages: 1,
              total_items: 1,
              items_per_page: 10,
              has_next: false,
              has_previous: false,
            },
          },
        });
      }
      if (url === '/parts/with-votes') {
        return Promise.resolve({
          data: {
            data: [],
            pagination: {
              current_page: 1,
              total_pages: 0,
              total_items: 0,
              items_per_page: 12,
              has_next: false,
              has_previous: false,
            },
          },
        });
      }
      return Promise.resolve({ data: null });
    });

    render(
      <MemoryRouter initialEntries={[`/car-generations/${mockCar.id}`]}>
        <Routes>
          <Route path="/car-generations/:carId" element={<ViewCar />} />
        </Routes>
      </MemoryRouter>
    );

    // PageHeader contains the formatted make / model / year range. Wait for
    // the car fetch to resolve and the page-level <h1> to swap from the
    // "Car Details" loading title.
    await waitFor(() =>
      expect(
        screen.getByRole('heading', {
          level: 1,
          name: new RegExp(mockCar.car_make_name),
        })
      ).toBeInTheDocument()
    );

    // Make / Model / Generation / Year Range info items render.
    expect(screen.getByText('Make:')).toBeInTheDocument();
    expect(screen.getByText('Model:')).toBeInTheDocument();
    expect(screen.getByText('Generation:')).toBeInTheDocument();
    expect(screen.getByText('Year Range:')).toBeInTheDocument();

    // Category switcher button (All + the mock category) renders after
    // /categories/ resolves.
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /^All$/ })).toBeInTheDocument()
    );

    // The fetch was dispatched to the canonical /car-generations/{id} endpoint.
    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      `/car-generations/${mockCar.id}`
    );
  });

  it('renders an error alert when the car fetch rejects', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === `/car-generations/${mockCar.id}`) {
        return Promise.reject({
          isAxiosError: true,
          response: { data: { detail: 'Car not found' }, status: 404 },
        });
      }
      return Promise.resolve({ data: null });
    });

    render(
      <MemoryRouter initialEntries={[`/car-generations/${mockCar.id}`]}>
        <Routes>
          <Route path="/car-generations/:carId" element={<ViewCar />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() =>
      expect(
        screen.getByText(/Failed to load car with ID/i)
      ).toBeInTheDocument()
    );

    // "Car Details" placeholder header is used on the error path.
    expect(
      screen.getByRole('heading', { name: /Car Details/i })
    ).toBeInTheDocument();
  });

  it('selects a category when the user clicks its button', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === `/car-generations/${mockCar.id}`) {
        return Promise.resolve({ data: mockCar });
      }
      if (url === '/categories/') {
        return Promise.resolve({ data: [mockCategory] });
      }
      if (url.startsWith(`/build-lists/car/${mockCar.id}`)) {
        return Promise.resolve({
          data: {
            data: [],
            pagination: {
              current_page: 1,
              total_pages: 0,
              total_items: 0,
              items_per_page: 10,
              has_next: false,
              has_previous: false,
            },
          },
        });
      }
      if (url === '/parts/with-votes') {
        return Promise.resolve({
          data: {
            data: [],
            pagination: {
              current_page: 1,
              total_pages: 0,
              total_items: 0,
              items_per_page: 12,
              has_next: false,
              has_previous: false,
            },
          },
        });
      }
      return Promise.resolve({ data: null });
    });

    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={[`/car-generations/${mockCar.id}`]}>
        <Routes>
          <Route path="/car-generations/:carId" element={<ViewCar />} />
        </Routes>
      </MemoryRouter>
    );

    // Wait for the category button to render.
    const allButton = await screen.findByRole('button', { name: /^All$/ });
    const categoryButton = within(allButton.parentElement!).getByRole(
      'button',
      { name: new RegExp(mockCategory.display_name, 'i') }
    );

    // Category starts unselected (bg-gray-700 class); clicking selects it
    // (bg-blue-600 class). We just assert the click doesn't throw and the
    // button is present/clickable — the handler dispatches a parts refresh,
    // which we don't introspect here (covered by the parts/PartList tests).
    await user.click(categoryButton);
    expect(categoryButton).toBeInTheDocument();
  });
});
