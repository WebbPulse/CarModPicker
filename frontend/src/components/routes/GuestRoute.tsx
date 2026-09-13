import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { useSessionSettled } from '../../hooks/useSessionSettled';
import Spinner from '../ui/spinner';

/**
 * Guards routes meant for signed-out users, honouring a same-origin returnTo.
 * The spinner shows only until the session first settles, so a sign in already
 * in flight keeps the page mounted and holds its state.
 */
const GuestRoute: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();
  const settled = useSessionSettled(isLoading);

  if (isLoading && !settled) {
    return <Spinner />;
  }

  if (isAuthenticated && !isLoading) {
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
