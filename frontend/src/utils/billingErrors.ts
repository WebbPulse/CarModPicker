/**
 * Friendly copy for the billing endpoints' error codes.
 */

import { getApiErrorCode } from './apiError';

/** The message to show for a failed Checkout session request. */
export const getCheckoutErrorMessage = (err: unknown): string => {
  switch (getApiErrorCode(err)) {
    case 'ALREADY_PREMIUM':
      return 'You already have an active Premium subscription.';
    case 'STRIPE_NOT_CONFIGURED':
    case 'STRIPE_PRICE_MISSING':
      return 'Payments are not available right now. Please try again later.';
    default:
      return 'We could not start checkout. Please try again.';
  }
};

/** The message to show for a failed Customer Portal session request. */
export const getPortalErrorMessage = (err: unknown): string => {
  switch (getApiErrorCode(err)) {
    case 'NO_BILLING_ACCOUNT':
      return 'We could not find a billing account for you. If you subscribed recently, try again in a minute or contact us.';
    case 'STRIPE_NOT_CONFIGURED':
      return 'Billing is not available right now. Please try again later.';
    default:
      return 'We could not open the billing portal. Please try again.';
  }
};
