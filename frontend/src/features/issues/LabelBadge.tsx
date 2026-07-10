import type { Label } from './types';
import { cn } from '@/lib/utils';

/** Puce colorée d'un label (fond teinté + texte à la couleur du label). */
export function LabelBadge({
  label,
  className,
}: {
  label: Pick<Label, 'name' | 'color'>;
  className?: string;
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium',
        className
      )}
      style={{ backgroundColor: `${label.color}22`, color: label.color }}
    >
      {label.name}
    </span>
  );
}
