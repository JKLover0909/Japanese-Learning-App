import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { api } from '../api/client';
import type { AuthUser } from '../api/types';

interface AuthState {
  /** The signed-in account, or null for an anonymous browser. */
  user: AuthUser | null;
  /** False until the first `/auth/me` answer arrived. */
  ready: boolean;
  setUser: (user: AuthUser | null) => void;
  logout: () => Promise<void>;
}

// The default lets components render without a provider (tests, admin pages).
const AuthContext = createContext<AuthState>({
  user: null,
  ready: true,
  setUser: () => undefined,
  logout: () => Promise.resolve(),
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    api.me(controller.signal)
      .then((response) => setUser(response.user))
      .catch(() => undefined) // Treated as signed out; the learner pages report their own errors.
      .finally(() => { if (!controller.signal.aborted) setReady(true); });
    return () => controller.abort();
  }, []);

  const logout = useCallback(async () => {
    await api.logout();
    // Give the browser its anonymous identity before any page asks for data, so parallel
    // requests share one identity instead of each creating their own.
    await api.initLearner();
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, ready, setUser, logout }), [user, ready, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  return useContext(AuthContext);
}
