import { useQuery } from '@tanstack/react-query';
import { Check, Tag } from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { LabelBadge } from './LabelBadge';
import { fetchLabels } from './api';
import { queryKeys } from '@/lib/queryKeys';

interface LabelPickerProps {
  projectId: number | string;
  selectedIds: number[];
  onChange: (ids: number[]) => void;
  disabled?: boolean;
}

/** Sélecteur multi de labels du projet (JIR-39). */
export function LabelPicker({
  projectId,
  selectedIds,
  onChange,
  disabled,
}: LabelPickerProps) {
  const { data: labels = [] } = useQuery({
    queryKey: queryKeys.labels.list(projectId),
    queryFn: () => fetchLabels(projectId),
  });

  const selected = labels.filter((l) => selectedIds.includes(l.id));

  function toggle(id: number) {
    onChange(
      selectedIds.includes(id)
        ? selectedIds.filter((x) => x !== id)
        : [...selectedIds, id]
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {selected.map((l) => (
        <LabelBadge key={l.id} label={l} />
      ))}
      {!disabled && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm" className="h-6 gap-1 px-2 text-xs">
              <Tag className="h-3 w-3" />
              Labels
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-52">
            <DropdownMenuLabel>Labels du projet</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {labels.length === 0 && (
              <DropdownMenuItem disabled>
                Aucun label (voir Paramètres)
              </DropdownMenuItem>
            )}
            {labels.map((l) => (
              <DropdownMenuItem
                key={l.id}
                onSelect={(e) => {
                  e.preventDefault();
                  toggle(l.id);
                }}
              >
                <span className="flex w-4 justify-center">
                  {selectedIds.includes(l.id) && <Check className="h-3.5 w-3.5" />}
                </span>
                <LabelBadge label={l} />
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </div>
  );
}
