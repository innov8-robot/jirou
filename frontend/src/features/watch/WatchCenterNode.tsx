import { Handle, Position } from 'reactflow';

/** Hub central rond (mindmap) : point de départ d'où rayonnent les thèmes. */
export function WatchCenterNode({ data }: { data: { label: string } }) {
  return (
    <div className="flex h-28 w-28 items-center justify-center rounded-full bg-primary p-3 text-center text-sm font-bold text-primary-foreground shadow-lg ring-4 ring-primary/20">
      {/* Handles cachés : requis pour que React Flow relie les arêtes flottantes. */}
      <Handle type="source" position={Position.Top} className="!opacity-0" />
      <Handle type="target" position={Position.Bottom} className="!opacity-0" />
      <span>{data.label}</span>
    </div>
  );
}
