import type { UserRead } from '../types/Api';

/**
 * Returns true if the user has an active premium subscription.
 * Use this to gate ads and premium features (e.g. unlimited build lists).
 *
 * Premium is active when:
 * - subscription_tier === 'premium'
 * - subscription_status === 'active'
 * - subscription_expires_at is null or in the future
 */
export function isPremium(user: UserRead | null | undefined): boolean {
  if (!user) return false;
  if (user.subscription_tier !== 'premium') return false;
  if (user.subscription_status !== 'active') return false;
  const expiresAt = user.subscription_expires_at;
  if (expiresAt != null && new Date(expiresAt) <= new Date()) return false;
  return true;
}
