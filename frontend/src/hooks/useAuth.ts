/**
 * Accessor for the session that fails loudly outside its provider. A thin
 * wrapper over `useAuth` from `@webbpulse/auth/react`, adding the three pieces
 * that package does not own: the Sentry user effect, the `UserRead` typing of
 * the user object, and a logout that returns to the home page.
 */

import * as Sentry from '@sentry/react';
import { useContext, useEffect } from 'react';
import { useAuth as usePackageAuth } from '@webbpulse/auth/react';
import { AuthExtrasContext } from '../contexts/AuthContextDefinition';
import type { AuthContextType } from '../contexts/AuthContextDefinition';
import type { UserRead } from '../types/Api';

/** Returns the current session, throwing outside an AuthProvider. */
export const useAuth = (): AuthContextType => {
  const extras = useContext(AuthExtrasContext);
  if (extras === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  const {
    isAuthenticated,
    isLoading,
    user: storeUser,
  } = usePackageAuth<UserRead>();
  const { login, logout, checkAuthStatus, freshUser } = extras;

  const user = isAuthenticated ? (freshUser ?? storeUser) : null;

  useEffect(() => {
    Sentry.setUser(user ? { id: String(user.id) } : null);
  }, [user]);

  return { isAuthenticated, user, isLoading, login, logout, checkAuthStatus };
};
