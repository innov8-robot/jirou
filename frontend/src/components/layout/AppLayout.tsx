import { Outlet } from 'react-router-dom';

import { Sidebar } from '@/components/layout/Sidebar';
import { Topbar } from '@/components/layout/Topbar';
import { cn } from '@/lib/utils';
import { useUiStore } from '@/stores/uiStore';

/**
 * Authenticated app shell (JIR-17): dark sidebar + topbar around a scrollable
 * content area rendered via <Outlet />. Applied to authenticated routes only
 * (not /login or /register).
 *
 * Responsive: on md+ the sidebar is always visible and the collapse toggle
 * turns it into an icon-only rail; below md it becomes a slide-in overlay
 * driven by the same `isSidebarCollapsed` flag.
 */
export function AppLayout() {
  const collapsed = useUiStore((s) => s.isSidebarCollapsed);
  const setSidebarCollapsed = useUiStore((s) => s.setSidebarCollapsed);

  return (
    <div className="flex h-screen overflow-hidden">
      <aside
        className={cn(
          'z-40 h-full shrink-0',
          'max-md:fixed max-md:inset-y-0 max-md:left-0 max-md:transition-transform max-md:duration-200',
          collapsed ? 'max-md:-translate-x-full' : 'max-md:translate-x-0',
          'md:static md:translate-x-0'
        )}
      >
        <Sidebar />
      </aside>

      {/* Mobile backdrop when the drawer is open. */}
      {!collapsed && (
        <button
          type="button"
          aria-label="Fermer la navigation"
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
          onClick={() => setSidebarCollapsed(true)}
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
