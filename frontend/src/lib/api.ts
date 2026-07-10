import axios, {
  type AxiosInstance,
  type InternalAxiosRequestConfig,
} from 'axios';

import { useAuthStore } from '@/stores/authStore';

/**
 * Base URL of the backend API, read from Vite env (`VITE_API_URL`).
 * Falls back to the conventional local backend port (see docs/CONVENTIONS.md).
 */
export const API_BASE_URL: string =
  import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

/** Prefix shared by all versioned business routes (ex. `/api/v1/auth/login`). */
export const API_PREFIX = '/api/v1';

/** Centralized HTTP client. All API calls should go through this instance. */
export const api: AxiosInstance = axios.create({
  baseURL: `${API_BASE_URL}${API_PREFIX}`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Attach `Authorization: Bearer <token>` from the auth store when present.
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`);
  }
  return config;
});

/**
 * Refresh en cours, partagé : si plusieurs requêtes se prennent un 401 en même
 * temps, elles attendent le même appel `/auth/refresh` (pas de rafale).
 */
let refreshPromise: Promise<string | null> | null = null;

async function tryRefresh(): Promise<string | null> {
  const { refreshToken } = useAuthStore.getState();
  if (!refreshToken) {
    useAuthStore.getState().logout();
    return null;
  }
  if (!refreshPromise) {
    // Appel « nu » (hors instance `api`) pour éviter la récursion d'intercepteur.
    refreshPromise = axios
      .post(`${API_BASE_URL}${API_PREFIX}/auth/refresh`, {
        refresh_token: refreshToken,
      })
      .then((res) => {
        const newAccess = res.data.access_token as string;
        useAuthStore
          .getState()
          .setTokens(newAccess, res.data.refresh_token ?? refreshToken);
        return newAccess;
      })
      .catch(() => {
        useAuthStore.getState().logout();
        return null;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

// On 401 : tente un refresh unique puis rejoue la requête. Sinon, propage.
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config as
      | (InternalAxiosRequestConfig & { _retry?: boolean })
      | undefined;
    const status = error.response?.status;
    const url = original?.url ?? '';

    const isAuthEndpoint =
      url.includes('/auth/login') || url.includes('/auth/refresh');

    if (status === 401 && original && !original._retry && !isAuthEndpoint) {
      original._retry = true;
      const newAccess = await tryRefresh();
      if (newAccess) {
        original.headers.set('Authorization', `Bearer ${newAccess}`);
        return api(original);
      }
    }
    return Promise.reject(error);
  }
);

export default api;
