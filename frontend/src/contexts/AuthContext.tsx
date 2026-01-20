// filepath: src/contexts/AuthContext.tsx
import type { ReactNode } from 'react';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient, { authApi, removeStoredToken } from '../services/Api';
import type { UserRead } from '../types/Api';
import { AuthContext } from './AuthContextDefinition';

export const AuthProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  const [user, setUser] = useState<UserRead | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const navigate = useNavigate();

  const checkAuthStatus = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await apiClient.get<UserRead>('/users/me');
      if (response.data) {
        setUser(response.data);
        setIsAuthenticated(true);
      } else {
        setUser(null);
        setIsAuthenticated(false);
      }
    } catch (error) {
      // Silently handle auth errors - user might not be logged in
      setUser(null);
      setIsAuthenticated(false);
      // Clear invalid token on 401
      if (
        (error as { response?: { status?: number } }).response?.status === 401
      ) {
        removeStoredToken();
      }
      // Don't log network errors in console to avoid noise
      // Only log unexpected errors
      if (
        (error as { response?: { status?: number } }).response?.status &&
        (error as { response?: { status?: number } }).response?.status !== 401
      ) {
        console.error('Auth check failed:', error);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void checkAuthStatus();
  }, [checkAuthStatus]);

  const login = (userData: UserRead) => {
    setUser(userData);
    setIsAuthenticated(true);
  };

  const logout = useCallback(async () => {
    setIsLoading(true);
    try {
      await authApi.logout();
    } catch {
      // Clear token even if logout API call fails
      removeStoredToken();
    } finally {
      setUser(null);
      setIsAuthenticated(false);
      setIsLoading(false);
      void navigate('/'); // Redirect to login after logout
    }
  }, [navigate]);

  const contextValue = useMemo(
    () => ({
      isAuthenticated,
      user,
      login,
      logout,
      checkAuthStatus,
      isLoading,
    }),
    [isAuthenticated, user, logout, checkAuthStatus, isLoading]
  );

  return (
    <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>
  );
};
