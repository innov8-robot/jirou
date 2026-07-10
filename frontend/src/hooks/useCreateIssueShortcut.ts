import { useEffect } from 'react';

import { useUiStore } from '@/stores/uiStore';

/**
 * Global keyboard shortcut: pressing `c` opens the quick "Create issue"
 * modal (JIR-21) — matching Jira. Ignored while typing in a field or when a
 * modifier key is held, and a no-op if the modal is already open.
 *
 * Mounted once at the app root (App.tsx).
 */
export function useCreateIssueShortcut() {
  const openCreateIssue = useUiStore((s) => s.openCreateIssue);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== 'c' && event.key !== 'C') return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;

      const target = event.target as HTMLElement | null;
      const tag = target?.tagName;
      const isTyping =
        tag === 'INPUT' ||
        tag === 'TEXTAREA' ||
        tag === 'SELECT' ||
        target?.isContentEditable === true;
      if (isTyping) return;

      // Don't hijack `c` while another modal/menu is open.
      if (useUiStore.getState().isCreateIssueOpen) return;

      event.preventDefault();
      openCreateIssue();
    }

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [openCreateIssue]);
}
