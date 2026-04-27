/* eslint-disable @typescript-eslint/unbound-method --
 * vi.mocked(apiClient.post) is the canonical Phase 8 mocking pattern.
 */

// Phase 8 plan 08-14 (D-11) — BugReport page form render + submit + error.
//
// BugReport imports `bugReportsApi` from `../services/Api`. Global setup.ts
// mock provides only `default: mockApiClient`. We extend with a local vi.mock
// that forwards bugReportsApi.createBugReport through the mocked apiClient.
//
// NOTE: bypasses test-utils.tsx's customRender because that helper
// registers its own vi.mock('../../services/Api', ...) with ONLY `default`,
// which shadows the test-file mock and drops `bugReportsApi`.

import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { apiClient } from '../api/client';
import { mockUseAuth } from '../test/utils/test-mocks';
import { mockUser } from '../test/mocks/api';

vi.mock('../services/Api', async () => {
  const clientMod = await import('../api/client');
  const client = clientMod.apiClient;
  return {
    default: client,
    apiClient: client,
    bugReportsApi: {
      createBugReport: (data: unknown) => client.post('/bug-reports/', data),
    },
  };
});

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

import BugReport from './BugReport';

describe('BugReport page', () => {
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

  it('renders the bug report form with title + description fields + submit button', () => {
    render(
      <MemoryRouter>
        <BugReport />
      </MemoryRouter>
    );

    expect(
      screen.getByRole('heading', { name: /report a bug/i })
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/title/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^description/i)).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /submit bug report/i })
    ).toBeInTheDocument();
  });

  it('submits the form and calls bugReportsApi.createBugReport via apiClient.post', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { id: '11111111-1111-7111-8111-000000000001' },
    });
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <BugReport />
      </MemoryRouter>
    );

    await user.type(screen.getByLabelText(/title/i), 'Test bug');
    await user.type(screen.getByLabelText(/^description/i), 'Description text');
    await user.click(
      screen.getByRole('button', { name: /submit bug report/i })
    );

    await waitFor(() =>
      expect(vi.mocked(apiClient.post)).toHaveBeenCalledWith(
        '/bug-reports/',
        expect.objectContaining({
          title: 'Test bug',
          description: 'Description text',
        })
      )
    );
  });

  it('shows a validation error when title is empty (bypassing HTML5 required attr)', async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <BugReport />
      </MemoryRouter>
    );

    await user.type(screen.getByLabelText(/^description/i), 'Some description');

    // Bypass HTML5 `required` validation so the JS guard in handleSubmit runs.
    const form = document.querySelector('form');
    if (!form) throw new Error('No form element found');
    form.noValidate = true;

    await user.click(
      screen.getByRole('button', { name: /submit bug report/i })
    );

    await waitFor(() =>
      expect(screen.getByText(/title is required/i)).toBeInTheDocument()
    );
    expect(vi.mocked(apiClient.post)).not.toHaveBeenCalled();
  });
});
