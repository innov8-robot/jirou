import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { cn } from '@/lib/utils';

interface UserAvatarProps {
  name: string;
  /** Optional photo URL; falls back to initials when absent or failing. */
  src?: string | null;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const SIZES: Record<NonNullable<UserAvatarProps['size']>, string> = {
  sm: 'h-6 w-6 text-[10px]',
  md: 'h-9 w-9 text-sm',
  lg: 'h-12 w-12 text-base',
};

/** Deterministic background derived from the name for stable avatar colors. */
const PALETTE = [
  '#6D5AE6',
  '#8B5CF6',
  '#3B82F6',
  '#22C55E',
  '#F59E0B',
  '#EF4444',
  '#0EA5E9',
];

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function colorFor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i += 1) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return PALETTE[Math.abs(hash) % PALETTE.length];
}

/**
 * Avatar for a user: shows the photo when available, otherwise colored
 * initials. The fallback color is stable per name.
 */
export function UserAvatar({
  name,
  src,
  size = 'md',
  className,
}: UserAvatarProps) {
  return (
    <Avatar className={cn(SIZES[size], className)}>
      {src ? <AvatarImage src={src} alt={name} /> : null}
      <AvatarFallback
        style={{ backgroundColor: colorFor(name), color: '#fff' }}
      >
        {initials(name)}
      </AvatarFallback>
    </Avatar>
  );
}
