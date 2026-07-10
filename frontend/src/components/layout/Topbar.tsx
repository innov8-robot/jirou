import { Link, useNavigate } from 'react-router-dom';
import { LogOut, Menu, Plus, Shield, User } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { UserAvatar } from '@/components/UserAvatar';
import { GlobalSearch } from '@/features/search/GlobalSearch';
import { NotificationBell } from '@/features/notifications/NotificationBell';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useAuth } from '@/features/auth/useAuth';
import { useUiStore } from '@/stores/uiStore';

/**
 * Application top bar (JIR-17): sidebar toggle, Jirou logo, global search,
 * the "Créer" quick-action, and the user menu (real session — JIR-14).
 */
export function Topbar() {
  const toggleSidebar = useUiStore((s) => s.toggleSidebar);
  const toggleMobileNav = useUiStore((s) => s.toggleMobileNav);
  const openCreateIssue = useUiStore((s) => s.openCreateIssue);
  const { user, isAdmin, logout } = useAuth();
  const navigate = useNavigate();

  const displayName = user?.full_name || user?.email || 'Utilisateur';

  // Desktop (md+) : bascule le rail icônes ; mobile : ouvre/ferme le drawer.
  function handleNavToggle() {
    if (window.matchMedia('(min-width: 768px)').matches) toggleSidebar();
    else toggleMobileNav();
  }

  function handleLogout() {
    logout();
    navigate('/login', { replace: true });
  }

  return (
    <header className="flex h-14 items-center gap-3 border-b border-border bg-background px-4">
      <Button
        variant="ghost"
        size="icon"
        onClick={handleNavToggle}
        aria-label="Afficher/masquer la navigation"
      >
        <Menu className="h-5 w-5" />
      </Button>

      <Link to="/projects" className="text-lg font-bold text-primary">
        Jirou
      </Link>

      <GlobalSearch />

      <div className="ml-auto flex items-center gap-2">
        <Button onClick={openCreateIssue}>
          <Plus className="h-4 w-4" />
          <span className="hidden sm:inline">Créer</span>
        </Button>

        <NotificationBell />

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              className="rounded-full outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              aria-label="Menu utilisateur"
            >
              <UserAvatar name={displayName} src={user?.avatar_url} size="md" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel className="max-w-[12rem] truncate">
              {displayName}
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link to="/profile">
                <User />
                Profil
              </Link>
            </DropdownMenuItem>
            {isAdmin && (
              <DropdownMenuItem asChild>
                <Link to="/admin/users">
                  <Shield />
                  Utilisateurs
                </Link>
              </DropdownMenuItem>
            )}
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={handleLogout}>
              <LogOut />
              Déconnexion
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
