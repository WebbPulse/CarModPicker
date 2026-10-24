import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import {
  render,
  screen,
  fireEvent,
  waitFor,
} from '../../test/utils/test-utils';

const listSessions = vi.fn();
const revokeSession = vi.fn();
const revokeOtherSessions = vi.fn();
let clientIsNull = false;

vi.mock('../../api/identityClient', () => ({
  getIdentityClient: () =>
    clientIsNull ? null : { listSessions, revokeSession, revokeOtherSessions },
}));

import IdentitySessions from './IdentitySessions';

const CURRENT = {
  id: 'fam-current',
  device: 'desktop',
  ip: '203.0.113.1',
  lastIp: '203.0.113.9',
  client: '',
  platform: 'macOS',
  clientId: '',
  startedAt: '2026-10-20T10:00:00Z',
  lastActiveAt: '2026-10-23T10:00:00Z',
  expiresAt: null,
  amr: ['pwd'],
  current: true,
};

const PHONE = {
  ...CURRENT,
  id: 'fam-phone',
  device: 'mobile',
  ip: '198.51.100.7',
  lastIp: '',
  platform: '',
  current: false,
};

const OTHER = {
  ...CURRENT,
  id: 'fam-other',
  device: 'other',
  ip: '',
  lastIp: '',
  platform: '',
  current: false,
};

const CHROME = {
  ...CURRENT,
  id: 'fam-chrome',
  browser: 'Chrome',
  platform: 'Windows',
  current: false,
};

const AGENT = {
  ...CURRENT,
  id: 'fam-agent',
  device: 'other',
  ip: '192.0.2.4',
  lastIp: '192.0.2.5',
  client: 'claude-code',
  platform: 'Linux',
  clientId: 'mcp-client',
  current: false,
};

