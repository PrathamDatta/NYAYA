import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, ApiError, type User } from "./api";

interface AuthState { user: User | null; loading: boolean; login: (e: string, p: string) => Promise<void>; register: (e: string, p: string, n: string) => Promise<void>; logout: () => Promise<void> }
const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api<User>("/api/auth/me").then(setUser).catch((e) => { if (!(e instanceof ApiError && e.status === 401)) console.warn(e); }).finally(() => setLoading(false));
  }, []);
  const login = useCallback(async (email: string, password: string) => setUser(await api<User>("/api/auth/login", { method: "POST", json: { email, password } })), []);
  const register = useCallback(async (email: string, password: string, display_name: string) => setUser(await api<User>("/api/auth/register", { method: "POST", json: { email, password, display_name } })), []);
  const logout = useCallback(async () => { await api("/api/auth/logout", { method: "POST" }); setUser(null); }, []);
  const v = useMemo(() => ({ user, loading, login, register, logout }), [user, loading, login, register, logout]);
  return <Ctx.Provider value={v}>{children}</Ctx.Provider>;
}
export function useAuth() { const c = useContext(Ctx); if (!c) throw new Error("AuthProvider missing"); return c; }
