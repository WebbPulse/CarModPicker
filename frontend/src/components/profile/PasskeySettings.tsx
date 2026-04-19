import { useEffect, useState } from 'react';
import { FaKey, FaPlus, FaTrash } from 'react-icons/fa';
import {
  browserSupportsWebAuthn,
  startRegistration,
} from '@simplewebauthn/browser';
import { authApi } from '../../services/Api';
import type { WebAuthnCredentialSummary } from '../../services/Api';
import ActionButton from '../buttons/ActionButton';
import SecondaryButton from '../buttons/SecondaryButton';
import { ConfirmationAlert, ErrorAlert } from '../common/Alerts';
import Input from '../common/Input';
import LoadingSpinner from '../common/LoadingSpinner';

function formatDate(value?: string | null): string {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleDateString();
  } catch {
    return value;
  }
}

function PasskeySettings() {
  const [credentials, setCredentials] = useState<WebAuthnCredentialSummary[]>(
    []
  );
  const [isLoading, setIsLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newNickname, setNewNickname] = useState('');
  const [isRegistering, setIsRegistering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const browserSupported = browserSupportsWebAuthn();

  const loadCredentials = async () => {
    try {
      const resp = await authApi.webauthnListCredentials();
      setCredentials(resp.data);
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: string } } };
      setError(axiosError.response?.data?.detail || 'Failed to load passkeys.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadCredentials();
  }, []);

  const handleAdd = async () => {
    setError(null);
    setSuccess(null);
    const nickname = newNickname.trim();
    if (!nickname) {
      setError('Please give your passkey a name (e.g. "Laptop", "YubiKey").');
      return;
    }
    setIsRegistering(true);
    try {
      const optsResp = await authApi.webauthnRegisterOptions(nickname);
      const { options, challenge_token } = optsResp.data;
      const credential = await startRegistration({
        optionsJSON: options as unknown as Parameters<
          typeof startRegistration
        >[0]['optionsJSON'],
      });
      await authApi.webauthnRegisterVerify({
        challenge_token,
        credential,
        nickname,
      });
      setSuccess(`Passkey "${nickname}" added.`);
      setShowAddForm(false);
      setNewNickname('');
      await loadCredentials();
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'NotAllowedError') {
        setError('Registration was cancelled.');
      } else {
        const axiosError = err as {
          response?: { data?: { detail?: string } };
          message?: string;
        };
        setError(
          axiosError.response?.data?.detail ||
            axiosError.message ||
            'Failed to register passkey.'
        );
      }
    } finally {
      setIsRegistering(false);
    }
  };

  const handleDelete = async (id: string, nickname: string) => {
    setError(null);
    setSuccess(null);
    if (!window.confirm(`Remove passkey "${nickname}"?`)) return;
    try {
      await authApi.webauthnDeleteCredential(id);
      setSuccess(`Passkey "${nickname}" removed.`);
      await loadCredentials();
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: string } } };
      setError(
        axiosError.response?.data?.detail || 'Failed to remove passkey.'
      );
    }
  };

  if (!browserSupported) {
    return (
      <div className="space-y-4">
        <div className="flex items-center space-x-3 text-gray-300">
          <FaKey className="text-primary-400 text-2xl" />
          <div>
            <h3 className="text-lg font-semibold">Passkeys</h3>
            <p className="text-sm text-gray-400">
              Your browser does not support passkeys. Try a recent version of
              Chrome, Safari, Edge, or Firefox.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {success && <ConfirmationAlert message={success} />}
      {error && <ErrorAlert message={error} />}

      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start space-x-3 text-gray-300">
          <FaKey className="text-primary-400 text-2xl mt-1" />
          <div>
            <h3 className="text-lg font-semibold">Passkeys</h3>
            <p className="text-sm text-gray-400">
              Sign in without a password or 2FA code — your device or hardware
              key proves it's you. Passkeys bypass 2FA on sign-in.
            </p>
          </div>
        </div>
        {!showAddForm && (
          <ActionButton
            onClick={() => {
              setShowAddForm(true);
              setError(null);
              setSuccess(null);
            }}
          >
            <FaPlus className="mr-2" /> Add passkey
          </ActionButton>
        )}
      </div>

      {showAddForm && (
        <div className="bg-gray-800/50 rounded-lg p-4 space-y-4">
          <Input
            label="Passkey name"
            name="nickname"
            type="text"
            value={newNickname}
            onChange={(e) => setNewNickname(e.target.value)}
            placeholder="e.g. Work laptop, YubiKey 5C"
            disabled={isRegistering}
            leftIcon={<FaKey />}
            helperText="This helps you identify it later when you have multiple."
          />
          <div className="flex space-x-2">
            <ActionButton
              onClick={() => void handleAdd()}
              disabled={isRegistering || !newNickname.trim()}
              className="flex-1"
            >
              {isRegistering ? (
                <>
                  <LoadingSpinner />
                  <span className="ml-2">Waiting for your device…</span>
                </>
              ) : (
                'Create passkey'
              )}
            </ActionButton>
            <SecondaryButton
              onClick={() => {
                setShowAddForm(false);
                setNewNickname('');
              }}
              disabled={isRegistering}
              className="flex-1"
            >
              Cancel
            </SecondaryButton>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="flex items-center space-x-2 text-gray-400">
          <LoadingSpinner />
          <span>Loading passkeys…</span>
        </div>
      ) : credentials.length === 0 ? (
        <p className="text-sm text-gray-400">
          You don't have any passkeys yet.
        </p>
      ) : (
        <ul className="space-y-2">
          {credentials.map((cred) => (
            <li
              key={cred.id}
              className="flex items-center justify-between bg-gray-800/50 rounded-lg p-3"
            >
              <div>
                <div className="font-medium text-gray-200">{cred.nickname}</div>
                <div className="text-xs text-gray-500">
                  Added {formatDate(cred.created_at)} • Last used{' '}
                  {formatDate(cred.last_used_at)}
                </div>
              </div>
              <button
                type="button"
                onClick={() => void handleDelete(cred.id, cred.nickname)}
                className="text-red-400 hover:text-red-300 p-2"
                aria-label={`Remove ${cred.nickname}`}
                title="Remove passkey"
              >
                <FaTrash />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default PasskeySettings;
