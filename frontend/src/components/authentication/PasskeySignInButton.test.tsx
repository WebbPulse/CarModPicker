import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { act } from 'react';
import {
  fireEvent,
  render,
  screen,
  waitFor,
} from '../../test/utils/test-utils';

const { identityClient, signInWithPasskey, passkeyLoginAvailability } =
  vi.hoisted(() => {
    const signInWithPasskey = vi.fn();
    return {
      signInWithPasskey,
      passkeyLoginAvailability: vi.fn(),
      identityClient: { signInWithPasskey },
    };
  });

vi.mock('../../api/identityClient', () => ({
  PASSKEY_AVAILABILITY_PATH: '/api/auth/passkeys/availability',
  identityUrl: (path: string) => `https://api.test${path}`,
  passkeyLoginAvailability,
  getIdentityClient: () => identityClient,
}));

import PasskeySignInButton from './PasskeySignInButton';

const SIGNED_IN = { ok: true, kind: 'signed-in' };

/** Renders the button with the autofill ceremony off, then waits for it. */
const renderOffered = async (
  props: Partial<React.ComponentProps<typeof PasskeySignInButton>> = {}
) => {
  const onResult = vi.fn();
  render(
    <PasskeySignInButton onResult={onResult} conditional={false} {...props} />
  );
  const button = await screen.findByRole('button', {
    name: /sign in with a passkey/i,
  });
  return { button, onResult };
};

/** Presses the button and lets the ceremony promise settle. */
const press = async (button: HTMLElement) => {
  await act(async () => {
    fireEvent.click(button);
    await Promise.resolve();
  });
};

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
  it('appears once the deployment says it offers passwordless sign in', async () => {
    const { button } = await renderOffered();
    expect(button).toBeInTheDocument();
    expect(passkeyLoginAvailability).toHaveBeenCalledWith(
      'https://api.test/api/auth/passkeys/availability'
    );
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

  it('arms conditional mediation once the deployment and browser both say yes', async () => {
    render(<PasskeySignInButton onResult={vi.fn()} />);

    await waitFor(() => {
      expect(signInWithPasskey).toHaveBeenCalledWith(
        expect.objectContaining({ mediation: 'conditional' })
      );
    });
  });

  it('sends the typed username as the email so a known user skips the chooser', async () => {
    signInWithPasskey.mockResolvedValue(SIGNED_IN);
    const { button } = await renderOffered({ username: '  me@example.com  ' });

    await press(button);

    expect(signInWithPasskey).toHaveBeenCalledWith({
      email: 'me@example.com',
      mediation: 'optional',
    });
  });

  it('runs the discoverable flow when the username field is empty', async () => {
    signInWithPasskey.mockResolvedValue(SIGNED_IN);
    const { button } = await renderOffered({ username: '' });

    await press(button);

    expect(signInWithPasskey).toHaveBeenCalledWith({ mediation: 'optional' });
  });

  it('reports a completed ceremony as authenticated', async () => {
    signInWithPasskey.mockResolvedValue(SIGNED_IN);
    const { button, onResult } = await renderOffered();

    await press(button);

    await waitFor(() => {
      expect(onResult).toHaveBeenCalledWith({ status: 'authenticated' });
    });
  });

  it('carries an MFA ticket through to the page', async () => {
    signInWithPasskey.mockResolvedValue({
      ok: true,
      kind: 'mfa-required',
      ticket: 'tick-1',
      factors: ['totp'],
    });
    const { button, onResult } = await renderOffered();

    await press(button);

    await waitFor(() => {
      expect(onResult).toHaveBeenCalledWith({
        status: 'mfa-required',
        ticket: 'tick-1',
        factors: ['totp'],
      });
    });
  });

  it('stays silent on a cancellation', async () => {
    signInWithPasskey.mockResolvedValue({
      ok: false,
      reason: 'cancelled',
      message: 'Cancelled.',
    });
    const { button, onResult } = await renderOffered();

    await press(button);

    await waitFor(() => {
      expect(button).not.toBeDisabled();
    });
    expect(onResult).not.toHaveBeenCalled();
  });

  it('reports a refusal with the server sentence', async () => {
    signInWithPasskey.mockResolvedValue({
      ok: false,
      reason: 'rejected',
      message: 'That passkey is not registered.',
    });
    const { button, onResult } = await renderOffered();

    await press(button);

    await waitFor(() => {
      expect(onResult).toHaveBeenCalledWith({
        status: 'failed',
        error: 'That passkey is not registered.',
      });
    });
  });

  it('reports a ceremony that threw as a failure rather than leaking it', async () => {
    signInWithPasskey.mockRejectedValue(new Error('network down'));
    const { button, onResult } = await renderOffered();

    await press(button);

    await waitFor(() => {
      expect(onResult).toHaveBeenCalledWith({
        status: 'failed',
        error: 'network down',
      });
    });
    expect(button).not.toBeDisabled();
  });

  it('shows the waiting label and disables itself while the ceremony is outstanding', async () => {
    const { button } = await renderOffered();

    fireEvent.click(button);

    expect(
      await screen.findByRole('button', { name: /waiting for your passkey/i })
    ).toBeDisabled();
  });

  it('is disabled while the page says so', async () => {
    const { button } = await renderOffered({ disabled: true });
    expect(button).toBeDisabled();
  });
});
