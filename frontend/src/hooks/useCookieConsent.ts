import { useEffect, useState } from 'react';

const STORAGE_KEY = 'cookie_consent_v1';
const CHANGE_EVENT = 'cookie-consent-change';

export type CookieConsent = 'accepted' | 'rejected' | null;

function read(): CookieConsent {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    if (value === 'accepted' || value === 'rejected') return value;
  } catch {
    // localStorage may be unavailable (privacy mode, etc.)
  }
  return null;
}

export function useCookieConsent() {
  const [consent, setConsent] = useState<CookieConsent>(read);

  useEffect(() => {
    const sync = () => setConsent(read());
    const storageHandler = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) sync();
    };
    window.addEventListener('storage', storageHandler);
    window.addEventListener(CHANGE_EVENT, sync);
    return () => {
      window.removeEventListener('storage', storageHandler);
      window.removeEventListener(CHANGE_EVENT, sync);
    };
  }, []);

  const persist = (value: Exclude<CookieConsent, null>) => {
    try {
      localStorage.setItem(STORAGE_KEY, value);
    } catch {
      // ignore
    }
    setConsent(value);
    window.dispatchEvent(new Event(CHANGE_EVENT));
  };

  const reset = () => {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
    setConsent(null);
    window.dispatchEvent(new Event(CHANGE_EVENT));
  };

  return {
    consent,
    accept: () => persist('accepted'),
    reject: () => persist('rejected'),
    reset,
  };
}
