import { NavLink } from 'react-router-dom';
import {
  CalendarRange,
  Columns3,
  FolderKanban,
  LayoutGrid,
  ListTodo,
  type LucideIcon,
} from 'lucide-react';

import { cn } from '@/lib/utils';
import { useUiStore } from '@/stores/uiStore';

interface NavItem {
  label: string;
  to: string;
  icon: LucideIcon;
  /** When true the route isn't wired yet (EPIC-04+); shown but inert. */
  placeholder?: boolean;
}

interface NavSection {
  heading?: string;
  items: NavItem[];
}

const SECTIONS: NavSection[] = [
  {
    items: [
      {
        label: 'Mon travail',
        to: '/my-work',
        icon: LayoutGrid,
      },
      { label: 'Projets', to: '/projects', icon: FolderKanban },
    ],
  },
  {
    heading: 'Projet courant',
    items: [
      { label: 'Board', to: '/board', icon: Columns3, placeholder: true },
      { label: 'Backlog', to: '/backlog', icon: ListTodo, placeholder: true },
      {
        label: 'Timeline',
        to: '/timeline',
        icon: CalendarRange,
        placeholder: true,
      },
    ],
  },
];

/**
 * Dark left navigation rail (JIR-17). Collapses to an icon-only rail on
 * demand (state in the Zustand UI store); on small screens it slides in as
 * an overlay handled by {@link AppLayout}.
 */
export function Sidebar() {
  const collapsed = useUiStore((s) => s.isSidebarCollapsed);

  return (
    <nav
      aria-label="Navigation principale"
      className={cn(
        'flex h-full flex-col gap-6 bg-sidebar py-4 text-sidebar-foreground transition-[width] duration-200',
        collapsed ? 'w-16 px-2' : 'w-60 px-3'
      )}
    >
      {SECTIONS.map((section, i) => (
        <div key={section.heading ?? i} className="space-y-1">
          {section.heading && !collapsed && (
            <p className="px-3 pb-1 text-xs font-semibold uppercase tracking-wider text-sidebar-foreground/50">
              {section.heading}
            </p>
          )}
          {section.items.map((item) => (
            <SidebarLink key={item.to} item={item} collapsed={collapsed} />
          ))}
        </div>
      ))}
    </nav>
  );
}

function SidebarLink({
  item,
  collapsed,
}: {
  item: NavItem;
  collapsed: boolean;
}) {
  const Icon = item.icon;
  const base = cn(
    'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
    collapsed && 'justify-center px-0'
  );

  // Placeholder items (routes land with later epics) render inert.
  if (item.placeholder) {
    return (
      <div
        className={cn(base, 'cursor-default text-sidebar-foreground/40')}
        title={collapsed ? `${item.label} (bientôt)` : 'Bientôt disponible'}
        aria-disabled="true"
      >
        <Icon className="h-4 w-4 shrink-0" />
        {!collapsed && <span>{item.label}</span>}
      </div>
    );
  }

  return (
    <NavLink
      to={item.to}
      title={collapsed ? item.label : undefined}
      className={({ isActive }) =>
        cn(
          base,
          isActive
            ? 'bg-primary text-primary-foreground'
            : 'text-sidebar-foreground/80 hover:bg-white/10 hover:text-sidebar-foreground'
        )
      }
    >
      <Icon className="h-4 w-4 shrink-0" />
      {!collapsed && <span>{item.label}</span>}
    </NavLink>
  );
}
