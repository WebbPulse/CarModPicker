import { useEffect, useState } from 'react';
import { GoogleLogin, type CredentialResponse } from '@react-oauth/google';
import { FaEye, FaEyeSlash, FaLock, FaShieldAlt, FaUser } from 'react-icons/fa';
import Button from '../buttons/Button';
import Dialog from '../common/Dialog';
import Input from '../common/Input';
import {
  isGoogleConfigured,
  useGoogleSignIn,
} from '../../hooks/useGoogleSignIn';
import { authApi } from '../../services/Api';
import type { UserRead } from '../../types/Api';

interface GoogleAuthFlowProps {
  onLoggedIn: (user: UserRead) => void;
  onError: (message: string) => void;
  disabled?: boolean;
}

const errMessage = (err: unknown, fallback: string): string => {
  const ax = err as {
    response?: { data?: { detail?: string; message?: string } };
  };
  return ax.response?.data?.message || ax.response?.data?.detail || fallback;
};

const GoogleAuthFlow: React.FC<GoogleAuthFlowProps> = ({
  onLoggedIn,
  onError,
  disabled,
}) => {
  const { state, nonce, submitCredential, reset } = useGoogleSignIn({
    onLoggedIn,
    onError,
  });

  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [otp, setOtp] = useState('');
  const [username, setUsername] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const openLink = state.kind === 'link';
  const openSignup = state.kind === 'signup';
  const open2FA = state.kind === 'twoFactor';

  // Pre-fill the username field when the signup dialog first opens. Resetting back
  // to '' on close prevents a stale value bleeding into a later dialog.
  useEffect(() => {
    if (state.kind === 'signup') {
      setUsername(state.payload.suggested_username);
    } else {
      setUsername('');
    }
  }, [state]);

  if (!isGoogleConfigured()) return null;

  const closeDialog = () => {
    setPassword('');
    setOtp('');
    setUsername('');
    reset();
  };

  const handleCredential = (resp: CredentialResponse) => {
    if (!resp.credential) {
      onError('Google did not return a credential. Please try again.');
      return;
    }
    void submitCredential(resp.credential);
  };

  const handleLinkSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (state.kind !== 'link') return;
    setSubmitting(true);
    try {
      const result = await authApi.googleLink({
        link_token: state.payload.link_token,
        password,
        ...(state.payload.has_totp ? { otp } : {}),
      });
      onLoggedIn(result.data);
      closeDialog();
    } catch (err) {
      onError(errMessage(err, 'Linking failed. Please try again.'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleSignupSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (state.kind !== 'signup') return;
    setSubmitting(true);
    try {
      const result = await authApi.googleSignup({
        signup_token: state.payload.signup_token,
        username: username.trim(),
      });
      onLoggedIn(result.data);
      closeDialog();
    } catch (err) {
      onError(errMessage(err, 'Could not finish account creation.'));
    } finally {
      setSubmitting(false);
    }
  };

  const handle2FASubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (state.kind !== 'twoFactor') return;
    setSubmitting(true);
    try {
      const result = await authApi.oauthTwoFactor({
        otp_token: state.payload.otp_token,
        otp,
      });
      onLoggedIn(result.data);
      closeDialog();
    } catch (err) {
      onError(errMessage(err, 'Invalid code. Please try again.'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <div
        className={`flex justify-center ${disabled ? 'opacity-60 pointer-events-none' : ''}`}
      >
        <GoogleLogin
          onSuccess={handleCredential}
          onError={() => onError('Google sign-in was cancelled or failed.')}
          nonce={nonce}
          theme="filled_black"
          shape="pill"
          text="continue_with"
          width="320"
          useOneTap={false}
        />
      </div>

      <Dialog
        isOpen={openLink}
        onClose={closeDialog}
        title="Link Google to your account"
        maxWidth="md"
      >
        {state.kind === 'link' && (
          <form
            onSubmit={(e) => void handleLinkSubmit(e)}
            className="space-y-5"
          >
            <p className="text-neutral-300 text-sm">
              An account already exists for{' '}
              <span className="text-white font-medium">
                {state.payload.email}
              </span>
              . Enter your password to merge Google sign-in into it.
            </p>
            <Input
              label="Password"
              name="password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              leftIcon={<FaLock />}
              rightIcon={
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="text-neutral-400 hover:text-white transition-colors"
                >
                  {showPassword ? <FaEyeSlash /> : <FaEye />}
                </button>
              }
              variant="glass"
            />
            {state.payload.has_totp && (
              <Input
                label="Authentication code"
                name="otp"
                type="text"
                required
                value={otp}
                onChange={(e) =>
                  setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))
                }
                placeholder="000000"
                leftIcon={<FaShieldAlt />}
                variant="glass"
                maxLength={6}
              />
            )}
            <Button
              type="submit"
              loading={submitting}
              disabled={submitting || !password}
              className="w-full"
              size="lg"
            >
              Link &amp; sign in
            </Button>
          </form>
        )}
      </Dialog>

      <Dialog
        isOpen={openSignup}
        onClose={closeDialog}
        title="Choose your username"
        maxWidth="md"
      >
        {state.kind === 'signup' && (
          <form
            onSubmit={(e) => void handleSignupSubmit(e)}
            className="space-y-5"
          >
            <p className="text-neutral-300 text-sm">
              Welcome! Pick a username to finish creating your account for{' '}
              <span className="text-white font-medium">
                {state.payload.email}
              </span>
              .
            </p>
            <Input
              label="Username"
              name="username"
              type="text"
              autoComplete="username"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              leftIcon={<FaUser />}
              variant="glass"
            />
            <Button
              type="submit"
              loading={submitting}
              disabled={submitting || !username.trim()}
              className="w-full"
              size="lg"
            >
              Create account
            </Button>
          </form>
        )}
      </Dialog>

      <Dialog
        isOpen={open2FA}
        onClose={closeDialog}
        title="Two-factor authentication"
        maxWidth="md"
      >
        {state.kind === 'twoFactor' && (
          <form onSubmit={(e) => void handle2FASubmit(e)} className="space-y-5">
            <p className="text-neutral-300 text-sm">
              Enter the 6-digit code from your authenticator app to complete
              sign-in.
            </p>
            <Input
              label="Authentication code"
              name="otp"
              type="text"
              required
              value={otp}
              onChange={(e) =>
                setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))
              }
              placeholder="000000"
              leftIcon={<FaShieldAlt />}
              variant="glass"
              maxLength={6}
            />
            <Button
              type="submit"
              loading={submitting}
              disabled={submitting || otp.length !== 6}
              className="w-full"
              size="lg"
            >
              Verify
            </Button>
          </form>
        )}
      </Dialog>
    </>
  );
};

export default GoogleAuthFlow;
