import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '../../test/utils/test-utils';

const { listPasskeys, passkeyEnrolmentAvailability } = vi.hoisted(() => ({
  listPasskeys: vi.fn(),
  passkeyEnrolmentAvailability: vi.fn(),
}));

vi.mock('../../api/identityClient', () => ({
  PASSKEY_AVAILABILITY_PATH: '/api/auth/passkeys/availability',
  identityUrl: (path: string) => `https://api.test${path}`,
  passkeyEnrolmentAvailability,
  getIdentityClient: () => ({ listPasskeys }),
}));

import IdentityPasskeySettings from './IdentityPasskeySettings';

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal('PublicKeyCredential', class {});
  listPasskeys.mockResolvedValue({ ok: true, passkeys: [] });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('IdentityPasskeySettings when the deployment has passkeys off', () => {
  it('says so and never asks for the list', async () => {
    passkeyEnrolmentAvailability.mockResolvedValue('unavailable');
    render(<IdentityPasskeySettings />);

    expect(
      await screen.findByText('Passkeys are not available in this deployment.')
    ).toBeInTheDocument();
    expect(listPasskeys).not.toHaveBeenCalled();
    expect(
      screen.queryByRole('button', { name: /add a passkey/i })
    ).not.toBeInTheDocument();
  });
});

describe('IdentityPasskeySettings when the deployment has passkeys on', () => {
  it('loads the list through the panel hook and offers enrolment', async () => {
    passkeyEnrolmentAvailability.mockResolvedValue('available');
    render(<IdentityPasskeySettings />);

    expect(
      await screen.findByRole('button', { name: /add a passkey/i })
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(listPasskeys).toHaveBeenCalled();
    });
    expect(
      screen.queryByText('Passkeys are not available in this deployment.')
    ).not.toBeInTheDocument();
  });

  it('still loads the list when availability could not be read', async () => {
    passkeyEnrolmentAvailability.mockResolvedValue('unknown');
    render(<IdentityPasskeySettings />);

    await waitFor(() => {
      expect(listPasskeys).toHaveBeenCalled();
    });
    expect(
      screen.queryByText('Passkeys are not available in this deployment.')
    ).not.toBeInTheDocument();
  });

  it('renders the passkeys the hook loaded', async () => {
    passkeyEnrolmentAvailability.mockResolvedValue('available');
    listPasskeys.mockResolvedValue({
      ok: true,
      passkeys: [
        {
          credentialId: 'cred-1',
          name: 'Laptop',
          createdAt: '2026-01-01T00:00:00Z',
          transports: ['internal'],
          aaguid: '',
        },
      ],
    });
    render(<IdentityPasskeySettings />);

    expect(await screen.findByText('Laptop')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Rename Laptop' })
    ).toBeInTheDocument();
    expect(
      screen.queryByText('You have not added a passkey yet.')
    ).not.toBeInTheDocument();
  });

  it('hides enrolment in a browser without WebAuthn', async () => {
    vi.stubGlobal('PublicKeyCredential', undefined);
    passkeyEnrolmentAvailability.mockResolvedValue('available');
    render(<IdentityPasskeySettings />);

    expect(
      await screen.findByText(/this browser cannot use passkeys/i)
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /add a passkey/i })
    ).not.toBeInTheDocument();
  });

  it('renders a refused list as the server sentence', async () => {
    passkeyEnrolmentAvailability.mockResolvedValue('available');
    listPasskeys.mockResolvedValue({
      ok: false,
      reason: 'unavailable',
      message: 'Passkeys are switched off for your account.',
    });
    render(<IdentityPasskeySettings />);

    expect(
      await screen.findByText('Passkeys are switched off for your account.')
    ).toBeInTheDocument();
  });
});
