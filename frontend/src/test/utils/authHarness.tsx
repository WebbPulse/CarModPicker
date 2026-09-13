/**
 * Renders a tree inside the real session providers, over a stub `AuthClient`.
 * Tests state a session rather than a context value, so they exercise the same
 * `@webbpulse/auth` store the application runs on.
 */

import type { ReactNode } from 'react';
import {
  AuthProvider as PackageAuthProvider,
  type AnyAuthClient,
} from '@webbpulse/auth/react';
import type { AuthState, AuthStatus } from '@webbpulse/auth';
import { vi } from 'vitest';
import {
  AuthExtrasContext,
  type AuthExtrasContextType,
} from '../../contexts/AuthContextDefinition';
import type { UserRead } from '../../types/Api';

/** A stub auth client whose state a test drives directly. */
export interface StubAuthClient {
  /** Passed to the package provider in place of a real client. */
  client: AnyAuthClient;
  /**
   * Replaces the state and notifies every subscriber, as the real store does,
   * latching `settled` on the first settled status the way `AuthClient` does.
   */
  setState: (patch: Partial<AuthState<UserRead>>) => void;
  /** Moves the store to `anonymous`, as a failed refresh or a logout does. */
  endSession: () => void;
}

/**
 * Builds a stub `AuthClient` carrying only what the React bindings read: the
 * store surface of `getState` and `subscribe`. `useAuth` binds each client
 * method lazily on first read, and no guard under this harness reads one.
 */
export function createStubAuthClient(
  initial: Partial<AuthState<UserRead>> = {}
): StubAuthClient {
  const latch = (next: AuthState<UserRead>): AuthState<UserRead> =>
    next.settled ||
    !(next.status === 'authenticated' || next.status === 'anonymous')
      ? next
      : { ...next, settled: true };

  let state: AuthState<UserRead> = latch({
    status: 'unknown',
    user: null,
    hasAccessToken: false,
    error: null,
    sessionEnded: null,
    pendingMfa: null,
    settled: false,
    ...initial,
  });
  const listeners = new Set<(next: AuthState<UserRead>) => void>();

  const setState = (patch: Partial<AuthState<UserRead>>): void => {
    state = latch({ ...state, ...patch });
    for (const listener of [...listeners]) listener(state);
  };

  const client = {
    getState: () => state,
    subscribe: (listener: (next: AuthState<UserRead>) => void) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  } as unknown as AnyAuthClient;

  return {
    client,
    setState,
    endSession: () =>
      setState({
        status: 'anonymous',
        user: null,
        hasAccessToken: false,
        pendingMfa: null,
      }),
  };
}

/** A session a test wants rendered, as the two fields a guard reads. */
export interface HarnessSession {
  status?: AuthStatus;
  user?: UserRead | null;
}

/** The stub extras a harness supplies when a test does not override them. */
export type HarnessExtras = Partial<AuthExtrasContextType>;

/**
 * Wraps children in the package provider and the CarModPicker extras, so
 * `useAuth` resolves exactly as it does in the application.
 */
export function renderAuthHarness(
  stub: StubAuthClient,
  extras: HarnessExtras = {}
) {
  const value: AuthExtrasContextType = {
    login: vi.fn(),
    logout: vi.fn().mockResolvedValue(undefined),
    checkAuthStatus: vi.fn().mockResolvedValue(undefined),
    ...extras,
  };

  return ({ children }: { children: ReactNode }) => (
    <PackageAuthProvider client={stub.client} initializeOnMount={false}>
      <AuthExtrasContext.Provider value={value}>
        {children}
      </AuthExtrasContext.Provider>
    </PackageAuthProvider>
  );
}

/**
 * The common case: a stub client already in the given session plus the wrapper
 * that mounts it. Returns both, so a test can flip the session mid render.
 */
export function authHarness(
  session: HarnessSession = {},
  extras: HarnessExtras = {}
) {
  const status: AuthStatus = session.status ?? 'anonymous';
  const stub = createStubAuthClient({
    status,
    user: session.user ?? null,
    hasAccessToken: status === 'authenticated',
  });
  return { stub, Wrapper: renderAuthHarness(stub, extras) };
}
