import { useEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';

import { Sidebar } from '@/components/layout/Sidebar';
import { Topbar } from '@/components/layout/Topbar';
import { cn } from '@/lib/utils';
import { useUiStore } from '@/stores/uiStore';

/**
 * Authenticated app shell (JIR-17): dark sidebar + topbar around a scrollable
 * content area rendered via <Outlet />.
 *
 * Responsive :
 *  - md+ : sidebar toujours visible ; le bouton bascule un rail icônes
 *    (`isSidebarCollapsed`).
 *  - <md : sidebar en drawer coulissant, FERMÉ par défaut (`isMobileNavOpen`),
 *    ouvert par le bouton et refermé par le backdrop ou un changement de route.
 */
export function AppLayout() {
  const mobileNavOpen = useUiStore((s) => s.isMobileNavOpen);
  const setMobileNavOpen = useUiStore((s) => s.setMobileNavOpen);
  const location = useLocation();

  // Referme le drawer mobile à chaque navigation.
  useEffect(() => {
    setMobileNavOpen(false);
  }, [location.pathname, setMobileNavOpen]);

  return (
    <div className="flex h-screen overflow-hidden">
      <aside
        className={cn(
          'z-40 h-full shrink-0',
          'max-md:fixed max-md:inset-y-0 max-md:left-0 max-md:transition-transform max-md:duration-200',
          mobileNavOpen ? 'max-md:translate-x-0' : 'max-md:-translate-x-full',
          'md:static md:translate-x-0'
        )}
      >
        <Sidebar />
      </aside>

      {/* Backdrop mobile quand le drawer est ouvert. */}
      {mobileNavOpen && (
        <button
          type="button"
          aria-label="Fermer la navigation"
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
          onClick={() => setMobileNavOpen(false)}
        />
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="flex-1 overflow-auto bg-surface">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
