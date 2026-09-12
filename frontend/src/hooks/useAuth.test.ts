/**
 * Tests for useAuth, the thin wrapper over `@webbpulse/auth/react`.
 */

import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import * as Sentry from '@sentry/react';
import { useAuth } from './useAuth';
import { mockUser } from '../test/mocks/api';
import { authHarness } from '../test/utils/authHarness';

vi.mock('@sentry/react', () => ({ setUser: vi.fn() }));

describe('useAuth', () => {
  it('returns unauthenticated state for an anonymous store', () => {
    const { Wrapper } = authHarness({ status: 'anonymous' });
    const { result } = renderHook(() => useAuth(), { wrapper: Wrapper });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });

  it('returns the authenticated user from the store', () => {
    const { Wrapper } = authHarness({
      status: 'authenticated',
      user: mockUser,
    });
    const { result } = renderHook(() => useAuth(), { wrapper: Wrapper });

    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user).toEqual(mockUser);
    expect(result.current.isLoading).toBe(false);
  });

  it('reports isLoading while a session call is in flight', () => {
    const { Wrapper } = authHarness({ status: 'loading' });
    const { result } = renderHook(() => useAuth(), { wrapper: Wrapper });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
  });

  it('reports isLoading before the first refresh settles', () => {
    const { Wrapper } = authHarness({ status: 'unknown' });
    const { result } = renderHook(() => useAuth(), { wrapper: Wrapper });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.isAuthenticated).toBe(false);
  });

  it('reads the user straight from the store, with no overlay', () => {
    const { stub, Wrapper } = authHarness({
      status: 'authenticated',
      user: mockUser,
    });
    const { result } = renderHook(() => useAuth(), { wrapper: Wrapper });

    expect(result.current.user?.username).toBe(mockUser.username);

    act(() => {
      stub.setState({ user: { ...mockUser, username: 'renamed' } });
    });

    expect(result.current.user?.username).toBe('renamed');
  });

  it('throws when used outside of an AuthProvider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => renderHook(() => useAuth())).toThrow(
      /useAuth must be used within an AuthProvider/
    );
    spy.mockRestore();
  });

  it('exposes login/logout/checkAuthStatus callables', () => {
    const { Wrapper } = authHarness({
      status: 'authenticated',
      user: mockUser,
    });
    const { result } = renderHook(() => useAuth(), { wrapper: Wrapper });

    expect(typeof result.current.login).toBe('function');
    expect(typeof result.current.logout).toBe('function');
    expect(typeof result.current.checkAuthStatus).toBe('function');
  });

  it('reports the signed in user to Sentry, and clears it on sign out', async () => {
    vi.mocked(Sentry.setUser).mockClear();
    const { stub, Wrapper } = authHarness({
      status: 'authenticated',
      user: mockUser,
    });
    renderHook(() => useAuth(), { wrapper: Wrapper });

    await waitFor(() =>
      expect(vi.mocked(Sentry.setUser)).toHaveBeenCalledWith({
        id: String(mockUser.id),
      })
    );

    stub.endSession();

    await waitFor(() =>
      expect(vi.mocked(Sentry.setUser)).toHaveBeenLastCalledWith(null)
    );
  });
});
