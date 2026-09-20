import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  CURRENT_USER_PATH,
  getIdentityClient,
  resetIdentityClientForTests,
} from './identityClient';

/** Loads the module with the environment stubbed to `apiUrl`. */
const loadWithApiUrl = async (apiUrl: string) => {
  vi.resetModules();
  vi.stubEnv('VITE_API_URL', apiUrl);
  return import('./identityClient');
};

afterEach(() => {
  resetIdentityClientForTests();
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe('getIdentityClient', () => {
  it('builds a client and caches it', () => {
    const first = getIdentityClient();
    expect(first).not.toBeNull();
    expect(getIdentityClient()).toBe(first);
  });

  it('builds a fresh client after the test reset', () => {
    const first = getIdentityClient();
    resetIdentityClientForTests();
    expect(getIdentityClient()).not.toBe(first);
  });
});

describe('the identity origin', () => {
  it('is the deployed API base stripped back to its origin', async () => {
    const fresh = await loadWithApiUrl('https://api.carmodpicker.com/api');
    expect(fresh.identityOrigin()).toBe('https://api.carmodpicker.com');
    expect(fresh.identityUrl('/api/auth/passkeys/availability')).toBe(
      'https://api.carmodpicker.com/api/auth/passkeys/availability'
    );
  });

  it('keeps the local backend port', async () => {
    const fresh = await loadWithApiUrl('http://localhost:8000/api');
    expect(fresh.identityOrigin()).toBe('http://localhost:8000');
  });

  it('is empty for the root relative default, so a route resolves on the page origin', async () => {
    const fresh = await loadWithApiUrl('');
    expect(fresh.identityOrigin()).toBe('');
    expect(fresh.identityUrl('/api/auth/login')).toBe('/api/auth/login');
  });
});

describe('CURRENT_USER_PATH', () => {
  it('carries the /api prefix the gateway routes on', () => {
    expect(CURRENT_USER_PATH).toBe('/api/users/me');
  });

  it('is what the built client reads the signed in user from, on the configured origin', async () => {
    vi.resetModules();
    vi.stubEnv('VITE_API_URL', 'https://api.carmodpicker.com');
    const built = vi.fn();
    vi.doMock('@webbpulse/auth/browser', async () => {
      const actual = await vi.importActual<
        typeof import('@webbpulse/auth/browser')
      >('@webbpulse/auth/browser');
      return {
        ...actual,
        createIdentityClientSingleton: (
          options: Parameters<typeof actual.createIdentityClientSingleton>[0]
        ) =>
          actual.createIdentityClientSingleton({
            ...options,
            createClient: (clientOptions) => {
              built(clientOptions);
              return { dispose: () => undefined } as never;
            },
          }),
      };
    });

    try {
      const fresh = await import('./identityClient');
      fresh.getIdentityClient();

      const options = built.mock.calls.at(0)?.at(0) as {
        baseUrl: string;
        loadUser: (api: { get: ReturnType<typeof vi.fn> }) => Promise<unknown>;
      };
      expect(options.baseUrl).toBe('https://api.carmodpicker.com');

      const get = vi.fn().mockResolvedValue({ data: { id: 1 } });
      await expect(options.loadUser({ get })).resolves.toEqual({ id: 1 });
      expect(get).toHaveBeenCalledWith('/api/users/me');
      expect(options.baseUrl + String(get.mock.calls.at(0)?.at(0))).toBe(
        'https://api.carmodpicker.com/api/users/me'
      );
    } finally {
      vi.doUnmock('@webbpulse/auth/browser');
    }
  });
});
