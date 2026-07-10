import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { cn } from '@/lib/utils';

/** Rendu d'un contenu Markdown (GFM : tables, listes de tâches, etc.). */
export function MarkdownView({
  content,
  className,
}: {
  content: string;
  className?: string;
}) {
  if (!content.trim()) {
    return (
      <p className={cn('text-sm italic text-muted-foreground', className)}>
        Document vide.
      </p>
    );
  }
  return (
    <div
      className={cn(
        'prose prose-sm max-w-none dark:prose-invert prose-headings:font-semibold prose-a:text-primary',
        className
      )}
    >
      <Markdown remarkPlugins={[remarkGfm]}>{content}</Markdown>
    </div>
  );
}
