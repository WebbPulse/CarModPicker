import { useEffect, useState } from 'react';
import { FaClock, FaKey, FaLink, FaLock, FaShieldAlt } from 'react-icons/fa';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { authApi, usersApi } from '../../services/Api';
import type { TOTPSetupResponse } from '../../types/Api';
import ActionButton from '../buttons/ActionButton';
import SecondaryButton from '../buttons/SecondaryButton';
import { ConfirmationAlert, ErrorAlert } from '../common/Alerts';
import Dialog from '../common/Dialog';
import Input from '../common/Input';
import LoadingSpinner from '../common/LoadingSpinner';
import ConnectedAccountsSettings from './ConnectedAccountsSettings';
import PasskeySettings from './PasskeySettings';

const SESSION_EXPIRE_OPTIONS: { value: number | null; label: string }[] = [
  { value: null, label: 'Use server default (60 min)' },
  { value: 15, label: '15 minutes' },
  { value: 30, label: '30 minutes' },
  { value: 60, label: '1 hour' },
  { value: 240, label: '4 hours' },
  { value: 480, label: '8 hours' },
  { value: 1440, label: '24 hours' },
  { value: 10080, label: '7 days' },
];

interface SecuritySettingsDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onPasswordChanged: () => void;
  on2FAEnabled: () => void;
  on2FADisabled: () => void;
  onSessionUpdated?: () => void;
}

type TabType = 'password' | '2fa' | 'passkeys' | 'connected' | 'session';

