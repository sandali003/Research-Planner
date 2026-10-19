'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState, type ReactNode } from 'react';
import { tokenStore } from './api';

/** Redirects to /login when there is no token; renders children only once a token exists. */
export function AuthGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (tokenStore.get()) setReady(true);
    else router.replace('/login');
  }, [router]);

  return ready ? <>{children}</> : null;
}

export function useLogout() {
  const router = useRouter();
  return () => {
    tokenStore.clear();
    router.replace('/login');
  };
}
