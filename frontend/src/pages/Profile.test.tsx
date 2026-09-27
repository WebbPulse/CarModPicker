/* eslint-disable @typescript-eslint/no-unsafe-assignment */

import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';

import { apiClient } from '../api/client';
import { mockUser } from '../test/mocks/api';
import { billingError, mockPremiumUser } from '../test/mocks/billing';
import { mockUseAuth } from '../test/utils/test-mocks';

const billingMocks = vi.hoisted(() => ({
  createCheckoutSession: vi.fn(),
  createPortalSession: vi.fn(),
  redirectToBilling: vi.fn(),
}));

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock('../api/billing', () => billingMocks);

import Profile from './Profile';

describe('Profile page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: mockUser,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      checkAuthStatus: vi.fn(),
    });
  });

  it('renders authenticated user profile with username + email visible', async () => {
    render(
      <BrowserRouter>
        <Profile />
      </BrowserRouter>
    );

    await waitFor(() =>
      expect(
        screen.getAllByText(new RegExp(mockUser.username)).length
      ).toBeGreaterThan(0)
    );
    expect(
      screen.getAllByText(new RegExp(mockUser.email)).length
    ).toBeGreaterThan(0);
  });

  it('uploads profile image via apiClient.post with FormData when user picks a file in edit mode', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        file_key: 'users/test/avatar.jpg',
        presigned_url: 'https://example.com/avatar-signed.jpg',
        message: 'ok',
      },
    });
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <Profile />
      </BrowserRouter>
    );

    await user.click(screen.getByRole('button', { name: /edit profile/i }));

    const fileInput =
      document.querySelector<HTMLInputElement>('input[type="file"]');
    if (!fileInput) throw new Error('Could not find hidden file input');

    const file = new File(['hello'], 'avatar.jpg', { type: 'image/jpeg' });
    await user.upload(fileInput, file);

    await waitFor(() =>
      expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
        expect.stringContaining('/images/upload'),
        expect.any(FormData),
        expect.objectContaining({
          headers: expect.objectContaining({
            'Content-Type': 'multipart/form-data',
          }),
        })
      )
    );

    const call = vi
      .mocked(apiClient.post)
      .mock.calls.find(
        ([url]) => typeof url === 'string' && url.includes('/images/upload')
      );
    expect(call).toBeDefined();
    const fd: FormData = call?.[1] as FormData;
    expect(fd.get('file')).toBe(file);
  });

  it('shows an error when the image upload request fails', async () => {
    vi.mocked(apiClient.post).mockRejectedValueOnce(
      new Error('Upload failed: server error')
    );
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <Profile />
      </BrowserRouter>
    );

    await user.click(screen.getByRole('button', { name: /edit profile/i }));

    const fileInput =
      document.querySelector<HTMLInputElement>('input[type="file"]');
    if (!fileInput) throw new Error('Could not find hidden file input');

    const file = new File(['hello'], 'avatar.jpg', { type: 'image/jpeg' });
    await user.upload(fileInput, file);

    await waitFor(() =>
      expect(screen.getByText(/upload failed/i)).toBeInTheDocument()
    );
  });

  it('hides the subscription section for a free user', () => {
    render(
      <BrowserRouter>
        <Profile />
      </BrowserRouter>
    );

    expect(
      screen.queryByRole('button', { name: /manage subscription/i })
    ).not.toBeInTheDocument();
  });

  it('opens the billing portal from the subscription section for a premium user', async () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: mockPremiumUser,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      checkAuthStatus: vi.fn(),
    });
    let resolve: (url: string) => void = () => undefined;
    billingMocks.createPortalSession.mockReturnValueOnce(
      new Promise<string>((r) => {
        resolve = r;
      })
    );
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <Profile />
      </BrowserRouter>
    );

    expect(screen.getByText('Premium')).toBeInTheDocument();
    const button = screen.getByRole('button', {
      name: /manage subscription/i,
    });
    await user.click(button);
    expect(button).toBeDisabled();

    resolve('https://billing.stripe.com/p/session/test_1');

    await waitFor(() =>
      expect(billingMocks.redirectToBilling).toHaveBeenCalledWith(
        'https://billing.stripe.com/p/session/test_1'
      )
    );
  });

  it('shows an inline error when the billing portal is unavailable', async () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: mockPremiumUser,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      checkAuthStatus: vi.fn(),
    });
    billingMocks.createPortalSession.mockRejectedValueOnce(
      billingError(503, 'STRIPE_NOT_CONFIGURED')
    );
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <Profile />
      </BrowserRouter>
    );

    await user.click(
      screen.getByRole('button', { name: /manage subscription/i })
    );

    expect(
      await screen.findByText(/billing is not available right now/i)
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /manage subscription/i })
    ).toBeEnabled();
  });
});
