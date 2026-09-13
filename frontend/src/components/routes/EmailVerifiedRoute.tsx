import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { useSessionSettled } from '../../hooks/useSessionSettled';
import Spinner from '../ui/spinner';

/**
 * Guards routes that need a signed-in user with a verified email address.
 * The spinner shows only until the session first settles, so a token call made
 * from inside the route keeps the page mounted.
 */
const EmailVerifiedRoute: React.FC = () => {
  const { isAuthenticated, user, isLoading } = useAuth();
  const location = useLocation();
  const settled = useSessionSettled(isLoading);

  if (isLoading && !settled) {
    return <Spinner />;
  }

  if (!isAuthenticated && !isLoading) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (isAuthenticated && !user?.email_verified) {
    return (
      <Navigate
        to="/verify-email"
        state={{
          from: location,
          message: 'Please verify your email to access this page.',
        }}
        replace
      />
    );
  }

  return <Outlet />;
};

export default EmailVerifiedRoute;
