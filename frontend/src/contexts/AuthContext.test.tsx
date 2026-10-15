import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@webbpulse/api-client';
import { buildApiError } from '../test/apiResponse';
import { mockUser } from '../test/mocks/api';

const { mockApiClient, mockIdentityClient } = vi.hoisted(() => {
  const listeners = new Set<(state: unknown) => void>();
  const freshState = () => ({
    status: 'unknown' as string,
    user: null as unknown,
    hasAccessToken: false,
    error: null,
    sessionEnded: null as unknown,
    pendingMfa: null,
    settled: false,
  });
  let state = freshState();
  const setState = (patch: Record<string, unknown>) => {
    const next = { ...state, ...patch };
    if (
      !next.settled &&
      (next.status === 'authenticated' || next.status === 'anonymous')
    ) {
      next.settled = true;
    }
    state = next;
    for (const listener of [...listeners]) listener(state);
  };
  const apiClient = {
    get: vi.fn().mockResolvedValue({ data: null }),
    post: vi.fn().mockResolvedValue({ data: null }),
    put: vi.fn().mockResolvedValue({ data: null }),
    delete: vi.fn().mockResolvedValue({ data: null }),
    patch: vi.fn().mockResolvedValue({ data: null }),
  };
  return {
    mockApiClient: apiClient,
    mockIdentityClient: {
      listeners,
      getState: () => state,
      setState,
      reset: () => {
        listeners.clear();
        state = freshState();
      },
      subscribe: (listener: (next: unknown) => void) => {
        listeners.add(listener);
        return () => listeners.delete(listener);
      },
      initialize: vi.fn(),
      logout: vi.fn(),
      setUser: vi.fn((user: unknown) => {
        setState({ user });
      }),
      reloadUser: vi.fn(async (): Promise<unknown> => {
        try {
          const response = (await apiClient.get('/users/me')) as {
            data?: unknown;
          };
          const user = response.data ?? null;
          setState({ user });
          return user;
        } catch (error) {
          if ((error as { status?: number }).status === 401) {
            setState({
              status: 'anonymous',
              user: null,
              hasAccessToken: false,
              sessionEnded: error,
            });
            return null;
          }
          setState({ error });
          return null;
        }
      }),
    },
  };
});

vi.mock('../api/identityClient', async () => {
  const actual = await vi.importActual<typeof import('../api/identityClient')>(
    '../api/identityClient'
  );
  return {
    ...actual,
    getIdentityClient: () => mockIdentityClient,
  };
});

vi.mock('../api/client', () => ({
  default: mockApiClient,
  apiClient: mockApiClient,
  setStoredToken: vi.fn(),
  getStoredToken: vi.fn(() => null),
  removeStoredToken: vi.fn(),
  isApiErrorWithStatus: (error: unknown): error is ApiError =>
    error instanceof ApiError,
}));

import { AuthProvider } from './AuthContext';
import { useAuth } from '../hooks/useAuth';

function Consumer() {
  const { isAuthenticated, user, isLoading, setUser, logout, reloadUser } =
    useAuth();
  return (
    <div>
      <span data-testid="state">
        {isAuthenticated ? (user?.username ?? 'authed-noname') : 'anon'}
      </span>
      <span data-testid="loading">{isLoading ? 'loading' : 'idle'}</span>
      <button type="button" onClick={() => setUser(mockUser)}>
        login-direct
      </button>
      <button type="button" onClick={() => void reloadUser()}>
        check
      </button>
      <button
        type="button"
        onClick={() => {
          void logout();
        }}
      >
        logout
      </button>
    </div>
  );
}

function renderWithProvider(children: ReactNode = <Consumer />) {
  return render(
    <MemoryRouter>
      <AuthProvider>{children}</AuthProvider>
    </MemoryRouter>
  );
}

