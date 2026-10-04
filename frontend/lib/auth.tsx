"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import type { SessionInfo, User } from "@/types/auth";
import { ApiError, api, onUnauthorized, setCsrfToken } from "./api";
import { useTheme } from "./theme";

interface AuthContextValue {
  user: User | null;
  timezone: string;
  status: "loading" | "authenticated" | "unauthenticated";
  login: (email: string, password: string, remember: boolean) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  setUser: (user: User) => void;
  setTimezone: (tz: string) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);
const FALLBACK_TZ = "Asia/Kolkata";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { setTheme } = useTheme();
  const [user, setUser] = useState<User | null>(null);
  const [timezone, setTimezone] = useState(FALLBACK_TZ);
  const [status, setStatus] = useState<AuthContextValue["status"]>("loading");
  const pathRef = useRef(pathname);
  useEffect(() => {
    pathRef.current = pathname;
  }, [pathname]);

  const applySession = useCallback(
    (session: SessionInfo) => {
      setCsrfToken(session.csrf_token);
      setUser(session.user);
      setTimezone(session.settings.timezone || FALLBACK_TZ);
      setTheme(session.settings.theme, { persistRemote: false });
      setStatus("authenticated");
    },
    [setTheme],
  );

  const clearSession = useCallback(() => {
    setCsrfToken(null);
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  const refresh = useCallback(async () => {
    try {
      applySession(await api.get<SessionInfo>("/auth/me"));
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        clearSession();
        return;
      }
      throw error;
    }
  }, [applySession, clearSession]);

  useEffect(() => {
    let cancelled = false;
    api.get<SessionInfo>("/auth/me")
      .then((session) => !cancelled && applySession(session))
      .catch(() => !cancelled && clearSession());
    return () => {
      cancelled = true;
    };
  }, [applySession, clearSession]);

  useEffect(() => {
    onUnauthorized(() => {
      clearSession();
      const current = pathRef.current;
      if (current !== "/login") router.replace(`/login?next=${encodeURIComponent(current)}&expired=1`);
    });
    return () => onUnauthorized(null);
  }, [router, clearSession]);

  const login = useCallback(
    async (email: string, password: string, remember: boolean) => {
      applySession(await api.post<SessionInfo>("/auth/login", { email, password, remember }));
    },
    [applySession],
  );

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } finally {
      clearSession();
      router.replace("/login");
    }
  }, [router, clearSession]);

  const value = useMemo(
    () => ({ user, timezone, status, login, logout, refresh, setUser, setTimezone }),
    [user, timezone, status, login, logout, refresh],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
