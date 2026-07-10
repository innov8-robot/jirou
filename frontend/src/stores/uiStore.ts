import { create } from 'zustand';

/**
 * Global UI state (Zustand). This holds *ephemeral, client-only* state —
 * things that don't belong in the TanStack Query server cache: the
 * open/closed state of global modals and the sidebar layout preference.
 *
 * Server data (projects, issues…) must NOT live here — use TanStack Query.
 */
interface UiState {
  /** Quick "Create issue" modal (JIR-21). */
  isCreateIssueOpen: boolean;
  openCreateIssue: () => void;
  closeCreateIssue: () => void;
  setCreateIssueOpen: (open: boolean) => void;

  /** Collapsed state of the app sidebar (JIR-17, responsive). */
  isSidebarCollapsed: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
}

export const useUiStore = create<UiState>((set) => ({
  isCreateIssueOpen: false,
  openCreateIssue: () => set({ isCreateIssueOpen: true }),
  closeCreateIssue: () => set({ isCreateIssueOpen: false }),
  setCreateIssueOpen: (open) => set({ isCreateIssueOpen: open }),

  isSidebarCollapsed: false,
  toggleSidebar: () =>
    set((state) => ({ isSidebarCollapsed: !state.isSidebarCollapsed })),
  setSidebarCollapsed: (collapsed) => set({ isSidebarCollapsed: collapsed }),
}));
