import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bell } from 'lucide-react';

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';
import {
  fetchNotifications,
  fetchUnreadCount,
  markAllRead,
  markRead,
  type Notification,
} from './api';
import { queryKeys } from '@/lib/queryKeys';
import { cn } from '@/lib/utils';

function relativeTime(iso: string): string {
  const min = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (min < 1) return "à l'instant";
  if (min < 60) return `${min} min`;
  const h = Math.round(min / 60);
  if (h < 24) return `${h} h`;
  return `${Math.round(h / 24)} j`;
}

export function NotificationBell() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: count = 0 } = useQuery({
    queryKey: queryKeys.notifications.unreadCount,
    queryFn: fetchUnreadCount,
    refetchInterval: 60_000,
  });

  const { data: notifications = [] } = useQuery({
    queryKey: queryKeys.notifications.list(),
    queryFn: () => fetchNotifications(false),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.notifications.all });
  };

  const readMutation = useMutation({
    mutationFn: (id: number) => markRead(id),
    onSuccess: invalidate,
  });
  const readAllMutation = useMutation({
    mutationFn: markAllRead,
    onSuccess: invalidate,
  });

  function open(n: Notification) {
    if (!n.is_read) readMutation.mutate(n.id);
    if (n.project_id && n.issue_key) {
      navigate(`/projects/${n.project_id}/issues/${n.issue_key}`);
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className="relative rounded-full p-2 outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
          aria-label={`Notifications${count ? ` (${count} non lues)` : ''}`}
        >
          <Bell className="h-5 w-5" />
          {count > 0 && (
            <span className="absolute right-0 top-0 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-bold text-white">
              {count > 9 ? '9+' : count}
            </span>
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80">
        <div className="flex items-center justify-between px-2 py-1.5">
          <span className="text-sm font-semibold">Notifications</span>
          {count > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-auto p-0 text-xs"
              onClick={() => readAllMutation.mutate()}
            >
              Tout marquer lu
            </Button>
          )}
        </div>
        <div className="max-h-96 overflow-y-auto">
          {notifications.length === 0 && (
            <p className="px-2 py-6 text-center text-sm text-muted-foreground">
              Aucune notification.
            </p>
          )}
          {notifications.map((n) => (
            <button
              key={n.id}
              type="button"
              onClick={() => open(n)}
              className={cn(
                'flex w-full items-start gap-2 px-2 py-2 text-left text-sm hover:bg-muted',
                !n.is_read && 'bg-primary/5'
              )}
            >
              {!n.is_read && (
                <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary" />
              )}
              <span className={cn('min-w-0 flex-1', n.is_read && 'pl-4')}>
                <span className="block">{n.message}</span>
                <span className="text-xs text-muted-foreground">
                  {relativeTime(n.created_at)}
                </span>
              </span>
            </button>
          ))}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
