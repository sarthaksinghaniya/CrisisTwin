import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function RoleRoute({ children, allowedRoles }) {
  const auth = useAuth();

  if (!auth) {
    console.warn("useAuth() returned undefined in RoleRoute. This can happen during dev server hot-reloading.");
    return null;
  }

  const { user, role, loading } = auth;
  const location = useLocation();

  if (loading) return null;

  if (!user || !role) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Handle case where user's role isn't in the allowed array
  if (!allowedRoles.includes(role)) {
    // If they are an admin trying to access citizen routes, bounce to admin dashboard
    if (role === 'admin') {
      return <Navigate to="/admin" replace />;
    }
    // If they are a citizen trying to access admin routes, bounce to dashboard
    if (role === 'citizen') {
      return <Navigate to="/dashboard" replace />;
    }
    // Fallback unhandled role
    return <Navigate to="/login" replace />;
  }

  return children;
}
