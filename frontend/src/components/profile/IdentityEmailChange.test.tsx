import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  render,
  screen,
  fireEvent,
  waitFor,
} from '../../test/utils/test-utils';

const requestEmailChange = vi.fn();
const stepUp = vi.fn();
const stepUpWithPasskey = vi.fn();
let clientIsNull = false;

vi.mock('../../api/identityClient', () => ({
  getIdentityClient: () =>
    clientIsNull ? null : { requestEmailChange, stepUp, stepUpWithPasskey },
  identityOrigin: () => 'https://api.test',
}));

import IdentityEmailChange from './IdentityEmailChange';

const STEP_UP = {
  ok: false,
  reason: 'step-up-required',
  code: 'STEP_UP_REQUIRED',
  message: 'Sign in again to continue.',
  maxAge: 600,
};

/** Types a new address and submits the form. */
const submitAddress = (address: string) => {
  fireEvent.change(screen.getByLabelText(/new email address/i), {
    target: { value: address },
  });
  fireEvent.click(
    screen.getByRole('button', { name: /send confirmation link/i })
  );
};

beforeEach(() => {
  vi.clearAllMocks();
  clientIsNull = false;
});

describe('IdentityEmailChange', () => {
  it('requests the change and says where the link went', async () => {
    requestEmailChange.mockResolvedValue({ ok: true });
    render(<IdentityEmailChange currentEmail="old@example.test" />);
    submitAddress('new@example.test');

    expect(
      await screen.findByText(/sent a confirmation link to new@example.test/i)
    ).toBeInTheDocument();
    expect(requestEmailChange).toHaveBeenCalledWith({
      email: 'new@example.test',
    });
  });

  it('renders the refusal sentence the server sent', async () => {
    requestEmailChange.mockResolvedValue({
      ok: false,
      reason: 'taken',
      code: 'EMAIL_TAKEN',
      message: 'That email address belongs to another account.',
    });
    render(<IdentityEmailChange currentEmail="old@example.test" />);
    submitAddress('new@example.test');

    expect(
      await screen.findByText(/belongs to another account/i)
    ).toBeInTheDocument();
  });

  it('asks for the password when the sign-in is too old, then retries', async () => {
    requestEmailChange
      .mockResolvedValueOnce(STEP_UP)
      .mockResolvedValueOnce({ ok: true });
    stepUp.mockResolvedValue({ ok: true });
    render(<IdentityEmailChange currentEmail="old@example.test" />);
    submitAddress('new@example.test');

    const password = await screen.findByLabelText(/^password$/i);
    fireEvent.change(password, { target: { value: 'hunter22hunter' } });
    fireEvent.click(
      screen.getByRole('button', { name: /confirm and send link/i })
    );

    expect(
      await screen.findByText(/sent a confirmation link to new@example.test/i)
    ).toBeInTheDocument();
    expect(stepUp).toHaveBeenCalledWith({ password: 'hunter22hunter' });
    expect(requestEmailChange).toHaveBeenCalledTimes(2);
  });

  it('keeps the prompt open on a wrong password', async () => {
    requestEmailChange.mockResolvedValue(STEP_UP);
    stepUp.mockResolvedValue({
      ok: false,
      reason: 'invalid-password',
      message: 'That password is not right.',
    });
    render(<IdentityEmailChange currentEmail="old@example.test" />);
    submitAddress('new@example.test');

    fireEvent.change(await screen.findByLabelText(/^password$/i), {
      target: { value: 'wrong' },
    });
    fireEvent.click(
      screen.getByRole('button', { name: /confirm and send link/i })
    );

    expect(
      await screen.findByText(/that password is not right/i)
    ).toBeInTheDocument();
    expect(requestEmailChange).toHaveBeenCalledTimes(1);
  });

  it('re-authenticates with a passkey, then retries', async () => {
    requestEmailChange
      .mockResolvedValueOnce(STEP_UP)
      .mockResolvedValueOnce({ ok: true });
    stepUpWithPasskey.mockResolvedValue({ ok: true });
    render(<IdentityEmailChange currentEmail="old@example.test" />);
    submitAddress('new@example.test');

    fireEvent.click(
      await screen.findByRole('button', { name: /use a passkey/i })
    );

    await waitFor(() => expect(requestEmailChange).toHaveBeenCalledTimes(2));
    expect(stepUpWithPasskey).toHaveBeenCalledTimes(1);
  });

  it('says the change is unavailable without an identity client', () => {
    clientIsNull = true;
    render(<IdentityEmailChange currentEmail="old@example.test" />);
    expect(
      screen.getByText(/not available in this deployment/i)
    ).toBeInTheDocument();
  });
});
