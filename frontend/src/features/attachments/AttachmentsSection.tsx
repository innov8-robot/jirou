import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, FileIcon, Trash2, Upload } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { useProject } from '@/features/projects/useProject';
import { useAuth } from '@/features/auth/useAuth';
import {
  deleteAttachment,
  downloadAttachment,
  fetchAttachmentBlobUrl,
  fetchAttachments,
  uploadAttachment,
  type Attachment,
} from './api';
import { queryKeys } from '@/lib/queryKeys';
import { cn } from '@/lib/utils';
import { getErrorMessage, toast } from '@/lib/toast';

function formatBytes(n: number): string {
  if (n < 1024) return `${n} o`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} Ko`;
  return `${(n / 1024 / 1024).toFixed(1)} Mo`;
}

export function AttachmentsSection({
  issueKey,
  canEdit,
}: {
  issueKey: string;
  canEdit: boolean;
}) {
  const { project } = useProject();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const { data: attachments = [] } = useQuery({
    queryKey: queryKeys.attachments.list(issueKey),
    queryFn: () => fetchAttachments(issueKey),
  });

  const invalidate = () =>
    queryClient.invalidateQueries({
      queryKey: queryKeys.attachments.list(issueKey),
    });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadAttachment(issueKey, file),
    onSuccess: () => {
      invalidate();
      toast.success('Fichier ajouté');
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteAttachment(id),
    onSuccess: () => {
      invalidate();
      toast.success('Fichier supprimé');
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  function handleFiles(files: FileList | null) {
    if (!files) return;
    for (const f of Array.from(files)) uploadMutation.mutate(f);
  }

  const canDelete = (a: Attachment) =>
    a.uploaded_by.id === user?.id ||
    user?.role === 'admin' ||
    project.my_role === 'admin';

  return (
    <section>
      <h2 className="mb-3 text-sm font-semibold text-muted-foreground">
        Pièces jointes
      </h2>

      {attachments.length > 0 && (
        <ul className="mb-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
          {attachments.map((a) => (
            <li
              key={a.id}
              className="flex items-center gap-3 rounded border border-border p-2"
            >
              <Thumb attachment={a} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{a.filename}</p>
                <p className="text-xs text-muted-foreground">
                  {formatBytes(a.size)}
                </p>
              </div>
              <button
                type="button"
                aria-label="Télécharger"
                className="text-muted-foreground hover:text-foreground"
                onClick={() => void downloadAttachment(a)}
              >
                <Download className="h-4 w-4" />
              </button>
              {canDelete(a) && (
                <button
                  type="button"
                  aria-label="Supprimer"
                  className="text-muted-foreground hover:text-destructive"
                  onClick={() => deleteMutation.mutate(a.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {canEdit && (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            handleFiles(e.dataTransfer.files);
          }}
          className={cn(
            'flex flex-col items-center gap-2 rounded-lg border border-dashed border-border p-4 text-center text-sm text-muted-foreground',
            dragOver && 'border-primary bg-primary/5'
          )}
        >
          <Upload className="h-5 w-5" />
          <span>Glissez des fichiers ici, ou</span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => inputRef.current?.click()}
            disabled={uploadMutation.isPending}
          >
            {uploadMutation.isPending ? 'Envoi…' : 'Choisir un fichier'}
          </Button>
          <input
            ref={inputRef}
            type="file"
            multiple
            className="hidden"
            onChange={(e) => handleFiles(e.target.files)}
          />
        </div>
      )}
    </section>
  );
}

/** Miniature : image chargée en blob (avec auth) sinon icône générique. */
function Thumb({ attachment }: { attachment: Attachment }) {
  const [url, setUrl] = useState<string | null>(null);
  const isImage = attachment.content_type.startsWith('image/');

  useEffect(() => {
    if (!isImage) return;
    let revoked: string | null = null;
    let active = true;
    fetchAttachmentBlobUrl(attachment.id)
      .then((u) => {
        if (active) {
          revoked = u;
          setUrl(u);
        } else {
          URL.revokeObjectURL(u);
        }
      })
      .catch(() => undefined);
    return () => {
      active = false;
      if (revoked) URL.revokeObjectURL(revoked);
    };
  }, [attachment.id, isImage]);

  if (isImage && url) {
    return (
      <img
        src={url}
        alt={attachment.filename}
        className="h-10 w-10 rounded object-cover"
      />
    );
  }
  return (
    <span className="flex h-10 w-10 items-center justify-center rounded bg-muted text-muted-foreground">
      <FileIcon className="h-5 w-5" />
    </span>
  );
}
