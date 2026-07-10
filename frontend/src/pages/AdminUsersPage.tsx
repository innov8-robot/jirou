import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { UserAvatar } from '@/components/UserAvatar';
import { EmptyState } from '@/components/EmptyState';
import { ErrorState } from '@/components/ErrorState';
import { ListSkeleton } from '@/components/LoadingSkeletons';
import { adminUpdateUser, fetchUsers } from '@/features/users/api';
import type { User, UserRole } from '@/features/auth/types';
import { useAuth } from '@/features/auth/useAuth';
import { queryKeys } from '@/lib/queryKeys';
import { getErrorMessage, toast } from '@/lib/toast';

const ROLES: UserRole[] = ['admin', 'member', 'viewer'];

function UserRow({ user, isSelf }: { user: User; isSelf: boolean }) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (payload: { role?: UserRole; is_active?: boolean }) =>
      adminUpdateUser(user.id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.all });
      toast.success('Utilisateur mis à jour');
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  return (
    <tr className="border-b border-border last:border-0">
      <td className="py-3 pr-4">
        <div className="flex items-center gap-3">
          <UserAvatar name={user.full_name || user.email} src={user.avatar_url} size="sm" />
          <div className="min-w-0">
            <div className="truncate font-medium">
              {user.full_name}
              {isSelf && (
                <span className="ml-2 text-xs text-muted-foreground">(vous)</span>
              )}
            </div>
            <div className="truncate text-sm text-muted-foreground">{user.email}</div>
          </div>
        </div>
      </td>
      <td className="py-3 pr-4">
        <Select
          value={user.role}
          onValueChange={(role) => mutation.mutate({ role: role as UserRole })}
          disabled={isSelf || mutation.isPending}
        >
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ROLES.map((role) => (
              <SelectItem key={role} value={role}>
                {role}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </td>
      <td className="py-3 pr-4">
        <span
          className={
            user.is_active
              ? 'inline-flex rounded-full bg-status-done/15 px-2 py-0.5 text-xs font-medium text-status-done'
              : 'inline-flex rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground'
          }
        >
          {user.is_active ? 'Actif' : 'Désactivé'}
        </span>
      </td>
      <td className="py-3 text-right">
        <Button
          variant="outline"
          size="sm"
          disabled={isSelf || mutation.isPending}
          onClick={() => mutation.mutate({ is_active: !user.is_active })}
        >
          {user.is_active ? 'Désactiver' : 'Activer'}
        </Button>
      </td>
    </tr>
  );
}

export default function AdminUsersPage() {
  const { user: currentUser } = useAuth();
  const query = useQuery({
    queryKey: queryKeys.users.list(),
    queryFn: fetchUsers,
  });

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold">Utilisateurs</h1>
        <p className="text-sm text-muted-foreground">
          Gérer les rôles et l'activation des comptes.
        </p>
      </div>

      {query.isLoading && <ListSkeleton />}

      {query.isError && (
        <ErrorState
          description="Impossible de charger les utilisateurs."
          onRetry={() => query.refetch()}
        />
      )}

      {query.data && query.data.length === 0 && (
        <EmptyState title="Aucun utilisateur" description="La liste est vide." />
      )}

      {query.data && query.data.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border bg-surface text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-2 font-medium">Utilisateur</th>
                <th className="px-4 py-2 font-medium">Rôle</th>
                <th className="px-4 py-2 font-medium">Statut</th>
                <th className="px-4 py-2 text-right font-medium">Action</th>
              </tr>
            </thead>
            <tbody>
              {query.data.map((u) => (
                <UserRow
                  key={u.id}
                  user={u}
                  isSelf={u.id === currentUser?.id}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
