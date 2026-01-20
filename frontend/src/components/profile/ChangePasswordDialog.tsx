import React, { useState } from 'react';
import SecondaryButton from '../buttons/SecondaryButton';
import ButtonStretch from '../buttons/StretchButton';
import { ErrorAlert } from '../common/Alerts';
import Dialog from '../common/Dialog';
import Input from '../common/Input';
import LoadingSpinner from '../common/LoadingSpinner';

interface ChangePasswordDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onPasswordChanged: () => void;
  userId: number;
}

const ChangePasswordDialog: React.FC<ChangePasswordDialogProps> = ({
  isOpen,
  onClose,
  onPasswordChanged,
  userId,
}) => {
  const [formData, setFormData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmNewPassword: '',
  });
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    setError(null);
  };

  const handleClose = () => {
    setFormData({
      currentPassword: '',
      newPassword: '',
      confirmNewPassword: '',
    });
    setError(null);
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);

    // Validation
    if (!formData.currentPassword.trim()) {
      setError('Current password is required.');
      return;
    }

    if (!formData.newPassword.trim()) {
      setError('New password is required.');
      return;
    }

    if (formData.newPassword !== formData.confirmNewPassword) {
      setError("New passwords don't match.");
      return;
    }

    if (formData.newPassword.length < 8) {
      setError('New password must be at least 8 characters long.');
      return;
    }

    setIsSubmitting(true);

    try {
      const { usersApi } = await import('../../services/Api');
      const response = await usersApi.updateUser(userId, {
        current_password: formData.currentPassword,
        password: formData.newPassword,
      });

      if (response.data) {
        handleClose();
        onPasswordChanged();
      }
    } catch (err: unknown) {
      let errorMessage = 'Failed to change password';
      if (err instanceof Error) {
        errorMessage = err.message;
      } else if (typeof err === 'object' && err !== null && 'response' in err) {
        const response = (err as { response?: { data?: { detail?: string } } }).response;
        if (response?.data?.detail) {
          errorMessage = response.data.detail;
        }
      }
      setError(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog isOpen={isOpen} onClose={handleClose} title="Change Password" maxWidth="md">
      <form onSubmit={handleSubmit} className="space-y-6">
        {error && <ErrorAlert message={error} />}

        <Input
          label="Current Password"
          id="currentPassword"
          name="currentPassword"
          type="password"
          value={formData.currentPassword}
          onChange={handleInputChange}
          disabled={isSubmitting}
          required
          autoComplete="current-password"
        />

        <Input
          label="New Password"
          id="newPassword"
          name="newPassword"
          type="password"
          value={formData.newPassword}
          onChange={handleInputChange}
          disabled={isSubmitting}
          required
          autoComplete="new-password"
          minLength={8}
        />

        <Input
          label="Confirm New Password"
          id="confirmNewPassword"
          name="confirmNewPassword"
          type="password"
          value={formData.confirmNewPassword}
          onChange={handleInputChange}
          disabled={isSubmitting}
          required
          autoComplete="new-password"
        />

        <div className="flex space-x-3 pt-4">
          <ButtonStretch type="submit" disabled={isSubmitting}>
            {isSubmitting ? (
              <>
                <LoadingSpinner />
                <span className="ml-2">Changing Password...</span>
              </>
            ) : (
              'Change Password'
            )}
          </ButtonStretch>
          <SecondaryButton
            type="button"
            onClick={handleClose}
            disabled={isSubmitting}
            className="w-full"
          >
            Cancel
          </SecondaryButton>
        </div>
      </form>
    </Dialog>
  );
};

export default ChangePasswordDialog;
