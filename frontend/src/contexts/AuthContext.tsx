import type { ReactNode } from 'react';
import React, { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AuthProvider as PackageAuthProvider,
  type AnyAuthClient,
} from '@webbpulse/auth/react';
import { apiClient, isApiErrorWithStatus } from '../api/client';
import { CURRENT_USER_PATH, getIdentityClient } from '../api/identityClient';
import type { UserRead } from '../types/Api';
import {
  AuthExtrasContext,
  type AuthExtrasContextType,
} from './AuthContextDefinition';

/**
 * Supplies the session calls `@webbpulse/auth` does not own. Mounted inside the
 * package provider so `useAuthClient` resolves, and holding no status of its
 * own: the package store stays the single source of truth for that.
 */
const AuthExtrasProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  const navigate = useNavigate();
  const [freshUser, setFreshUser] = useState<UserRead | null>(null);

  const login = useCallback((userData: UserRead) => {
    setFreshUser(userData);
  }, []);

  const checkAuthStatus = useCallback(async () => {
    try {
      const response = await apiClient.get<UserRead>(CURRENT_USER_PATH);
      setFreshUser(response.data ?? null);
    } catch (error) {
      const status = isApiErrorWithStatus(error) ? error.status : undefined;
      setFreshUser(null);
      if (status !== undefined && status !== 401) {
        console.error('Auth check failed:', error);
      }
    }
  }, []);

  const logout = useCallback(async () => {
    const client = getIdentityClient();
    try {
      await client?.logout();
    } catch {
      void 0;
    } finally {
      setFreshUser(null);
      void navigate('/');
    }
  }, [navigate]);

  const value = useMemo<AuthExtrasContextType>(
    () => ({ login, logout, checkAuthStatus, freshUser }),
    [login, logout, checkAuthStatus, freshUser]
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
