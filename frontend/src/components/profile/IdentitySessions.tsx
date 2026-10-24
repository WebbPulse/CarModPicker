/**
 * The active sessions panel for identity mode. Lists the user's live sign-ins
 * with the one in use marked, and ends any other one, singly or all at once.
 * The session in use is ended by signing out, so it has no end button.
 * The state machine is `useSessionsPanel` from `@webbpulse/auth/panels`; this
 * file is the markup and copy.
 */
import { FaDesktop, FaMobileAlt, FaQuestionCircle } from 'react-icons/fa';
import type { AccountSession } from '@webbpulse/auth';
import { useSessionsPanel } from '@webbpulse/auth/panels';
import {
  getIdentityClient,
  type IdentityClient,
} from '../../api/identityClient';
import { ConfirmationAlert, ErrorAlert } from '../ui/alert';
import { Button } from '../ui/button';
import Spinner from '../ui/spinner';

/** The readable name of a coarse device class. */
const DEVICE_LABELS: Record<string, string> = {
  desktop: 'Desktop browser',
  mobile: 'Mobile device',
  bot: 'Automated client',
};

/** A session's client or browser and operating system, or its device class. */
const describeSession = (session: AccountSession): string => {
  const base =
    session.client ||
    session.browser ||
    DEVICE_LABELS[session.device] ||
    'Unknown device';
  return session.platform ? `${base} on ${session.platform}` : base;
};

/** The notice after the other sessions were ended, by how many ended. */
const revokedOthersMessage = (count: number): string => {
  if (count === 0) return 'No other sessions were signed in.';
  if (count === 1) return 'Signed out 1 other session.';
  return `Signed out ${count} other sessions.`;
};

/** A date and time for display, falling back to the raw value. */
const formatDateTime = (value: string): string => {
  if (!value) return 'Unknown';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
};

/** The icon for a coarse device class. */
const DeviceIcon: React.FC<{ device: string }> = ({ device }) => {
  const className = 'shrink-0 text-primary';
  if (device === 'mobile') return <FaMobileAlt className={className} />;
  if (device === 'desktop') return <FaDesktop className={className} />;
  return <FaQuestionCircle className={className} />;
};

/** The panel body, mounted only once the identity client could be built. */
const SessionsBody: React.FC<{ client: IdentityClient }> = ({ client }) => {
  const panel = useSessionsPanel({
    client,
    messages: {
      removed: 'Session ended. That device is signed out.',
      revokedOthers: revokedOthersMessage,
    },
  });

  if (panel.loading) {
    return (
      <div className="flex justify-center py-8">
        <Spinner />
      </div>
    );
  }

  const sessions = panel.items ?? [];

  const signOutOthers = () => {
    if (
      !window.confirm(
        'Sign out every other session? Those devices will need to sign in again.'
      )
    ) {
      return;
    }
    void panel.revokeOthers();
  };

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-white">Active sessions</h3>
        <p className="text-sm text-muted-foreground">
          The devices signed in to your account. End any session you do not
          recognise, then change your password.
        </p>
      </div>

      {panel.error && <ErrorAlert message={panel.error} />}
      {panel.notice && <ConfirmationAlert message={panel.notice} />}

      {sessions.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No active sessions were found.
        </p>
      ) : (
        <ul className="space-y-2">
          {sessions.map((session) => {
            const label = describeSession(session);
            const lastActive = formatDateTime(session.lastActiveAt);
            const detail = [
              session.lastIp || session.ip,
              `Signed in ${formatDateTime(session.startedAt)}`,
              `Last active ${lastActive}`,
            ]
              .filter(Boolean)
              .join(' · ');
            return (
              <li
                key={session.id}
                className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/5 p-3"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <DeviceIcon device={session.device} />
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 font-medium text-white">
                      <span className="truncate">{label}</span>
                      {session.current && (
                        <span className="shrink-0 rounded-full bg-primary/20 px-2 py-0.5 text-xs text-primary">
                          This device
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {detail}
                    </div>
                  </div>
                </div>
                {!session.current && (
                  <Button
                    type="button"
                    size="sm"
                    variant="destructive"
                    aria-label={`End session on ${label} last active ${lastActive}`}
                    onClick={() => void panel.revoke(session.id)}
                    disabled={panel.busy}
                  >
                    End
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {sessions.length > 0 && (
        <Button
          type="button"
          variant="destructive"
          onClick={signOutOthers}
          disabled={panel.busy || panel.others.length === 0}
          loading={panel.busy && panel.others.length > 0}
          className="w-full"
        >
          Sign out other sessions
        </Button>
      )}
    </div>
  );
};

/** The active sessions panel, or the unavailable notice in bearer mode. */
function IdentitySessions() {
  const client = getIdentityClient();
  if (client === null) {
    return (
      <ErrorAlert message="Managing sessions is not available in this deployment." />
    );
  }
  return <SessionsBody client={client} />;
}

export default IdentitySessions;
