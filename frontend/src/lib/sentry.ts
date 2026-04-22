import * as Sentry from '@sentry/react';

/**
 * Frontend Sentry initialization.
 *
 * OBS-05: captures React runtime errors in staging + production environments,
 * with Session Replay enabled ON ERROR ONLY (zero ambient) to stay well under
 * the Sentry free-tier 500-replays/month quota (D-32).
 *
 * Decision refs: 02-CONTEXT.md D-32..D-43. Landmine refs: 02-RESEARCH.md §5
 * Landmines 11 (v10 sendDefaultPii + strict IP exclusion), 12 (build.sourcemap
 * 'hidden' required for vite-plugin), 13 (process.env.CI cross-CI standard),
 * 14 (beforeErrorSampling decides replay attach, NOT error reporting —
 * auth-route errors still report, replay just doesn't attach).
 *
 * PII posture (D-36 + D-40):
 * - sendDefaultPii: false — v10 strictly excludes IP address
 * - maskAllText / maskAllInputs / blockAllMedia for Session Replay
 * - Sentry.setUser({ id }) only — never email/username (see AuthContext.tsx)
 */

/**
 * Auth-route pathname prefixes where Session Replay must NOT attach.
 * D-37: defense-in-depth against token-bearing URL fragments (oauth redirects,
 * password-reset tokens, 2FA step-up challenges). Errors on these pages still
 * report to Sentry — the replay video is what gets dropped.
 */
const AUTH_PATHS = [
  '/login',
  '/register',
  '/oauth-callback',
  '/reset-password',
  '/2fa',
];

export function initSentry(): void {
  // Gate 1: never initialize in local dev (noise + wrong env tag).
  if (import.meta.env.MODE === 'development') return;

  // Gate 2: no DSN → no-op (T-02-TEST-POLLUTION: vitest sets MODE=test but
  // leaves VITE_SENTRY_DSN unset, so tests hit this return path).
  // Bracket access required for custom env vars (noPropertyAccessFromIndexSignature);
  // cast to string because Vite env index-signature values are typed as `any`.
  const dsn = import.meta.env['VITE_SENTRY_DSN'] as string | undefined;
  if (!dsn) return;

  const release = import.meta.env['VITE_SENTRY_RELEASE'] as string | undefined;

  Sentry.init({
    dsn,
    environment: import.meta.env.MODE, // "staging" | "production"
    release,
    sendDefaultPii: false, // D-36 + Landmine 11 (v10 strict IP exclusion)
    tracesSampleRate: 0.05, // D-38
    replaysSessionSampleRate: 0, // D-32 — zero ambient replay
    replaysOnErrorSampleRate: 1.0, // D-32 — 100% on error
    integrations: [
      Sentry.browserTracingIntegration(),
      Sentry.replayIntegration({
        maskAllText: true, // D-36
        maskAllInputs: true, // D-36
        blockAllMedia: true,
        // D-37: returning false here drops the replay; the error event itself
        // still reports (Landmine 14).
        beforeErrorSampling: () => {
          const path = window.location.pathname;
          return !AUTH_PATHS.some((p) => path.startsWith(p));
        },
      }),
    ],
  });
}
