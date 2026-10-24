import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import {
  render,
  screen,
  fireEvent,
  waitFor,
} from '../../test/utils/test-utils';

const listSessions = vi.fn();
const revokeSession = vi.fn();
let clientIsNull = false;

vi.mock('../../api/identityClient', () => ({
  getIdentityClient: () =>
    clientIsNull ? null : { listSessions, revokeSession },
}));

import IdentitySessions from './IdentitySessions';

const CURRENT = {
  id: 'fam-current',
  device: 'desktop',
  ip: '203.0.113.1',
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
  current: false,
};

const OTHER = {
  ...CURRENT,
  id: 'fam-other',
  device: 'other',
  ip: '',
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
  vi.spyOn(window, 'confirm').mockReturnValue(true);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('IdentitySessions', () => {
  it('lists every session and marks the current one', async () => {
    render(<IdentitySessions />);

    expect(await screen.findByText('Desktop browser')).toBeInTheDocument();
    expect(screen.getByText('Mobile device')).toBeInTheDocument();
    expect(screen.getByText('Unknown device')).toBeInTheDocument();
    expect(screen.getByText('This device')).toBeInTheDocument();
    expect(screen.getByText(/198\.51\.100\.7/)).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /end session on desktop/i })
    ).not.toBeInTheDocument();
    expect(
      screen.getAllByRole('button', { name: /^end session on/i })
    ).toHaveLength(2);
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

  it('ends every other session but never the current one', async () => {
    render(<IdentitySessions />);

    fireEvent.click(
      await screen.findByRole('button', { name: 'End all other sessions' })
    );

    expect(
      await screen.findByText(
        'All other sessions ended. Those devices are signed out.'
      )
    ).toBeInTheDocument();
    expect(revokeSession).toHaveBeenCalledTimes(2);
    expect(revokeSession).toHaveBeenCalledWith('fam-phone');
    expect(revokeSession).toHaveBeenCalledWith('fam-other');
    expect(revokeSession).not.toHaveBeenCalledWith('fam-current');
  });

  it('does nothing when ending the others is not confirmed', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    render(<IdentitySessions />);

    fireEvent.click(
      await screen.findByRole('button', { name: 'End all other sessions' })
    );

    await waitFor(() => {
      expect(confirm).toHaveBeenCalled();
    });
    expect(revokeSession).not.toHaveBeenCalled();
  });

  it('hides the end all action when only the current session is live', async () => {
    listSessions.mockResolvedValue({ ok: true, sessions: [CURRENT] });
    render(<IdentitySessions />);

    expect(await screen.findByText('This device')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'End all other sessions' })
    ).not.toBeInTheDocument();
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
