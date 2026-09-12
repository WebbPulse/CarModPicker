/**
 * Tests for useIsPremium.
 */

import { createElement, type ReactNode } from 'react';
import { renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useIsPremium, useIsPremiumSystemDisabled } from './useIsPremium';
import {
  AppSettingsContext,
  type AppSettingsContextType,
} from '../contexts/AppSettingsContextDefinition';
import type { AppSettings } from '../api/app_settings';
import type { UserRead } from '../types/Api';
import { mockUser } from '../test/mocks/api';
import { authHarness } from '../test/utils/authHarness';
import { testScenarios } from '../test/utils/test-utils';

function settingsValue(settings: AppSettings | null): AppSettingsContextType {
  return {
    settings,
    isLoading: false,
    refresh: vi.fn().mockResolvedValue(undefined),
    setSettings: vi.fn(),
  };
}

/**
 * Mounts the hook over the real session providers plus a settings context, so
 * the session comes from the `@webbpulse/auth` store the application reads.
 */
const wrap = (
  scenario: (typeof testScenarios)[keyof typeof testScenarios],
  settings: AppSettingsContextType,
  userOverride?: UserRead | null
) => {
  const { initialAuthState } = scenario;
  const { Wrapper: AuthWrapper } = authHarness({
    status: initialAuthState.isAuthenticated ? 'authenticated' : 'anonymous',
    user: userOverride ?? null,
  });
  const Wrapper = ({ children }: { children: ReactNode }) =>
    createElement(
      AuthWrapper,
      null,
      createElement(AppSettingsContext.Provider, { value: settings }, children)
    );
  return Wrapper;
};

const makePremiumUser = (overrides: Partial<UserRead> = {}): UserRead => ({
  ...mockUser,
  subscription_tier: 'premium',
  subscription_status: 'active',
  subscription_expires_at: null,
  ...overrides,
});

describe('useIsPremium', () => {
  it('returns false for an unauthenticated user', () => {
    const { result } = renderHook(() => useIsPremium(), {
      wrapper: wrap(testScenarios.unauthenticated, settingsValue(null)),
    });

    expect(result.current).toBe(false);
  });

  it("returns false for a user with subscription_tier='free'", () => {
    const freeUser: UserRead = {
      ...mockUser,
      subscription_tier: 'free',
      subscription_status: 'active',
    };
    const { result } = renderHook(() => useIsPremium(), {
      wrapper: wrap(testScenarios.authenticated, settingsValue(null), freeUser),
    });

    expect(result.current).toBe(false);
  });

  it('returns true for an active premium user', () => {
    const premiumUser = makePremiumUser();
    const { result } = renderHook(() => useIsPremium(), {
      wrapper: wrap(
        testScenarios.authenticated,
        settingsValue(null),
        premiumUser
      ),
    });

    expect(result.current).toBe(true);
  });

  it('returns false for a premium user whose subscription has expired', () => {
    const expiredUser = makePremiumUser({
      subscription_expires_at: '2000-01-01T00:00:00Z',
    });
    const { result } = renderHook(() => useIsPremium(), {
      wrapper: wrap(
        testScenarios.authenticated,
        settingsValue(null),
        expiredUser
      ),
    });

    expect(result.current).toBe(false);
  });

  it('returns true for any user when admin kill-switch disables premium system', () => {
    const freeUser: UserRead = {
      ...mockUser,
      subscription_tier: 'free',
      subscription_status: 'active',
    };
    const killSwitch: AppSettings = {
      premium_disabled: true,
      updated_at: '2026-04-24T00:00:00Z',
    };
    const { result } = renderHook(() => useIsPremium(), {
      wrapper: wrap(
        testScenarios.authenticated,
        settingsValue(killSwitch),
        freeUser
      ),
    });

    expect(result.current).toBe(true);
  });
});

describe('useIsPremiumSystemDisabled', () => {
  it('returns true when settings.premium_disabled is true', () => {
    const killSwitch: AppSettings = {
      premium_disabled: true,
      updated_at: '2026-04-24T00:00:00Z',
    };
    const { result } = renderHook(() => useIsPremiumSystemDisabled(), {
      wrapper: wrap(testScenarios.unauthenticated, settingsValue(killSwitch)),
    });

    expect(result.current).toBe(true);
  });

  it('returns false when settings are null or premium_disabled=false', () => {
    const { result: nullResult } = renderHook(
      () => useIsPremiumSystemDisabled(),
      {
        wrapper: wrap(testScenarios.unauthenticated, settingsValue(null)),
      }
    );
    expect(nullResult.current).toBe(false);

    const enabled: AppSettings = {
      premium_disabled: false,
      updated_at: '2026-04-24T00:00:00Z',
    };
    const { result: enabledResult } = renderHook(
      () => useIsPremiumSystemDisabled(),
      {
        wrapper: wrap(testScenarios.unauthenticated, settingsValue(enabled)),
      }
    );
    expect(enabledResult.current).toBe(false);
  });
});
