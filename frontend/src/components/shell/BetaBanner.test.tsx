/**
 * Covers BetaBanner over `useDismissedUntilSignIn`: a dismissal hides it for the
 * rest of the tab's session and lapses when the session crosses a sign-in.
 */

import '@testing-library/jest-dom';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { DISMISSAL_STORAGE_PREFIX } from '@webbpulse/auth/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { authHarness } from '../../test/utils/authHarness';
import BetaBanner from './BetaBanner';

const STORAGE_KEY = `${DISMISSAL_STORAGE_PREFIX}beta-banner`;
const BANNER_TEXT = /CarModPicker is under active development/;

/** Renders the banner inside the session providers for the given status. */
function renderBanner(status: 'anonymous' | 'authenticated') {
  const harness = authHarness({ status });
  const view = render(<BetaBanner />, { wrapper: harness.Wrapper });
  return { ...harness, ...view };
}

describe('BetaBanner', () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  afterEach(() => {
    sessionStorage.clear();
  });

  it('renders the development notice by default', () => {
    renderBanner('anonymous');
    expect(screen.getByText(BANNER_TEXT)).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Dismiss banner' })
    ).toBeInTheDocument();
  });

  it('hides on dismiss and stores the dismissal under the shared prefix', () => {
    renderBanner('anonymous');
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss banner' }));
    expect(screen.queryByText(BANNER_TEXT)).not.toBeInTheDocument();
    expect(sessionStorage.getItem(STORAGE_KEY)).toBe('out');
    expect(sessionStorage.getItem('beta_banner_dismissed')).toBeNull();
  });

  it('stays dismissed across a remount in the same session', () => {
    const first = renderBanner('authenticated');
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss banner' }));
    first.unmount();

    renderBanner('authenticated');
    expect(screen.queryByText(BANNER_TEXT)).not.toBeInTheDocument();
  });

  it('returns on the next sign-in after an anonymous dismissal', () => {
    const { stub } = renderBanner('anonymous');
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss banner' }));
    expect(screen.queryByText(BANNER_TEXT)).not.toBeInTheDocument();

    act(() => {
      stub.setState({ status: 'authenticated', hasAccessToken: true });
    });
    expect(screen.getByText(BANNER_TEXT)).toBeInTheDocument();
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it('returns after sign-out ends the session it was dismissed in', () => {
    const { stub } = renderBanner('authenticated');
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss banner' }));
    expect(screen.queryByText(BANNER_TEXT)).not.toBeInTheDocument();

    act(() => {
      stub.endSession();
    });
    expect(screen.getByText(BANNER_TEXT)).toBeInTheDocument();
  });
});
