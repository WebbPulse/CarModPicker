/* eslint-disable @typescript-eslint/unbound-method --
 * vi.mocked(apiClient.post/put) is the canonical Phase 8 mocking pattern.
 */

// Phase 8 plan 08-14 (D-11) — Profile page: authenticated render + image
// upload via FormData + upload error path.
//
// Profile uses `apiClient` (default export of services/Api) directly via
// apiClient.put<UserRead> for profile updates, AND transitively via
// ImageUpload → imageApi.uploadImage → apiClient.post(FormData).
//
// NOTE: bypasses test-utils.tsx's customRender because that helper
// registers its own vi.mock('../../services/Api', ...) with ONLY `default`,
// which drops the `imageApi` named export that ImageUpload needs.

import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';

import { apiClient } from '../api/client';
import { mockUser } from '../test/mocks/api';
import { mockUseAuth } from '../test/utils/test-mocks';

// Local services/Api mock that exposes BOTH `default: apiClient` AND `imageApi`
// (for the ImageUpload child component, which calls imageApi.uploadImage).
vi.mock('../services/Api', async () => {
  const clientMod = await import('../api/client');
  const client = clientMod.apiClient;
  return {
    default: client,
    apiClient: client,
    imageApi: {
      uploadImage: async (file: File, entityType: string, entityId?: string) => {
        const formData = new FormData();
        formData.append('file', file);
        const params = new URLSearchParams();
        params.append('entity_type', entityType);
        if (entityId !== undefined) params.append('entity_id', entityId);
        const response = await client.post(
          `/images/upload?${params.toString()}`,
          formData,
          { headers: { 'Content-Type': 'multipart/form-data' } }
        );
        return response.data;
      },
    },
  };
});

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

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

    // PageHeader subtitle contains the username, and Username/Email
    // CardInfoItems also render it. Use getAllByText for robustness.
    await waitFor(() =>
      expect(screen.getAllByText(new RegExp(mockUser.username)).length).toBeGreaterThan(0)
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

    // Click Edit Profile to expose the ImageUpload component.
    await user.click(screen.getByRole('button', { name: /edit profile/i }));

    // ImageUpload exposes a hidden <input type="file"> and a "Choose Image"
    // button that triggers the input. userEvent.upload targets the input
    // directly.
    const fileInput = document.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement | null;
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

    // Verify the FormData actually carries the file under the 'file' key.
    const call = vi.mocked(apiClient.post).mock.calls.find(
      ([url]) => typeof url === 'string' && url.includes('/images/upload')
    );
    expect(call).toBeDefined();
    const fd = call?.[1] as FormData;
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

    const fileInput = document.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement | null;
    if (!fileInput) throw new Error('Could not find hidden file input');

    const file = new File(['hello'], 'avatar.jpg', { type: 'image/jpeg' });
    await user.upload(fileInput, file);

    // ImageUpload surfaces the error via ErrorAlert in its own subtree.
    await waitFor(() =>
      expect(screen.getByText(/upload failed/i)).toBeInTheDocument()
    );
  });
});
