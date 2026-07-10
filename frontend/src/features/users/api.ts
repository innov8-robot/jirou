import api from '@/lib/api';
import type { User, UserRole } from '@/features/auth/types';

/** PATCH /users/me — met à jour le profil courant. */
export async function updateProfile(payload: {
  full_name?: string;
  avatar_url?: string | null;
}): Promise<User> {
  const { data } = await api.patch<User>('/users/me', payload);
  return data;
}

/** PUT /users/me/password — change le mot de passe courant (204). */
export async function changePassword(payload: {
  current_password: string;
  new_password: string;
}): Promise<void> {
  await api.put('/users/me/password', payload);
}

/** GET /users — liste des utilisateurs (admin uniquement). */
export async function fetchUsers(): Promise<User[]> {
  const { data } = await api.get<User[]>('/users');
  return data;
}

/** PATCH /users/{id} — modifie rôle/activation (admin uniquement). */
export async function adminUpdateUser(
  userId: number | string,
  payload: { role?: UserRole; is_active?: boolean }
): Promise<User> {
  const { data } = await api.patch<User>(`/users/${userId}`, payload);
  return data;
}
