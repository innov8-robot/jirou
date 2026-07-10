import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Bot, RefreshCw, Send } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { MarkdownView } from '@/features/documents/MarkdownView';
import {
  ragChat,
  ragReindex,
  ragStatus,
  type RagSource,
} from '@/features/rag/api';
import { queryKeys } from '@/lib/queryKeys';
import { getErrorMessage, toast } from '@/lib/toast';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  sources?: RagSource[];
  pending?: boolean;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  const statusQuery = useQuery({
    queryKey: queryKeys.rag.status,
    queryFn: ragStatus,
  });

  const reindexMutation = useMutation({
    mutationFn: ragReindex,
    onSuccess: (r) => toast.success(`Base indexée`, `${r.indexed} éléments`),
    onError: (err) => toast.error('Réindexation échouée', getErrorMessage(err)),
  });

  const chatMutation = useMutation({
    mutationFn: (q: string) => ragChat(q),
    onSuccess: (res) => {
      setMessages((m) => {
        const copy = [...m];
        const idx = copy.findIndex((x) => x.pending);
        if (idx !== -1)
          copy[idx] = {
            role: 'assistant',
            content: res.answer,
            sources: res.sources,
          };
        return copy;
      });
    },
    onError: (err) => {
      const msg = getErrorMessage(err);
      setMessages((m) => {
        const copy = [...m];
        const idx = copy.findIndex((x) => x.pending);
        if (idx !== -1)
          copy[idx] = { role: 'assistant', content: `⚠️ ${msg}` };
        return copy;
      });
    },
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  function send(e: FormEvent) {
    e.preventDefault();
    const q = input.trim();
    if (!q || chatMutation.isPending) return;
    setMessages((m) => [
      ...m,
      { role: 'user', content: q },
      { role: 'assistant', content: '…', pending: true },
    ]);
    setInput('');
    chatMutation.mutate(q);
  }

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col px-4 py-6">
      <header className="mb-4 flex items-center gap-2">
        <Bot className="h-6 w-6 text-primary" />
        <div className="flex-1">
          <h1 className="text-xl font-bold">Assistant Jirou</h1>
          <p className="text-sm text-muted-foreground">
            Posez une question sur vos tickets, commentaires et documents.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => reindexMutation.mutate()}
          disabled={reindexMutation.isPending}
        >
          <RefreshCw
            className={reindexMutation.isPending ? 'h-4 w-4 animate-spin' : 'h-4 w-4'}
          />
          Réindexer
        </Button>
      </header>

      {statusQuery.data && !statusQuery.data.enabled && (
        <div className="mb-4 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
          Chatbot non configuré : renseignez <code>MISTRAL_API_KEY</code> dans{' '}
          <code>.env</code> puis redémarrez le backend.
        </div>
      )}

      <div className="flex-1 space-y-4 overflow-y-auto rounded-lg border border-border bg-background p-4">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-sm text-muted-foreground">
            <Bot className="h-10 w-10 text-muted-foreground/40" />
            <p>Ex. : « Quels bugs sont en cours ? », « Résume l'epic paiement ».</p>
            <p className="text-xs">
              Pensez à « Réindexer » après avoir créé/modifié des tickets.
            </p>
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={m.role === 'user' ? 'flex justify-end' : 'flex justify-start'}
          >
            <div
              className={
                m.role === 'user'
                  ? 'max-w-[80%] rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground'
                  : 'max-w-[85%] rounded-lg bg-surface px-3 py-2 text-sm'
              }
            >
              {m.role === 'assistant' && !m.pending ? (
                <MarkdownView content={m.content} />
              ) : (
                <span className={m.pending ? 'animate-pulse' : undefined}>
                  {m.content}
                </span>
              )}
              {m.sources && m.sources.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1 border-t border-border pt-2">
                  {m.sources.map((s, j) =>
                    s.issue_key && s.project_id ? (
                      <Link
                        key={j}
                        to={`/projects/${s.project_id}/issues/${s.issue_key}`}
                        className="rounded bg-background px-1.5 py-0.5 font-mono text-xs text-primary hover:underline"
                      >
                        {s.issue_key}
                      </Link>
                    ) : (
                      <span
                        key={j}
                        className="rounded bg-background px-1.5 py-0.5 text-xs text-muted-foreground"
                        title={s.kind}
                      >
                        {s.title}
                      </span>
                    )
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <form className="mt-3 flex gap-2" onSubmit={send}>
        <Input
          placeholder="Votre question…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={statusQuery.data?.enabled === false}
        />
        <Button
          type="submit"
          disabled={
            !input.trim() ||
            chatMutation.isPending ||
            statusQuery.data?.enabled === false
          }
        >
          <Send className="h-4 w-4" />
        </Button>
      </form>
    </div>
  );
}
