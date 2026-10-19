'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, type ReactNode } from 'react';
import { useLogout } from '@/lib/auth';

interface NavItem {
  label: string;
  href?: string;          // no href = not available yet
  icon: ReactNode;
}

const OVERVIEW: NavItem[] = [
  {
    label: 'Dashboard',
    href: '/dashboard',
    icon: <path d="M4 4h7v7H4zM13 4h7v4h-7zM13 10h7v10h-7zM4 13h7v7H4z" />,
  },
];

const COMPONENTS: NavItem[] = [
  {
    label: 'Vehicle Health',
    href: '/vehicles',
    icon: <path d="M3 12h4l2-6 4 12 2-6h6" />,
  },
  {
    label: 'Hidden Fault & Mitigation',
    href: '/hidden-fault',
    icon: <path d="M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7l8-4zM12 8v5M12 16h.01" />,
  },
  {
    label: 'Age & Mileage Deterioration',
    href: '/deterioration',
    icon: <path d="M12 7v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z" />,
  },
  {
    label: 'Maintenance & Valuation',
    href: '/maintenance-valuation',
    icon: <path d="M20.6 13.4l-7.2 7.2a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8zM7.5 7.5h.01" />,
  },
];

function NavIcon({ children }: { children: ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {children}
    </svg>
  );
}

function NavLink({ item, pathname, onNavigate }: {
  item: NavItem; pathname: string; onNavigate: () => void;
}) {
  if (!item.href) {
    return (
      <span className="side-link disabled" aria-disabled="true">
        <NavIcon>{item.icon}</NavIcon>
        <span>{item.label}</span>
        <span className="side-badge">Soon</span>
      </span>
    );
  }
  const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
  return (
    <Link href={item.href} className={`side-link${active ? ' active' : ''}`}
      aria-current={active ? 'page' : undefined} onClick={onNavigate}>
      <NavIcon>{item.icon}</NavIcon>
      <span>{item.label}</span>
    </Link>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const logout = useLogout();
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);

  return (
    <aside className={`sidebar${open ? ' open' : ''}`}>
      <div className="side-head">
        <Link href="/dashboard" className="brand side-brand" onClick={close}>Auto<span>Sense</span></Link>
        <button type="button" className="side-menu" aria-label="Toggle menu"
          aria-expanded={open} onClick={() => setOpen(!open)}>
          <NavIcon><path d={open ? 'M6 6l12 12M18 6L6 18' : 'M4 7h16M4 12h16M4 17h16'} /></NavIcon>
        </button>
      </div>

      <nav className="side-nav">
        <p className="side-section">Overview</p>
        {OVERVIEW.map((item) => <NavLink key={item.label} item={item} pathname={pathname} onNavigate={close} />)}

        <p className="side-section">Components</p>
        {COMPONENTS.map((item) => <NavLink key={item.label} item={item} pathname={pathname} onNavigate={close} />)}

        <button type="button" className="side-link side-logout" onClick={logout}>
          <NavIcon><path d="M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10" /></NavIcon>
          <span>Log out</span>
        </button>
      </nav>
    </aside>
  );
}
