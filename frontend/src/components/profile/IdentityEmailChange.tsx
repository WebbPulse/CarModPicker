/**
 * The sign-in address change form for identity mode. A new address only takes
 * effect once the link mailed to it is opened, so this form asks for the mail
 * and says where to look. A sign-in older than the server's window asks for the
 * password or a passkey first, then sends the request again.
 */
import { useState } from 'react';
import { FaEnvelope, FaKey, FaLock } from 'react-icons/fa';
import { identityAvailability } from '../../api/authMode';
import {
  getIdentityClient,
  type IdentityClient,
} from '../../api/identityClient';
import { ConfirmationAlert, ErrorAlert } from '../ui/alert';
import { Button } from '../ui/button';
import { Input } from '../ui/input';

/** The sentence shown when the request could not reach the server. */
const FAILED =
  'Could not reach the server. Check your connection and try again.';

/** The form body, mounted only once the identity client could be built. */
const EmailChangeBody: React.FC<{
  client: IdentityClient;
  currentEmail: string;
}> = ({ client, currentEmail }) => {
  const passkeys = identityAvailability().passkeys;
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [needsReauth, setNeedsReauth] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);

  const request = async (address: string) => {
    const outcome = await client.requestEmailChange({ email: address });
    if (outcome.ok) {
      setSentTo(address);
      setEmail('');
      setNeedsReauth(false);
      return;
    }
    if (outcome.reason === 'step-up-required') {
      setNeedsReauth(true);
      return;
    }
    setError(outcome.message);
  };

  const run = async (step: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await step();
    } catch {
      setError(FAILED);
    } finally {
      setBusy(false);
    }
  };

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const address = email.trim();
    if (!address) {
      setError('Enter the new email address.');
      return;
    }
    setSentTo(null);
    void run(() => request(address));
  };

  const handlePasswordReauth = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!password) {
      setError('Enter your password.');
      return;
    }
    void run(async () => {
      const outcome = await client.stepUp({ password });
      setPassword('');
      if (!outcome.ok) {
        setError(outcome.message);
        return;
      }
      await request(email.trim());
    });
  };

  const handlePasskeyReauth = () => {
    void run(async () => {
      const outcome = await client.stepUpWithPasskey();
      if (!outcome.ok) {
        if (outcome.reason !== 'cancelled') setError(outcome.message);
        return;
      }
      await request(email.trim());
    });
  };

  if (needsReauth) {
    return (
      <div className="space-y-6">
        {error && <ErrorAlert message={error} />}
        <p className="text-sm text-gray-300">
          For your security, confirm it is you before changing your email
          address.
        </p>
        <form
          onSubmit={handlePasswordReauth}
          className="space-y-4"
          aria-label="Confirm it is you"
        >
          <div>
            <label
              htmlFor="email-change-password"
              className="block text-sm font-medium text-foreground mb-2"
            >
              Password
            </label>
            <div className="relative">
              <span
                aria-hidden="true"
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-white/60"
              >
                <FaLock />
              </span>
              <Input
                id="email-change-password"
                type="password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  setError(null);
                }}
                disabled={busy}
                autoComplete="current-password"
                className="pl-10"
              />
            </div>
          </div>
          <div className="flex space-x-3">
            <Button
              type="submit"
              disabled={busy}
              loading={busy}
              className="flex-1"
            >
              Confirm and send link
            </Button>
            {passkeys && (
              <Button
                type="button"
                variant="secondary"
                onClick={handlePasskeyReauth}
                disabled={busy}
                className="flex-1"
              >
                <FaKey className="mr-2" />
                Use a passkey
              </Button>
            )}
          </div>
        </form>
        <p className="text-sm text-gray-400">
          Signed in with Google or GitHub and have no password? Sign out, sign
          back in, and try again within 10 minutes.
        </p>
        <Button
          type="button"
          variant="secondary"
          onClick={() => {
            setNeedsReauth(false);
            setPassword('');
            setError(null);
          }}
          disabled={busy}
          className="w-full"
        >
          Cancel
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {sentTo && (
        <ConfirmationAlert
          message={`We sent a confirmation link to ${sentTo}. Your email address changes when you open it. Until then you keep signing in with ${currentEmail}.`}
        />
      )}
      {error && <ErrorAlert message={error} />}
      <p className="text-sm text-gray-300">
        Your current email address is{' '}
        <span className="font-medium">{currentEmail}</span>.
      </p>
      <div>
        <label
          htmlFor="new-email"
          className="block text-sm font-medium text-foreground mb-2"
        >
          New email address
        </label>
        <div className="relative">
          <span
            aria-hidden="true"
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-white/60"
          >
            <FaEnvelope />
          </span>
          <Input
            id="new-email"
            type="email"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              setError(null);
            }}
            disabled={busy}
            autoComplete="email"
            className="pl-10"
          />
        </div>
        <div className="mt-2 text-sm text-muted-foreground">
          We will email a link to the new address. Signing in with the new
          address works once you open it, and your other devices are signed out.
        </div>
      </div>
      <Button type="submit" disabled={busy} loading={busy} className="w-full">
        Send confirmation link
      </Button>
    </form>
  );
};

/** The email change form, or the unavailable notice in bearer mode. */
function IdentityEmailChange({ currentEmail }: { currentEmail: string }) {
  const client = getIdentityClient();
  if (client === null) {
    return (
      <ErrorAlert message="Changing your email address is not available in this deployment." />
    );
  }
  return <EmailChangeBody client={client} currentEmail={currentEmail} />;
}

export default IdentityEmailChange;
