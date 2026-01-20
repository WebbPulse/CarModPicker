import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import AuthCard from '../components/auth/AuthCard';
import AuthRedirectLink from '../components/auth/AuthRedirectLink';
import ActionButton from '../components/buttons/ActionButton';
import SecondaryButton from '../components/buttons/SecondaryButton';
import ButtonStretch from '../components/buttons/StretchButton';
import { ConfirmationAlert, ErrorAlert } from '../components/common/Alerts';
import Card from '../components/common/Card';
import CardInfoItem from '../components/common/CardInfoItem';
import ImageUpload from '../components/common/ImageUpload';
import LoadingSpinner from '../components/common/LoadingSpinner';
import Divider from '../components/layout/Divider';
import PageHeader from '../components/layout/PageHeader';
import SectionHeader from '../components/layout/SectionHeader';
import SecuritySettingsDialog from '../components/profile/SecuritySettingsDialog';
import useApiRequest from '../hooks/UseApiRequest';
import { useAuth } from '../hooks/useAuth';
import apiClient from '../services/Api';
import type { UserRead, UserUpdate } from '../types/Api';

function Profile() {
  const {
    user,
    isLoading: authIsLoading,
    checkAuthStatus,
    login: authLogin,
  } = useAuth();

  const [isEditing, setIsEditing] = useState(false);
  const [isSecurityDialogOpen, setIsSecurityDialogOpen] = useState(false);
  const [imageFileKey, setImageFileKey] = useState<string | null>(null);
  const [imageChanged, setImageChanged] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{
    type: 'success' | 'error' | 'info';
    message: string;
  } | null>(null);

  useEffect(() => {
    if (user) {
      // Note: user.image_url is now a presigned URL from the API
      setImageFileKey(null);
      setImageChanged(false);
    }
  }, [user]);

  const updateUserRequestFn = (payload: { userId: number; data: UserUpdate }) =>
    apiClient.put<UserRead>(`/users/${payload.userId}`, payload.data);

  const {
    error: updateApiError,
    isLoading: isUpdating,
    executeRequest: executeUpdateUser,
    setError: setUpdateApiError,
  } = useApiRequest(updateUserRequestFn);

  const handleEditToggle = () => {
    setIsEditing(!isEditing);
    setUpdateApiError(null);
    setStatusMessage(null);
    if (user) {
      setImageFileKey(null);
      setImageChanged(false);
    }
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!user) return;
    setUpdateApiError(null);
    setStatusMessage(null);

    const payload: UserUpdate = {};
    let hasChanges = false;

    // Image URL - only include if changed
    if (imageChanged) {
      payload.image_url = imageFileKey || null; // Set to null if removed
      hasChanges = true;
    }

    if (!hasChanges) {
      setStatusMessage({
        type: 'info',
        message:
          'No changes were detected in your profile information. ' +
          'To save, please modify the fields you wish to change.',
      });
      return;
    }

    const result = await executeUpdateUser({ userId: user.id, data: payload });

    if (result) {
      authLogin(result); // Use the returned user data to update auth context
      setIsEditing(false);
      setStatusMessage({
        type: 'success',
        message: 'Profile updated successfully!',
      });
    }
  };

  if (authIsLoading) {
    return <LoadingSpinner />;
  }

  if (!user) {
    return (
      <AuthCard title="Profile">
        <ErrorAlert message="User not found. Please log in." />
        <AuthRedirectLink text="Go to" linkText="Login" to="/login" />
      </AuthCard>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title="Profile"
        subtitle={`Manage your account details, ${user.username}.`}
      />
      <Card>
        <SectionHeader title="Account Information" />

        {statusMessage && (
          <div className="mb-4">
            {statusMessage.type === 'success' && (
              <ConfirmationAlert message={statusMessage.message} />
            )}
            {statusMessage.type === 'error' && (
              <ErrorAlert message={statusMessage.message} />
            )}
            {statusMessage.type === 'info' && (
              <ConfirmationAlert message={statusMessage.message} />
            )}
          </div>
        )}
        {updateApiError && (
          <div className="mb-4">
            <ErrorAlert message={updateApiError} />
          </div>
        )}

        {!isEditing ? (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-gray-300 mb-6">
              <CardInfoItem label="Profile Picture">
                {user.image_url ? (
                  <img
                    src={user.image_url}
                    alt={`${user.username}'s profile`}
                    className="h-48 w-48 rounded-lg object-cover"
                  />
                ) : (
                  <p className="text-gray-400">No image set.</p>
                )}
              </CardInfoItem>

              <div className="hidden md:block"></div>
              <CardInfoItem label="Username:">
                <p>{user.username}</p>
              </CardInfoItem>
              <CardInfoItem label="Email:">
                <p>{user.email}</p>
              </CardInfoItem>
              <CardInfoItem label="Email Verified">
                {user.email_verified ? (
                  <ConfirmationAlert message="Yes" />
                ) : (
                  <div className="flex items-center">
                    <ErrorAlert message="No" />
                    <Link
                      to="/verify-email"
                      className="ml-2 text-sm text-indigo-400 hover:text-indigo-300"
                    >
                      Verify Email
                    </Link>
                  </div>
                )}
              </CardInfoItem>
              <CardInfoItem label="Account Status">
                <p>{user.disabled ? 'Disabled' : 'Active'}</p>
              </CardInfoItem>
              <CardInfoItem label="Two-Factor Authentication">
                {user.totp_enabled ? (
                  <ConfirmationAlert message="Enabled" />
                ) : (
                  <ErrorAlert message="Disabled" />
                )}
              </CardInfoItem>
            </div>
            <div className="flex space-x-2">
              <ActionButton onClick={handleEditToggle} className="mr-2">
                Edit Profile
              </ActionButton>
              <ActionButton
                onClick={() => setIsSecurityDialogOpen(true)}
                className="bg-indigo-600 hover:bg-indigo-700"
              >
                Manage Security Settings
              </ActionButton>
            </div>
          </>
        ) : (
          <form
            onSubmit={(e) => void handleSubmit(e)}
            className="space-y-6 mb-6"
          >
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-gray-300 mb-6">
              <CardInfoItem label="Username:">
                <p className="text-gray-400">{user.username}</p>
                <p className="text-xs text-gray-500 mt-1">Username cannot be changed</p>
              </CardInfoItem>
              <CardInfoItem label="Email:">
                <p className="text-gray-400">{user.email}</p>
                <p className="text-xs text-gray-500 mt-1">Email cannot be changed</p>
              </CardInfoItem>
            </div>
            <ImageUpload
              currentImageUrl={user.image_url ?? null}
              entityType="user"
              entityId={user.id}
              onImageUploaded={(fileKey) => {
                setImageFileKey(fileKey);
                setImageChanged(true);
              }}
              onImageRemoved={() => {
                setImageFileKey(null);
                setImageChanged(true);
              }}
              label="Profile Image (Optional)"
              maxSizeMB={10}
            />
            <div className="flex space-x-2 pt-2">
              <ButtonStretch type="submit" disabled={isUpdating}>
                {isUpdating ? 'Saving...' : 'Save Changes'}
              </ButtonStretch>
              <SecondaryButton
                type="button"
                onClick={handleEditToggle}
                disabled={isUpdating}
                className="w-full"
              >
                Cancel
              </SecondaryButton>
            </div>
          </form>
        )}

        <Divider />
        <ActionButton
          onClick={() =>
            void (async () => {
              setStatusMessage(null);
              setUpdateApiError(null);
              await checkAuthStatus();
              setStatusMessage({
                type: 'success',
                message: 'Profile data refreshed.',
              });
            })()
          }
          disabled={authIsLoading || isUpdating}
        >
          {authIsLoading || isUpdating
            ? 'Refreshing...'
            : 'Refresh Profile Data'}
        </ActionButton>

        <div className="mt-4 space-y-2">
          <ActionButton
            onClick={() => (window.location.href = '/subscription')}
            className="bg-yellow-600 hover:bg-yellow-700 w-full"
          >
            Manage Subscription
          </ActionButton>
          <ActionButton
            onClick={() => (window.location.href = '/my-global-parts')}
            className="bg-blue-600 hover:bg-blue-700 w-full"
          >
            Manage My Parts
          </ActionButton>
        </div>
      </Card>

      {user && (
        <SecuritySettingsDialog
          isOpen={isSecurityDialogOpen}
          onClose={() => setIsSecurityDialogOpen(false)}
          onPasswordChanged={() => {
            setStatusMessage({
              type: 'success',
              message: 'Password changed successfully!',
            });
            void checkAuthStatus();
          }}
          on2FAEnabled={() => {
            setStatusMessage({
              type: 'success',
              message: '2FA enabled successfully!',
            });
            void checkAuthStatus();
          }}
          on2FADisabled={() => {
            setStatusMessage({
              type: 'success',
              message: '2FA disabled successfully!',
            });
            void checkAuthStatus();
          }}
        />
      )}
    </div>
  );
}

export default Profile;
