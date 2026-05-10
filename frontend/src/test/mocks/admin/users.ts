// Phase 8 D-06: admin-user view factories for Admin Users tab tests.
//
// Factory pattern per research §Pitfall 6 — every call returns a fresh object
// so parallel Vitest workers do not leak fixture state across files.
//
// The admin Users tab consumes `UserRead` shaped records; there is no separate
// backend "AdminUserView" type today. If the backend later introduces one,
// swap the import here — the call sites use `makeAdminUserView()` only.
import type { UserRead } from '../../../types/Api';

export const makeAdminUserView = (
  overrides: Partial<UserRead> = {}
): UserRead => ({
  id: '11111111-1111-7111-8111-111111111111',
  username: 'adminuser',
  email: 'admin@example.com',
  disabled: false,
  email_verified: true,
  image_urls: ['https://example.com/admin.jpg'],
  is_superuser: false,
  is_admin: true,
  is_service_account: false,
  subscription_tier: 'free',
  subscription_status: 'active',
  totp_enabled: false,
  ...overrides,
});

export const makeUserList = (items?: UserRead[]): UserRead[] =>
  items ?? [makeAdminUserView()];
