import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '../../test/utils/test-utils';

const { listPasskeys, passkeyEnrolmentAvailability } = vi.hoisted(() => ({
  listPasskeys: vi.fn(),
  passkeyEnrolmentAvailability: vi.fn(),
}));

vi.mock('../../api/identityPasskeys', () => ({
  listPasskeys,
  enrolPasskey: vi.fn(),
  renamePasskey: vi.fn(),
  deletePasskey: vi.fn(),
  passkeysSupported: () => true,
}));

vi.mock('../../api/identityClient', () => ({
  PASSKEY_AVAILABILITY_PATH: '/api/auth/passkeys/availability',
  identityUrl: (path: string) => `https://api.test${path}`,
  passkeyEnrolmentAvailability,
}));

import IdentityPasskeySettings from './IdentityPasskeySettings';

beforeEach(() => {
  vi.clearAllMocks();
  listPasskeys.mockResolvedValue({ status: 'ok', value: [] });
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
  it('loads the list and offers enrolment', async () => {
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
});
