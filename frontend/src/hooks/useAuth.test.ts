import { createElement, type ReactNode } from 'react';
import { renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useAuth } from './useAuth';
import {
  AuthContext,
  type AuthContextType,
} from '../contexts/AuthContextDefinition';
import { mockUser } from '../test/mocks/api';
import { testScenarios } from '../test/utils/test-utils';

// Phase 8 D-09 — first use of renderHook in the repo.
//
// Gotcha #8 warning: `test/utils/test-utils.tsx` registers
// `vi.mock('../../hooks/useAuth')`. To exercise the REAL useAuth against a
// predictable context, we bypass AllTheProviders/TestProviders and wrap
// renderHook in a plain AuthContext.Provider seeded from testScenarios. That
// gives us deterministic context values without tripping the test-utils mock.
//
// File is .ts (not .tsx) per the plan's files_modified list — we compose the
// wrapper with React.createElement so no JSX is needed.

function makeContextValue(
  scenario: (typeof testScenarios)[keyof typeof testScenarios]
): AuthContextType {
  const { initialAuthState } = scenario;
  // Do NOT pull `user` directly from `initialAuthState` — the legacy
  // createMockUser() helper in test-utils.tsx returns a shape that lacks
  // subscription_tier/is_service_account/totp_enabled, so it is not assignable
  // to UserRead. We seed `user: null` here and the per-test body swaps in
  // mockUser (or a variant) from test/mocks/api.ts for authenticated cases.
  return {
    isAuthenticated: initialAuthState.isAuthenticated,
    user: null,
    isLoading: initialAuthState.isLoading ?? false,
    login: vi.fn(),
    logout: vi.fn(),
    checkAuthStatus: vi.fn().mockResolvedValue(undefined),
  };
}

const wrap = (value: AuthContextType) => {
  const Wrapper = ({ children }: { children: ReactNode }) =>
    createElement(AuthContext.Provider, { value }, children);
  return Wrapper;
};

describe('useAuth', () => {
  it('returns unauthenticated state with testScenarios.unauthenticated', () => {
    const value = makeContextValue(testScenarios.unauthenticated);
    const { result } = renderHook(() => useAuth(), {
      wrapper: wrap(value),
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });

  it('returns authenticated state with testScenarios.authenticated', () => {
    const base = makeContextValue(testScenarios.authenticated);
    // testScenarios.authenticated.user comes from createMockUser which omits
    // subscription fields — swap in the canonical UserRead mockUser so a
    // consumer assertion on tier fields does not need a cast.
    const value: AuthContextType = { ...base, user: mockUser };
    const { result } = renderHook(() => useAuth(), {
      wrapper: wrap(value),
    });

    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user).toEqual(mockUser);
    expect(result.current.isLoading).toBe(false);
  });

  it('returns isLoading=true with testScenarios.loading', () => {
    const value = makeContextValue(testScenarios.loading);
    const { result } = renderHook(() => useAuth(), {
      wrapper: wrap(value),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
  });

  it('throws when used outside of an AuthProvider', () => {
    // useAuth guards against missing provider context — branch worth covering.
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => renderHook(() => useAuth())).toThrow(
      /useAuth must be used within an AuthProvider/
    );
    spy.mockRestore();
  });

  it('exposes login/logout/checkAuthStatus callables from context', () => {
    const value = makeContextValue(testScenarios.authenticated);
    const { result } = renderHook(() => useAuth(), {
      wrapper: wrap(value),
    });

    expect(typeof result.current.login).toBe('function');
    expect(typeof result.current.logout).toBe('function');
    expect(typeof result.current.checkAuthStatus).toBe('function');
  });
});
