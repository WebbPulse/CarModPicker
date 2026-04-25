import { FaArrowLeft, FaCrown, FaLock } from 'react-icons/fa';
import { Link } from 'react-router-dom';

import { Card } from '../components/ui/card';
import { PREMIUM_MONTHLY_PRICE_USD } from '../constants';
import { useAuth } from '../hooks/useAuth';
import { isPremium } from '../utils/subscription';

function Checkout() {
  const { user } = useAuth();
  const userIsPremium = isPremium(user);

  return (
    <div className="min-h-screen">
      <section className="py-10 px-4">
        <div className="container mx-auto max-w-3xl">
          <Link
            to="/pricing"
            className="inline-flex items-center gap-2 text-sm text-neutral-400 hover:text-white transition-colors mb-4"
          >
            <FaArrowLeft />
            Back to pricing
          </Link>

          <div className="text-center mb-8 animate-fadeInScale">
            <div className="flex justify-center mb-4">
              <div className="w-16 h-16 bg-linear-to-br from-amber-400 via-orange-500 to-red-500 rounded-2xl flex items-center justify-center shadow-2xl">
                <FaCrown className="text-white text-2xl" />
              </div>
            </div>
            <h1 className="text-4xl md:text-5xl font-bold mb-3">
              <span className="text-gradient">Go Premium</span>
            </h1>
            <p className="text-neutral-400 leading-relaxed">
              Review your plan and complete checkout.
            </p>
          </div>

          {userIsPremium && (
            <Card
              variant="glass"
              className="mb-6 border border-emerald-500/30 bg-emerald-500/5"
            >
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/20 text-emerald-300 flex items-center justify-center flex-shrink-0">
                  <FaCrown />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-white mb-1">
                    You're already Premium
                  </h3>
                  <p className="text-sm text-neutral-300 leading-relaxed">
                    Your subscription is active. Manage it from your{' '}
                    <Link
                      to="/profile"
                      className="text-primary-300 hover:text-primary-200 underline"
                    >
                      profile
                    </Link>
                    .
                  </p>
                </div>
              </div>
            </Card>
          )}

          {/* Plan summary */}
          <Card variant="glass" className="mb-6 animate-slideInUp">
            <h2 className="text-lg font-semibold text-white mb-4">
              Order summary
            </h2>
            <div className="flex items-center justify-between py-3 border-b border-white/10">
              <div>
                <div className="text-white font-medium">
                  CarModPicker Premium
                </div>
                <div className="text-sm text-neutral-400">Monthly plan</div>
              </div>
              <div className="text-right">
                <div className="text-white font-semibold">
                  ${PREMIUM_MONTHLY_PRICE_USD.toFixed(2)}
                </div>
                <div className="text-sm text-neutral-400">per month</div>
              </div>
            </div>
            <div className="flex items-center justify-between py-3 border-b border-white/10 text-sm">
              <span className="text-neutral-400">Billed to</span>
              <span className="text-neutral-200">{user?.email}</span>
            </div>
            <div className="flex items-center justify-between pt-4">
              <span className="text-white font-semibold">Total today</span>
              <span className="text-white font-bold text-xl">
                ${PREMIUM_MONTHLY_PRICE_USD.toFixed(2)}
              </span>
            </div>
          </Card>

          {/* Payment section — placeholder until provider is wired up */}
          <Card
            variant="glass"
            className="animate-slideInUp"
            style={{ animationDelay: '0.1s' }}
          >
            <div className="flex items-center gap-2 mb-4">
              <FaLock className="text-neutral-400" />
              <h2 className="text-lg font-semibold text-white">Payment</h2>
            </div>

            <div className="rounded-xl border border-dashed border-white/15 bg-white/5 p-6 text-center">
              <div className="inline-flex items-center gap-1.5 px-3 py-1 mb-3 rounded-full text-xs font-semibold bg-amber-400/20 text-amber-300 border border-amber-400/30">
                Coming soon
              </div>
              <h3 className="text-lg font-semibold text-white mb-2">
                Payment processing is almost ready
              </h3>
              <p className="text-sm text-neutral-400 max-w-md mx-auto leading-relaxed mb-4">
                We're finishing the integration with our payment provider. In
                the meantime, you can{' '}
                <Link
                  to="/support"
                  className="text-primary-300 hover:text-primary-200 underline"
                >
                  support the project directly
                </Link>{' '}
                or check back shortly.
              </p>
              <button
                type="button"
                disabled
                className="btn-primary px-5 py-3 rounded-xl text-sm font-semibold opacity-50 cursor-not-allowed inline-flex items-center gap-2"
              >
                <FaCrown />
                Subscribe for ${PREMIUM_MONTHLY_PRICE_USD.toFixed(2)}/mo
              </button>
            </div>

            <p className="text-xs text-neutral-500 text-center mt-4 leading-relaxed">
              By subscribing you'll agree to our{' '}
              <Link
                to="/terms-of-service"
                className="text-neutral-400 hover:text-white underline"
              >
                Terms of Service
              </Link>{' '}
              and{' '}
              <Link
                to="/privacy-policy"
                className="text-neutral-400 hover:text-white underline"
              >
                Privacy Policy
              </Link>
              . Cancel any time.
            </p>
          </Card>
        </div>
      </section>
    </div>
  );
}

export default Checkout;
