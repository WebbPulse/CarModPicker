/**
 * The active sessions panel for identity mode. Lists the user's live sign-ins
 * with the one in use marked, and ends any other one, singly or all at once.
 * The session in use is ended by signing out, so it has no end button.
 */
import { useCallback, useEffect, useState } from 'react';
import { FaDesktop, FaMobileAlt, FaQuestionCircle } from 'react-icons/fa';
import type { AccountSession } from '@webbpulse/auth';
import {
  getIdentityClient,
  type IdentityClient,
} from '../../api/identityClient';
import { ConfirmationAlert, ErrorAlert } from '../ui/alert';
import { Button } from '../ui/button';
import Spinner from '../ui/spinner';

/** The sentence shown when a call could not reach the server. */
const FAILED =
  'Could not reach the server. Check your connection and try again.';

/** The readable name of a coarse device class. */
const DEVICE_LABELS: Record<string, string> = {
  desktop: 'Desktop browser',
  mobile: 'Mobile device',
  bot: 'Automated client',
};

/** A session's client and operating system, or its device class. */
const describeSession = (session: AccountSession): string => {
  const base =
    session.client || DEVICE_LABELS[session.device] || 'Unknown device';
  return session.platform ? `${base} on ${session.platform}` : base;
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
  const [sessions, setSessions] = useState<AccountSession[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const outcome = await client.listSessions();
      setSessions(outcome.sessions);
    } catch {
      setSessions((current) => current ?? []);
      setError(FAILED);
    }
  }, [client]);

  useEffect(() => {
    void load();
  }, [load]);

  const run = async (step: () => Promise<string | null>) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const message = await step();
      if (message) setNotice(message);
    } catch {
      setError(FAILED);
    } finally {
      await load();
      setBusy(false);
    }
  };

  const endOne = (session: AccountSession) =>
    run(async () => {
      const outcome = await client.revokeSession(session.id);
      if (outcome.ok || outcome.reason === 'not-found') {
        return 'Session ended. That device is signed out.';
      }
      setError(outcome.message);
      return null;
    });

  const endOthers = (others: AccountSession[]) =>
    run(async () => {
      const outcomes = await Promise.all(
        others.map((session) => client.revokeSession(session.id))
      );
      const refused = outcomes.find(
        (outcome) => !outcome.ok && outcome.reason !== 'not-found'
      );
      if (refused && !refused.ok) {
        setError(refused.message);
        return null;
      }
      return 'All other sessions ended. Those devices are signed out.';
    });

  if (sessions === null) {
    return (
      <div className="flex justify-center py-8">
        <Spinner />
      </div>
    );
  }

  const others = sessions.filter((session) => !session.current);

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-white">Active sessions</h3>
        <p className="text-sm text-muted-foreground">
          The devices signed in to your account. End any session you do not
          recognise, then change your password.
        </p>
      </div>

      {error && <ErrorAlert message={error} />}
      {notice && <ConfirmationAlert message={notice} />}

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
                    onClick={() => void endOne(session)}
                    disabled={busy}
                  >
                    End
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {others.length > 0 && (
        <Button
          type="button"
          variant="destructive"
          onClick={() => {
            if (
              !window.confirm(
                'End every other session? Those devices will need to sign in again.'
              )
            ) {
              return;
            }
            void endOthers(others);
          }}
          disabled={busy}
          loading={busy}
          className="w-full"
        >
          End all other sessions
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
