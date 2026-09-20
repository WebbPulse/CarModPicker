/**
 * The "Sign in with a passkey" button for identity mode, hidden unless the
 * browser supports WebAuthn and the deployment enables passwordless sign in.
 * `usePasskeySignInButton` answers both questions, arms the autofill ceremony
 * and runs the pressed one; the markup here is CarModPicker's own.
 */
import { FaKey } from 'react-icons/fa';
import { usePasskeySignInButton } from '@webbpulse/auth/react';
import { Button } from '../ui/button';
import {
  PASSKEY_AVAILABILITY_PATH,
  getIdentityClient,
  identityUrl,
  passkeyLoginAvailability,
} from '../../api/identityClient';
import {
  passkeySignInFailure,
  toPasskeySignInResult,
} from '../../api/identityPasskeys';
import type { PasskeySignInResult } from '../../api/identityPasskeys';

/**
 * Props for PasskeySignInButton: the username hint, outcome callback, and autofill flag.
 */
export interface PasskeySignInButtonProps {
  /** Whatever is in the username field, so a known user skips the chooser. */
  username?: string;
  /** Called for every outcome except a cancellation, which is silent. */
  onResult: (result: PasskeySignInResult) => void | Promise<void>;
  disabled?: boolean;
  /** Whether to arm conditional mediation on mount. Off in tests by default. */
  conditional?: boolean;
}

function PasskeySignInButton({
  username,
  onResult,
  disabled,
  conditional = true,
}: PasskeySignInButtonProps) {
  const button = usePasskeySignInButton({
    client: getIdentityClient(),
    probe: () =>
      passkeyLoginAvailability(identityUrl(PASSKEY_AVAILABILITY_PATH)),
    ...(username === undefined ? {} : { email: username }),
    onResult: (outcome) => onResult(toPasskeySignInResult(outcome)),
    onError: (error) => void onResult(passkeySignInFailure(error)),
    conditional,
  });

  if (!button.offered) return null;

  return (
    <Button
      type="button"
      variant="secondary"
      size="lg"
      className="w-full"
      onClick={() => void button.signIn()}
      disabled={disabled || button.busy}
    >
      <FaKey />
      <span>
        {button.busy ? 'Waiting for your passkey…' : 'Sign in with a passkey'}
      </span>
    </Button>
  );
}

export default PasskeySignInButton;
