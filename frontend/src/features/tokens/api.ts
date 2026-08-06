import api from '@/lib/api';

/** Métadonnées d'un jeton d'API personnel — le secret n'y figure jamais. */
export interface ApiToken {
  id: number;
  name: string;
  /** Début du jeton, pour le reconnaître (ex. `jir_pat_AbCd`). */
  prefix: string;
  last_used_at: string | null;
  expires_at: string | null;
  /** Non nul = jeton révoqué, donc inutilisable. */
  revoked_at: string | null;
  created_at: string;
}

/** Jeton fraîchement créé : seule réponse à porter le secret en clair. */
export interface ApiTokenCreated extends ApiToken {
  token: string;
}

/** GET /users/me/tokens — mes jetons, les plus récents d'abord. */
export async function fetchApiTokens(): Promise<ApiToken[]> {
  const { data } = await api.get<ApiToken[]>('/users/me/tokens');
  return data;
}

/**
 * POST /users/me/tokens — crée un jeton. La réponse est la **seule** occasion
 * de lire le secret : il n'est pas récupérable ensuite.
 */
export async function createApiToken(payload: {
  name: string;
  expires_in_days?: number | null;
}): Promise<ApiTokenCreated> {
  const { data } = await api.post<ApiTokenCreated>('/users/me/tokens', {
    name: payload.name,
    expires_in_days: payload.expires_in_days ?? null,
  });
  return data;
}

/** DELETE /users/me/tokens/{id} — révoque un jeton (accès coupé immédiatement). */
export async function revokeApiToken(id: number): Promise<void> {
  await api.delete(`/users/me/tokens/${id}`);
}
