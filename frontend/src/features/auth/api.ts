import api from '@/lib/api';

import type { AuthTokens, LoginPayload, RegisterPayload, User } from './types';

/** POST /auth/register → crée un compte (rôle `member` par défaut). */
export async function registerRequest(payload: RegisterPayload): Promise<User> {
  const { data } = await api.post<User>('/auth/register', payload);
  return data;
}

/** POST /auth/login → access + refresh tokens. */
export async function loginRequest(payload: LoginPayload): Promise<AuthTokens> {
  const { data } = await api.post<AuthTokens>('/auth/login', payload);
  return data;
}

/** GET /auth/me → utilisateur courant (à partir du Bearer token). */
export async function meRequest(): Promise<User> {
  const { data } = await api.get<User>('/auth/me');
  return data;
}
