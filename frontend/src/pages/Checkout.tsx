import { useEffect, useState } from 'react';
import {
  FaArrowLeft,
  FaCheckCircle,
  FaCrown,
  FaLock,
  FaTimesCircle,
} from 'react-icons/fa';
import { Link, useSearchParams } from 'react-router-dom';

import { createCheckoutSession, redirectToBilling } from '../api/billing';
import ManageSubscriptionButton from '../components/billing/ManageSubscriptionButton';
import { ErrorAlert } from '../components/ui/alert';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import Spinner from '../components/ui/spinner';
import { PREMIUM_MONTHLY_PRICE_USD } from '../constants';
import { useAuth } from '../hooks/useAuth';
import { getCheckoutErrorMessage } from '../utils/billingErrors';
import { isPremium } from '../utils/subscription';

/** Milliseconds between user refreshes while a new subscription activates. */
const ACTIVATION_POLL_INTERVAL_MS = 2500;

/** User refreshes to attempt before showing the delayed activation state. */
const ACTIVATION_MAX_ATTEMPTS = 12;

/**
 * The state shown after Stripe returns a completed payment: activating while
 * the webhook lands, confirmed once the user is premium, or a delayed note
 * when activation takes longer than the polling window.
 */
function CheckoutSuccessState({
  userIsPremium,
  timedOut,
}: {
  userIsPremium: boolean;
  timedOut: boolean;
}) {
  if (userIsPremium) {
    return (
      <Card
        variant="glass"
        className="mb-6 border border-success/30 bg-success/5"
        role="status"
      >
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-success/20 text-success flex items-center justify-center flex-shrink-0">
            <FaCheckCircle />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white mb-1">
              Welcome to Premium
            </h3>
            <p className="text-sm text-foreground leading-relaxed">
              Your subscription is active. You can manage it any time from your{' '}
              <Link
                to="/profile"
                className="text-primary hover:text-primary/90 underline"
              >
                profile
              </Link>
              .
            </p>
          </div>
        </div>
      </Card>
    );
  }

  if (timedOut) {
    return (
      <Card
        variant="glass"
        className="mb-6 border border-warning/30 bg-warning/5"
        role="status"
      >
        <h3 className="text-lg font-semibold text-white mb-1">
          Payment received, still activating
        </h3>
        <p className="text-sm text-foreground leading-relaxed">
          Activation is taking longer than usual. It should finish within a few
          minutes. Check your{' '}
          <Link
            to="/profile"
            className="text-primary hover:text-primary/90 underline"
          >
            profile
          </Link>{' '}
          shortly, or{' '}
          <Link
            to="/contact-us"
            className="text-primary hover:text-primary/90 underline"
          >
            contact us
          </Link>{' '}
          if it does not update.
        </p>
      </Card>
    );
  }

  return (
    <Card
      variant="glass"
      className="mb-6 border border-primary/30 bg-primary/5"
      role="status"
    >
      <div className="flex items-start gap-3">
        <Spinner inline />
        <div>
          <h3 className="text-lg font-semibold text-white mb-1">
            Payment received, activating Premium
          </h3>
          <p className="text-sm text-foreground leading-relaxed">
            This usually takes a few seconds.
          </p>
        </div>
      </div>
    </Card>
  );
}

/**
 * Subscription checkout page. Shows the order summary, starts Stripe Checkout,
 * and handles the success and cancelled returns from Stripe.
 */
