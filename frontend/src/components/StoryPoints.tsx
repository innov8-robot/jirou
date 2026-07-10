import { cn } from '@/lib/utils';

interface StoryPointsProps {
  points: number | null | undefined;
  className?: string;
}

/**
 * Small rounded pill showing an issue's story-point estimate. Renders
 * nothing when no estimate is set.
 */
export function StoryPoints({ points, className }: StoryPointsProps) {
  if (points == null) return null;

  return (
    <span
      className={cn(
        'inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-secondary px-1.5 text-xs font-semibold text-secondary-foreground',
        className
      )}
      title={`${points} story points`}
    >
      {points}
    </span>
  );
}
