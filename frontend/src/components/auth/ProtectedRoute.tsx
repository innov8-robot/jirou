import { Navigate, Outlet, useLocation } from 'react-router-dom';

import type { UserRole } from '@/features/auth/types';
import { useAuthStore } from '@/stores/authStore';

/** Écran plein centré pendant la vérification de session au démarrage. */
function AuthLoading() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div
        className="h-8 w-8 animate-spin rounded-full border-2 border-muted border-t-primary"
        role="status"
        aria-label="Chargement"
      />
    </div>
  );
}

/**
 * Garde de route (JIR-14).
 * - `loading` → écran d'attente (le temps de valider le token via /me).
 * - non authentifié → redirection vers /login (mémorise la destination).
 * - `roles` fourni + rôle insuffisant → redirection vers /projects.
 */
export function ProtectedRoute({ roles }: { roles?: UserRole[] }) {
  const status = useAuthStore((s) => s.status);
  const user = useAuthStore((s) => s.user);
  const location = useLocation();

  if (status === 'loading') {
    return <AuthLoading />;
  }

  if (status === 'unauthenticated' || !user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (roles && !roles.includes(user.role)) {
    return <Navigate to="/projects" replace />;
  }

  return <Outlet />;
}
