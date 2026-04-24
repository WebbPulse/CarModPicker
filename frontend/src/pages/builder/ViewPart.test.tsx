// Phase 8 plan 08-11 (D-11) — page test for ViewPart.
//
// ViewPart is the app's largest single page (~800 lines). It routes as
// `/parts/:partId` and fetches from 7 endpoints on mount:
//   - /parts/{id}                     (part)
//   - /votes/part/{id}/summary        (vote summary via partVotesApi)
//   - /categories/                    (category list)
//   - /users/{userId}                 (owner)
//   - /parts/{id}/listings            (retailer listings)
//   - /parts/{id}/price-history       (price history)
// Optional (only when part.part_manufacturer_id is set): /part-manufacturers/{id}
//
// Coverage targets per D-11 + PATTERNS.md §11:
//   1. Happy path — part name + specifications render.
//   2. Community Rating section + vote widget render.
//   3. Interactive vote flow — clicking upvote triggers apiClient.post to
//      `/votes/part/${id}` (the votesApi polymorphic URL; see api/votes.ts).

/* eslint-disable @typescript-eslint/unbound-method --
 * vi.mocked(apiClient.*) is the canonical Vitest pattern for typed mock
 * introspection; same rationale as AuthContext.test.tsx.
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// jsdom ResizeObserver stub (same rationale as ViewBuildlist.test.tsx).
class ResizeObserverStub {
  constructor(_cb: ResizeObserverCallback) {
    void _cb;
  }
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
if (typeof globalThis.ResizeObserver === 'undefined') {
  (
    globalThis as unknown as { ResizeObserver: typeof ResizeObserverStub }
  ).ResizeObserver = ResizeObserverStub;
}

import { apiClient } from '../../api/client';
import {
  mockCategory,
  mockPart,
  mockUser,
  mockVoteSummary,
} from '../../test/mocks/api';
import { mockUseAuth } from '../../test/utils/test-mocks';
import ViewPart from './ViewPart';

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

// Extend the global services/Api mock to expose named domain APIs (partsApi,
// partVotesApi, categoriesApi, usersApi, etc. — all consumed by ViewPart).
vi.mock('../../services/Api', async () => {
  const actual =
    await vi.importActual<typeof import('../../services/Api')>(
      '../../services/Api'
    );
  return actual;
});

// testScenarios.authenticated equivalent (Phase 8 D-05).
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

function installDefaultGetRouting(): void {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === `/parts/${mockPart.id}`) {
      return Promise.resolve({ data: mockPart });
    }
    if (url === `/votes/part/${mockPart.id}/summary`) {
      return Promise.resolve({ data: mockVoteSummary });
    }
    if (url === '/categories/') {
      return Promise.resolve({ data: [mockCategory] });
    }
    if (url === `/users/${mockUser.id}`) {
      return Promise.resolve({ data: mockUser });
    }
    if (url === `/parts/${mockPart.id}/listings`) {
      return Promise.resolve({ data: [] });
    }
    if (url === `/parts/${mockPart.id}/price-history`) {
      return Promise.resolve({ data: [] });
    }
    return Promise.resolve({ data: null });
  });
}

describe('ViewPart page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    seedAuthenticated();
  });

  it('renders the part name and specification rows once fetches resolve', async () => {
    installDefaultGetRouting();

    render(
      <MemoryRouter initialEntries={[`/parts/${mockPart.id}`]}>
        <Routes>
          <Route path="/parts/:partId" element={<ViewPart />} />
        </Routes>
      </MemoryRouter>
    );

    // PageHeader swaps from "Part Details" loader to the part name.
    await waitFor(() =>
      expect(
        screen.getByRole('heading', { level: 1, name: mockPart.name })
      ).toBeInTheDocument()
    );

    // Specifications block labels + values render.
    await waitFor(() =>
      expect(screen.getByText('Specifications:')).toBeInTheDocument()
    );
    // Values from mockPart.specifications — { weight: '2.5kg', material: 'aluminum' }
    expect(screen.getByText(/aluminum/i)).toBeInTheDocument();
    expect(screen.getByText(/2\.5kg/i)).toBeInTheDocument();

    // Canonical fetch paths observed.
    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      `/parts/${mockPart.id}`
    );
    expect(vi.mocked(apiClient.get)).toHaveBeenCalledWith(
      `/votes/part/${mockPart.id}/summary`
    );
  });

  it('renders the Community Rating vote widget with upvote + downvote buttons', async () => {
    installDefaultGetRouting();

    render(
      <MemoryRouter initialEntries={[`/parts/${mockPart.id}`]}>
        <Routes>
          <Route path="/parts/:partId" element={<ViewPart />} />
        </Routes>
      </MemoryRouter>
    );

    // "Community Rating" header renders once partWithVotes is derived.
    await waitFor(() =>
      expect(screen.getByText('Community Rating')).toBeInTheDocument()
    );

    // VoteButtons renders both upvote + downvote buttons (accessible via
    // their `title` attributes → accessible name).
    expect(
      screen.getByRole('button', { name: /upvote/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /downvote/i })
    ).toBeInTheDocument();

    // Current vote score surfaces — mockVoteSummary has 5 upvotes / 1 downvote
    // → local total = 5 - 1 = 4, rendered as "+4".
    expect(screen.getByText('+4')).toBeInTheDocument();
  });

  it('posts to the vote endpoint when the user clicks a vote button', async () => {
    installDefaultGetRouting();
    // mockVoteSummary.user_vote is 'upvote'. Clicking upvote should call
    // voteApi.removeVote (toggle off) → DELETE /votes/part/{id}. Click
    // downvote to trigger a fresh POST instead (the canonical "voted on
    // part" flow the plan targets).
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { entity_id: mockPart.id, vote_type: 'downvote' },
    });

    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={[`/parts/${mockPart.id}`]}>
        <Routes>
          <Route path="/parts/:partId" element={<ViewPart />} />
        </Routes>
      </MemoryRouter>
    );

    // Wait for vote widget to render.
    await waitFor(() =>
      expect(screen.getByText('Community Rating')).toBeInTheDocument()
    );
    const downvoteButton = screen.getByRole('button', { name: /downvote/i });

    await user.click(downvoteButton);

    // partVotesApi.voteOnPart → votesApi.voteOnEntity('part', id, ...) →
    // POST `/votes/part/${id}` with the vote payload.
    await waitFor(() =>
      expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
        `/votes/part/${mockPart.id}`,
        expect.objectContaining({ vote_type: 'downvote' })
      )
    );
  });
});
