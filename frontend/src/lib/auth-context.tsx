import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { login as transportLogin, logout as transportLogout } from '../features/auth/session';
import { request, message } from '../features/common-reference/api';

export type AuthUser = {
  user_id: number;
  username: string;
  permissions: string[];
  /** IAM module codes granted through role assignments (drives navigation only). */
  access_modules?: string[];
  is_superuser: boolean;
  groups?: string[];
  must_change_password?: boolean;
};

type AuthState = {
  user: AuthUser | null;
  checking: boolean;
  failure: string;
  busy: boolean;
  retryLogout: boolean;
  signIn: (username: string, password: string, mfa?: string) => Promise<void>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
  clearFailure: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [checking, setChecking] = useState(true);
  const [failure, setFailure] = useState('');
  const [busy, setBusy] = useState(false);
  const [retryLogout, setRetryLogout] = useState(false);

  const refreshUser = useCallback(async () => {
    setUser(await request<AuthUser>('/auth/me/'));
  }, []);

  useEffect(() => {
    let alive = true;
    request<AuthUser>('/auth/me/')
      .then((u) => {
        if (alive) setUser(u);
      })
      .catch((e: unknown) => {
        const status = (e as { status?: number }).status;
        if (alive && status !== 401) setFailure(message(e));
      })
      .finally(() => {
        if (alive) setChecking(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    const expired = () => {
      setUser(null);
      setFailure('Your session expired. Sign in again to continue.');
    };
    window.addEventListener('sims-session-expired', expired);
    return () => window.removeEventListener('sims-session-expired', expired);
  }, []);

  const signIn = useCallback(
    async (username: string, password: string, mfa?: string) => {
      setBusy(true);
      setFailure('');
      try {
        await transportLogin(username, password, mfa);
        setUser(await request<AuthUser>('/auth/me/'));
        setRetryLogout(false);
      } catch (e) {
        setFailure(message(e));
        throw e;
      } finally {
        setBusy(false);
      }
    },
    [],
  );

  const signOut = useCallback(async () => {
    setBusy(true);
    setFailure('');
    setUser(null);
    try {
      await transportLogout();
      setRetryLogout(false);
    } catch (e) {
      setFailure(message(e));
      setRetryLogout(true);
      throw e;
    } finally {
      setBusy(false);
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        checking,
        failure,
        busy,
        retryLogout,
        signIn,
        signOut,
        refreshUser,
        clearFailure: () => setFailure(''),
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}

export function hasPermission(user: AuthUser | null, prefix: string): boolean {
  if (!user) return false;
  if (user.is_superuser) return true;
  return user.permissions.some((p) => p === prefix || p.startsWith(`${prefix}.`));
}
