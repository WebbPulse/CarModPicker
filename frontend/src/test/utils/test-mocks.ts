import { vi } from 'vitest';
import type { AuthContextType } from '../../contexts/AuthContextDefinition';
import type { UserRead } from '../../types/Api';
import { mockUser } from '../mocks/api';

// Mock the useAuth hook. Typed to match the real hook's return so callers
// passing partial auth state still type-check (Mock<...> generic narrows the
// `vi.fn()` `any` return). See Phase 6 D-05 — test-file `no-unsafe-*` strict.
// Each property is allowed to be `undefined` explicitly because the project
// uses `exactOptionalPropertyTypes: true` and TestProviders forwards optional
// fields from a `Partial`-shaped initialAuthState.
type MockAuthState = {
  [K in keyof AuthContextType]?: AuthContextType[K] | undefined;
};

export const mockUseAuth = vi.fn<() => MockAuthState>();

// Phase 8 D-05: admin + superuser variants for admin-area test scenarios.
// Composed from the canonical `mockUser` shape so the field set stays
// consistent (do NOT hand-roll these — Pitfall 2 exactOptionalPropertyTypes
// prohibits explicit `undefined` assignment on optional fields).
export const mockAdminUser: UserRead = { ...mockUser, is_admin: true };
export const mockSuperuserUser: UserRead = {
  ...mockUser,
  is_admin: true,
  is_superuser: true,
};
