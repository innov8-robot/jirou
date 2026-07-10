import type { UserRole } from '@/features/auth/types';

/** Rôle d'un utilisateur AU SEIN d'un projet (même échelle que les rôles globaux). */
export type ProjectRole = UserRole;

export interface Project {
  id: number | string;
  name: string;
  key: string;
  description: string | null;
  color: string | null;
  lead_id: number | string;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  member_count: number;
  /** Rôle du user courant dans ce projet (null si admin global non-membre). */
  my_role: ProjectRole | null;
}

export interface ProjectMember {
  user_id: number | string;
  role: ProjectRole;
  joined_at: string;
  user: {
    id: number | string;
    email: string;
    full_name: string;
    avatar_url: string | null;
    role: UserRole;
  };
}

export interface ProjectDetail extends Project {
  members: ProjectMember[];
}

export interface CreateProjectPayload {
  name: string;
  key: string;
  description?: string;
  color?: string;
}

export interface UpdateProjectPayload {
  name?: string;
  description?: string | null;
  color?: string | null;
  is_archived?: boolean;
}
