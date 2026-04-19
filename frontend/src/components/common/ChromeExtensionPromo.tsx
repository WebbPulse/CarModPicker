import { useEffect, useState } from 'react';
import { FaChrome, FaTimes } from 'react-icons/fa';

import {
  CHROME_EXTENSION_STORE_URL,
  EXTENSION_INSTALLED_DATA_ATTR,
} from '../../constants';
import { useCookieConsent } from '../../hooks/useCookieConsent';

const DISMISS_KEY = 'chrome_extension_promo_dismissed_v1';
// Content scripts run at document_idle, which can land after our first effect.
// Poll briefly so we don't flash the banner at users who already have the extension.
const DETECTION_TIMEOUT_MS = 2000;
const DETECTION_INTERVAL_MS = 200;

function isExtensionInstalled(): boolean {
  return (
    document.documentElement.dataset[EXTENSION_INSTALLED_DATA_ATTR] ===
    'installed'
  );
}

function isChromiumBrowser(): boolean {
  if (typeof navigator === 'undefined') return false;
  const ua = navigator.userAgent;
  // Exclude Firefox and Safari (non-Chromium). Chrome/Edge/Brave/Opera all match.
  if (/Firefox\//i.test(ua)) return false;
  if (/Safari\//i.test(ua) && !/Chrome\//i.test(ua) && !/Chromium\//i.test(ua))
    return false;
  return /Chrome\//i.test(ua) || /Chromium\//i.test(ua);
}

function wasDismissed(): boolean {
  try {
    return localStorage.getItem(DISMISS_KEY) === 'true';
  } catch {
    return false;
  }
}

function ChromeExtensionPromo() {
  const [visible, setVisible] = useState(false);
  const { consent } = useCookieConsent();

  useEffect(() => {
    // Wait until the cookie consent decision is made — both render at bottom z-50.
    if (consent === null) return;
    if (wasDismissed() || !isChromiumBrowser()) return;

    let cancelled = false;

    const tick = (elapsed: number) => {
      if (cancelled) return;
      if (isExtensionInstalled()) return;
      if (elapsed >= DETECTION_TIMEOUT_MS) {
        setVisible(true);
        return;
      }
      window.setTimeout(
        () => tick(elapsed + DETECTION_INTERVAL_MS),
        DETECTION_INTERVAL_MS
      );
    };
    tick(0);

    return () => {
      cancelled = true;
    };
  }, [consent]);

  if (!visible) return null;

  const handleDismiss = () => {
    try {
      localStorage.setItem(DISMISS_KEY, 'true');
    } catch {
      // ignore
    }
    setVisible(false);
  };

  const handleInstall = () => {
    handleDismiss();
    window.open(CHROME_EXTENSION_STORE_URL, '_blank', 'noopener,noreferrer');
  };

  return (
    <div
      role="dialog"
      aria-label="Install CarModPicker Chrome extension"
      className="fixed bottom-4 right-4 z-50 max-w-sm w-[calc(100%-2rem)] sm:w-96 bg-neutral-950 rounded-2xl border border-white/10 shadow-2xl animate-slideInUp"
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
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500 to-primary-600 flex items-center justify-center shadow-lg">
            <FaChrome className="text-white text-lg" />
          </div>
          <h3 className="text-base font-semibold text-white">
            Add the Chrome extension
          </h3>
        </div>
        <p className="text-sm text-neutral-300 leading-relaxed mb-4">
          Scrape parts straight from retailer pages and add them to your build
          lists in one click.
        </p>
        <div className="flex gap-2 justify-end">
          <button
            type="button"
            onClick={handleDismiss}
            className="px-4 py-2 text-sm font-medium rounded-lg text-neutral-300 hover:text-white hover:bg-white/5 transition-colors"
          >
            Not now
          </button>
          <button
            type="button"
            onClick={handleInstall}
            className="btn-primary px-4 py-2 rounded-lg text-sm font-medium inline-flex items-center gap-2"
          >
            <FaChrome />
            Get extension
          </button>
        </div>
      </div>
    </div>
  );
}

export default ChromeExtensionPromo;
