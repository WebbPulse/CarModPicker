import { describe, expect, it } from 'vitest';
import { AUTH_MODE, AUTH_MODES, identityAvailability } from './authMode';

describe('AUTH_MODE', () => {
  it('is identity, and is the only mode', () => {
    expect(AUTH_MODE).toBe('identity');
    expect([...AUTH_MODES]).toEqual(['identity']);
  });

  it('reads nothing from the environment', () => {
    expect(AUTH_MODE).toBe('identity');
    expect(import.meta.env['VITE_AUTH_MODE']).toBeUndefined();
  });
});

describe('identityAvailability', () => {
  it('takes no argument', () => {
    expect(identityAvailability).toHaveLength(0);
  });

  it('offers password and TOTP', () => {
    const available = identityAvailability();
    expect(available.password).toBe(true);
    expect(available.totp).toBe(true);
  });

  it('offers passkeys and Google', () => {
    const available = identityAvailability();
    expect(available.passkeys).toBe(true);
    expect(available.googleOauth).toBe(true);
  });

  it('offers recovery codes', () => {
    expect(identityAvailability().recoveryCodes).toBe(true);
  });
});
