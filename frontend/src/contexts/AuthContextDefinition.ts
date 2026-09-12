/**
 * Context object and type for the CarModPicker-only half of the session, kept
 * apart from the provider so the provider file exports only components and stays
 * refresh safe. Status, the user and the session calls live in
 * `@webbpulse/auth`; this context carries only what that package does not own.
 */

import { createContext } from 'react';
import type { UserRead } from '../types/Api';

/** The session calls CarModPicker adds on top of the package's `useAuth`. */
export interface AuthExtrasContextType {
  /** Seeds the user a login response already returned, with no extra request. */
  login: (userData: UserRead) => void;
  /**
   * Ends the session and returns to the home page. Resolves even when the
   * server call fails, since the package clears its own state either way and a
   * signed-out user has nothing to act on.
   */
  logout: () => Promise<void>;
  /**
   * Re-reads the signed in profile without rotating the refresh cookie. A 401
   * ends the session, exactly as a failed refresh does.
   */
  checkAuthStatus: () => Promise<void>;
}

/**
 * The full value `useAuth` returns: the package store's status and user plus the
 * calls above.
 */
export interface AuthContextType extends AuthExtrasContextType {
  isAuthenticated: boolean;
  user: UserRead | null;
  isLoading: boolean;
}

/** Context carrying the CarModPicker-only session calls to the tree. */
export const AuthExtrasContext = createContext<
  AuthExtrasContextType | undefined
>(undefined);
