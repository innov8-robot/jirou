import { useState, type FormEvent } from 'react';
import { useMutation } from '@tanstack/react-query';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { UserAvatar } from '@/components/UserAvatar';
import { changePassword, updateProfile } from '@/features/users/api';
import { useAuth } from '@/features/auth/useAuth';
import { useAuthStore } from '@/stores/authStore';
import { getErrorMessage, toast } from '@/lib/toast';

const MIN_PASSWORD_LENGTH = 8;

function ProfileSection() {
  const { user } = useAuth();
  const setUser = useAuthStore((s) => s.setUser);

  const [fullName, setFullName] = useState(user?.full_name ?? '');
  const [avatarUrl, setAvatarUrl] = useState(user?.avatar_url ?? '');

  const mutation = useMutation({
    mutationFn: () =>
      updateProfile({
        full_name: fullName,
        avatar_url: avatarUrl.trim() === '' ? null : avatarUrl.trim(),
      }),
    onSuccess: (updated) => {
      setUser(updated);
      toast.success('Profil mis à jour');
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    mutation.mutate();
  }

  return (
    <section className="rounded-lg border border-border p-6">
      <h2 className="mb-4 text-lg font-semibold">Profil</h2>
      <div className="mb-4 flex items-center gap-3">
        <UserAvatar name={fullName || user?.email || '?'} src={avatarUrl} size="lg" />
        <span className="text-sm text-muted-foreground">{user?.email}</span>
      </div>
      <form className="space-y-4" onSubmit={handleSubmit}>
        <div className="space-y-1.5">
          <Label htmlFor="full_name">Nom complet</Label>
          <Input
            id="full_name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="avatar_url">URL de l'avatar</Label>
          <Input
            id="avatar_url"
            placeholder="https://…"
            value={avatarUrl}
            onChange={(e) => setAvatarUrl(e.target.value)}
          />
        </div>
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? 'Enregistrement…' : 'Enregistrer'}
        </Button>
      </form>
    </section>
  );
}

function PasswordSection() {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      changePassword({ current_password: current, new_password: next }),
    onSuccess: () => {
      toast.success('Mot de passe modifié');
      setCurrent('');
      setNext('');
      setConfirm('');
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (next.length < MIN_PASSWORD_LENGTH) {
      setError(`Le nouveau mot de passe doit faire au moins ${MIN_PASSWORD_LENGTH} caractères.`);
      return;
    }
    if (next !== confirm) {
      setError('La confirmation ne correspond pas.');
      return;
    }
    mutation.mutate();
  }

  return (
    <section className="rounded-lg border border-border p-6">
      <h2 className="mb-4 text-lg font-semibold">Mot de passe</h2>
      <form className="space-y-4" onSubmit={handleSubmit} noValidate>
        <div className="space-y-1.5">
          <Label htmlFor="current_password">Mot de passe actuel</Label>
          <Input
            id="current_password"
            type="password"
            autoComplete="current-password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="new_password">Nouveau mot de passe</Label>
          <Input
            id="new_password"
            type="password"
            autoComplete="new-password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="confirm_password">Confirmation</Label>
          <Input
            id="confirm_password"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
        </div>
        {error && (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        )}
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? 'Modification…' : 'Changer le mot de passe'}
        </Button>
      </form>
    </section>
  );
}

export default function ProfilePage() {
  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <h1 className="text-2xl font-bold">Mon profil</h1>
      <ProfileSection />
      <PasswordSection />
    </div>
  );
}
