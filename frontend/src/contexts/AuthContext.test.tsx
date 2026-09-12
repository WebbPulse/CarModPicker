import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@webbpulse/api-client';
import { buildApiError } from '../test/apiResponse';
import { mockUser } from '../test/mocks/api';

const { mockApiClient, mockIdentityClient, mockNavigate } = vi.hoisted(() => {
  const listeners = new Set<(state: unknown) => void>();
  let state = {
    status: 'unknown' as string,
    user: null as unknown,
    hasAccessToken: false,
    error: null,
    sessionEnded: null as unknown,
    pendingMfa: null,
  };
  const setState = (patch: Record<string, unknown>) => {
    state = { ...state, ...patch };
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
    mockNavigate: vi.fn(),
    mockIdentityClient: {
      listeners,
      getState: () => state,
      setState,
      reset: () => {
        listeners.clear();
        state = {
          status: 'unknown',
          user: null,
          hasAccessToken: false,
          error: null,
          sessionEnded: null,
          pendingMfa: null,
        };
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
          throw error;
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

vi.mock('react-router-dom', async () => {
  const actual =
    await vi.importActual<typeof import('react-router-dom')>(
      'react-router-dom'
    );
  return { ...actual, useNavigate: () => mockNavigate };
});

import { AuthProvider } from './AuthContext';
import { useAuth } from '../hooks/useAuth';

function Consumer() {
  const { isAuthenticated, user, isLoading, login, logout, checkAuthStatus } =
    useAuth();
  return (
    <div>
      <span data-testid="state">
        {isAuthenticated ? (user?.username ?? 'authed-noname') : 'anon'}
      </span>
      <span data-testid="loading">{isLoading ? 'loading' : 'idle'}</span>
      <button type="button" onClick={() => login(mockUser)}>
        login-direct
      </button>
      <button type="button" onClick={() => void checkAuthStatus()}>
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

  it('shows the profile a direct login() seeded, with no extra request', async () => {
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

  it('re-reads the profile on checkAuthStatus()', async () => {
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

  it('ends the session when checkAuthStatus() is refused with a 401', async () => {
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

  it('keeps the session and logs a non-401 checkAuthStatus() failure', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
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

    await waitFor(() => expect(errorSpy).toHaveBeenCalled());
    expect(screen.getByTestId('state').textContent).toBe(mockUser.username);
    errorSpy.mockRestore();
  });

  it('signs out and navigates home on logout', async () => {
    renderWithProvider();

    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe(mockUser.username)
    );

    fireEvent.click(screen.getByText('logout'));

    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe('anon')
    );

    expect(mockIdentityClient.logout).toHaveBeenCalledTimes(1);
    expect(mockNavigate).toHaveBeenCalledWith('/');
  });

  it('still clears the session and navigates home when logout rejects', async () => {
    mockIdentityClient.logout.mockRejectedValueOnce(new Error('network down'));

    renderWithProvider();

    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe(mockUser.username)
    );

    fireEvent.click(screen.getByText('logout'));

    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/'));
  });
});
