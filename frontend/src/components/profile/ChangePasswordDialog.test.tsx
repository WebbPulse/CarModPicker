import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '../../test/utils/test-utils';
import { changePassword } from '../../api/identityAuth';
import { mockUser } from '../../test/mocks/api';
import ChangePasswordDialog from './ChangePasswordDialog';

vi.mock('../../api/identityAuth', () => ({
  changePassword: vi.fn(),
}));

const changePasswordMock = vi.mocked(changePassword);

function renderDialog({ isOpen = true }: { isOpen?: boolean } = {}) {
  const onClose = vi.fn();
  const onPasswordChanged = vi.fn();
  const utils = render(
    <ChangePasswordDialog
      isOpen={isOpen}
      onClose={onClose}
      onPasswordChanged={onPasswordChanged}
    />,
    {
      initialAuthState: {
        isAuthenticated: true,
        user: mockUser,
        isLoading: false,
      },
    }
  );
  return { onClose, onPasswordChanged, ...utils };
}

function fill(label: RegExp, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

function submitForm() {
  const form = screen.getByLabelText(/^current password$/i).closest('form');
  if (!form) throw new Error('form not found');
  fireEvent.submit(form);
}

function fillValidPasswords() {
  fill(/^current password$/i, 'oldpassword1');
  fill(/^new password$/i, 'newpassword1');
  fill(/^confirm new password$/i, 'newpassword1');
}

describe('ChangePasswordDialog', () => {
  it('renders no dialog content while isOpen is false', () => {
    renderDialog({ isOpen: false });

    expect(screen.queryByText('Change Password')).not.toBeInTheDocument();
  });

  it('rejects submission with an empty current password', async () => {
    renderDialog();
    fill(/^new password$/i, 'newpassword1');
    fill(/^confirm new password$/i, 'newpassword1');

    submitForm();

    expect(
      await screen.findByText('Current password is required.')
    ).toBeInTheDocument();
    expect(changePasswordMock).not.toHaveBeenCalled();
  });

  it('rejects submission with an empty new password', async () => {
    renderDialog();
    fill(/^current password$/i, 'oldpassword1');

    submitForm();

    expect(
      await screen.findByText('New password is required.')
    ).toBeInTheDocument();
    expect(changePasswordMock).not.toHaveBeenCalled();
  });

  it('rejects a confirmation that does not match the new password', async () => {
    renderDialog();
    fill(/^current password$/i, 'oldpassword1');
    fill(/^new password$/i, 'newpassword1');
    fill(/^confirm new password$/i, 'newpassword2');

    submitForm();

    expect(
      await screen.findByText("New passwords don't match.")
    ).toBeInTheDocument();
    expect(changePasswordMock).not.toHaveBeenCalled();
  });

  it('rejects a new password shorter than eight characters', async () => {
    renderDialog();
    fill(/^current password$/i, 'oldpassword1');
    fill(/^new password$/i, 'short7x');
    fill(/^confirm new password$/i, 'short7x');

    submitForm();

    expect(
      await screen.findByText(
        'New password must be at least 8 characters long.'
      )
    ).toBeInTheDocument();
    expect(changePasswordMock).not.toHaveBeenCalled();
  });

  it('clears a previous error as soon as a field is edited', async () => {
    renderDialog();
    submitForm();
    expect(
      await screen.findByText('Current password is required.')
    ).toBeInTheDocument();

    fill(/^current password$/i, 'oldpassword1');

    expect(
      screen.queryByText('Current password is required.')
    ).not.toBeInTheDocument();
  });

  it('offers no 2FA field since identity does not step up a password change', () => {
    renderDialog();

    expect(screen.queryByLabelText(/2fa code/i)).not.toBeInTheDocument();
  });

  it('sends the current and new password to identity on success', async () => {
    const { onPasswordChanged } = renderDialog();
    changePasswordMock.mockResolvedValueOnce({ status: 'changed' });
    fillValidPasswords();

    submitForm();

    await vi.waitFor(() => {
      expect(changePasswordMock).toHaveBeenCalledTimes(1);
    });
    expect(changePasswordMock).toHaveBeenCalledWith(
      'oldpassword1',
      'newpassword1'
    );
    await vi.waitFor(() => {
      expect(onPasswordChanged).toHaveBeenCalledTimes(1);
    });
  });

  it('surfaces the identity error and leaves the dialog open', async () => {
    const { onPasswordChanged } = renderDialog();
    changePasswordMock.mockResolvedValueOnce({
      status: 'failed',
      error: 'Incorrect current password',
    });
    fillValidPasswords();

    submitForm();

    expect(
      await screen.findByText('Incorrect current password')
    ).toBeInTheDocument();
    expect(onPasswordChanged).not.toHaveBeenCalled();
    expect(screen.getByLabelText(/^current password$/i)).toHaveValue(
      'oldpassword1'
    );
  });

  it('clears the form and calls onClose when Cancel is pressed', () => {
    const { onClose } = renderDialog();
    fillValidPasswords();

    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText(/^current password$/i)).toHaveValue('');
    expect(screen.getByLabelText(/^new password$/i)).toHaveValue('');
  });
});
