import '@testing-library/jest-dom';
import { vi, beforeAll, afterAll } from 'vitest';

// Mock the API client to prevent network requests during tests
const mockApiClient = {
  get: vi.fn().mockResolvedValue({ data: null }),
  post: vi.fn().mockResolvedValue({ data: null }),
  put: vi.fn().mockResolvedValue({ data: null }),
  delete: vi.fn().mockResolvedValue({ data: null }),
  patch: vi.fn().mockResolvedValue({ data: null }),
};

// Dual mock per Phase 8 D-18/D-19 — both resolve to the same mockApiClient
// (services/Api.ts is a re-export shim for ../api/client). Legacy tests that
// import from `../services/Api` and new Phase 8 tests that import from
// `../api/<domain>` (which internally imports `../api/client`) both get the
// same mocked Axios surface.
//
// Phase 8 plan 08-10 fix: preserve the shim's re-exports (authApi,
// buildListsApi, etc.) via importOriginal so page tests that import
// `{ authApi } from '../../services/Api'` get the real domain API objects
// whose internal `apiClient.post(...)` calls land on our mocked client.
// Previously this factory returned ONLY `default`, stripping every named
// export and causing pages like Login.tsx to crash with "No <export> export
// defined on the ../../services/Api mock".
vi.mock('../services/Api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/Api')>();
  return {
    ...actual,
    default: mockApiClient,
  };
});

vi.mock('../api/client', () => ({
  default: mockApiClient,
  apiClient: mockApiClient,
  setStoredToken: vi.fn(),
  getStoredToken: vi.fn(() => null),
  removeStoredToken: vi.fn(),
}));

// Mock console methods to reduce noise in tests
const originalError = console.error;
const originalWarn = console.warn;

beforeAll(() => {
  console.error = (...args: unknown[]) => {
    if (
      typeof args[0] === 'string' &&
      args[0].includes('Warning: ReactDOM.render is no longer supported')
    ) {
      return;
    }
    originalError.call(console, ...args);
  };

  console.warn = (...args: unknown[]) => {
    if (
      typeof args[0] === 'string' &&
      (args[0].includes('Warning: componentWillReceiveProps') ||
        args[0].includes('Warning: componentWillUpdate'))
    ) {
      return;
    }
    originalWarn.call(console, ...args);
  };
});

afterAll(() => {
  console.error = originalError;
  console.warn = originalWarn;
});
