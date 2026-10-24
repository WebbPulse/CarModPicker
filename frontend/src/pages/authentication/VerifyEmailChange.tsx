/**
 * Landing page for a mailed email change link, at `VERIFY_EMAIL_CHANGE_PATH`.
 *
 * Spends the `?token=` once on mount through `confirmEmailChange`, which works
 * signed in or not, since the link may open in another browser. Refusals carry
 * the server's own sentence.
 */
import { useEffect, useRef, useState } from 'react';
import {
  VERIFY_EMAIL_CHANGE_PATH,
  readLinkToken,
  type AuthClient,
} from '@webbpulse/auth';
import AuthCard from '../../components/auth/AuthCard';
import AuthRedirectLink from '../../components/auth/AuthRedirectLink';
import { ConfirmationAlert, ErrorAlert } from '../../components/ui/alert';
import Spinner from '../../components/ui/spinner';
import { getIdentityClient } from '../../api/identityClient';
import { useAuth } from '../../hooks/useAuth';

/** The sentence shown when the link could not be spent at all. */
const FAILED =
  'Could not reach the server to confirm your new email address. Check your connection and try the link again.';

/** The sentence shown when the link arrived without its token. */
const MISSING =
  'This link is missing its token. Request a new one from your security settings.';

type ChangeState =
  | { kind: 'confirming' }
  | { kind: 'confirmed' }
  | { kind: 'refused'; message: string };

/** Spends a mailed email change token once on mount and reports the outcome. */
const VerifyEmailChangeBody: React.FC<{ client: AuthClient<unknown> }> = ({
  client,
}) => {
  const { isAuthenticated, reloadUser } = useAuth();
  const [token] = useState(() =>
    readLinkToken({ expectedPath: VERIFY_EMAIL_CHANGE_PATH })
  );
  const [state, setState] = useState<ChangeState>(() =>
    token === null
      ? { kind: 'refused', message: MISSING }
      : { kind: 'confirming' }
  );
  const spent = useRef(false);

  useEffect(() => {
    if (token === null || spent.current) return;
    spent.current = true;
    client
      .confirmEmailChange({ token })
      .then(async (outcome) => {
        if (!outcome.ok) {
          setState({ kind: 'refused', message: outcome.message });
          return;
        }
        setState({ kind: 'confirmed' });
        if (isAuthenticated) {
          await reloadUser().catch(() => undefined);
        }
      })
      .catch(() => setState({ kind: 'refused', message: FAILED }));
  }, [client, token, isAuthenticated, reloadUser]);

  if (state.kind === 'confirming') {
    return (
      <AuthCard title="Confirming your new email">
        <Spinner />
      </AuthCard>
    );
  }

  if (state.kind === 'confirmed') {
    return (
      <AuthCard title="Email address changed">
        <ConfirmationAlert message="Your new email address is confirmed. Use it the next time you sign in. Your other devices have been signed out." />
        {isAuthenticated ? (
          <AuthRedirectLink text="Go to" linkText="Profile" to="/profile" />
        ) : (
          <AuthRedirectLink text="Proceed to" linkText="Sign In" to="/login" />
        )}
      </AuthCard>
    );
  }

  return (
    <AuthCard title="Email change failed">
      <ErrorAlert message={state.message} />
      <AuthRedirectLink text="Back to" linkText="Home" to="/" />
    </AuthCard>
  );
};

/** The email change landing page, or the unavailable notice in bearer mode. */
function VerifyEmailChange() {
  const client = getIdentityClient();
  if (client === null) {
    return (
      <AuthCard title="Confirm your new email">
        <ErrorAlert message="Changing your email address is not available in this deployment." />
        <AuthRedirectLink text="Back to" linkText="Home" to="/" />
      </AuthCard>
    );
  }
  return <VerifyEmailChangeBody client={client} />;
}

export default VerifyEmailChange;
