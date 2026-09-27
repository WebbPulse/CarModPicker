/**
 * Stripe billing: hosted Checkout for new subscriptions and the Customer
 * Portal for managing an existing one.
 */

import { apiClient } from './client';

/** A Stripe-hosted page the browser is sent to. */
export interface BillingRedirect {
  url: string;
}

/** Starts Stripe Checkout and opens the Customer Portal. */
export const billingApi = {
  /** Creates a Checkout session for the premium plan. */
  createCheckoutSession: () =>
    apiClient.post<BillingRedirect>('/billing/checkout-session'),
  /** Creates a Customer Portal session for the signed in subscriber. */
  createPortalSession: () =>
    apiClient.post<BillingRedirect>('/billing/portal-session'),
};

/** Creates a Checkout session and returns its Stripe URL. */
export const createCheckoutSession = async (): Promise<string> =>
  (await billingApi.createCheckoutSession()).data.url;

/** Creates a Customer Portal session and returns its Stripe URL. */
export const createPortalSession = async (): Promise<string> =>
  (await billingApi.createPortalSession()).data.url;

/** Sends the browser to a Stripe-hosted billing page. */
export const redirectToBilling = (url: string): void => {
  window.location.assign(url);
};
