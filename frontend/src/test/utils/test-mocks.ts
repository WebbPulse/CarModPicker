import { vi } from 'vitest';
import type { AuthContextType } from '../../contexts/AuthContextDefinition';

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
