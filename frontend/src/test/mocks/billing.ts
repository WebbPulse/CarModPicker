/**
 * Builders for billing endpoint errors and a premium user fixture.
 */

import { ApiError } from '@webbpulse/api-client';

import type { UserRead } from '../../types/Api';
import { mockUser } from './api';

/** An `ApiError` carrying the platform error envelope with `code`. */
export const billingError = (status: number, code: string) =>
  new ApiError({
    status,
    statusText: '',
    url: 'https://api.test/api/billing/checkout-session',
    method: 'POST',
    body: {
      success: false,
      status,
      message: 'Billing request failed',
      request_id: 'req-1',
      error_code: code,
    },
  });

/** User fixture holding an active premium subscription. */
export const mockPremiumUser: UserRead = {
  ...mockUser,
  subscription_tier: 'premium',
  subscription_status: 'active',
  subscription_expires_at: '2099-01-01T00:00:00Z',
};
