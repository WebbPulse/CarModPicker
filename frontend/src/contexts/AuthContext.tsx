import type { ReactNode } from 'react';
import React from 'react';
import {
  AuthProvider as PackageAuthProvider,
  type AnyAuthClient,
} from '@webbpulse/auth/react';
import { getIdentityClient } from '../api/identityClient';

/**
 * Mounts the `@webbpulse/auth` provider, which spends the refresh cookie on
 * mount. Renders children bare when the identity client could not be built, so
 * a deployment with no identity origin still paints.
 */
export const AuthProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  const client = getIdentityClient();

  if (client === null) {
    return <>{children}</>;
  }

  return (
    <PackageAuthProvider client={client as unknown as AnyAuthClient}>
      {children}
    </PackageAuthProvider>
  );
};
