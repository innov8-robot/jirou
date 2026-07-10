import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { LinkIcon, Trash2, Upload } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  addMediaLink,
  deleteMedia,
  fetchMediaBlobUrl,
  uploadMedia,
  type WatchMedia,
} from './api';
import { queryKeys } from '@/lib/queryKeys';
import { getErrorMessage, toast } from '@/lib/toast';

/** Extrait l'ID d'une URL YouTube pour l'embed, sinon null. */
function youtubeId(url: string): string | null {
  const m = url.match(
    /(?:youtube\.com\/(?:watch\?v=|embed\/)|youtu\.be\/)([\w-]{11})/
  );
  return m ? m[1] : null;
}

export function WatchMediaGallery({
  nodeId,
  media,
}: {
  nodeId: number;
  media: WatchMedia[];
}) {
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [url, setUrl] = useState('');

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: queryKeys.watch.node(nodeId) });

  const uploadMut = useMutation({
    mutationFn: (file: File) => uploadMedia(nodeId, file),
    onSuccess: () => {
      invalidate();
      toast.success('Média ajouté');
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });
  const linkMut = useMutation({
    mutationFn: () => addMediaLink(nodeId, { url: url.trim() }),
    onSuccess: () => {
      invalidate();
      setUrl('');
      toast.success('Lien ajouté');
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });
  const delMut = useMutation({
    mutationFn: (id: number) => deleteMedia(id),
    onSuccess: invalidate,
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  return (
    <div className="space-y-3">
      {media.length > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {media.map((m) => (
            <div
              key={m.id}
              className="group relative overflow-hidden rounded-md border border-border"
            >
              <MediaContent media={m} />
              <button
                type="button"
                aria-label="Supprimer le média"
                onClick={() => delMut.mutate(m.id)}
                className="absolute right-1 top-1 rounded bg-black/60 p-1 text-white opacity-0 transition-opacity group-hover:opacity-100"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => inputRef.current?.click()}
          disabled={uploadMut.isPending}
        >
          <Upload className="h-4 w-4" />
          {uploadMut.isPending ? 'Envoi…' : 'Image / vidéo'}
        </Button>
        <input
          ref={inputRef}
          type="file"
          accept="image/*,video/*"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) uploadMut.mutate(f);
            e.target.value = '';
          }}
        />
        <form
          className="flex flex-1 items-center gap-2"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            if (url.trim()) linkMut.mutate();
          }}
        >
          <Input
            placeholder="Lien vidéo (YouTube…)"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            className="flex-1"
          />
          <Button type="submit" size="sm" variant="outline" disabled={linkMut.isPending}>
            <LinkIcon className="h-4 w-4" />
            Lien
          </Button>
        </form>
      </div>
    </div>
  );
}

function MediaContent({ media }: { media: WatchMedia }) {
  if (media.kind === 'link' && media.url) {
    const yt = youtubeId(media.url);
    if (yt) {
      return (
        <div className="aspect-video">
          <iframe
            className="h-full w-full"
            src={`https://www.youtube.com/embed/${yt}`}
            title={media.title ?? 'Vidéo'}
            allowFullScreen
          />
        </div>
      );
    }
    return (
      <a
        href={media.url}
        target="_blank"
        rel="noreferrer"
        className="block truncate p-3 text-sm text-primary hover:underline"
      >
        🔗 {media.title || media.url}
      </a>
    );
  }
  return <BlobMedia media={media} />;
}

/** Charge un média uploadé (image/vidéo) en blob authentifié. */
function BlobMedia({ media }: { media: WatchMedia }) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    let revoked: string | null = null;
    let active = true;
    fetchMediaBlobUrl(media.id)
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
  }, [media.id]);

  if (!url) return <div className="aspect-video animate-pulse bg-muted" />;
  if (media.kind === 'video') {
    return <video src={url} controls className="aspect-video w-full bg-black" />;
  }
  return (
    <img src={url} alt={media.filename ?? ''} className="aspect-video w-full object-cover" />
  );
}
