/* eslint-disable @typescript-eslint/no-unsafe-assignment */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { apiClient, type ApiRequestConfig } from '../api/client';
import type { SearchResults } from '../api/search';
import {
  mockBuildList,
  mockCar,
  mockPart,
  mockUser,
  mockVoteSummary,
} from '../test/mocks/api';
import { mockUseAuth } from '../test/utils/test-mocks';

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

import Search from './Search';

const searchResults: SearchResults = {
  query: 'honda',
  build_lists: { items: [mockBuildList], next_cursor: null, has_next: false },
  users: { items: [mockUser], next_cursor: null, has_next: false },
  parts: { items: [mockPart], next_cursor: 'parts-cursor-1', has_next: true },
};

const secondPartsPage: SearchResults = {
  query: 'honda',
  build_lists: { items: [mockBuildList], next_cursor: null, has_next: false },
  users: { items: [mockUser], next_cursor: null, has_next: false },
  parts: {
    items: [{ ...mockPart, id: 'part-2', name: 'Second Part' }],
    next_cursor: null,
    has_next: false,
  },
};

const emptyResults: SearchResults = {
  query: 'missing',
  build_lists: { items: [], next_cursor: null, has_next: false },
  users: { items: [], next_cursor: null, has_next: false },
  parts: { items: [], next_cursor: null, has_next: false },
};

const routeGet = (
  search: (params: Record<string, unknown>) => SearchResults
) => {
  vi.mocked(apiClient.get).mockImplementation(
    (path: string, config?: ApiRequestConfig) => {
      if (path === '/search') {
        const params = (config?.params ?? {}) as Record<string, unknown>;
        return Promise.resolve({ data: search(params) });
      }
      if (path.startsWith('/car-generations/')) {
        return Promise.resolve({ data: mockCar });
      }
      return Promise.resolve({ data: mockVoteSummary });
    }
  );
};

describe('Search page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      isLoading: false,
      setUser: vi.fn(),
      logout: vi.fn(),
      reloadUser: vi.fn(),
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
      screen.getByPlaceholderText(/search build lists, parts and users/i)
    ).toBeInTheDocument();
  });

  it('renders build lists, parts and users from the cursor paged response', async () => {
    routeGet(() => searchResults);

    render(
      <MemoryRouter initialEntries={['/search?q=honda']}>
        <Search />
      </MemoryRouter>
    );

    expect(await screen.findByText(mockBuildList.name)).toBeInTheDocument();
    expect(screen.getByText(mockPart.name)).toBeInTheDocument();
    expect(screen.getByText(mockUser.username)).toBeInTheDocument();
    expect(screen.getByText('Parts (1+)')).toBeInTheDocument();
    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      '/search',
      expect.objectContaining({
        params: expect.objectContaining({ q: 'honda' }),
      })
    );
  });

  it('loads the next page of one category with its cursor', async () => {
    routeGet((params) =>
      params['parts_cursor'] === 'parts-cursor-1'
        ? secondPartsPage
        : searchResults
    );

    render(
      <MemoryRouter initialEntries={['/search?q=honda']}>
        <Search />
      </MemoryRouter>
    );

    fireEvent.click(
      await screen.findByRole('button', { name: /load more parts/i })
    );

    expect(await screen.findByText('Second Part')).toBeInTheDocument();
    expect(screen.getByText(mockPart.name)).toBeInTheDocument();
    expect(screen.getByText('Parts (2)')).toBeInTheDocument();
    expect(screen.getAllByText(mockBuildList.name)).toHaveLength(1);
    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      '/search',
      expect.objectContaining({
        params: expect.objectContaining({
          q: 'honda',
          parts_cursor: 'parts-cursor-1',
        }),
      })
    );
    expect(
      screen.queryByRole('button', { name: /load more parts/i })
    ).not.toBeInTheDocument();
  });

  it('shows a no-results message when the API returns empty result sets', async () => {
    routeGet(() => emptyResults);

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
