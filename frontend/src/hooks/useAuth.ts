import { useAuth as usePackageAuth } from '@webbpulse/auth/react';
import type { UserRead } from '../types/Api';

/** The session from `@webbpulse/auth/react`, typed to CarModPicker's user. */
export const useAuth = () => usePackageAuth<UserRead>();
