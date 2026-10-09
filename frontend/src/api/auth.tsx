import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api, login as apiLogin, logout as apiLogout, refreshSession } from './client';
import type { Me } from './types';

type AuthState = {
  user: Me | null;
  loading: boolean;
  notice: string;
  signIn: (username: string, password: string, mfa?: string, portal?: string) => Promise<void>;
  signOut: () => Promise<void>;
  reload: () => Promise<void>;
};

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState('');

  const reload = useCallback(async () => {
    setUser(await api<Me>('/auth/me'));
  }, []);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        if (await refreshSession()) await reload();
      } catch {
        /* not signed in */
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [reload]);

  useEffect(() => {
    const expired = () => {
      qc.clear();
      setUser(null);
      setNotice('Your session expired. Please sign in again.');
    };
    window.addEventListener('sims:session-expired', expired);
    return () => window.removeEventListener('sims:session-expired', expired);
  }, [qc]);

  const signIn = useCallback(
    async (username: string, password: string, mfa?: string, portal?: string) => {
      setNotice('');
      qc.clear();
      await apiLogin(username, password, mfa, portal);
      await reload();
    },
    [qc, reload],
  );

  const signOut = useCallback(async () => {
    try {
      await apiLogout();
    } finally {
      qc.clear();
      setUser(null);
    }
  }, [qc]);

  const value = useMemo(() => ({ user, loading, notice, signIn, signOut, reload }), [user, loading, notice, signIn, signOut, reload]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error('useAuth must be used inside <AuthProvider>');
  return v;
}

/** Navigation convenience only; the server enforces every permission. */
export function can(user: Me | null, code: string): boolean {
  return !!user && (user.is_superuser || user.permissions.includes(code) || user.permissions.some((p) => p.endsWith(`.ALL.${code.split('.').pop()}`) && p.startsWith(`${code.split('.')[0]}.`)));
}
