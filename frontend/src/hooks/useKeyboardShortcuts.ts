import { useEffect } from 'react';

import { useUiStore } from '@/stores/uiStore';

/**
 * Raccourcis clavier globaux type Jira (JIR-73) :
 *  - `c` : ouvrir la création rapide de ticket
 *  - `/` : focus la recherche globale
 *  - `?` : ouvrir l'aide des raccourcis
 * Ignorés pendant la saisie dans un champ (sauf effets neutres).
 */
export function useKeyboardShortcuts(openHelp: () => void) {
  const openCreateIssue = useUiStore((s) => s.openCreateIssue);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey) return;

      const target = event.target as HTMLElement | null;
      const tag = target?.tagName;
      const isTyping =
        tag === 'INPUT' ||
        tag === 'TEXTAREA' ||
        tag === 'SELECT' ||
        target?.isContentEditable === true;
      if (isTyping) return;

      if (useUiStore.getState().isCreateIssueOpen) return;

      if (event.key === 'c' || event.key === 'C') {
        event.preventDefault();
        openCreateIssue();
      } else if (event.key === '/') {
        event.preventDefault();
        window.dispatchEvent(new CustomEvent('jirou:focus-search'));
      } else if (event.key === '?') {
        event.preventDefault();
        openHelp();
      }
    }

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [openCreateIssue, openHelp]);
}