describe('AuthContext provider', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIdentityClient.reset();
    mockIdentityClient.initialize.mockImplementation(() => {
      mockIdentityClient.setState({
        status: 'authenticated',
        user: mockUser,
        hasAccessToken: true,
      });
      return Promise.resolve(mockUser);
    });
    mockIdentityClient.logout.mockImplementation(() => {
      mockIdentityClient.setState({
        status: 'anonymous',
        user: null,
        hasAccessToken: false,
      });
      return Promise.resolve();
    });
  });

  it('spends the refresh cookie on mount and renders the signed in user', async () => {
    renderWithProvider();

    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe(mockUser.username)
    );

    expect(mockIdentityClient.initialize).toHaveBeenCalled();
    expect(screen.getByTestId('loading').textContent).toBe('idle');
  });

  it('stays unauthenticated when the startup refresh finds no session', async () => {
    mockIdentityClient.initialize.mockImplementation(() => {
      mockIdentityClient.setState({
        status: 'anonymous',
        user: null,
        hasAccessToken: false,
      });
      return Promise.resolve(null);
    });

    renderWithProvider();

    await waitFor(() =>
      expect(screen.getByTestId('loading').textContent).toBe('idle')
    );

    expect(screen.getByTestId('state').textContent).toBe('anon');
  });

  it('flips isAuthenticated to false when the session ends', async () => {
    renderWithProvider();

    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe(mockUser.username)
    );

    mockIdentityClient.setState({
      status: 'anonymous',
      user: null,
      hasAccessToken: false,
    });

    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe('anon')
    );
  });

  it('shows the profile a direct setUser() seeded, with no extra request', async () => {
    renderWithProvider();

    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe(mockUser.username)
    );

    vi.mocked(mockApiClient.get).mockClear();
    fireEvent.click(screen.getByText('login-direct'));

    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe(mockUser.username)
    );
    expect(vi.mocked(mockApiClient.get)).not.toHaveBeenCalled();
  });

  it('re-reads the profile on reloadUser()', async () => {
    renderWithProvider();

    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe(mockUser.username)
    );

    const renamed = { ...mockUser, username: 'renamed' };
    vi.mocked(mockApiClient.get).mockResolvedValueOnce({ data: renamed });

    fireEvent.click(screen.getByText('check'));

    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe('renamed')
    );
    expect(vi.mocked(mockApiClient.get)).toHaveBeenCalledWith('/users/me');
  });

  it('ends the session when reloadUser() is refused with a 401', async () => {
    renderWithProvider();

    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe(mockUser.username)
    );

    const renamed = { ...mockUser, username: 'renamed' };
    vi.mocked(mockApiClient.get).mockResolvedValueOnce({ data: renamed });
    fireEvent.click(screen.getByText('check'));
    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe('renamed')
    );

    vi.mocked(mockApiClient.get).mockRejectedValueOnce(
      buildApiError(401, {
        success: false,
        status: 401,
        message: 'Not authenticated',
        request_id: 'req-401',
      })
    );

    fireEvent.click(screen.getByText('check'));

    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe('anon')
    );
  });

  it('keeps the session on a non-401 reloadUser() failure', async () => {
    renderWithProvider();

    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe(mockUser.username)
    );

    vi.mocked(mockApiClient.get).mockRejectedValueOnce(
      buildApiError(500, {
        success: false,
        status: 500,
        message: 'Boom',
        request_id: 'req-500',
      })
    );

    fireEvent.click(screen.getByText('check'));

    await waitFor(() =>
      expect(mockIdentityClient.reloadUser).toHaveBeenCalled()
    );
    expect(screen.getByTestId('state').textContent).toBe(mockUser.username);
  });

  it('signs out on logout', async () => {
    renderWithProvider();

    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe(mockUser.username)
    );

    fireEvent.click(screen.getByText('logout'));

    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe('anon')
    );

    expect(mockIdentityClient.logout).toHaveBeenCalledTimes(1);
  });
});
