// filepath: src/components/routes/guestRoute.tsx
import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import Spinner from '../ui/spinner';

const GuestRoute: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <Spinner />;
  }

  if (isAuthenticated) {
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
