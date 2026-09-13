import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { useSessionSettled } from '../../hooks/useSessionSettled';
import Spinner from '../ui/spinner';

/**
 * Guards routes that need a signed-in user, redirecting to login otherwise.
 * The spinner shows only until the session first settles, so a token call made
 * from inside the route keeps the page mounted.
 */
const ProtectedRoute: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();
  const settled = useSessionSettled(isLoading);

  if (isLoading && !settled) {
    return <Spinner />;
  }

  if (!isAuthenticated && !isLoading) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <Outlet />;
};

export default ProtectedRoute;
