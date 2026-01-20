import { useState } from 'react';
import { FaLock, FaShieldAlt } from 'react-icons/fa';
import useApiRequest from '../../hooks/UseApiRequest';
import { authApi } from '../../services/Api';
import type { TOTPSetupResponse } from '../../types/Api';
import ActionButton from '../buttons/ActionButton';
import SecondaryButton from '../buttons/SecondaryButton';
import { ConfirmationAlert, ErrorAlert } from '../common/Alerts';
import Dialog from '../common/Dialog';
import Input from '../common/Input';

interface TwoFactorAuthDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onEnabled: () => void;
  onDisabled: () => void;
  isEnabled: boolean;
}

function TwoFactorAuthDialog({
  isOpen,
  onClose,
  onEnabled,
  onDisabled,
  isEnabled,
}: TwoFactorAuthDialogProps) {
  const [setupData, setSetupData] = useState<TOTPSetupResponse | null>(null);
  const [otp, setOtp] = useState('');
  const [disablePassword, setDisablePassword] = useState('');
  const [disableOtp, setDisableOtp] = useState('');
  const [isVerifying, setIsVerifying] = useState(false);
  const [isDisabling, setIsDisabling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const setupRequestFn = () => authApi.setup2FA();
  const {
    error: setupError,
    isLoading: isSettingUp,
    executeRequest: performSetup,
  } = useApiRequest(setupRequestFn);

  const handleSetup = async () => {
    setError(null);
    setSuccess(null);
    setOtp('');
    try {
      const result = await performSetup();
      if (result) {
        setSetupData(result);
      }
    } catch {
      // Error handled by useApiRequest
    }
  };

  const handleVerify = async () => {
    if (!otp.trim() || otp.length !== 6) {
      setError('Please enter a valid 6-digit OTP code.');
      return;
    }

    setError(null);
    setIsVerifying(true);

    try {
      await authApi.verify2FA({ otp });
      setSuccess('2FA has been enabled successfully!');
      setSetupData(null);
      setOtp('');
      setTimeout(() => {
        onEnabled();
        onClose();
      }, 1500);
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: string } } };
      setError(
        axiosError.response?.data?.detail ||
          'Invalid OTP code. Please try again.'
      );
    } finally {
      setIsVerifying(false);
    }
  };

  const handleDisable = async () => {
    setError(null);
    setSuccess(null);

    // Validation
    if (!disablePassword.trim()) {
      setError('Password is required to disable 2FA.');
      return;
    }

    if (!disableOtp.trim() || disableOtp.length !== 6) {
      setError('Please enter a valid 6-digit OTP code.');
      return;
    }

    setIsDisabling(true);

    try {
      await authApi.disable2FA({
        password: disablePassword,
        otp: disableOtp,
      });
      setSuccess('2FA has been disabled successfully!');
      setTimeout(() => {
        setDisablePassword('');
        setDisableOtp('');
        onDisabled();
        onClose();
      }, 1500);
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: string } } };
      setError(
        axiosError.response?.data?.detail ||
          'Failed to disable 2FA. Please try again.'
      );
    } finally {
      setIsDisabling(false);
    }
  };

  const handleClose = () => {
    setSetupData(null);
    setOtp('');
    setDisablePassword('');
    setDisableOtp('');
    setError(null);
    setSuccess(null);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <Dialog
      isOpen={isOpen}
      onClose={handleClose}
      title="Two-Factor Authentication"
    >
      <div className="space-y-6">
        {success && <ConfirmationAlert message={success} />}
        {(error || setupError) && (
          <ErrorAlert message={error || setupError || 'An error occurred'} />
        )}

        {!isEnabled && !setupData && (
          <div className="space-y-4">
            <div className="flex items-center space-x-3 text-gray-300">
              <FaShieldAlt className="text-primary-400 text-2xl" />
              <div>
                <h3 className="text-lg font-semibold">
                  Enable Two-Factor Authentication
                </h3>
                <p className="text-sm text-gray-400">
                  Add an extra layer of security to your account by requiring a
                  code from your authenticator app when you log in.
                </p>
              </div>
            </div>

            <div className="bg-gray-800/50 rounded-lg p-4 space-y-2 text-sm text-gray-300">
              <p className="font-semibold">How it works:</p>
              <ol className="list-decimal list-inside space-y-1 ml-2">
                <li>
                  Scan the QR code with an authenticator app (Google
                  Authenticator, Authy, etc.)
                </li>
                <li>
                  Enter the 6-digit code from your app to verify and enable 2FA
                </li>
                <li>You'll need this code every time you log in</li>
              </ol>
            </div>

            <ActionButton
              onClick={() => void handleSetup()}
              disabled={isSettingUp}
              className="w-full"
            >
              {isSettingUp ? 'Setting up...' : 'Set Up 2FA'}
            </ActionButton>
          </div>
        )}

        {!isEnabled && setupData && (
          <div className="space-y-4">
            <div className="text-center">
              <h3 className="text-lg font-semibold text-gray-300 mb-2">
                Scan this QR code
              </h3>
              <div className="flex justify-center mb-4">
                <img
                  src={setupData.qr_code_data}
                  alt="2FA QR Code"
                  className="border-2 border-gray-700 rounded-lg p-2 bg-white"
                />
              </div>
              <p className="text-sm text-gray-400 mb-2">
                Or enter this code manually:
              </p>
              <p className="text-sm font-mono text-primary-400 bg-gray-800/50 p-2 rounded">
                {setupData.manual_entry_key}
              </p>
            </div>

            <div>
              <Input
                label="Enter 6-digit code from your app"
                name="otp"
                type="text"
                value={otp}
                onChange={(e) => {
                  const value = e.target.value.replace(/\D/g, '').slice(0, 6);
                  setOtp(value);
                }}
                placeholder="000000"
                maxLength={6}
                leftIcon={<FaShieldAlt />}
              />
            </div>

            <div className="flex space-x-2">
              <ActionButton
                onClick={() => void handleVerify()}
                disabled={isVerifying || otp.length !== 6}
                className="flex-1"
              >
                {isVerifying ? 'Verifying...' : 'Verify & Enable'}
              </ActionButton>
              <SecondaryButton
                onClick={() => {
                  setSetupData(null);
                  setOtp('');
                  setError(null);
                }}
                className="flex-1"
              >
                Cancel
              </SecondaryButton>
            </div>
          </div>
        )}

        {isEnabled && (
          <div className="space-y-4">
            <div className="flex items-center space-x-3 text-gray-300">
              <FaShieldAlt className="text-green-400 text-2xl" />
              <div>
                <h3 className="text-lg font-semibold">2FA is Enabled</h3>
                <p className="text-sm text-gray-400">
                  Your account is protected with two-factor authentication.
                </p>
              </div>
            </div>

            <div className="bg-yellow-900/20 border border-yellow-700/50 rounded-lg p-4">
              <p className="text-sm text-yellow-300">
                <strong>Warning:</strong> Disabling 2FA will remove this
                security feature from your account. Make sure you have backup
                codes or another way to secure your account.
              </p>
            </div>

            <div className="space-y-4">
              <Input
                label="Password"
                name="disablePassword"
                type="password"
                value={disablePassword}
                onChange={(e) => {
                  setDisablePassword(e.target.value);
                  setError(null);
                }}
                placeholder="Enter your password"
                disabled={isDisabling}
                required
                autoComplete="current-password"
                leftIcon={<FaLock />}
              />

              <Input
                label="2FA Code"
                name="disableOtp"
                type="text"
                value={disableOtp}
                onChange={(e) => {
                  const value = e.target.value.replace(/\D/g, '').slice(0, 6);
                  setDisableOtp(value);
                  setError(null);
                }}
                placeholder="000000"
                disabled={isDisabling}
                required
                maxLength={6}
                leftIcon={<FaShieldAlt />}
                helperText="Enter the 6-digit code from your authenticator app"
              />
            </div>

            <ActionButton
              onClick={() => void handleDisable()}
              disabled={
                isDisabling ||
                !disablePassword.trim() ||
                disableOtp.length !== 6
              }
              className="w-full bg-red-600 hover:bg-red-700"
            >
              {isDisabling ? 'Disabling...' : 'Disable 2FA'}
            </ActionButton>
          </div>
        )}
      </div>
    </Dialog>
  );
}

export default TwoFactorAuthDialog;