function SecuritySettingsDialog({
  isOpen,
  onClose,
  onPasswordChanged,
  on2FAEnabled,
  on2FADisabled,
  onSessionUpdated,
}: SecuritySettingsDialogProps) {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<TabType>('password');

  // Password change state
  const [passwordData, setPasswordData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmNewPassword: '',
    otp: '',
  });
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null);

  // 2FA state
  const [setupData, setSetupData] = useState<TOTPSetupResponse | null>(null);
  const [otp, setOtp] = useState('');
  const [disablePassword, setDisablePassword] = useState('');
  const [disableOtp, setDisableOtp] = useState('');
  const [isVerifying, setIsVerifying] = useState(false);
  const [isDisabling, setIsDisabling] = useState(false);
  const [twoFAError, setTwoFAError] = useState<string | null>(null);
  const [twoFASuccess, setTwoFASuccess] = useState<string | null>(null);

  // Session expiry state
  const [sessionExpireMinutes, setSessionExpireMinutes] = useState<
    number | null
  >(() => user?.session_expire_minutes ?? null);
  const [isSavingSession, setIsSavingSession] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [sessionSuccess, setSessionSuccess] = useState<string | null>(null);

  const setupRequestFn = () => authApi.setup2FA();
  const {
    error: setupError,
    isLoading: isSettingUp,
    executeRequest: performSetup,
  } = useApiRequest(setupRequestFn);

  useEffect(() => {
    if (isOpen && user) {
      setSessionExpireMinutes(user.session_expire_minutes ?? null);
      setSessionError(null);
      setSessionSuccess(null);
    }
  }, [isOpen, user]);

  const handleClose = () => {
    // Reset password form
    setPasswordData({
      currentPassword: '',
      newPassword: '',
      confirmNewPassword: '',
      otp: '',
    });
    setPasswordError(null);
    setPasswordSuccess(null);

    // Reset 2FA form
    setSetupData(null);
    setOtp('');
    setDisablePassword('');
    setDisableOtp('');
    setTwoFAError(null);
    setTwoFASuccess(null);

    setSessionError(null);
    setSessionSuccess(null);

    onClose();
  };

  const handleSaveSession = async () => {
    if (!user) return;
    setSessionError(null);
    setSessionSuccess(null);
    setIsSavingSession(true);
    try {
      await usersApi.updateUser(user.id, {
        session_expire_minutes: sessionExpireMinutes,
      });
      setSessionSuccess(
        'Session length updated. Your current session has been extended with the new expiry.'
      );
      onSessionUpdated?.();
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: string } } };
      setSessionError(
        axiosError.response?.data?.detail || 'Failed to update session length.'
      );
    } finally {
      setIsSavingSession(false);
    }
  };

  // Password change handlers
  const handlePasswordChange = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setPasswordError(null);
    setPasswordSuccess(null);

    // Validation
    if (!passwordData.currentPassword.trim()) {
      setPasswordError('Current password is required.');
      return;
    }

    if (!passwordData.newPassword.trim()) {
      setPasswordError('New password is required.');
      return;
    }

    if (passwordData.newPassword !== passwordData.confirmNewPassword) {
      setPasswordError("New passwords don't match.");
      return;
    }

    if (passwordData.newPassword.length < 8) {
      setPasswordError('New password must be at least 8 characters long.');
      return;
    }

    // If 2FA is enabled, require OTP
    if (user?.totp_enabled) {
      if (!passwordData.otp.trim() || passwordData.otp.length !== 6) {
        setPasswordError(
          '2FA is enabled. Please enter a valid 6-digit OTP code.'
        );
        return;
      }
    }

    setIsChangingPassword(true);

    try {
      const updateData: {
        current_password: string;
        password: string;
        otp?: string;
      } = {
        current_password: passwordData.currentPassword,
        password: passwordData.newPassword,
      };

      // Include OTP if 2FA is enabled
      if (user?.totp_enabled) {
        updateData.otp = passwordData.otp;
      }

      const response = await usersApi.updateUser(user!.id, updateData);

      if (response.data) {
        setPasswordSuccess('Password changed successfully!');
        setTimeout(() => {
          setPasswordData({
            currentPassword: '',
            newPassword: '',
            confirmNewPassword: '',
            otp: '',
          });
          onPasswordChanged();
        }, 1500);
      }
    } catch (err: unknown) {
      let errorMessage = 'Failed to change password';
      if (err instanceof Error) {
        errorMessage = err.message;
      } else if (typeof err === 'object' && err !== null && 'response' in err) {
        const response = (err as { response?: { data?: { detail?: string } } })
          .response;
        if (response?.data?.detail) {
          errorMessage = response.data.detail;
        }
      }
      setPasswordError(errorMessage);
    } finally {
      setIsChangingPassword(false);
    }
  };

  // 2FA handlers
  const handleSetup = async () => {
    setTwoFAError(null);
    setTwoFASuccess(null);
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
      setTwoFAError('Please enter a valid 6-digit OTP code.');
      return;
    }

    setTwoFAError(null);
    setIsVerifying(true);

    try {
      await authApi.verify2FA({ otp });
      setTwoFASuccess('2FA has been enabled successfully!');
      setSetupData(null);
      setOtp('');
      setTimeout(() => {
        on2FAEnabled();
      }, 1500);
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: string } } };
      setTwoFAError(
        axiosError.response?.data?.detail ||
          'Invalid OTP code. Please try again.'
      );
    } finally {
      setIsVerifying(false);
    }
  };

  const handleDisable = async () => {
    setTwoFAError(null);
    setTwoFASuccess(null);

    // Validation
    if (!disablePassword.trim()) {
      setTwoFAError('Password is required to disable 2FA.');
      return;
    }

    if (!disableOtp.trim() || disableOtp.length !== 6) {
      setTwoFAError('Please enter a valid 6-digit OTP code.');
      return;
    }

    setIsDisabling(true);

    try {
      await authApi.disable2FA({
        password: disablePassword,
        otp: disableOtp,
      });
      setTwoFASuccess('2FA has been disabled successfully!');
      setTimeout(() => {
        setDisablePassword('');
        setDisableOtp('');
        on2FADisabled();
      }, 1500);
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: string } } };
      setTwoFAError(
        axiosError.response?.data?.detail ||
          'Failed to disable 2FA. Please try again.'
      );
    } finally {
      setIsDisabling(false);
    }
  };

  if (!isOpen) return null;

  return (
    <Dialog
      isOpen={isOpen}
      onClose={handleClose}
      title="Manage Security Settings"
      maxWidth="lg"
    >
      <div className="space-y-6">
        {/* Tabs */}
        <div className="flex border-b border-gray-700">
          <button
            type="button"
            onClick={() => setActiveTab('password')}
            className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
              activeTab === 'password'
                ? 'text-primary-400 border-b-2 border-primary-400'
                : 'text-gray-400 hover:text-gray-300'
            }`}
          >
            <div className="flex items-center justify-center space-x-2">
              <FaLock />
              <span>Change Password</span>
            </div>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('2fa')}
            className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
              activeTab === '2fa'
                ? 'text-primary-400 border-b-2 border-primary-400'
                : 'text-gray-400 hover:text-gray-300'
            }`}
          >
            <div className="flex items-center justify-center space-x-2">
              <FaShieldAlt />
              <span>Two-Factor Authentication</span>
            </div>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('passkeys')}
            className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
              activeTab === 'passkeys'
                ? 'text-primary-400 border-b-2 border-primary-400'
                : 'text-gray-400 hover:text-gray-300'
            }`}
          >
            <div className="flex items-center justify-center space-x-2">
              <FaKey />
              <span>Passkeys</span>
            </div>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('connected')}
            className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
              activeTab === 'connected'
                ? 'text-primary-400 border-b-2 border-primary-400'
                : 'text-gray-400 hover:text-gray-300'
            }`}
          >
            <div className="flex items-center justify-center space-x-2">
              <FaLink />
              <span>Connected</span>
            </div>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('session')}
            className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
              activeTab === 'session'
                ? 'text-primary-400 border-b-2 border-primary-400'
                : 'text-gray-400 hover:text-gray-300'
            }`}
          >
            <div className="flex items-center justify-center space-x-2">
              <FaClock />
              <span>Session</span>
            </div>
          </button>
        </div>

        {/* Password Change Tab */}
        {activeTab === 'password' && (
          <form
            onSubmit={(e) => void handlePasswordChange(e)}
            className="space-y-6"
          >
            {passwordSuccess && <ConfirmationAlert message={passwordSuccess} />}
            {passwordError && <ErrorAlert message={passwordError} />}

            <Input
              label="Current Password"
              id="currentPassword"
              name="currentPassword"
              type="password"
              value={passwordData.currentPassword}
              onChange={(e) => {
                setPasswordData((prev) => ({
                  ...prev,
                  currentPassword: e.target.value,
                }));
                setPasswordError(null);
              }}
              disabled={isChangingPassword}
              required
              autoComplete="current-password"
              leftIcon={<FaLock />}
            />

            <Input
              label="New Password"
              id="newPassword"
              name="newPassword"
              type="password"
              value={passwordData.newPassword}
              onChange={(e) => {
                setPasswordData((prev) => ({
                  ...prev,
                  newPassword: e.target.value,
                }));
                setPasswordError(null);
              }}
              disabled={isChangingPassword}
              required
              autoComplete="new-password"
              minLength={8}
              leftIcon={<FaLock />}
            />

            <Input
              label="Confirm New Password"
              id="confirmNewPassword"
              name="confirmNewPassword"
              type="password"
              value={passwordData.confirmNewPassword}
              onChange={(e) => {
                setPasswordData((prev) => ({
                  ...prev,
                  confirmNewPassword: e.target.value,
                }));
                setPasswordError(null);
              }}
              disabled={isChangingPassword}
              required
              autoComplete="new-password"
              leftIcon={<FaLock />}
            />

            {user?.totp_enabled && (
              <Input
                label="2FA Code"
                id="otp"
                name="otp"
                type="text"
                value={passwordData.otp}
                onChange={(e) => {
                  const value = e.target.value.replace(/\D/g, '').slice(0, 6);
                  setPasswordData((prev) => ({ ...prev, otp: value }));
                  setPasswordError(null);
                }}
                placeholder="000000"
                disabled={isChangingPassword}
                required
                maxLength={6}
                leftIcon={<FaShieldAlt />}
                helperText="Enter the 6-digit code from your authenticator app"
              />
            )}

            <div className="flex space-x-3 pt-4">
              <ActionButton
                type="submit"
                disabled={isChangingPassword}
                className="flex-1"
              >
                {isChangingPassword ? (
                  <>
                    <LoadingSpinner />
                    <span className="ml-2">Changing Password...</span>
                  </>
                ) : (
                  'Change Password'
                )}
              </ActionButton>
              <SecondaryButton
                type="button"
                onClick={handleClose}
                disabled={isChangingPassword}
                className="flex-1"
              >
                Cancel
              </SecondaryButton>
            </div>
          </form>
        )}

        {/* 2FA Tab */}
        {activeTab === '2fa' && (
          <div className="space-y-6">
            {twoFASuccess && <ConfirmationAlert message={twoFASuccess} />}
            {(twoFAError || setupError) && (
              <ErrorAlert
                message={twoFAError || setupError || 'An error occurred'}
              />
            )}

            {!user?.totp_enabled && !setupData && (
              <div className="space-y-4">
                <div className="flex items-center space-x-3 text-gray-300">
                  <FaShieldAlt className="text-primary-400 text-2xl" />
                  <div>
                    <h3 className="text-lg font-semibold">
                      Enable Two-Factor Authentication
                    </h3>
                    <p className="text-sm text-gray-400">
                      Add an extra layer of security to your account by
                      requiring a code from your authenticator app when you log
                      in.
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
                      Enter the 6-digit code from your app to verify and enable
                      2FA
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

            {!user?.totp_enabled && setupData && (
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
                      const value = e.target.value
                        .replace(/\D/g, '')
                        .slice(0, 6);
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
                      setTwoFAError(null);
                    }}
                    className="flex-1"
                  >
                    Cancel
                  </SecondaryButton>
                </div>
              </div>
            )}

            {user?.totp_enabled && (
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
                    security feature from your account. Make sure you have
                    backup codes or another way to secure your account.
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
                      setTwoFAError(null);
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
                      const value = e.target.value
                        .replace(/\D/g, '')
                        .slice(0, 6);
                      setDisableOtp(value);
                      setTwoFAError(null);
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
        )}

        {/* Session Tab */}
        {activeTab === 'session' && (
          <div className="space-y-6">
            {sessionSuccess && <ConfirmationAlert message={sessionSuccess} />}
            {sessionError && <ErrorAlert message={sessionError} />}

            <div className="flex items-center space-x-3 text-gray-300">
              <FaClock className="text-primary-400 text-2xl" />
              <div>
                <h3 className="text-lg font-semibold">Session length</h3>
                <p className="text-sm text-gray-400">
                  Choose how long you stay signed in. Shorter sessions are more
                  secure. A new token with the selected expiry is issued when
                  you save.
                </p>
              </div>
            </div>

            <div>
              <label
                htmlFor="session-expire"
                className="block text-sm font-medium text-gray-300 mb-2"
              >
                Stay signed in for
              </label>
              <select
                id="session-expire"
                value={sessionExpireMinutes ?? ''}
                onChange={(e) => {
                  const v = e.target.value;
                  setSessionExpireMinutes(v === '' ? null : Number(v));
                  setSessionError(null);
                }}
                disabled={isSavingSession}
                className="block w-full rounded-lg border border-gray-600 bg-gray-800 px-4 py-2 text-gray-300 focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
              >
                {SESSION_EXPIRE_OPTIONS.map((opt) => (
                  <option key={opt.value ?? 'default'} value={opt.value ?? ''}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <ActionButton
              onClick={() => void handleSaveSession()}
              disabled={isSavingSession}
              className="w-full"
            >
              {isSavingSession ? (
                <>
                  <LoadingSpinner />
                  <span className="ml-2">Saving...</span>
                </>
              ) : (
                'Save session length'
              )}
            </ActionButton>
          </div>
        )}
        {activeTab === 'passkeys' && <PasskeySettings />}
        {activeTab === 'connected' && <ConnectedAccountsSettings />}
      </div>
    </Dialog>
  );
}

export default SecuritySettingsDialog;
