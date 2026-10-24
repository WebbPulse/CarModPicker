import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '../../test/utils/test-utils';

const confirmEmailChange = vi.fn();
let clientIsNull = false;

vi.mock('../../api/identityClient', () => ({
  getIdentityClient: () => (clientIsNull ? null : { confirmEmailChange }),
  identityOriginFrom: (v: string) => v,
  resetIdentityClientForTests: () => undefined,
}));

import VerifyEmailChange from './VerifyEmailChange';

/** Put a token in the URL the way a mailed email change link would. */
const arriveWithToken = (token: string | null) => {
  window.history.replaceState(
    {},
    '',
    token === null
      ? '/verify-email-change'
      : `/verify-email-change?token=${token}`
  );
};

beforeEach(() => {
  vi.clearAllMocks();
  clientIsNull = false;
  arriveWithToken('tok-1');
});

describe('VerifyEmailChange', () => {
  it('confirms the token and reports the new address is in use', async () => {
    confirmEmailChange.mockResolvedValue({ ok: true });
    render(<VerifyEmailChange />);
    expect(
      await screen.findByText(/new email address is confirmed/i)
    ).toBeInTheDocument();
    expect(confirmEmailChange).toHaveBeenCalledWith({ token: 'tok-1' });
  });

  it('spends the token exactly once across a rerender', async () => {
    confirmEmailChange.mockResolvedValue({ ok: true });
    const { rerender } = render(<VerifyEmailChange />);
    rerender(<VerifyEmailChange />);
    await screen.findByText(/new email address is confirmed/i);
    expect(confirmEmailChange).toHaveBeenCalledTimes(1);
  });

  it('renders the refusal sentence the server sent', async () => {
    confirmEmailChange.mockResolvedValue({
      ok: false,
      reason: 'invalid-link',
      code: 'INVALID_LINK',
      message: 'This link is no longer valid.',
    });
    render(<VerifyEmailChange />);
    expect(
      await screen.findByText(/this link is no longer valid/i)
    ).toBeInTheDocument();
  });

  it('explains a lost address race and that the address did not change', async () => {
    confirmEmailChange.mockResolvedValue({
      ok: false,
      reason: 'taken',
      code: 'EMAIL_TAKEN',
      message: 'That email address belongs to another account.',
    });
    render(<VerifyEmailChange />);
    expect(
      await screen.findByText(
        /another account started using that email address/i
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText(/your sign-in address has not changed/i)
    ).toBeInTheDocument();
  });

  it('reports a missing token rather than calling the server', async () => {
    arriveWithToken(null);
    render(<VerifyEmailChange />);
    expect(await screen.findByText(/missing its token/i)).toBeInTheDocument();
    expect(confirmEmailChange).not.toHaveBeenCalled();
  });

  it('survives a network failure with a retryable message', async () => {
    confirmEmailChange.mockRejectedValue(new Error('offline'));
    render(<VerifyEmailChange />);
    expect(
      await screen.findByText(/check your connection/i)
    ).toBeInTheDocument();
  });

  it('says the change is unavailable without an identity client', async () => {
    clientIsNull = true;
    render(<VerifyEmailChange />);
    expect(
      await screen.findByText(/not available in this deployment/i)
    ).toBeInTheDocument();
    expect(confirmEmailChange).not.toHaveBeenCalled();
  });
});
