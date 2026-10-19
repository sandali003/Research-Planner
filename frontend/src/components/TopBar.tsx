'use client';

import Link from 'next/link';
import { useLogout } from '@/lib/auth';

export function TopBar() {
  const logout = useLogout();
  return (
    <header className="topbar">
      <Link href="/vehicles" className="brand">Auto<span>Sense</span></Link>
      <button onClick={logout}>Log out</button>
    </header>
  );
}