function Checkout() {
  const { user, checkAuthStatus } = useAuth();
  const userIsPremium = isPremium(user);
  const [searchParams] = useSearchParams();
  const status = searchParams.get('status');
  const returnedFromSuccess = status === 'success';
  const returnedFromCancel = status === 'cancelled';

  const [isStartingCheckout, setIsStartingCheckout] = useState(false);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [activationAttempts, setActivationAttempts] = useState(0);
  const activationTimedOut =
    !userIsPremium && activationAttempts >= ACTIVATION_MAX_ATTEMPTS;

  useEffect(() => {
    if (!returnedFromSuccess || userIsPremium) return;
    if (activationAttempts >= ACTIVATION_MAX_ATTEMPTS) return;
    let cancelled = false;
    const timer = window.setTimeout(
      () => {
        void (async () => {
          await checkAuthStatus();
          if (!cancelled) setActivationAttempts((n) => n + 1);
        })();
      },
      activationAttempts === 0 ? 0 : ACTIVATION_POLL_INTERVAL_MS
    );
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [returnedFromSuccess, userIsPremium, activationAttempts, checkAuthStatus]);

  const handleSubscribe = async () => {
    setCheckoutError(null);
    setIsStartingCheckout(true);
    try {
      redirectToBilling(await createCheckoutSession());
    } catch (err) {
      setCheckoutError(getCheckoutErrorMessage(err));
      setIsStartingCheckout(false);
    }
  };

  return (
    <div className="min-h-screen">
      <section className="py-10 px-4">
        <div className="container mx-auto max-w-3xl">
          <Link
            to="/pricing"
            className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-white transition-colors mb-4"
          >
            <FaArrowLeft />
            Back to pricing
          </Link>

          <div className="text-center mb-8 animate-fadeInScale">
            <div className="flex justify-center mb-4">
              <div className="w-16 h-16 bg-linear-to-br from-warning to-warning rounded-2xl flex items-center justify-center shadow-2xl">
                <FaCrown className="text-white text-2xl" />
              </div>
            </div>
            <h1 className="text-4xl md:text-5xl font-bold mb-3">
              <span className="text-gradient">Go Premium</span>
            </h1>
            <p className="text-muted-foreground leading-relaxed">
              Review your plan and complete checkout.
            </p>
          </div>

          {returnedFromSuccess && (
            <CheckoutSuccessState
              userIsPremium={userIsPremium}
              timedOut={activationTimedOut}
            />
          )}

          {returnedFromCancel && !userIsPremium && (
            <Card
              variant="glass"
              className="mb-6 border border-white/15"
              role="status"
            >
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-white/10 text-muted-foreground flex items-center justify-center flex-shrink-0">
                  <FaTimesCircle />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-white mb-1">
                    Checkout cancelled
                  </h3>
                  <p className="text-sm text-foreground leading-relaxed">
                    No charge was made. You can subscribe whenever you're ready.
                  </p>
                </div>
              </div>
            </Card>
          )}

          {!returnedFromSuccess && userIsPremium && (
            <Card
              variant="glass"
              className="mb-6 border border-success/30 bg-success/5"
            >
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-success/20 text-success flex items-center justify-center flex-shrink-0">
                  <FaCrown />
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-white mb-1">
                    You're already Premium
                  </h3>
                  <p className="text-sm text-foreground leading-relaxed mb-4">
                    Your subscription is active. Update your payment method,
                    view invoices, or cancel from the billing portal.
                  </p>
                  <ManageSubscriptionButton className="rounded-xl" />
                </div>
              </div>
            </Card>
          )}

          <Card variant="glass" className="mb-6 animate-slideInUp">
            <h2 className="text-lg font-semibold text-white mb-4">
              Order summary
            </h2>
            <div className="flex items-center justify-between py-3 border-b border-white/10">
              <div>
                <div className="text-white font-medium">
                  CarModPicker Premium
                </div>
                <div className="text-sm text-muted-foreground">
                  Monthly plan
                </div>
              </div>
              <div className="text-right">
                <div className="text-white font-semibold">
                  ${PREMIUM_MONTHLY_PRICE_USD.toFixed(2)}
                </div>
                <div className="text-sm text-muted-foreground">per month</div>
              </div>
            </div>
            <div className="flex items-center justify-between py-3 border-b border-white/10 text-sm">
              <span className="text-muted-foreground">Billed to</span>
              <span className="text-foreground">{user?.email}</span>
            </div>
            <div className="flex items-center justify-between pt-4">
              <span className="text-white font-semibold">Total today</span>
              <span className="text-white font-bold text-xl">
                ${PREMIUM_MONTHLY_PRICE_USD.toFixed(2)}
              </span>
            </div>
          </Card>

          {!returnedFromSuccess && !userIsPremium && (
            <Card
              variant="glass"
              className="animate-slideInUp"
              style={{ animationDelay: '0.1s' }}
            >
              <div className="flex items-center gap-2 mb-4">
                <FaLock className="text-muted-foreground" />
                <h2 className="text-lg font-semibold text-white">Payment</h2>
              </div>

              <div className="rounded-xl border border-white/10 bg-white/5 p-6 text-center">
                <p className="text-sm text-muted-foreground max-w-md mx-auto leading-relaxed mb-4">
                  You'll finish payment on a secure page hosted by Stripe, then
                  come straight back here.
                </p>
                <Button
                  type="button"
                  className="rounded-xl"
                  loading={isStartingCheckout}
                  onClick={() => void handleSubscribe()}
                >
                  {!isStartingCheckout && <FaCrown />}
                  Subscribe for ${PREMIUM_MONTHLY_PRICE_USD.toFixed(2)}/mo
                </Button>
                {checkoutError && (
                  <div className="mt-4 text-left">
                    <ErrorAlert message={checkoutError} />
                  </div>
                )}
              </div>

              <p className="text-xs text-muted-foreground text-center mt-4 leading-relaxed">
                By subscribing you agree to our{' '}
                <Link
                  to="/terms-of-service"
                  className="text-muted-foreground hover:text-white underline"
                >
                  Terms of Service
                </Link>{' '}
                and{' '}
                <Link
                  to="/privacy-policy"
                  className="text-muted-foreground hover:text-white underline"
                >
                  Privacy Policy
                </Link>
                . Cancel any time.
              </p>
            </Card>
          )}
        </div>
      </section>
    </div>
  );
}

export default Checkout;
