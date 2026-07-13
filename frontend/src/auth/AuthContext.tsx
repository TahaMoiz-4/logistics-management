/**
 * Auth state for the app: who's logged in, and login/logout actions.
 *
 * On mount, if a token is present we call /auth/me to (a) validate it and
 * (b) hydrate the current user. A 401 anywhere clears the token and drops us
 * back to the login screen via the client's onUnauthorized hook.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { authApi } from "@/api/endpoints";
import { onUnauthorized } from "@/api/client";
import { clearToken, getToken, setToken } from "@/api/token";
import type { LoginRequest, SysUser } from "@/api/types";

interface AuthState {
  user: SysUser | null;
  /** True until we've resolved the initial token (avoids a login-screen flash). */
  initializing: boolean;
  login: (creds: LoginRequest) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SysUser | null>(null);
  const [initializing, setInitializing] = useState(true);

  // Validate an existing token on first load.
  useEffect(() => {
    let cancelled = false;
    const token = getToken();
    if (!token) {
      setInitializing(false);
      return;
    }
    authApi
      .me()
      .then((u) => {
        if (!cancelled) setUser(u);
      })
      .catch(() => {
        // Invalid/expired token — clear and stay logged out.
        clearToken();
      })
      .finally(() => {
        if (!cancelled) setInitializing(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Any 401 from the client forces a logout.
  useEffect(() => onUnauthorized(() => setUser(null)), []);

  const login = useCallback(async (creds: LoginRequest) => {
    const res = await authApi.login(creds);
    setToken(res.token);
    setUser(res.user);
  }, []);

  const logout = useCallback(() => {
    // Fire-and-forget server logout; local state is the source of truth.
    authApi.logout().catch(() => {});
    clearToken();
    setUser(null);
  }, []);

  const value = useMemo<AuthState>(
    () => ({ user, initializing, login, logout }),
    [user, initializing, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