beforeEach(() => {
  vi.clearAllMocks();
  clientIsNull = false;
  listSessions.mockResolvedValue({
    ok: true,
    sessions: [CURRENT, PHONE, OTHER],
  });
  revokeSession.mockResolvedValue({ ok: true });
  revokeOtherSessions.mockResolvedValue({ ok: true, revoked: 2 });
  vi.spyOn(window, 'confirm').mockReturnValue(true);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('IdentitySessions', () => {
  it('lists every session and marks the current one', async () => {
    render(<IdentitySessions />);

    expect(
      await screen.findByText('Desktop browser on macOS')
    ).toBeInTheDocument();
    expect(screen.getByText('Mobile device')).toBeInTheDocument();
    expect(screen.getByText('Unknown device')).toBeInTheDocument();
    expect(screen.getByText('This device')).toBeInTheDocument();
    expect(screen.getByText(/198\.51\.100\.7/)).toBeInTheDocument();
    expect(screen.getByText(/203\.0\.113\.9/)).toBeInTheDocument();
    expect(screen.queryByText(/203\.0\.113\.1\b/)).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /end session on desktop/i })
    ).not.toBeInTheDocument();
    expect(
      screen.getAllByRole('button', { name: /^end session on/i })
    ).toHaveLength(2);
  });

  it('names a non-browser client and shows its last address', async () => {
    listSessions.mockResolvedValue({ ok: true, sessions: [CURRENT, AGENT] });
    render(<IdentitySessions />);

    expect(await screen.findByText('claude-code on Linux')).toBeInTheDocument();
    expect(screen.getByText(/192\.0\.2\.5/)).toBeInTheDocument();
    expect(
      screen.getByRole('button', {
        name: /^end session on claude-code on linux/i,
      })
    ).toBeInTheDocument();
  });

  it('ends one other session and reloads the list', async () => {
    render(<IdentitySessions />);

    fireEvent.click(
      await screen.findByRole('button', { name: /end session on mobile/i })
    );

    expect(
      await screen.findByText('Session ended. That device is signed out.')
    ).toBeInTheDocument();
    expect(revokeSession).toHaveBeenCalledTimes(1);
    expect(revokeSession).toHaveBeenCalledWith('fam-phone');
    expect(listSessions).toHaveBeenCalledTimes(2);
  });

  it('shows the server sentence when a revoke is refused', async () => {
    revokeSession.mockResolvedValue({
      ok: false,
      reason: 'current-session',
      code: 'CURRENT_SESSION',
      message: 'This is the session you are using. Sign out to end it.',
    });
    render(<IdentitySessions />);

    fireEvent.click(
      await screen.findByRole('button', { name: /end session on mobile/i })
    );

    expect(
      await screen.findByText(
        'This is the session you are using. Sign out to end it.'
      )
    ).toBeInTheDocument();
  });

  it('names the browser when the session has no client', async () => {
    listSessions.mockResolvedValue({
      ok: true,
      sessions: [{ ...CURRENT, browser: 'Firefox' }, CHROME],
    });
    render(<IdentitySessions />);

    expect(await screen.findByText('Firefox on macOS')).toBeInTheDocument();
    expect(screen.getByText('Chrome on Windows')).toBeInTheDocument();
    expect(
      screen.queryByText('Desktop browser on macOS')
    ).not.toBeInTheDocument();
  });

  it('prefers the client name over the browser', async () => {
    listSessions.mockResolvedValue({
      ok: true,
      sessions: [CURRENT, { ...AGENT, browser: 'Chrome' }],
    });
    render(<IdentitySessions />);

    expect(await screen.findByText('claude-code on Linux')).toBeInTheDocument();
  });

  it('signs out every other session in one call and reports the count', async () => {
    render(<IdentitySessions />);

    fireEvent.click(
      await screen.findByRole('button', { name: 'Sign out other sessions' })
    );

    expect(
      await screen.findByText('Signed out 2 other sessions.')
    ).toBeInTheDocument();
    expect(revokeOtherSessions).toHaveBeenCalledTimes(1);
    expect(revokeSession).not.toHaveBeenCalled();
    expect(listSessions).toHaveBeenCalledTimes(2);
  });

  it('reports a single other session in the singular', async () => {
    revokeOtherSessions.mockResolvedValue({ ok: true, revoked: 1 });
    render(<IdentitySessions />);

    fireEvent.click(
      await screen.findByRole('button', { name: 'Sign out other sessions' })
    );

    expect(
      await screen.findByText('Signed out 1 other session.')
    ).toBeInTheDocument();
  });

  it('says so when signing out the others fails', async () => {
    revokeOtherSessions.mockRejectedValue(new Error('network'));
    render(<IdentitySessions />);

    fireEvent.click(
      await screen.findByRole('button', { name: 'Sign out other sessions' })
    );

    expect(
      await screen.findByText(/could not reach the server/i)
    ).toBeInTheDocument();
  });

  it('does nothing when signing out the others is not confirmed', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    render(<IdentitySessions />);

    fireEvent.click(
      await screen.findByRole('button', { name: 'Sign out other sessions' })
    );

    await waitFor(() => {
      expect(confirm).toHaveBeenCalled();
    });
    expect(revokeOtherSessions).not.toHaveBeenCalled();
  });

  it('disables signing out the others when only the current session is live', async () => {
    listSessions.mockResolvedValue({ ok: true, sessions: [CURRENT] });
    render(<IdentitySessions />);

    expect(await screen.findByText('This device')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Sign out other sessions' })
    ).toBeDisabled();
  });

  it('says so when the list cannot be loaded', async () => {
    listSessions.mockRejectedValue(new Error('network'));
    render(<IdentitySessions />);

    expect(
      await screen.findByText(/could not reach the server/i)
    ).toBeInTheDocument();
  });

  it('renders the unavailable notice without an identity client', () => {
    clientIsNull = true;
    render(<IdentitySessions />);

    expect(
      screen.getByText('Managing sessions is not available in this deployment.')
    ).toBeInTheDocument();
  });
});
