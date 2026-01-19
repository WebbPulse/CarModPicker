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
import Input from '../components/common/Input';
import LoadingSpinner from '../components/common/LoadingSpinner';
import Divider from '../components/layout/Divider';
import PageHeader from '../components/layout/PageHeader';
import SectionHeader from '../components/layout/SectionHeader';
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
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    currentPassword: '',
    newPassword: '',
    confirmNewPassword: '',
  });
  const [imageFileKey, setImageFileKey] = useState<string | null>(null);
  const [imageChanged, setImageChanged] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{
    type: 'success' | 'error' | 'info';
    message: string;
  } | null>(null);

  useEffect(() => {
    if (user) {
      setFormData({
        username: user.username,
        email: user.email,
        currentPassword: '',
        newPassword: '',
        confirmNewPassword: '',
      });
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

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    setUpdateApiError(null);
    setStatusMessage(null);
  };

  const handleEditToggle = () => {
    setIsEditing(!isEditing);
    setUpdateApiError(null);
    setStatusMessage(null);
    if (user) {
      setFormData({
        username: user.username,
        email: user.email,
        currentPassword: '',
        newPassword: '',
        confirmNewPassword: '',
      });
      setImageFileKey(null);
      setImageChanged(false);
    }
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!user) return;
    setUpdateApiError(null);
    setStatusMessage(null);

    if (!formData.currentPassword.trim()) {
      setUpdateApiError('Current password is required to save changes.');
      return;
    }

    const payload: UserUpdate = {
      current_password: formData.currentPassword,
    };
    let hasChanges = false;

    // Username
    if (formData.username && formData.username.trim() !== user.username) {
      if (!formData.username.trim()) {
        setUpdateApiError('Username cannot be empty.');
        return;
      }
      payload.username = formData.username.trim();
      hasChanges = true;
    } else if (formData.username === '' && user.username !== '') {
      // If user explicitly clears username, and it was not empty before
      setUpdateApiError('Username cannot be empty.');
      return;
    }

    // Email
    if (formData.email && formData.email.trim() !== user.email) {
      if (!formData.email.trim()) {
        setUpdateApiError('Email cannot be empty.');
        return;
      }
      if (!/\S+@\S+\.\S+/.test(formData.email.trim())) {
        setUpdateApiError('Please enter a valid email address.');
        return;
      }
      payload.email = formData.email.trim();
      hasChanges = true;
    } else if (formData.email === '' && user.email !== '') {
      setUpdateApiError('Email cannot be empty.');
      return;
    }

    // Image URL - only include if changed
    if (imageChanged) {
      payload.image_url = imageFileKey || null; // Set to null if removed
      hasChanges = true;
    }

    // New Password
    if (formData.newPassword) {
      if (!formData.newPassword.trim()) {
        setUpdateApiError('New password cannot be empty.');
        return;
      }
      if (formData.newPassword !== formData.confirmNewPassword) {
        setUpdateApiError("New passwords don't match.");
        return;
      }
      payload.password = formData.newPassword; // API expects 'password' for the new password
      hasChanges = true;
    } else if (formData.confirmNewPassword) {
      // If confirmNewPassword is set but newPassword is not
      setUpdateApiError(
        'New password is required if confirm new password is provided.'
      );
      return;
    }

    if (!hasChanges) {
      setStatusMessage({
        type: 'info',
        message:
          'No changes were detected in your profile information. ' +
          'To save, please modify the fields you wish to change and provide your current password.',
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
                    className="h-48 w-48 object-cover"
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
            </div>
            <ActionButton onClick={handleEditToggle} className="mr-2">
              Edit Profile
            </ActionButton>
          </>
        ) : (
          <form
            onSubmit={(e) => void handleSubmit(e)}
            className="space-y-6 mb-6"
          >
            <Input
              label="Username"
              id="username"
              name="username"
              type="text"
              value={formData.username}
              onChange={handleInputChange}
              disabled={isUpdating}
              required
              autoComplete="username"
            />
            <Input
              label="Email"
              id="email"
              name="email"
              type="email"
              value={formData.email}
              onChange={handleInputChange}
              disabled={isUpdating}
              required
              autoComplete="email"
            />
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
            <Input
              label="New Password (leave blank to keep current)"
              id="newPassword"
              name="newPassword"
              type="password"
              value={formData.newPassword}
              onChange={handleInputChange}
              disabled={isUpdating}
              autoComplete="new-password"
            />
            <Input
              label="Confirm New Password"
              id="confirmNewPassword"
              name="confirmNewPassword"
              type="password"
              value={formData.confirmNewPassword}
              onChange={handleInputChange}
              disabled={isUpdating}
              autoComplete="new-password"
            />
            <Divider />
            <Input
              label="Current Password (required to save any changes)"
              id="currentPassword"
              name="currentPassword"
              type="password"
              value={formData.currentPassword}
              onChange={handleInputChange}
              disabled={isUpdating}
              required
              autoComplete="current-password"
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
    </div>
  );
}

export default Profile;
