import { useQuery } from '@tanstack/react-query';

import { fetchVelocity } from './api';
import { queryKeys } from '@/lib/queryKeys';

/** Graphe de vélocité (JIR-53) : points engagés vs complétés par sprint clôturé. */
export function VelocityChart({ projectId }: { projectId: number | string }) {
  const { data = [] } = useQuery({
    queryKey: queryKeys.velocity.view(projectId),
    queryFn: () => fetchVelocity(projectId),
  });

  if (data.length === 0) return null;

  const max = Math.max(
    1,
    ...data.map((d) => Math.max(d.committed_points, d.completed_points))
  );

  return (
    <section className="rounded-lg border border-border p-4">
      <h2 className="mb-1 text-lg font-semibold">Vélocité</h2>
      <p className="mb-4 text-xs text-muted-foreground">
        Points engagés (gris) vs complétés (violet) par sprint clôturé.
      </p>
      <div className="flex items-end gap-4 overflow-x-auto pb-2" style={{ height: 160 }}>
        {data.map((d) => (
          <div key={d.sprint_id} className="flex flex-col items-center gap-1">
            <div className="flex items-end gap-1" style={{ height: 120 }}>
              <Bar value={d.committed_points} max={max} className="bg-muted-foreground/40" />
              <Bar value={d.completed_points} max={max} className="bg-primary" />
            </div>
            <span className="max-w-20 truncate text-xs text-muted-foreground" title={d.name}>
              {d.name}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

function Bar({
  value,
  max,
  className,
}: {
  value: number;
  max: number;
  className: string;
}) {
  const height = Math.round((value / max) * 120);
  return (
    <div className="flex w-6 flex-col items-center justify-end">
      <span className="mb-0.5 text-[10px] text-muted-foreground">{value}</span>
      <div
        className={`w-full rounded-t ${className}`}
        style={{ height: Math.max(2, height) }}
      />
    </div>
  );
}
