import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '../../test/utils/test-utils';

const { signInWithPasskey, passkeyLoginAvailability } = vi.hoisted(() => ({
  signInWithPasskey: vi.fn(),
  passkeyLoginAvailability: vi.fn(),
}));

vi.mock('../../api/identityClient', () => ({
  PASSKEY_AVAILABILITY_PATH: '/api/auth/passkeys/availability',
  identityUrl: (path: string) => `https://api.test${path}`,
  passkeyLoginAvailability,
}));

vi.mock('../../api/identityPasskeys', () => ({
  signInWithPasskey: (options?: unknown): Promise<unknown> =>
    signInWithPasskey(options) as Promise<unknown>,
}));

import PasskeySignInButton from './PasskeySignInButton';

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal(
    'PublicKeyCredential',
    class {
      static isConditionalMediationAvailable() {
        return Promise.resolve(true);
      }
    }
  );
  passkeyLoginAvailability.mockResolvedValue('available');
  signInWithPasskey.mockReturnValue(new Promise(() => {}));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('PasskeySignInButton', () => {
  it('appears once the hook says the deployment offers passwordless sign in', async () => {
    render(<PasskeySignInButton onResult={vi.fn()} conditional={false} />);

    expect(
      await screen.findByRole('button', { name: /sign in with a passkey/i })
    ).toBeInTheDocument();
  });

  it('stays hidden when the deployment has passwordless sign in off', async () => {
    passkeyLoginAvailability.mockResolvedValue('unavailable');
    render(<PasskeySignInButton onResult={vi.fn()} conditional={false} />);

    await waitFor(() => {
      expect(passkeyLoginAvailability).toHaveBeenCalled();
    });
    expect(
      screen.queryByRole('button', { name: /sign in with a passkey/i })
    ).toBeNull();
  });

  it('stays hidden when the availability route could not be read', async () => {
    passkeyLoginAvailability.mockResolvedValue('unknown');
    render(<PasskeySignInButton onResult={vi.fn()} conditional={false} />);

    await waitFor(() => {
      expect(passkeyLoginAvailability).toHaveBeenCalled();
    });
    expect(
      screen.queryByRole('button', { name: /sign in with a passkey/i })
    ).toBeNull();
  });

  it('never probes the route in a browser without WebAuthn', async () => {
    vi.stubGlobal('PublicKeyCredential', undefined);
    render(<PasskeySignInButton onResult={vi.fn()} conditional={false} />);

    await waitFor(() => {
      expect(
        screen.queryByRole('button', { name: /sign in with a passkey/i })
      ).toBeNull();
    });
    expect(passkeyLoginAvailability).not.toHaveBeenCalled();
  });

  it('arms conditional mediation once the hook reports support', async () => {
    render(<PasskeySignInButton onResult={vi.fn()} />);

    await waitFor(() => {
      expect(signInWithPasskey).toHaveBeenCalledWith(
        expect.objectContaining({ mediation: 'conditional' })
      );
    });
  });
});
