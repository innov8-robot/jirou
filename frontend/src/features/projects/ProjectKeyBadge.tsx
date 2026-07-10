import { cn } from '@/lib/utils';
import { DEFAULT_PROJECT_COLOR } from './colors';

interface ProjectKeyBadgeProps {
  projectKey: string;
  color?: string | null;
  className?: string;
}

/** Carré coloré affichant les 1-2 premières lettres de la clé du projet. */
export function ProjectKeyBadge({
  projectKey,
  color,
  className,
}: ProjectKeyBadgeProps) {
  return (
    <span
      className={cn(
        'flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-xs font-bold text-white',
        className
      )}
      style={{ backgroundColor: color ?? DEFAULT_PROJECT_COLOR }}
      aria-hidden
    >
      {projectKey.slice(0, 2)}
    </span>
  );
}
