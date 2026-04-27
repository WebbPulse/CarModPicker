// Phase 8 Wave 3 page test — PartsCatalog renders the public parts catalog
// and exercises the real usePartsFilters hook (reads from useSearchParams).
//
// Why this file does not import from ../../test/utils/test-utils:
//   test-utils.tsx registers `vi.mock('../../services/Api', () => ({ default }))`
//   which strips the named API handles (partsApi, categoriesApi, etc.) that
//   usePartsFilters + PartList require. Because test-utils.tsx's vi.mock is
//   hoisted AFTER ours when we import `render` from it, it always wins. We
//   instead build a local render that wraps children in <MemoryRouter> and
//   seeds useAuth via the same mockUseAuth singleton test-utils uses — so
//   testScenarios stay behaviorally identical without the services/Api mock.
/* eslint-disable @typescript-eslint/unbound-method */
import type { ReactElement, ReactNode } from 'react';
import { render as rtlRender, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { mockUseAuth } from '../../test/utils/test-mocks';
import { mockCategory, mockPart, mockUser } from '../../test/mocks/api';
import type { UserRead } from '../../types/Api';
import PartsCatalog from './PartsCatalog';

// Mock useAuth the same way TestProviders does — swap the auth state per
// scenario without pulling in test-utils.tsx's services/Api mock.
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

// Re-expose the named API handles that usePartsFilters + PartList pull from
// the services/Api re-export shim. Forward through the shared mocked
// apiClient (setup.ts D-18 already mocks `../api/client` as mockApiClient).
vi.mock('../../services/Api', async () => {
  const clientMod = await import('../../api/client');
  const client = clientMod.apiClient;
  return {
    default: client,
    apiClient: client,
    partsApi: {
      getParts: (params?: unknown) => client.get('/parts/', { params }),
      getPartsWithVotes: (params?: unknown) =>
        client.get('/parts/with-votes', { params }),
      getFilterOptions: (params?: unknown) =>
        client.get('/parts/filter-options', { params }),
      getPart: (partId: string) => client.get(`/parts/${partId}`),
      deletePart: (partId: string) => client.delete(`/parts/${partId}`),
      appendPartImages: (partId: string, fileKeys: string[]) =>
        client.post(`/parts/${partId}/append-images`, { file_keys: fileKeys }),
      removePartImage: (partId: string, i: number) =>
        client.delete(`/parts/${partId}/images/${i}`),
    },
    partVotesApi: {
      voteOnPart: (id: string, data: unknown) =>
        client.post(`/parts/${id}/votes`, data),
      removeVote: (id: string) => client.delete(`/parts/${id}/votes`),
    },
    categoriesApi: {
      getCategories: () => client.get('/categories/'),
    },
    partManufacturersApi: {
      getPartManufacturers: (active = true) =>
        client.get('/part-manufacturers/', { params: { active_only: active } }),
    },
    carGenerationsApi: {
      getCar: (id: string) => client.get(`/car-generations/${id}`),
      getCarsByIds: (ids: string[]) =>
        client.get('/car-generations/', { params: { ids } }),
      getCarsByMake: (make: string, params?: unknown) =>
        client.get(`/car-generations/make/${make}`, { params }),
      getCarMakeStats: () => client.get('/car-generations/stats/makes'),
      listCars: (params?: unknown) =>
        client.get('/car-generations/', { params }),
    },
    buildListPartsApi: {
      countBuildListsContainingPart: (partId: string) =>
        client.get(`/build-list-parts/part/${partId}/count`),
    },
  };
});

// Import apiClient AFTER vi.mock declarations so it resolves to the mocked
// module (setup.ts already mocks `../api/client` globally).
import { apiClient } from '../../api/client';

// PartList renders inside PartsCatalog and depends on ResizeObserver via
// useContainerWidth. jsdom doesn't ship one — stub here so mounting doesn't
// throw when useContainerWidth's callback ref attaches to a DOM node.
class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
if (typeof globalThis.ResizeObserver === 'undefined') {
  (
    globalThis as unknown as { ResizeObserver: typeof ResizeObserverStub }
  ).ResizeObserver = ResizeObserverStub;
}

interface AuthState {
  isAuthenticated: boolean;
  user: UserRead | null;
  isLoading?: boolean;
}

const seedAuth = (state: AuthState) => {
  mockUseAuth.mockReturnValue({
    isAuthenticated: state.isAuthenticated,
    user: state.user,
    isLoading: state.isLoading ?? false,
    login: vi.fn(),
    logout: vi.fn(),
    checkAuthStatus: vi.fn(),
  });
};

const renderWithRouter = (
  ui: ReactElement,
  { route = '/parts' }: { route?: string } = {}
) =>
  rtlRender(ui, {
    wrapper: ({ children }: { children: ReactNode }) => (
      <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
    ),
  });

// Paginated response shape matches PaginatedResponse<PartReadWithVotes>
// (see frontend/src/types/Api.ts:334-337). PartReadWithVotes extends PartRead
// with upvotes/downvotes/total_votes/user_vote.
const makePaginatedPartsResponse = (
  items: (typeof mockPart)[] = [mockPart]
) => ({
  data: items.map((p) => ({
    ...p,
    upvotes: 0,
    downvotes: 0,
    total_votes: 0,
    user_vote: null,
  })),
  pagination: {
    current_page: 1,
    total_pages: 1,
    total_items: items.length,
    items_per_page: 100,
    has_next: false,
    has_previous: false,
  },
});

describe('PartsCatalog page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url.startsWith('/parts/with-votes')) {
        return Promise.resolve({ data: makePaginatedPartsResponse() });
      }
      if (url.startsWith('/parts/filter-options')) {
        return Promise.resolve({
          data: {
            category_ids: [mockCategory.id],
            part_manufacturer_ids: [],
            car_ids: [],
            make_names: [],
          },
        });
      }
      if (url.startsWith('/categories')) {
        return Promise.resolve({ data: [mockCategory] });
      }
      if (url.startsWith('/part-manufacturers')) {
        return Promise.resolve({ data: [] });
      }
      return Promise.resolve({ data: [] });
    });
  });

  it('renders the catalog title and fetches parts on mount', async () => {
    seedAuth({ isAuthenticated: false, user: null });
    renderWithRouter(<PartsCatalog />);

    // Title renders synchronously from PageHeader.
    expect(screen.getAllByText(/parts catalog/i).length).toBeGreaterThan(0);

    // PartList drives an effect that calls /parts/with-votes.
    await waitFor(() => {
      const calls = vi.mocked(apiClient.get).mock.calls.map(([url]) => url);
      expect(calls.some((u) => u.startsWith('/parts/with-votes'))).toBe(true);
    });

    // The fetched part name appears in the rendered row (link text).
    await waitFor(() => {
      expect(screen.getByText(mockPart.name)).toBeInTheDocument();
    });
  });

  it('renders the empty-state message when the API returns zero parts', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url.startsWith('/parts/with-votes')) {
        return Promise.resolve({ data: makePaginatedPartsResponse([]) });
      }
      if (url.startsWith('/parts/filter-options')) {
        return Promise.resolve({
          data: {
            category_ids: [],
            part_manufacturer_ids: [],
            car_ids: [],
            make_names: [],
          },
        });
      }
      if (url.startsWith('/categories')) {
        return Promise.resolve({ data: [mockCategory] });
      }
      return Promise.resolve({ data: [] });
    });

    seedAuth({ isAuthenticated: false, user: null });
    renderWithRouter(<PartsCatalog />);

    // Empty-state copy is wired in PartsCatalog.tsx:126 —
    // "No parts found. Try adjusting your filters."
    await waitFor(() => {
      expect(screen.getByText(/no parts found/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(mockPart.name)).not.toBeInTheDocument();
  });

  it('shows the "My Parts" shortcut only when the viewer is authenticated', async () => {
    seedAuth({ isAuthenticated: true, user: mockUser });
    renderWithRouter(<PartsCatalog />);

    // LinkButton text "My Parts" only renders when isAuthenticated is true.
    await waitFor(() => {
      expect(screen.getByText(/my parts/i)).toBeInTheDocument();
    });
  });
});
