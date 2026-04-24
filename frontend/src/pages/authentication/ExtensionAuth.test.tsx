// Phase 8 Plan 10 (D-11 Wave 3) — ExtensionAuth page coverage.
//
// ExtensionAuth.tsx exposes a Chrome-extension sign-in handoff. When the user
// is authenticated AND the page has valid `extensionId` + `state` query
// parameters AND the extension ID is allow-listed AND chrome.runtime is
// available AND a session token is stored, it calls
// `chrome.runtime.sendMessage(...)` with the token. We test three fan-out
// branches:
//   1. Happy path — runtime responds success → <FaCheckCircle/> + success copy.
//   2. Missing extensionId/state → error message ("Missing extensionId or
//      state parameter.").
//   3. No chrome runtime available → error message.
//
// We bypass `testScenarios.authenticated` and construct an authenticated
// `initialAuthState` from the canonical UserRead mockUser — the legacy
// `createMockUser()` helper in test-utils returns a shape missing
// subscription_tier/is_service_account/totp_enabled, which makes
// `{ ...testScenarios.authenticated }` fail to type-check against the
// CustomRenderOptions `user?: UserRead | null` field (same pattern as the
// Wave 2 useAuth.test.ts fix).
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor } from '../../test/utils/test-utils';
import { mockUser } from '../../test/mocks/api';
import { getStoredToken } from '../../api/client';
import ExtensionAuth from './ExtensionAuth';

type ChromeSendMessage = (
  extensionId: string,
  message: unknown,
  callback?: (response: unknown) => void
) => void;

interface FakeRuntime {
  sendMessage: ChromeSendMessage;
  lastError?: { message?: string };
}

const installChromeRuntime = (runtime: FakeRuntime | null): void => {
  // jsdom has no `chrome` global. ExtensionAuth reads it via
  // `(window as any).chrome?.runtime`, so defining the property satisfies the
  // feature-detection in getChromeRuntime().
  Object.defineProperty(window, 'chrome', {
    configurable: true,
    writable: true,
    value: runtime ? { runtime } : undefined,
  });
};

const authenticatedState = {
  isAuthenticated: true,
  user: mockUser,
  isLoading: false,
};

describe('ExtensionAuth page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default to an authenticated user with a stored token. Individual tests
    // override per-case (e.g. null token for the "missing token" branch).
    vi.mocked(getStoredToken).mockReturnValue('stored-token-value');
  });

  afterEach(() => {
    // Clean up the injected chrome global so cross-test state doesn't leak.
    installChromeRuntime(null);
  });

  it('hands off the stored token on success and shows the success state', async () => {
    const sendMessage: ChromeSendMessage = (
      _extensionId,
      _message,
      callback
    ) => {
      // Invoke the callback with a success response — synchronously simulates
      // the background script acknowledging the handoff.
      callback?.({ success: true });
    };
    installChromeRuntime({ sendMessage });

    render(<ExtensionAuth />, {
      initialAuthState: authenticatedState,
      route:
        '/extension-auth?extensionId=knownexttestidknownexttestidknow&state=abc',
    });

    await waitFor(() => {
      expect(screen.getByText(/extension signed in/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/you can close this tab/i)).toBeInTheDocument();
  });

  it('renders the connecting-extension card while the handoff is in flight', () => {
    // Don't install chrome.runtime so the effect short-circuits into an
    // error — the card header should still render.
    render(<ExtensionAuth />, {
      initialAuthState: authenticatedState,
      route: '/extension-auth?extensionId=extid&state=xyz',
    });
    expect(screen.getByText(/connecting extension/i)).toBeInTheDocument();
  });

  it('surfaces an error when chrome.runtime is not available', async () => {
    installChromeRuntime(null);

    render(<ExtensionAuth />, {
      initialAuthState: authenticatedState,
      route: '/extension-auth?extensionId=extid&state=xyz',
    });

    await waitFor(() => {
      expect(
        screen.getByText(/chrome extension apis are not available/i)
      ).toBeInTheDocument();
    });
  });

  it('surfaces an error when extensionId or state is missing from the URL', async () => {
    render(<ExtensionAuth />, {
      initialAuthState: authenticatedState,
      route: '/extension-auth',
    });

    await waitFor(() => {
      expect(
        screen.getByText(/missing extensionid or state parameter/i)
      ).toBeInTheDocument();
    });
  });
});
