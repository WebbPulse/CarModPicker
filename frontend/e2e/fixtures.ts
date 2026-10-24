/**
 * Shared Playwright fixtures: every page runs offline from third parties and
 * starts with the consent banner and extension promo already dismissed, so
 * ads, fonts and overlays cannot make a run flaky or nondeterministic.
 */

import { test as base, expect } from '@playwright/test';

const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1']);

export const test = base.extend<{ isolatePage: void }>({
  isolatePage: [
    async ({ context }, use) => {
      await context.route(
        (url) => !LOCAL_HOSTS.has(url.hostname),
        (route) => route.abort('blockedbyclient')
      );
      await context.addInitScript(() => {
        try {
          localStorage.setItem('cookie_consent_v1', 'accepted');
          const today = new Date();
          const y = today.getFullYear();
          const m = String(today.getMonth() + 1).padStart(2, '0');
          const d = String(today.getDate()).padStart(2, '0');
          localStorage.setItem(
            'chrome_extension_promo_last_dismissed',
            `${y}-${m}-${d}`
          );
        } catch {
          return;
        }
      });
      await use();
    },
    { auto: true },
  ],
});

export { expect };
export type { Page, Request, Route } from '@playwright/test';
