// Phase 8 plan 08-14 (D-11) — static public page render test for PrivacyPolicy.
//
// Minimal heading-visible + content-present shape per PATTERNS.md §11.
// Uses unauthenticated scenario — PrivacyPolicy is a public policy page.

import { describe, expect, it } from 'vitest';
import { render, screen, testScenarios } from '../test/utils/test-utils';
import PrivacyPolicy from './PrivacyPolicy';

describe('PrivacyPolicy page', () => {
  it('renders the Privacy Policy heading and last-updated stamp', () => {
    render(<PrivacyPolicy />, testScenarios.unauthenticated);
    expect(
      screen.getByRole('heading', { name: /privacy policy/i })
    ).toBeInTheDocument();
    // Policy carries a "Last updated:" line near the top. The literal text is
    // split across nodes; match the top-level paragraph via a function matcher
    // (or use getAllByText — there may be multiple mentions in the body).
    const lastUpdated = screen.getAllByText(/last updated/i);
    expect(lastUpdated.length).toBeGreaterThan(0);
  });

  it('renders the Information We Collect section', () => {
    render(<PrivacyPolicy />, testScenarios.unauthenticated);
    // Section 1 heading proves the policy body actually rendered, not just the
    // hero banner.
    expect(
      screen.getByRole('heading', { name: /information we collect/i })
    ).toBeInTheDocument();
  });
});
