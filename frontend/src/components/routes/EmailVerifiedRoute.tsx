import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import Spinner from '../ui/spinner';

/**
 * Guards routes that need a signed-in user with a verified email address.
 * `isLoading` is true only until the session first settles, so a token call made
 * from inside the route keeps the page mounted, and `isAuthenticated` stays true
 * for the duration of such a call, so neither branch fires mid-request.
 */
const EmailVerifiedRoute: React.FC = () => {
  const { isAuthenticated, user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <Spinner />;
  }

  if (!isAuthenticated) {
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
