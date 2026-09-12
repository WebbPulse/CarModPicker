import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  render,
  screen,
  waitFor,
  fireEvent,
  testScenarios,
} from '../../test/utils/test-utils';
import { register } from '../../api/identityAuth';
import Register from './Register';

vi.mock('../../api/identityAuth', () => ({
  register: vi.fn(),
}));

const registerMock = vi.mocked(register);

const getInputs = () => ({
  username: screen.getByPlaceholderText(/choose a username/i),
  email: screen.getByPlaceholderText(/you@example\.com/i),
  password: screen.getByPlaceholderText(/create a password/i),
  confirm: screen.getByPlaceholderText(/confirm your password/i),
});

const fillAndSubmit = (values: {
  username: string;
  email: string;
  password: string;
  confirm?: string;
}) => {
  const inputs = getInputs();
  fireEvent.change(inputs.username, { target: { value: values.username } });
  fireEvent.change(inputs.email, { target: { value: values.email } });
  fireEvent.change(inputs.password, { target: { value: values.password } });
  fireEvent.change(inputs.confirm, {
    target: { value: values.confirm ?? values.password },
  });
  const form = inputs.username.closest('form');
  if (!form) throw new Error('form element not found');
  fireEvent.submit(form);
};

describe('Register page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the register form with username, email, password and confirm fields', () => {
    render(<Register />, testScenarios.unauthenticated);

    expect(
      screen.getByPlaceholderText(/choose a username/i)
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/you@example\.com/i)
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/create a password/i)
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/confirm your password/i)
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /create account/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/join carmodpicker/i)).toBeInTheDocument();
  });

  it('registers through identity and navigates to /login on success', async () => {
    registerMock.mockResolvedValueOnce({ status: 'registered' });

    render(<Register />, testScenarios.unauthenticated);
    fillAndSubmit({
      username: 'newuser',
      email: 'new@example.com',
      password: 'password123',
    });

    await waitFor(() => {
      expect(registerMock).toHaveBeenCalledTimes(1);
    });
    expect(registerMock).toHaveBeenCalledWith(
      'newuser',
      'new@example.com',
      'password123'
    );
  });

  it('surfaces the identity failure and stays on the form', async () => {
    registerMock.mockResolvedValueOnce({
      status: 'failed',
      error: 'That address is already registered.',
    });

    render(<Register />, testScenarios.unauthenticated);
    fillAndSubmit({
      username: 'taken',
      email: 'taken@example.com',
      password: 'password123',
    });

    expect(
      await screen.findByText('That address is already registered.')
    ).toBeInTheDocument();
  });

  it('shows a validation error when passwords do not match (and does NOT call the API)', async () => {
    render(<Register />, testScenarios.unauthenticated);
    fillAndSubmit({
      username: 'user2',
      email: 'user2@example.com',
      password: 'password123',
      confirm: 'password999',
    });

    await waitFor(() => {
      expect(
        screen.getAllByText(/passwords don't match/i).length
      ).toBeGreaterThan(0);
    });
    expect(registerMock).not.toHaveBeenCalled();
  });

  it('rejects a password shorter than 8 characters without calling the API', async () => {
    render(<Register />, testScenarios.unauthenticated);
    fillAndSubmit({
      username: 'user3',
      email: 'user3@example.com',
      password: 'short',
    });

    await waitFor(() => {
      expect(
        screen.getByText(/password must be at least 8 characters long/i)
      ).toBeInTheDocument();
    });
    expect(registerMock).not.toHaveBeenCalled();
  });
});
