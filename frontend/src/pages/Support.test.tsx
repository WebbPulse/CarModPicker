// Phase 8 plan 08-14 (D-11) — static public page render test for Support.
//
// Support reads useIsPremiumSystemDisabled (which consumes AppSettingsContext).
// The customRender wrapper only provides Router + mocked useAuth; it does NOT
// install an AppSettingsProvider. So we mock the hook directly, which also
// lets us exercise the two kill-switch branches.

import { describe, expect, it, vi } from 'vitest';
import { render, screen, testScenarios } from '../test/utils/test-utils';
import Support from './Support';

vi.mock('../hooks/useIsPremium', () => ({
  useIsPremium: () => false,
  useIsPremiumSystemDisabled: () => false,
}));

describe('Support page', () => {
  it('renders the Support CarModPicker heading', () => {
    render(<Support />, testScenarios.unauthenticated);
    expect(
      screen.getByRole('heading', { name: /support carmodpicker/i })
    ).toBeInTheDocument();
  });

  it('renders support option cards including Buy Me a Coffee link', () => {
    render(<Support />, testScenarios.unauthenticated);
    // Buy Me a Coffee is always present regardless of kill-switch state.
    expect(
      screen.getByRole('heading', { name: /buy me a coffee/i })
    ).toBeInTheDocument();
    // When the kill switch is OFF (default mock), the premium subscribe card is present.
    expect(
      screen.getByRole('heading', { name: /subscribe to premium/i })
    ).toBeInTheDocument();
  });
});
