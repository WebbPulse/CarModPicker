/**
 * Tracks whether the session has settled at least once, so a route guard can
 * show its spinner during the first resolution and never again. Later token
 * calls (a sign in, an MFA completion, a step up) flip the package client back
 * to `loading`, and a guard that re-rendered a spinner for those would unmount
 * the page driving the call and lose its state.
 */

import { useRef } from 'react';

/** Returns true once `isLoading` has been false at least once. */
export const useSessionSettled = (isLoading: boolean): boolean => {
  const settled = useRef(false);
  if (!isLoading) {
    settled.current = true;
  }
  return settled.current;
};
