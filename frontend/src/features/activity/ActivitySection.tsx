import { useQuery } from '@tanstack/react-query';

import { UserAvatar } from '@/components/UserAvatar';
import { fetchActivity, type ActivityEntry } from './api';
import { queryKeys } from '@/lib/queryKeys';

const FIELD_LABEL: Record<string, string> = {
  status: 'le statut',
  assignee_id: "l'assigné",
  priority: 'la priorité',
  story_points: 'les points',
  summary: 'le résumé',
  sprint_id: 'le sprint',
};

function describe(a: ActivityEntry): string {
  const who = a.actor?.full_name || 'Quelqu’un';
  if (a.action === 'created') return `${who} a créé le ticket`;
  if (a.action === 'commented') return `${who} a commenté`;
  if (a.action === 'updated') {
    const f = a.field ? (FIELD_LABEL[a.field] ?? a.field) : 'un champ';
    return `${who} a modifié ${f} : ${a.old_value ?? '—'} → ${a.new_value ?? '—'}`;
  }
  return `${who} — ${a.action}`;
}

function relTime(iso: string): string {
  const min = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (min < 1) return "à l'instant";
  if (min < 60) return `il y a ${min} min`;
  const h = Math.round(min / 60);
  if (h < 24) return `il y a ${h} h`;
  return `il y a ${Math.round(h / 24)} j`;
}

export function ActivitySection({ issueKey }: { issueKey: string }) {
  const { data = [] } = useQuery({
    queryKey: queryKeys.activity.list(issueKey),
    queryFn: () => fetchActivity(issueKey),
  });

  return (
    <section>
      <h2 className="mb-3 text-sm font-semibold text-muted-foreground">
        Activité
      </h2>
      {data.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucune activité.</p>
      ) : (
        <ul className="space-y-2">
          {data.map((a) => (
            <li key={a.id} className="flex items-center gap-2 text-sm">
              <UserAvatar
                name={a.actor?.full_name || '?'}
                src={a.actor?.avatar_url}
                size="sm"
              />
              <span className="flex-1">{describe(a)}</span>
              <span className="shrink-0 text-xs text-muted-foreground">
                {relTime(a.created_at)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
