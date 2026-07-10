import { FileQuestion } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { IssueTypeBadge } from '@/components/IssueTypeBadge';
import { StatusBadge } from '@/components/StatusBadge';
import { PriorityIcon } from '@/components/PriorityIcon';
import { UserAvatar } from '@/components/UserAvatar';
import { StoryPoints } from '@/components/StoryPoints';
import { EmptyState } from '@/components/EmptyState';
import { ErrorState } from '@/components/ErrorState';
import { ListSkeleton, BoardSkeleton } from '@/components/LoadingSkeletons';
import {
  ISSUE_STATUSES,
  ISSUE_TYPES,
  PRIORITIES,
  STORY_POINT_SCALE,
} from '@/lib/issues';
import { toast } from '@/lib/toast';
import { useUiStore } from '@/stores/uiStore';

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold text-foreground">{title}</h2>
      {children}
    </section>
  );
}

/**
 * Internal styleguide (JIR-18): visual catalog + smoke test of the Jirou
 * design system — palette, transverse components, states, toasts and the
 * global create modal.
 */
export default function StyleguidePage() {
  const openCreateIssue = useUiStore((s) => s.openCreateIssue);

  return (
    <div className="mx-auto max-w-4xl space-y-10 px-6 py-8">
      <header>
        <h1 className="text-2xl font-bold text-primary">Jirou Styleguide</h1>
        <p className="text-sm text-muted-foreground">
          Design system EPIC-03 — composants transverses, états, toasts.
        </p>
      </header>

      <Section title="Buttons">
        <div className="flex flex-wrap gap-3">
          <Button>Default</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="destructive">Destructive</Button>
          <Button variant="link">Link</Button>
        </div>
      </Section>

      <Section title="Input">
        <Input placeholder="Rechercher un ticket…" className="max-w-sm" />
      </Section>

      <Section title="IssueTypeBadge">
        <div className="flex flex-wrap items-center gap-4">
          {ISSUE_TYPES.map((t) => (
            <IssueTypeBadge key={t} type={t} />
          ))}
        </div>
      </Section>

      <Section title="StatusBadge">
        <div className="flex flex-wrap items-center gap-3">
          {ISSUE_STATUSES.map((s) => (
            <StatusBadge key={s} status={s} />
          ))}
        </div>
      </Section>

      <Section title="PriorityIcon">
        <div className="flex flex-wrap items-center gap-4">
          {PRIORITIES.map((p) => (
            <PriorityIcon key={p} priority={p} showLabel />
          ))}
        </div>
      </Section>

      <Section title="UserAvatar">
        <div className="flex items-center gap-4">
          <UserAvatar name="Thomas Gossin" size="sm" />
          <UserAvatar name="Ada Lovelace" size="md" />
          <UserAvatar name="Grace Hopper" size="lg" />
          <UserAvatar
            name="Avec photo"
            src="https://i.pravatar.cc/80"
            size="lg"
          />
        </div>
      </Section>

      <Section title="StoryPoints">
        <div className="flex items-center gap-3">
          {STORY_POINT_SCALE.map((sp) => (
            <StoryPoints key={sp} points={sp} />
          ))}
        </div>
      </Section>

      <Section title="Toasts">
        <div className="flex flex-wrap gap-3">
          <Button
            variant="outline"
            onClick={() =>
              toast.success('Action réussie', 'Le ticket a été mis à jour.')
            }
          >
            Toast succès
          </Button>
          <Button
            variant="outline"
            onClick={() =>
              toast.error('Échec', 'Impossible de contacter le serveur.')
            }
          >
            Toast erreur
          </Button>
          <Button variant="outline" onClick={() => toast.info('Information')}>
            Toast info
          </Button>
        </div>
      </Section>

      <Section title="CreateIssueModal">
        <div className="space-y-2">
          <Button onClick={openCreateIssue}>
            Ouvrir la modale de création
          </Button>
          <p className="text-sm text-muted-foreground">
            Raccourci clavier : appuyez sur{' '}
            <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 text-xs">
              c
            </kbd>{' '}
            n&apos;importe où.
          </p>
        </div>
      </Section>

      <Section title="EmptyState">
        <EmptyState
          icon={FileQuestion}
          title="Aucun résultat"
          description="Aucun ticket ne correspond à votre recherche."
          actionLabel="Créer un ticket"
          onAction={openCreateIssue}
        />
      </Section>

      <Section title="ErrorState">
        <ErrorState onRetry={() => toast.info('Nouvelle tentative…')} />
      </Section>

      <Section title="ListSkeleton">
        <ListSkeleton rows={3} />
      </Section>

      <Section title="BoardSkeleton">
        <BoardSkeleton columns={3} cardsPerColumn={2} />
      </Section>
    </div>
  );
}
