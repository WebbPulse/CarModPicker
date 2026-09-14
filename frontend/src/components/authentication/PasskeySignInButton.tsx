/**
 * The "Sign in with a passkey" button for identity mode, hidden unless the
 * browser supports WebAuthn and the deployment enables passwordless sign in.
 * `usePasskeySignInSupport` answers both questions and reports whether the
 * browser can also put a passkey in its username autofill dropdown.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { FaKey } from 'react-icons/fa';
import { usePasskeySignInSupport } from '@webbpulse/auth/react';
import { Button } from '../ui/button';
import {
  PASSKEY_AVAILABILITY_PATH,
  identityUrl,
  passkeyLoginAvailability,
} from '../../api/identityClient';
import { signInWithPasskey } from '../../api/identityPasskeys';
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
  const [busy, setBusy] = useState(false);
  const handler = useRef(onResult);
  handler.current = onResult;

  const probe = useCallback(
    () => passkeyLoginAvailability(identityUrl(PASSKEY_AVAILABILITY_PATH)),
    []
  );
  const support = usePasskeySignInSupport({ probe });
  const armed = conditional && support.offered;

  useEffect(() => {
    if (!armed) return;
    const controller = new AbortController();
    void signInWithPasskey({
      mediation: 'conditional',
      signal: controller.signal,
    }).then((result) => {
      if (controller.signal.aborted) return;
      if (result.status === 'cancelled' || result.status === 'failed') return;
      void handler.current(result);
    });
    return () => {
      controller.abort();
    };
  }, [armed]);

  if (!support.offered) return null;

  const handleClick = async () => {
    setBusy(true);
    try {
      const result = await signInWithPasskey(
        username !== undefined && username.trim() !== ''
          ? { username, mediation: 'optional' }
          : { mediation: 'optional' }
      );
      if (result.status === 'cancelled') return;
      await handler.current(result);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Button
      type="button"
      variant="secondary"
      size="lg"
      className="w-full"
      onClick={() => void handleClick()}
      disabled={disabled || busy}
    >
      <FaKey />
      <span>
        {busy ? 'Waiting for your passkey…' : 'Sign in with a passkey'}
      </span>
    </Button>
  );
}

export default PasskeySignInButton;
