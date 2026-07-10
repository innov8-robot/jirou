/**
 * TanStack Query key conventions for Jirou.
 *
 * All query keys are built through this factory so that cache reads,
 * invalidations and prefetches stay consistent across the app. The real
 * data-fetching hooks (projects, issues, sprints…) arrive with later epics;
 * this module only fixes the *shape* of the keys.
 *
 * Convention (hierarchical, array-based):
 *   [entity]                          → everything about an entity
 *   [entity, 'list', filters?]        → a filtered/paginated list
 *   [entity, 'detail', id]            → a single record
 *
 * Example:
 *   queryClient.invalidateQueries({ queryKey: queryKeys.issues.all });
 *   useQuery({ queryKey: queryKeys.projects.detail(projectId), ... });
 */

export const queryKeys = {
  projects: {
    all: ['projects'] as const,
    list: (filters?: Record<string, unknown>) =>
      ['projects', 'list', filters ?? {}] as const,
    detail: (projectId: number | string) =>
      ['projects', 'detail', projectId] as const,
  },
  issues: {
    all: ['issues'] as const,
    list: (projectId: number | string, filters?: Record<string, unknown>) =>
      ['issues', 'list', projectId, filters ?? {}] as const,
    detail: (issueKey: string) => ['issues', 'detail', issueKey] as const,
  },
  labels: {
    all: ['labels'] as const,
    list: (projectId: number | string) =>
      ['labels', 'list', projectId] as const,
  },
  board: {
    all: ['board'] as const,
    view: (projectId: number | string, filters?: Record<string, unknown>) =>
      ['board', projectId, filters ?? {}] as const,
  },
  sprints: {
    all: ['sprints'] as const,
    list: (projectId: number | string) =>
      ['sprints', 'list', projectId] as const,
    detail: (sprintId: number | string) =>
      ['sprints', 'detail', sprintId] as const,
  },
  backlog: {
    all: ['backlog'] as const,
    view: (projectId: number | string, filters?: Record<string, unknown>) =>
      ['backlog', projectId, filters ?? {}] as const,
  },
  velocity: {
    view: (projectId: number | string) => ['velocity', projectId] as const,
  },
  timeline: {
    view: (projectId: number | string) => ['timeline', projectId] as const,
  },
  rag: {
    status: ['rag', 'status'] as const,
  },
  watch: {
    nodes: ['watch', 'nodes'] as const,
    node: (id: number) => ['watch', 'node', id] as const,
    comments: (id: number) => ['watch', 'comments', id] as const,
  },
  documents: {
    all: ['documents', 'all'] as const,
    list: (projectId: number | string) =>
      ['documents', 'list', projectId] as const,
    detail: (id: number) => ['documents', 'detail', id] as const,
  },
  comments: {
    list: (issueKey: string) => ['comments', issueKey] as const,
  },
  attachments: {
    list: (issueKey: string) => ['attachments', issueKey] as const,
  },
  notifications: {
    all: ['notifications'] as const,
    list: (unreadOnly?: boolean) =>
      ['notifications', 'list', unreadOnly ?? false] as const,
    unreadCount: ['notifications', 'unread-count'] as const,
  },
  search: {
    query: (q: string) => ['search', q] as const,
  },
  activity: {
    list: (issueKey: string) => ['activity', issueKey] as const,
  },
  stats: {
    project: (projectId: number | string) => ['stats', projectId] as const,
  },
  myIssues: {
    all: ['my-issues'] as const,
  },
  views: {
    list: (projectId: number | string) => ['views', projectId] as const,
  },
  auth: {
    me: ['auth', 'me'] as const,
  },
  users: {
    all: ['users'] as const,
    list: () => ['users', 'list'] as const,
  },
} as const;

export type QueryKeys = typeof queryKeys;
