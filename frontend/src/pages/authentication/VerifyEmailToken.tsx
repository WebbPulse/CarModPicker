/**
 * Landing page for a mailed verification link in identity mode.
 *
 * Mounted by `VerifyEmail` only for the `?token=` branch of `/verify-email`.
 * `useEmailVerificationLink` spends the token once and reports the outcome;
 * this file is the markup. Refusals carry the server's own sentence.
 */
import {
  LINK_TOKEN_PARAM,
  VERIFY_EMAIL_PATH,
  type AuthClient,
} from '@webbpulse/auth';
import { useEmailVerificationLink } from '@webbpulse/auth/react';
import AuthCard from '../../components/auth/AuthCard';
import AuthRedirectLink from '../../components/auth/AuthRedirectLink';
import { ConfirmationAlert, ErrorAlert } from '../../components/ui/alert';
import Spinner from '../../components/ui/spinner';
import { getIdentityClient } from '../../api/identityClient';
import { useAuth } from '../../hooks/useAuth';

/** The sentence shown when the link could not be spent at all. */
const FAILED =
  'Could not reach the server to verify your email. Check your connection and try the link again.';

/** The sentence shown when the link arrived without its token. */
const MISSING = 'This link is missing its token. Request a new one.';

/** Spends a mailed verification token once on mount and reports the outcome. */
const VerifyEmailTokenBody: React.FC<{ client: AuthClient<unknown> }> = ({
  client,
}) => {
  const { checkAuthStatus } = useAuth();
  const state = useEmailVerificationLink({
    client,
    expectedPath: VERIFY_EMAIL_PATH,
    onConfirmed: checkAuthStatus,
  });

  if (state.kind === 'confirming') {
    return (
      <AuthCard title="Verifying your email">
        <Spinner />
      </AuthCard>
    );
  }

  if (state.kind === 'confirmed') {
    return (
      <AuthCard title="Email verified">
        <ConfirmationAlert message="Your email address is verified. You can use every part of your account now." />
        <AuthRedirectLink text="Go to" linkText="Profile" to="/profile" />
      </AuthCard>
    );
  }

  const message =
    state.kind === 'missing-token'
      ? MISSING
      : state.kind === 'failed'
        ? FAILED
        : state.message;

  return (
    <AuthCard title="Verification failed">
      <ErrorAlert message={message} />
      <AuthRedirectLink text="Proceed to" linkText="Sign In" to="/login" />
    </AuthCard>
  );
};

/** The verification landing page, or the unavailable notice in bearer mode. */
function VerifyEmailToken() {
  const client = getIdentityClient();
  if (client === null) {
    return (
      <AuthCard title="Verify your email">
        <ErrorAlert message="Email verification is not available in this deployment." />
        <AuthRedirectLink text="Proceed to" linkText="Sign In" to="/login" />
      </AuthCard>
    );
  }
  return <VerifyEmailTokenBody client={client} />;
}

export { LINK_TOKEN_PARAM };
export default VerifyEmailToken;
