// Phase 8 plan 08-14 (D-11) — static public page render test for TermsOfService.
//
// Minimal heading-visible + content-present shape per PATTERNS.md §11.

import { describe, expect, it } from 'vitest';
import { render, screen, testScenarios } from '../test/utils/test-utils';
import TermsOfService from './TermsOfService';

describe('TermsOfService page', () => {
  it('renders the Terms of Service heading and last-updated stamp', () => {
    render(<TermsOfService />, testScenarios.unauthenticated);
    expect(
      screen.getByRole('heading', { name: /terms of service/i })
    ).toBeInTheDocument();
    // "Last updated:" text appears in multiple nodes (header stamp + body
    // references) — use getAllByText and assert at least one match.
    const lastUpdated = screen.getAllByText(/last updated/i);
    expect(lastUpdated.length).toBeGreaterThan(0);
  });

  it('renders the Service section describing the agreement', () => {
    render(<TermsOfService />, testScenarios.unauthenticated);
    // Section 1 heading proves the terms body rendered.
    expect(
      screen.getByRole('heading', { name: /the service/i })
    ).toBeInTheDocument();
  });
});
