import { create } from 'zustand';

import {
  loginRequest,
  meRequest,
  registerRequest,
} from '@/features/auth/api';
import type {
  LoginPayload,
  RegisterPayload,
  User,
} from '@/features/auth/types';

/**
 * Auth store (Zustand) — source de vérité de la session.
 *
 * Les tokens sont persistés dans le localStorage pour survivre à un rechargement ;
 * l'intercepteur HTTP (`src/lib/api.ts`) lit `accessToken` ici et gère le refresh.
 */

const ACCESS_KEY = 'jirou.access_token';
const REFRESH_KEY = 'jirou.refresh_token';

function readToken(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function persistTokens(access: string | null, refresh: string | null): void {
  try {
    if (access) localStorage.setItem(ACCESS_KEY, access);
    else localStorage.removeItem(ACCESS_KEY);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
    else localStorage.removeItem(REFRESH_KEY);
  } catch {
    /* localStorage indisponible (mode privé) : on reste en mémoire. */
  }
}

/**
 * `loading`  : token présent, vérification /me en cours (au démarrage).
 * `authenticated` / `unauthenticated` : états stables.
 */
export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  status: AuthStatus;

  /** Enregistre de nouveaux tokens (utilisé par le refresh). */
  setTokens: (access: string, refresh?: string | null) => void;
  setUser: (user: User) => void;

  login: (payload: LoginPayload) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => void;
  /** Au démarrage : valide le token en mémoire via /me (ou passe unauthenticated). */
  hydrate: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => {
  const access = readToken(ACCESS_KEY);
  const refresh = readToken(REFRESH_KEY);

  return {
    user: null,
    accessToken: access,
    refreshToken: refresh,
    status: access ? 'loading' : 'unauthenticated',

    setTokens: (newAccess, newRefresh) => {
      const refreshToKeep =
        newRefresh === undefined ? get().refreshToken : newRefresh;
      persistTokens(newAccess, refreshToKeep);
      set({ accessToken: newAccess, refreshToken: refreshToKeep });
    },

    setUser: (user) => set({ user }),

    login: async (payload) => {
      const tokens = await loginRequest(payload);
      persistTokens(tokens.access_token, tokens.refresh_token);
      set({
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
      });
      const user = await meRequest();
      set({ user, status: 'authenticated' });
    },

    register: async (payload) => {
      await registerRequest(payload);
      // Auto-connexion juste après l'inscription.
      await get().login({ email: payload.email, password: payload.password });
    },

    logout: () => {
      persistTokens(null, null);
      set({
        user: null,
        accessToken: null,
        refreshToken: null,
        status: 'unauthenticated',
      });
    },

    hydrate: async () => {
      if (!get().accessToken) {
        set({ status: 'unauthenticated' });
        return;
      }
      try {
        const user = await meRequest();
        set({ user, status: 'authenticated' });
      } catch {
        // Token invalide/expiré et refresh impossible → session nettoyée.
        get().logout();
      }
    },
  };
});
