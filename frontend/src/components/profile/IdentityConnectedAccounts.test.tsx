import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import {
  render,
  screen,
  fireEvent,
  waitFor,
} from '../../test/utils/test-utils';

const listOAuthLinks = vi.fn();
const unlinkOAuthProvider = vi.fn();
const linkOAuthProvider = vi.fn();
let clientIsNull = false;
let providerList: { id: string; displayName: string }[] = [];

vi.mock('../../api/identityClient', () => ({
  getIdentityClient: () =>
    clientIsNull
      ? null
      : { listOAuthLinks, unlinkOAuthProvider, linkOAuthProvider },
  identityOrigin: () => 'https://api.test',
}));

vi.mock('@webbpulse/discovery/react', () => ({
  useOAuthProviders: () => providerList,
}));

import IdentityConnectedAccounts from './IdentityConnectedAccounts';

beforeEach(() => {
  vi.clearAllMocks();
  clientIsNull = false;
  providerList = [
    { id: 'google', displayName: 'Google' },
    { id: 'github', displayName: 'GitHub' },
  ];
  listOAuthLinks.mockResolvedValue({ ok: true, links: [] });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('IdentityConnectedAccounts', () => {
  it('renders the links the panel hook loaded', async () => {
    listOAuthLinks.mockResolvedValue({
      ok: true,
      links: [
        {
          provider: 'google',
          email: 'someone@example.test',
          linkedAt: '2026-01-01T00:00:00Z',
        },
      ],
    });
    render(<IdentityConnectedAccounts />);

    expect(await screen.findByText('Google')).toBeInTheDocument();
    expect(screen.getByText(/someone@example.test/)).toBeInTheDocument();
  });

  it('offers a connect button only for providers not already linked', async () => {
    listOAuthLinks.mockResolvedValue({
      ok: true,
      links: [{ provider: 'google', email: 'someone@example.test' }],
    });
    render(<IdentityConnectedAccounts />);

    expect(
      await screen.findByRole('button', { name: /connect github/i })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /^connect google$/i })
    ).not.toBeInTheDocument();
  });

  it('unlinks through the hook once the confirmation is accepted', async () => {
    vi.stubGlobal('confirm', () => true);
    listOAuthLinks.mockResolvedValue({
      ok: true,
      links: [{ provider: 'github', email: 'someone@example.test' }],
    });
    unlinkOAuthProvider.mockResolvedValue({ ok: true });
    render(<IdentityConnectedAccounts />);

    fireEvent.click(
      await screen.findByRole('button', { name: /disconnect github/i })
    );

    await waitFor(() => {
      expect(unlinkOAuthProvider).toHaveBeenCalledWith('github');
    });
    expect(await screen.findByText(/github disconnected/i)).toBeInTheDocument();
  });

  it('leaves the link alone when the confirmation is declined', async () => {
    vi.stubGlobal('confirm', () => false);
    listOAuthLinks.mockResolvedValue({
      ok: true,
      links: [{ provider: 'github', email: 'someone@example.test' }],
    });
    render(<IdentityConnectedAccounts />);

    fireEvent.click(
      await screen.findByRole('button', { name: /disconnect github/i })
    );

    expect(unlinkOAuthProvider).not.toHaveBeenCalled();
  });

  it('renders a refused unlink as the server sentence', async () => {
    vi.stubGlobal('confirm', () => true);
    listOAuthLinks.mockResolvedValue({
      ok: true,
      links: [{ provider: 'github', email: 'someone@example.test' }],
    });
    unlinkOAuthProvider.mockResolvedValue({
      ok: false,
      reason: 'last-credential',
      message: 'Set a password before disconnecting your last sign in method.',
    });
    render(<IdentityConnectedAccounts />);

    fireEvent.click(
      await screen.findByRole('button', { name: /disconnect github/i })
    );

    expect(
      await screen.findByText(/set a password before disconnecting/i)
    ).toBeInTheDocument();
  });

  it('says so when the deployment configured no providers', async () => {
    providerList = [];
    render(<IdentityConnectedAccounts />);

    expect(
      await screen.findByText(/no sign in providers are configured/i)
    ).toBeInTheDocument();
  });

  it('says connected accounts are unavailable in bearer mode', () => {
    clientIsNull = true;
    render(<IdentityConnectedAccounts />);

    expect(
      screen.getByText(
        'Connected accounts are not available in this deployment.'
      )
    ).toBeInTheDocument();
    expect(listOAuthLinks).not.toHaveBeenCalled();
  });
});
