import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import Spinner from '../ui/spinner';

/**
 * Guards routes meant for signed-out users, honouring a same-origin returnTo.
 * `isLoading` is true only until the session first settles, so a sign in already
 * in flight keeps the page mounted and holds its state, which is what carries an
 * MFA challenge from the first leg to the second.
 */
const GuestRoute: React.FC = () => {
  const { isAuthenticated, isLoading, isBusy } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <Spinner />;
  }

  if (isAuthenticated && !isBusy) {
    const params = new URLSearchParams(location.search);
    const returnTo = params.get('returnTo');
    if (returnTo && returnTo.startsWith('/') && !returnTo.startsWith('//')) {
      return <Navigate to={returnTo} replace />;
    }
    return <Navigate to="/" state={{ from: location }} replace />;
  }

  return <Outlet />;
};

export default GuestRoute;
