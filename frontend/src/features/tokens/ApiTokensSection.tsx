import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, Copy, KeyRound, Plus } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  createApiToken,
  fetchApiTokens,
  revokeApiToken,
  type ApiToken,
} from './api';
import { queryKeys } from '@/lib/queryKeys';
import { getErrorMessage, toast } from '@/lib/toast';

const NEVER = 'never';

/** Durées de vie proposées, en jours (`never` = sans expiration). */
const EXPIRY_CHOICES: { value: string; label: string }[] = [
  { value: NEVER, label: "Pas d'expiration" },
  { value: '30', label: '30 jours' },
  { value: '90', label: '90 jours' },
  { value: '365', label: '1 an' },
];

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

/** Étiquette d'état : révoqué, expiré, ou actif. */
function tokenStatus(token: ApiToken): { label: string; className: string } {
  if (token.revoked_at) {
    return { label: 'Révoqué', className: 'text-destructive' };
  }
  if (token.expires_at && new Date(token.expires_at) <= new Date()) {
    return { label: 'Expiré', className: 'text-destructive' };
  }
  return { label: 'Actif', className: 'text-status-done' };
}

/** Encart affiché une seule fois après création, avec le secret et le copier. */
function NewTokenBanner({
  token,
  onDismiss,
}: {
  token: string;
  onDismiss: () => void;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(token);
      setCopied(true);
      toast.success('Jeton copié');
    } catch {
      toast.error('Copie impossible', 'Sélectionnez le jeton et copiez-le à la main.');
    }
  }

  return (
    <div className="space-y-2 rounded-md border border-primary/40 bg-primary/5 p-3">
      <p className="text-sm font-medium">
        Copiez ce jeton maintenant — il ne sera plus affiché.
      </p>
      <div className="flex items-center gap-2">
        <code className="min-w-0 flex-1 overflow-x-auto whitespace-nowrap rounded bg-background px-2 py-1.5 font-mono text-xs">
          {token}
        </code>
        <Button size="sm" variant="outline" onClick={copy}>
          {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          {copied ? 'Copié' : 'Copier'}
        </Button>
      </div>
      <Button size="sm" variant="ghost" onClick={onDismiss}>
        J'ai copié le jeton
      </Button>
    </div>
  );
}

/**
 * Gestion des jetons d'API personnels : accès machine à l'API Jirou (serveur
 * MCP pour Claude Code, scripts, CI) sans confier le mot de passe du compte.
 *
 * Un jeton porte exactement les droits de son propriétaire et se révoque
 * individuellement. Le secret n'est visible qu'à la création.
 */
export function ApiTokensSection() {
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [expiry, setExpiry] = useState<string>(NEVER);
  const [freshToken, setFreshToken] = useState<string | null>(null);

  const { data: tokens = [], isLoading } = useQuery({
    queryKey: queryKeys.apiTokens.list,
    queryFn: fetchApiTokens,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: queryKeys.apiTokens.list });

  const createMut = useMutation({
    mutationFn: () =>
      createApiToken({
        name: name.trim(),
        expires_in_days: expiry === NEVER ? null : Number(expiry),
      }),
    onSuccess: (created) => {
      setFreshToken(created.token);
      setName('');
      setExpiry(NEVER);
      invalidate();
      toast.success('Jeton créé');
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  const revokeMut = useMutation({
    mutationFn: (id: number) => revokeApiToken(id),
    onSuccess: () => {
      invalidate();
      toast.success('Jeton révoqué');
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (name.trim()) createMut.mutate();
  }

  return (
    <section className="rounded-lg border border-border p-6">
      <div className="mb-1 flex items-center gap-2">
        <KeyRound className="h-4 w-4 text-muted-foreground" />
        <h2 className="text-lg font-semibold">Jetons d'API</h2>
      </div>
      <p className="mb-4 text-sm text-muted-foreground">
        Donnent accès à l'API avec vos droits, sans votre mot de passe — pour le
        serveur MCP de Claude Code, un script ou une CI. Révocables à tout moment.
      </p>

      {freshToken && (
        <div className="mb-4">
          <NewTokenBanner token={freshToken} onDismiss={() => setFreshToken(null)} />
        </div>
      )}

      <form className="mb-5 flex flex-wrap items-end gap-2" onSubmit={handleSubmit}>
        <div className="min-w-48 flex-1 space-y-1.5">
          <Label htmlFor="token_name">Nom du jeton</Label>
          <Input
            id="token_name"
            placeholder="Claude Code — portable"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={100}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Expiration</Label>
          <Select value={expiry} onValueChange={setExpiry}>
            <SelectTrigger className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {EXPIRY_CHOICES.map((choice) => (
                <SelectItem key={choice.value} value={choice.value}>
                  {choice.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button type="submit" disabled={!name.trim() || createMut.isPending}>
          <Plus className="h-4 w-4" />
          {createMut.isPending ? 'Création…' : 'Créer'}
        </Button>
      </form>

      {isLoading && <p className="text-sm text-muted-foreground">Chargement…</p>}

      {!isLoading && tokens.length === 0 && (
        <p className="text-sm text-muted-foreground">Aucun jeton pour le moment.</p>
      )}

      {tokens.length > 0 && (
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border bg-surface text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">Nom</th>
                <th className="px-3 py-2 font-medium">Jeton</th>
                <th className="px-3 py-2 font-medium">État</th>
                <th className="px-3 py-2 font-medium">Dernier usage</th>
                <th className="px-3 py-2 font-medium">Expire</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {tokens.map((token) => {
                const status = tokenStatus(token);
                return (
                  <tr key={token.id} className="border-b border-border last:border-0">
                    <td className="px-3 py-2 font-medium">{token.name}</td>
                    <td className="whitespace-nowrap px-3 py-2 font-mono text-xs text-muted-foreground">
                      {token.prefix}…
                    </td>
                    <td className={`px-3 py-2 text-xs font-medium ${status.className}`}>
                      {status.label}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 text-xs text-muted-foreground">
                      {formatDate(token.last_used_at)}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 text-xs text-muted-foreground">
                      {token.expires_at ? formatDate(token.expires_at) : 'Jamais'}
                    </td>
                    <td className="px-3 py-2 text-right">
                      {!token.revoked_at && (
                        <button
                          type="button"
                          className="text-xs text-muted-foreground hover:text-destructive"
                          disabled={revokeMut.isPending}
                          onClick={() => {
                            if (
                              confirm(
                                `Révoquer « ${token.name} » ? Tout client qui l'utilise perdra l'accès immédiatement.`
                              )
                            )
                              revokeMut.mutate(token.id);
                          }}
                        >
                          Révoquer
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
