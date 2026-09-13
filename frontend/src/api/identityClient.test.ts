import { describe, expect, it, vi, afterEach } from 'vitest';
import {
  identityOriginFrom,
  getIdentityClient,
  CURRENT_USER_PATH,
} from './identityClient';

afterEach(() => {
  vi.resetModules();
  vi.unstubAllEnvs();
});

describe('identityOriginFrom', () => {
  it('strips a deployed API base back to its origin', () => {
    expect(identityOriginFrom('https://api.carmodpicker.com/api')).toBe(
      'https://api.carmodpicker.com'
    );
  });

  it('strips the staging API base back to its origin', () => {
    expect(identityOriginFrom('https://api.staging.carmodpicker.com/api')).toBe(
      'https://api.staging.carmodpicker.com'
    );
  });

  it('keeps a non default port', () => {
    expect(identityOriginFrom('http://localhost:8000/api')).toBe(
      'http://localhost:8000'
    );
  });

  it('returns an empty base for a root relative API base', () => {
    expect(identityOriginFrom('/api')).toBe('');
  });

  it('returns an empty base for a bare slash', () => {
    expect(identityOriginFrom('/')).toBe('');
  });

  it('returns a malformed value unchanged', () => {
    expect(identityOriginFrom('not a url')).toBe('not a url');
  });

  it('never produces a base that would double the api prefix', () => {
    for (const base of [
      'https://api.carmodpicker.com/api',
      'http://localhost:8000/api',
      '/api',
    ]) {
      expect(identityOriginFrom(base) + '/api/auth/login').not.toContain(
        '/api/api/auth'
      );
    }
  });
});

describe('getIdentityClient', () => {
  it('builds a client and caches it', async () => {
    vi.resetModules();
    const { getIdentityClient: fresh } = await import('./identityClient');
    const first = fresh();
    expect(first).not.toBeNull();
    expect(fresh()).toBe(first);
  });

  it('hands out the same instance to the module-level import too', () => {
    expect(getIdentityClient()).toBe(getIdentityClient());
  });
});

describe('CURRENT_USER_PATH', () => {
  it('carries the /api prefix the gateway routes on', () => {
    expect(CURRENT_USER_PATH).toBe('/api/users/me');
  });

  it('resolves against a deployed origin to the real gateway route', () => {
    const origin = identityOriginFrom('https://api.carmodpicker.com/api');
    expect(origin + CURRENT_USER_PATH).toBe(
      'https://api.carmodpicker.com/api/users/me'
    );
  });

  it('resolves against a root relative base to a same origin path', () => {
    expect(identityOriginFrom('/api') + CURRENT_USER_PATH).toBe(
      '/api/users/me'
    );
  });

  it('never doubles the api prefix', () => {
    for (const base of [
      'https://api.carmodpicker.com/api',
      'https://api.staging.carmodpicker.com/api',
      'http://localhost:8000/api',
      '/api',
    ]) {
      expect(identityOriginFrom(base) + CURRENT_USER_PATH).not.toContain(
        '/api/api/'
      );
    }
  });
});

describe('loadUser', () => {
  it('fetches the signed in user from /api/users/me on the configured base', async () => {
    vi.resetModules();
    vi.stubEnv('VITE_API_URL', 'https://api.carmodpicker.com');

    const loadUserOption = vi.fn();
    vi.doMock('@webbpulse/auth', async () => {
      const actual =
        await vi.importActual<typeof import('@webbpulse/auth')>(
          '@webbpulse/auth'
        );
      return {
        ...actual,
        createAuthClient: (options: {
          loadUser?: unknown;
          baseUrl?: string;
        }) => {
          loadUserOption.mockImplementation(
            options.loadUser as (...args: unknown[]) => unknown
          );
          return { dispose: () => undefined, baseUrl: options.baseUrl };
        },
      };
    });

    try {
      const { getIdentityClient: fresh, resetIdentityClientForTests } =
        await import('./identityClient');
      const built = fresh() as unknown as { baseUrl: string };
      expect(built.baseUrl).toBe('https://api.carmodpicker.com');

      const get = vi.fn().mockResolvedValue({ data: { id: 1 } });
      await loadUserOption({ get });

      expect(get).toHaveBeenCalledWith('/api/users/me');
      const requestedPath = get.mock.calls.at(0)?.at(0) as string | undefined;
      expect(built.baseUrl + String(requestedPath)).toBe(
        'https://api.carmodpicker.com/api/users/me'
      );

      resetIdentityClientForTests();
    } finally {
      vi.doUnmock('@webbpulse/auth');
      vi.resetModules();
    }
  });
});
