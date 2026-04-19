import { useEffect, useState } from 'react';
import { FaCrown, FaTimes } from 'react-icons/fa';
import { Link } from 'react-router-dom';

import { useAuth } from '../../hooks/useAuth';
import { useCookieConsent } from '../../hooks/useCookieConsent';
import { dismissForToday, isDismissedToday } from '../../utils/dailyDismiss';
import { isPremium } from '../../utils/subscription';

const DISMISS_KEY = 'subscription_promo_last_dismissed';

function SubscriptionPromo() {
  const [visible, setVisible] = useState(false);
  const { user, isAuthenticated, isLoading } = useAuth();
  const { consent } = useCookieConsent();

  useEffect(() => {
    // Wait for cookie-consent decision so we don't stack with that banner.
    if (consent === null) return;
    // Don't show while auth is still resolving; the isPremium check would be wrong.
    if (isLoading) return;
    // Premium users never see this, and it only makes sense for signed-in users
    // (signed-out users hit the Register CTA from the Pricing page instead).
    if (!isAuthenticated || isPremium(user)) return;
    if (isDismissedToday(DISMISS_KEY)) return;
    setVisible(true);
  }, [consent, isAuthenticated, isLoading, user]);

  if (!visible) return null;

  const handleDismiss = () => {
    dismissForToday(DISMISS_KEY);
    setVisible(false);
  };

  return (
    <div
      role="dialog"
      aria-label="Upgrade to CarModPicker Premium"
      className="relative w-full pointer-events-auto bg-neutral-950 rounded-2xl border border-white/10 shadow-2xl animate-slideInUp"
    >
      <button
        type="button"
        onClick={handleDismiss}
        aria-label="Dismiss"
        className="absolute top-3 right-3 text-neutral-400 hover:text-white transition-colors"
      >
        <FaTimes />
      </button>
      <div className="p-5 pr-10">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-lg">
            <FaCrown className="text-white text-lg" />
          </div>
          <h3 className="text-base font-semibold text-white">
            Go ad-free with Premium
          </h3>
        </div>
        <p className="text-sm text-neutral-300 leading-relaxed mb-4">
          Create unlimited build lists and browse without ads. Support the
          project for less than a cup of coffee a month.
        </p>
        <div className="flex gap-2 justify-end">
          <button
            type="button"
            onClick={handleDismiss}
            className="px-4 py-2 text-sm font-medium rounded-lg text-neutral-300 hover:text-white hover:bg-white/5 transition-colors"
          >
            Not now
          </button>
          <Link
            to="/pricing"
            onClick={handleDismiss}
            className="btn-primary px-4 py-2 rounded-lg text-sm font-medium inline-flex items-center gap-2"
          >
            <FaCrown />
            See plans
          </Link>
        </div>
      </div>
    </div>
  );
}

export default SubscriptionPromo;
