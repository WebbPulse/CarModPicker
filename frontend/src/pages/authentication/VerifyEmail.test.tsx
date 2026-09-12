import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  render,
  screen,
  waitFor,
  fireEvent,
} from '../../test/utils/test-utils';
import { mockUser } from '../../test/mocks/api';
import { requestVerificationEmail } from '../../api/identityAuth';
import VerifyEmail from './VerifyEmail';

vi.mock('../../api/identityAuth', () => ({
  requestVerificationEmail: vi.fn(),
}));

describe('VerifyEmail page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows "already verified" state when the user has email_verified=true', () => {
    render(<VerifyEmail />, {
      initialAuthState: {
        isAuthenticated: true,
        user: { ...mockUser, email_verified: true },
        isLoading: false,
      },
    });
    expect(screen.getByText(/email already verified/i)).toBeInTheDocument();
    expect(
      screen.getByText(/your email address has already been verified/i)
    ).toBeInTheDocument();
  });

  it('shows the send-verification form when email is not yet verified', () => {
    render(<VerifyEmail />, {
      initialAuthState: {
        isAuthenticated: true,
        user: { ...mockUser, email_verified: false },
        isLoading: false,
      },
    });
    expect(
      screen.getAllByText(new RegExp(mockUser.email, 'i')).length
    ).toBeGreaterThan(0);
    expect(
      screen.getByRole('button', { name: /send verification email/i })
    ).toBeInTheDocument();
  });

  it('asks the identity service for a mail to the user email on click', async () => {
    vi.mocked(requestVerificationEmail).mockResolvedValueOnce({
      ok: true,
      message: 'Verification email sent.',
    });

    render(<VerifyEmail />, {
      initialAuthState: {
        isAuthenticated: true,
        user: { ...mockUser, email_verified: false },
        isLoading: false,
      },
    });

    fireEvent.click(
      screen.getByRole('button', { name: /send verification email/i })
    );

    await waitFor(() => {
      expect(requestVerificationEmail).toHaveBeenCalledWith(mockUser.email);
    });

    await waitFor(() => {
      expect(screen.getByText(/verification email sent/i)).toBeInTheDocument();
    });
  });
});
