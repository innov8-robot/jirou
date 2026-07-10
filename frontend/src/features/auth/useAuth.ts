import { useAuthStore } from '@/stores/authStore';

/**
 * Accès pratique à la session. Chaque champ est sélectionné individuellement
 * (primitives/fonctions stables) pour éviter les re-renders superflus.
 */
export function useAuth() {
  const user = useAuthStore((s) => s.user);
  const status = useAuthStore((s) => s.status);
  const login = useAuthStore((s) => s.login);
  const register = useAuthStore((s) => s.register);
  const logout = useAuthStore((s) => s.logout);

  return {
    user,
    status,
    login,
    register,
    logout,
    isAuthenticated: status === 'authenticated',
    isAdmin: user?.role === 'admin',
  };
}
