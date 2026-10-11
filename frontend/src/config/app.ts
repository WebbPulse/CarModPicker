/**
 * Runtime app configuration read from the Vite environment.
 */

import { loadAppConfig, type AppConfig } from '@webbpulse/config';

/**
 * Loads and validates the configuration for an environment bag. Exported apart
 * from the singleton so tests can pass a synthetic bag. `backendTargets` is
 * honoured only under `DEV`, so a stray `VITE_BACKEND` cannot repoint a build.
 */
export const loadCarModPickerConfig = (env: ImportMetaEnv): AppConfig =>
  loadAppConfig(env, {
    defaultApiBaseUrl: '/api',
    defaultAppName: 'CarModPicker',
    apiBaseUrlAliases: ['VITE_API_URL'],
    assumeHttps: true,
    backendTargets: {
      staging: env['VITE_STAGING_API_URL'] as string | undefined,
      production: env['VITE_PROD_API_URL'] as string | undefined,
    },
    apiPathPrefix: '/api',
  });

/** The resolved configuration this bundle holds for its lifetime. */
export const appConfig: AppConfig = loadCarModPickerConfig(import.meta.env);
