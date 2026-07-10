import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Search } from 'lucide-react';

import { Input } from '@/components/ui/input';
import { IssueTypeBadge } from '@/components/IssueTypeBadge';
import { StatusBadge } from '@/components/StatusBadge';
import { ProjectKeyBadge } from '@/features/projects/ProjectKeyBadge';
import { fetchSearch } from './api';
import { queryKeys } from '@/lib/queryKeys';

export function GlobalSearch() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);

  // Raccourci « / » : focus le champ (émis par le hook de raccourcis).
  useEffect(() => {
    const focus = () => inputRef.current?.focus();
    window.addEventListener('jirou:focus-search', focus);
    return () => window.removeEventListener('jirou:focus-search', focus);
  }, []);

  const { data } = useQuery({
    queryKey: queryKeys.search.query(q.trim()),
    queryFn: () => fetchSearch(q.trim()),
    enabled: q.trim().length >= 2,
  });

  function go(path: string) {
    setOpen(false);
    setQ('');
    navigate(path);
  }

  const hasResults =
    data && (data.issues.length > 0 || data.projects.length > 0);

  return (
    <div className="relative ml-2 hidden max-w-md flex-1 sm:block">
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        ref={inputRef}
        type="search"
        placeholder="Rechercher… ( / )"
        aria-label="Rechercher"
        className="pl-9"
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            setOpen(false);
            inputRef.current?.blur();
          }
        }}
        onBlur={() => window.setTimeout(() => setOpen(false), 150)}
      />

      {open && q.trim().length >= 2 && (
        <div className="absolute left-0 right-0 top-11 z-50 max-h-96 overflow-y-auto rounded-md border border-border bg-background shadow-lg">
          {!hasResults && (
            <p className="px-3 py-4 text-sm text-muted-foreground">
              Aucun résultat.
            </p>
          )}
          {data && data.projects.length > 0 && (
            <div className="p-1">
              <p className="px-2 py-1 text-xs font-semibold uppercase text-muted-foreground">
                Projets
              </p>
              {data.projects.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => go(`/projects/${p.id}`)}
                  className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-muted"
                >
                  <ProjectKeyBadge projectKey={p.key} color={p.color} />
                  <span className="truncate">{p.name}</span>
                </button>
              ))}
            </div>
          )}
          {data && data.issues.length > 0 && (
            <div className="p-1">
              <p className="px-2 py-1 text-xs font-semibold uppercase text-muted-foreground">
                Tickets
              </p>
              {data.issues.map((i) => (
                <button
                  key={i.key}
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => go(`/projects/${i.project_id}/issues/${i.key}`)}
                  className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-muted"
                >
                  <IssueTypeBadge type={i.type} showLabel={false} />
                  <span className="font-mono text-xs text-muted-foreground">
                    {i.key}
                  </span>
                  <span className="flex-1 truncate">{i.summary}</span>
                  <StatusBadge status={i.status} />
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
