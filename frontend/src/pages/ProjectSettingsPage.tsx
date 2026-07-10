import { useState, type FormEvent } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { UserAvatar } from '@/components/UserAvatar';
import { cn } from '@/lib/utils';
import { queryKeys } from '@/lib/queryKeys';
import { getErrorMessage, toast } from '@/lib/toast';
import {
  addMember,
  archiveProject,
  removeMember,
  updateMember,
  updateProject,
} from '@/features/projects/api';
import { PROJECT_COLORS } from '@/features/projects/colors';
import { ProjectLabelsSection } from '@/features/issues/ProjectLabelsSection';
import { useProject } from '@/features/projects/useProject';
import type { ProjectRole } from '@/features/projects/types';

const ROLES: ProjectRole[] = ['admin', 'member', 'viewer'];

export default function ProjectSettingsPage() {
  const { project } = useProject();
  const canManage = project.my_role === 'admin';

  const queryClient = useQueryClient();
  const invalidate = () => {
    queryClient.invalidateQueries({
      queryKey: queryKeys.projects.detail(project.id),
    });
    queryClient.invalidateQueries({ queryKey: queryKeys.projects.all });
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <GeneralSection
        canManage={canManage}
        onSaved={invalidate}
      />
      <MembersSection canManage={canManage} onChanged={invalidate} />
      <ProjectLabelsSection
        projectId={project.id}
        canEdit={project.my_role === 'admin' || project.my_role === 'member'}
      />
      {canManage && <DangerSection />}
    </div>
  );
}

function GeneralSection({
  canManage,
  onSaved,
}: {
  canManage: boolean;
  onSaved: () => void;
}) {
  const { project } = useProject();
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description ?? '');
  const [color, setColor] = useState(project.color ?? PROJECT_COLORS[0]);

  const mutation = useMutation({
    mutationFn: () =>
      updateProject(project.id, {
        name: name.trim(),
        description: description.trim() || null,
        color,
      }),
    onSuccess: () => {
      onSaved();
      toast.success('Projet mis à jour');
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    mutation.mutate();
  }

  return (
    <section className="rounded-lg border border-border p-6">
      <h2 className="mb-4 text-lg font-semibold">Général</h2>
      <form className="space-y-4" onSubmit={handleSubmit}>
        <div className="space-y-1.5">
          <Label htmlFor="name">Nom</Label>
          <Input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={!canManage}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="description">Description</Label>
          <Textarea
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            disabled={!canManage}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Couleur</Label>
          <div className="flex flex-wrap gap-2">
            {PROJECT_COLORS.map((c) => (
              <button
                key={c}
                type="button"
                aria-label={`Couleur ${c}`}
                disabled={!canManage}
                onClick={() => setColor(c)}
                className={cn(
                  'h-7 w-7 rounded-full ring-offset-2 ring-offset-background transition disabled:opacity-50',
                  color === c && 'ring-2 ring-foreground'
                )}
                style={{ backgroundColor: c }}
              />
            ))}
          </div>
        </div>
        {canManage && (
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? 'Enregistrement…' : 'Enregistrer'}
          </Button>
        )}
      </form>
    </section>
  );
}

function MembersSection({
  canManage,
  onChanged,
}: {
  canManage: boolean;
  onChanged: () => void;
}) {
  const { project } = useProject();
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<ProjectRole>('member');

  const addMutation = useMutation({
    mutationFn: () => addMember(project.id, { email: email.trim(), role }),
    onSuccess: () => {
      onChanged();
      toast.success('Membre ajouté');
      setEmail('');
      setRole('member');
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  const roleMutation = useMutation({
    mutationFn: ({ userId, newRole }: { userId: number | string; newRole: ProjectRole }) =>
      updateMember(project.id, userId, { role: newRole }),
    onSuccess: () => {
      onChanged();
      toast.success('Rôle mis à jour');
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  const removeMutation = useMutation({
    mutationFn: (userId: number | string) => removeMember(project.id, userId),
    onSuccess: () => {
      onChanged();
      toast.success('Membre retiré');
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  return (
    <section className="rounded-lg border border-border p-6">
      <h2 className="mb-4 text-lg font-semibold">Membres</h2>

      <ul className="mb-4 divide-y divide-border">
        {project.members.map((m) => (
          <li key={m.user_id} className="flex items-center gap-3 py-3">
            <UserAvatar
              name={m.user.full_name || m.user.email}
              src={m.user.avatar_url}
              size="sm"
            />
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium">
                {m.user.full_name}
                {m.user_id === project.lead_id && (
                  <span className="ml-2 text-xs text-primary">lead</span>
                )}
              </div>
              <div className="truncate text-xs text-muted-foreground">
                {m.user.email}
              </div>
            </div>

            {canManage ? (
              <>
                <Select
                  value={m.role}
                  onValueChange={(newRole) =>
                    roleMutation.mutate({
                      userId: m.user_id,
                      newRole: newRole as ProjectRole,
                    })
                  }
                  disabled={roleMutation.isPending}
                >
                  <SelectTrigger className="w-28">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ROLES.map((r) => (
                      <SelectItem key={r} value={r}>
                        {r}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={removeMutation.isPending}
                  onClick={() => removeMutation.mutate(m.user_id)}
                >
                  Retirer
                </Button>
              </>
            ) : (
              <span className="text-xs text-muted-foreground">{m.role}</span>
            )}
          </li>
        ))}
      </ul>

      {canManage && (
        <form
          className="flex flex-col gap-2 sm:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            if (email.trim()) addMutation.mutate();
          }}
        >
          <Input
            type="email"
            placeholder="email@exemple.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="flex-1"
          />
          <Select value={role} onValueChange={(r) => setRole(r as ProjectRole)}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ROLES.map((r) => (
                <SelectItem key={r} value={r}>
                  {r}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button type="submit" disabled={addMutation.isPending}>
            Ajouter
          </Button>
        </form>
      )}
    </section>
  );
}

function DangerSection() {
  const { project } = useProject();
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const mutation = useMutation({
    mutationFn: () => archiveProject(project.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.all });
      toast.success('Projet archivé');
      navigate('/projects');
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  return (
    <section className="rounded-lg border border-destructive/40 p-6">
      <h2 className="mb-2 text-lg font-semibold text-destructive">
        Zone de danger
      </h2>
      <p className="mb-4 text-sm text-muted-foreground">
        L'archivage masque le projet de la liste. Les données sont conservées.
      </p>
      <Button
        variant="destructive"
        disabled={mutation.isPending || project.is_archived}
        onClick={() => mutation.mutate()}
      >
        {project.is_archived ? 'Déjà archivé' : 'Archiver le projet'}
      </Button>
    </section>
  );
}
