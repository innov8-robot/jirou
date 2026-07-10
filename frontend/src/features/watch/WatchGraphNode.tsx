import { useEffect, useState } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import {
  BookOpen,
  Cpu,
  Lightbulb,
  Link2,
  MessageSquare,
  Paperclip,
  Target,
  Video,
  type LucideIcon,
} from 'lucide-react';

import {
  WATCH_STATUS_META,
  WATCH_TYPE_META,
  fetchMediaBlobUrl,
  type WatchMediaPreview,
  type WatchNodeType,
  type WatchStatus,
} from './api';
import { cn } from '@/lib/utils';

const TYPE_ICON: Record<WatchNodeType, LucideIcon> = {
  theme: Target,
  techno: Cpu,
  solution: Lightbulb,
  resource: BookOpen,
};

export interface WatchNodeData {
  title: string;
  type: WatchNodeType;
  status: WatchStatus | null;
  media_count: number;
  comment_count: number;
  preview: WatchMediaPreview | null;
}

function youtubeId(url: string): string | null {
  const m = url.match(
    /(?:youtube\.com\/(?:watch\?v=|embed\/)|youtu\.be\/)([\w-]{11})/
  );
  return m ? m[1] : null;
}

function NodeThumb({ preview }: { preview: WatchMediaPreview }) {
  const [url, setUrl] = useState<string | null>(null);
  const isImage = preview.kind === 'image';
  const yt = preview.kind === 'link' && preview.url ? youtubeId(preview.url) : null;

  useEffect(() => {
    if (!isImage) return;
    let active = true;
    let revoked: string | null = null;
    fetchMediaBlobUrl(preview.media_id)
      .then((u) => {
        if (active) {
          revoked = u;
          setUrl(u);
        } else URL.revokeObjectURL(u);
      })
      .catch(() => undefined);
    return () => {
      active = false;
      if (revoked) URL.revokeObjectURL(revoked);
    };
  }, [preview.media_id, isImage]);

  if (isImage) {
    return url ? (
      <img src={url} alt="" className="h-20 w-full object-cover" />
    ) : (
      <div className="h-20 w-full animate-pulse bg-muted" />
    );
  }
  if (yt) {
    return (
      <img
        src={`https://img.youtube.com/vi/${yt}/mqdefault.jpg`}
        alt=""
        className="h-20 w-full object-cover"
      />
    );
  }
  return (
    <div className="flex h-20 w-full items-center justify-center bg-muted text-muted-foreground">
      {preview.kind === 'video' ? (
        <Video className="h-6 w-6" />
      ) : (
        <Link2 className="h-6 w-6" />
      )}
    </div>
  );
}

/** Nœud custom du graphe de veille (type coloré, miniature, statut, compteurs). */
export function WatchGraphNode({ data, selected }: NodeProps<WatchNodeData>) {
  const typeMeta = WATCH_TYPE_META[data.type] ?? WATCH_TYPE_META.theme;
  const TypeIcon = TYPE_ICON[data.type] ?? Target;
  const statusMeta = data.status ? WATCH_STATUS_META[data.status] : null;

  return (
    <div
      className={cn(
        'w-52 overflow-hidden rounded-lg border bg-background shadow-sm transition-shadow',
        selected ? 'border-primary ring-2 ring-primary/40' : 'border-border'
      )}
      style={{ borderTop: `3px solid ${typeMeta.color}` }}
    >
      <Handle type="target" position={Position.Top} className="!opacity-0" />

      <div
        className="flex items-center gap-1.5 px-2 pt-1.5 text-[11px] font-semibold uppercase tracking-wide"
        style={{ color: typeMeta.color }}
      >
        <TypeIcon className="h-3.5 w-3.5" />
        {typeMeta.label}
      </div>

      {data.preview && <NodeThumb preview={data.preview} />}

      <div className="space-y-1 px-2 py-1.5">
        <p className="line-clamp-2 text-sm font-medium leading-snug">
          {data.title}
        </p>
        <div className="flex items-center gap-2">
          {statusMeta && (
            <span
              className="rounded-full px-1.5 py-0.5 text-[10px] font-medium"
              style={{
                backgroundColor: `${statusMeta.color}22`,
                color: statusMeta.color,
              }}
            >
              {statusMeta.label}
            </span>
          )}
          <span className="ml-auto flex items-center gap-2 text-[11px] text-muted-foreground">
            {data.media_count > 0 && (
              <span className="flex items-center gap-0.5">
                <Paperclip className="h-3 w-3" />
                {data.media_count}
              </span>
            )}
            {data.comment_count > 0 && (
              <span className="flex items-center gap-0.5">
                <MessageSquare className="h-3 w-3" />
                {data.comment_count}
              </span>
            )}
          </span>
        </div>
      </div>

      <Handle type="source" position={Position.Bottom} className="!opacity-0" />
    </div>
  );
}
