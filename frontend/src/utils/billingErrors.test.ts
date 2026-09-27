import { describe, expect, it } from 'vitest';

import { billingError } from '../test/mocks/billing';
import {
  getCheckoutErrorMessage,
  getPortalErrorMessage,
} from './billingErrors';

describe('getCheckoutErrorMessage', () => {
  it.each([
    ['ALREADY_PREMIUM', 409, /already have an active premium/i],
    ['STRIPE_NOT_CONFIGURED', 503, /payments are not available/i],
    ['STRIPE_PRICE_MISSING', 503, /payments are not available/i],
    ['STRIPE_ERROR', 502, /could not start checkout/i],
  ])('maps %s', (code, status, copy) => {
    expect(getCheckoutErrorMessage(billingError(status, code))).toMatch(copy);
  });

  it('falls back for a non api error', () => {
    expect(getCheckoutErrorMessage(new Error('x'))).toMatch(
      /could not start checkout/i
    );
  });
});

describe('getPortalErrorMessage', () => {
  it.each([
    ['NO_BILLING_ACCOUNT', 409, /could not find a billing account/i],
    ['STRIPE_NOT_CONFIGURED', 503, /billing is not available/i],
    ['STRIPE_ERROR', 502, /could not open the billing portal/i],
  ])('maps %s', (code, status, copy) => {
    expect(getPortalErrorMessage(billingError(status, code))).toMatch(copy);
  });
});
