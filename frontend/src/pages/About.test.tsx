// Phase 8 plan 08-14 (D-11) — static public page render test for About.
//
// Coverage-backfill shape per PATTERNS.md §11: heading visible + content
// sections present. Rendered under testScenarios.unauthenticated because
// About is a public top-level page and does not require auth.

import { describe, expect, it } from 'vitest';
import { render, screen, testScenarios } from '../test/utils/test-utils';
import About from './About';

describe('About page', () => {
  it('renders the About CarModPicker heading', () => {
    render(<About />, testScenarios.unauthenticated);
    expect(
      screen.getByRole('heading', { name: /about carmodpicker/i })
    ).toBeInTheDocument();
  });

  it('renders key content sections (mission, features, values)', () => {
    render(<About />, testScenarios.unauthenticated);
    // Multiple section headings present
    const headings = screen.getAllByRole('heading');
    expect(headings.length).toBeGreaterThan(1);
    // Mission section heading
    expect(
      screen.getByRole('heading', { name: /our mission/i })
    ).toBeInTheDocument();
    // Values section heading
    expect(
      screen.getByRole('heading', { name: /our values/i })
    ).toBeInTheDocument();
  });
});
