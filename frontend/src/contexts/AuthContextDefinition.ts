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
  /** Re-reads the signed in profile without rotating the refresh cookie. */
  checkAuthStatus: () => Promise<void>;
  /**
   * The profile the last `login` or `checkAuthStatus` read, or null when neither
   * has run since the session changed. Layered over the package store's user,
   * which has no public setter, so a profile edit shows without a token refresh.
   */
  freshUser: UserRead | null;
}

/**
 * The full value `useAuth` returns: the package store's status and user plus the
 * calls above. `freshUser` is provider plumbing and deliberately absent, so a
 * consumer and a test mock state only what a component reads.
 */
export interface AuthContextType extends Omit<
  AuthExtrasContextType,
  'freshUser'
> {
  isAuthenticated: boolean;
  user: UserRead | null;
  isLoading: boolean;
}

/** Context carrying the CarModPicker-only session calls to the tree. */
export const AuthExtrasContext = createContext<
  AuthExtrasContextType | undefined
>(undefined);
