/**
 * Shared HTTP client for the CarModPicker API. Identity only since row 13, so
 * the access token comes from `AuthClient` and never from `localStorage`.
 */

import {
  ApiError,
  createApiClient,
  type QueryParams,
  type RequestOptions,
} from '@webbpulse/api-client';
import { getIdentityClient } from './identityClient';
import { appConfig } from '../config/app';

/**
 * Get the access token.
 *
 * The token lives in `AuthClient`'s closure rather than in `localStorage`.
 * Reading it through here keeps the one caller that needs the raw string,
 * `ExtensionAuth`, to a single call.
 */
export const getStoredToken = (): string | null =>
  getIdentityClient()?.getAccessToken() ?? null;

/**
 * Store the token. A no-op, kept callable so call sites need no branch; the
 * access token stays in memory and only `AuthClient` may set one.
 */
export const setStoredToken = (_token: string): void => {};

/**
 * Forget the token. Also a no-op; only the server can revoke the refresh
 * cookie, so the caller wants `AuthClient.logout()`.
 */
export const removeStoredToken = (): void => {};

/**
 * The identity token provider. Passing `auth` turns on the shared client's
 * retry-once-on-401 pipeline.
 */
const identityAuth = getIdentityClient();

const sharedClient = createApiClient({
  baseUrl: appConfig.apiBaseUrl,
  credentials: 'include',
  timeoutMs: 30000,
  ...(identityAuth !== null ? { auth: identityAuth } : {}),
});

/**
 * Response shape call sites destructure. Only `data` is exposed so callers do
 * not depend on the transport; status arrives on the thrown `ApiError`.
 */
export interface ApiClientResponse<T> {
  data: T;
}

/** The axios-shaped request options this application's call sites pass. */
export interface ApiRequestConfig {
  params?: QueryParams | URLSearchParams | undefined;
  headers?: Record<string, string> | undefined;
  signal?: AbortSignal | undefined;
}

/**
 * Maps axios-style `params` onto the shared client's `query`, accepting a
 * `URLSearchParams` and repeating keys for array values as the backend needs.
 */
const toQuery = (
  params: ApiRequestConfig['params']
): QueryParams | undefined => {
  if (params === undefined) return undefined;
  if (params instanceof URLSearchParams) {
    const query: QueryParams = {};
    for (const [key, value] of params.entries()) {
      const existing = query[key];
      if (existing === undefined) {
        query[key] = value;
      } else if (Array.isArray(existing)) {
        existing.push(value);
      } else {
        query[key] = [existing as string, value];
      }
    }
    return query;
  }
  return params;
};

/**
 * Translates an axios-style config into shared client `RequestOptions`. Drops
 * `multipart/form-data` so the browser sets its own boundary, and encodes a
 * form-urlencoded body into `URLSearchParams`.
 */
const toRequestOptions = (
  config: ApiRequestConfig | undefined,
  body?: unknown
): { options: RequestOptions; body: unknown } => {
  const options: RequestOptions = {};
  const query = toQuery(config?.params);
  if (query !== undefined) options.query = query;
  if (config?.signal !== undefined) options.signal = config.signal;

  let encodedBody = body;
  const headers: Record<string, string> = {};
  for (const [key, value] of Object.entries(config?.headers ?? {})) {
    const contentType =
      key.toLowerCase() === 'content-type' ? value.toLowerCase() : undefined;
    if (contentType?.includes('multipart/form-data') === true) {
      continue;
    }
    if (contentType?.includes('application/x-www-form-urlencoded') === true) {
      if (
        typeof encodedBody === 'object' &&
        encodedBody !== null &&
        !(encodedBody instanceof URLSearchParams) &&
        !(encodedBody instanceof FormData)
      ) {
        const search = new URLSearchParams();
        for (const [field, fieldValue] of Object.entries(
          encodedBody as Record<string, unknown>
        )) {
          if (
            typeof fieldValue === 'string' ||
            typeof fieldValue === 'number' ||
            typeof fieldValue === 'boolean'
          ) {
            search.append(field, String(fieldValue));
          }
        }
        encodedBody = search;
      }
      continue;
    }
    headers[key] = value;
  }
  if (Object.keys(headers).length > 0) options.headers = headers;

  return { options, body: encodedBody };
};

/**
 * Application-facing client. Each method resolves to `{ data }` and rejects
 * with `ApiError` on a non 2xx.
 */
export const apiClient = {
  get: <T = unknown>(
    path: string,
    config?: ApiRequestConfig
  ): Promise<ApiClientResponse<T>> => {
    const { options } = toRequestOptions(config);
    return sharedClient.get<T>(path, options);
  },
  post: <T = unknown>(
    path: string,
    data?: unknown,
    config?: ApiRequestConfig
  ): Promise<ApiClientResponse<T>> => {
    const { options, body } = toRequestOptions(config, data);
    return sharedClient.post<T>(path, body, options);
  },
  put: <T = unknown>(
    path: string,
    data?: unknown,
    config?: ApiRequestConfig
  ): Promise<ApiClientResponse<T>> => {
    const { options, body } = toRequestOptions(config, data);
    return sharedClient.put<T>(path, body, options);
  },
  patch: <T = unknown>(
    path: string,
    data?: unknown,
    config?: ApiRequestConfig
  ): Promise<ApiClientResponse<T>> => {
    const { options, body } = toRequestOptions(config, data);
    return sharedClient.patch<T>(path, body, options);
  },
  delete: <T = unknown>(
    path: string,
    config?: ApiRequestConfig
  ): Promise<ApiClientResponse<T>> => {
    const { options } = toRequestOptions(config);
    return sharedClient.delete<T>(path, options);
  },
};

/** True when the error came back from the API carrying an HTTP status. */
export const isApiErrorWithStatus = (error: unknown): error is ApiError =>
  error instanceof ApiError;

export default apiClient;
