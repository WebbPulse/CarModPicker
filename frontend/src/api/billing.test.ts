/**
 * Tests for the billing api.
 */

import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type MockedFunction,
} from 'vitest';
import { apiClient } from './client';
import {
  billingApi,
  createCheckoutSession,
  createPortalSession,
  redirectToBilling,
} from './billing';

const postMock = apiClient.post as MockedFunction<typeof apiClient.post>;

describe('billingApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('createCheckoutSession POSTs /billing/checkout-session with no body', async () => {
    postMock.mockResolvedValueOnce({
      data: { url: 'https://checkout.stripe.com/c/pay/cs_test_1' },
    });

    const url = await createCheckoutSession();

    expect(postMock).toHaveBeenCalledWith('/billing/checkout-session');
    expect(postMock).toHaveBeenCalledTimes(1);
    expect(url).toBe('https://checkout.stripe.com/c/pay/cs_test_1');
  });

  it('createPortalSession POSTs /billing/portal-session with no body', async () => {
    postMock.mockResolvedValueOnce({
      data: { url: 'https://billing.stripe.com/p/session/test_1' },
    });

    const url = await createPortalSession();

    expect(postMock).toHaveBeenCalledWith('/billing/portal-session');
    expect(url).toBe('https://billing.stripe.com/p/session/test_1');
  });

  it('billingApi returns the raw envelope', async () => {
    postMock.mockResolvedValueOnce({ data: { url: 'https://x.test' } });

    const result = await billingApi.createCheckoutSession();

    expect(result.data).toEqual({ url: 'https://x.test' });
  });

  it('propagates request failures', async () => {
    postMock.mockRejectedValueOnce(new Error('boom'));

    await expect(createPortalSession()).rejects.toThrow('boom');
  });

  it('redirectToBilling assigns the window location', () => {
    const assign = vi.fn();
    vi.stubGlobal('location', { ...window.location, assign });

    redirectToBilling('https://checkout.stripe.com/c/pay/cs_test_2');

    expect(assign).toHaveBeenCalledWith(
      'https://checkout.stripe.com/c/pay/cs_test_2'
    );
  });
});
