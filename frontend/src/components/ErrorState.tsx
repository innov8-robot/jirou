import { AlertTriangle, RefreshCw } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface ErrorStateProps {
  title?: string;
  description?: string;
  /** Retry handler; when provided a "Réessayer" button is shown. */
  onRetry?: () => void;
  className?: string;
}

/**
 * Reusable error panel with an optional retry action. Pair with TanStack
 * Query's `isError` / `refetch`, or with the {@link ErrorBoundary}.
 */
export function ErrorState({
  title = 'Une erreur est survenue',
  description = 'Impossible de charger ces données pour le moment.',
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        'flex flex-col items-center justify-center rounded-lg border border-destructive/30 bg-destructive/5 px-6 py-12 text-center',
        className
      )}
    >
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-destructive/10">
        <AlertTriangle
          className="h-7 w-7 text-destructive"
          aria-hidden="true"
        />
      </div>
      <h3 className="text-base font-semibold text-foreground">{title}</h3>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">
        {description}
      </p>
      {onRetry && (
        <Button variant="outline" className="mt-5" onClick={onRetry}>
          <RefreshCw className="h-4 w-4" />
          Réessayer
        </Button>
      )}
    </div>
  );
}
