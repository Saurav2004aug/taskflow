import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, setUnauthorizedHandler, tokenStore } from "../api/client";
import type { User } from "../api/types";

interface AuthState {
  user: User | null;
  loading: boolean; // true while we check a saved token on startup
  notice: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: (notice?: string) => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(() => tokenStore.get() !== null);
  const [notice, setNotice] = useState<string | null>(null);

  const logout = useCallback((message?: string) => {
    tokenStore.set(null);
    setUser(null);
    setNotice(message ?? null);
  }, []);

  // Any 401 from the API (expired token) signs the user out with a clear message.
  useEffect(() => {
    setUnauthorizedHandler(() => logout("Your session expired. Please log in again."));
  }, [logout]);

  // Restore the session from a saved token.
  useEffect(() => {
    if (!tokenStore.get()) return;
    api
      .me()
      .then(({ user }) => setUser(user))
      .catch(() => tokenStore.set(null))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.login(email, password);
    tokenStore.set(res.token);
    setNotice(null);
    setUser(res.user);
  }, []);

  const register = useCallback(async (name: string, email: string, password: string) => {
    const res = await api.register(name, email, password);
    tokenStore.set(res.token);
    setNotice(null);
    setUser(res.user);
  }, []);

  const value = useMemo(
    () => ({ user, loading, notice, login, register, logout }),
    [user, loading, notice, login, register, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
