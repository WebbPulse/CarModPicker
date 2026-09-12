import type { ReactNode } from 'react';
import React, { useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AuthProvider as PackageAuthProvider,
  useAuth as usePackageAuth,
  type AnyAuthClient,
} from '@webbpulse/auth/react';
import { getIdentityClient } from '../api/identityClient';
import type { UserRead } from '../types/Api';
import {
  AuthExtrasContext,
  type AuthExtrasContextType,
} from './AuthContextDefinition';

/**
 * Supplies the session calls `@webbpulse/auth` does not own. Mounted inside the
 * package provider so `useAuth` resolves, and holding no user of its own: the
 * package store is the single source of truth.
 */
const AuthExtrasProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  const navigate = useNavigate();
  const { setUser, reloadUser } = usePackageAuth<UserRead>();

  const login = useCallback(
    (userData: UserRead) => {
      setUser(userData);
    },
    [setUser]
  );

  const checkAuthStatus = useCallback(async () => {
    try {
      await reloadUser();
    } catch (error) {
      console.error('Auth check failed:', error);
    }
  }, [reloadUser]);

  const logout = useCallback(async () => {
    const client = getIdentityClient();
    try {
      await client?.logout();
    } catch {
      void 0;
    } finally {
      void navigate('/');
    }
  }, [navigate]);

  const value = useMemo<AuthExtrasContextType>(
    () => ({ login, logout, checkAuthStatus }),
    [login, logout, checkAuthStatus]
  );

  return (
    <AuthExtrasContext.Provider value={value}>
      {children}
    </AuthExtrasContext.Provider>
  );
};

/**
 * Mounts the `@webbpulse/auth` provider, which spends the refresh cookie on
 * mount, and layers the CarModPicker-only calls on top of it. Renders children
 * bare when the identity client could not be built, so a deployment with no
 * identity origin still paints.
 */
export const AuthProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  const client = getIdentityClient();

  if (client === null) {
    return <>{children}</>;
  }

  return (
    <PackageAuthProvider client={client as unknown as AnyAuthClient}>
      <AuthExtrasProvider>{children}</AuthExtrasProvider>
    </PackageAuthProvider>
  );
};
