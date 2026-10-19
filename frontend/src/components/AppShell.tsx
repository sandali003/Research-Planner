'use client';

import type { ReactNode } from 'react';
import { AuthGuard } from '@/lib/auth';
import { Sidebar } from './Sidebar';

/** Logged-in page layout: auth check + left sidebar + page content. */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <AuthGuard>
      <div className="app-shell">
        <Sidebar />
        <div className="app-content">{children}</div>
      </div>
    </AuthGuard>
  );
}
