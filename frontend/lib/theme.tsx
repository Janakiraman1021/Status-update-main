"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useSyncExternalStore } from "react";

import type { Theme } from "@/types/auth";
import { api } from "./api";

export const THEME_STORAGE_KEY = "worklog-theme";

/**
 * Runs before first paint (inlined in <head>) so the page never flashes the wrong theme.
 * Keep in sync with applyTheme below.
 */
export const themeInitScript = `(function(){try{var t=localStorage.getItem('${THEME_STORAGE_KEY}')||'system';var d=t==='dark'||(t==='system'&&window.matchMedia('(prefers-color-scheme: dark)').matches);var r=document.documentElement;r.classList.toggle('dark',d);r.dataset.theme=t;}catch(e){}})();`;

// --- tiny external store: the stored preference + OS preference ------------

const listeners = new Set<() => void>();
const DARK_QUERY = "(prefers-color-scheme: dark)";

function readStoredTheme(): Theme {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    return stored === "light" || stored === "dark" ? stored : "system";
  } catch {
    return "system";
  }
}

function writeStoredTheme(theme: Theme) {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    /* storage unavailable — the theme still applies for this session */
  }
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  const media = window.matchMedia(DARK_QUERY);
  media.addEventListener("change", listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    media.removeEventListener("change", listener);
    window.removeEventListener("storage", listener);
  };
}

const prefersDark = () => window.matchMedia(DARK_QUERY).matches;

function applyTheme(theme: Theme, dark: boolean) {
  document.documentElement.classList.toggle("dark", dark);
  document.documentElement.dataset.theme = theme;
}

interface ThemeContextValue {
  theme: Theme;
  resolved: "light" | "dark";
  setTheme: (theme: Theme, options?: { persistRemote?: boolean }) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const theme = useSyncExternalStore<Theme>(subscribe, readStoredTheme, () => "system");
  const osDark = useSyncExternalStore(subscribe, prefersDark, () => false);
  const resolved: "light" | "dark" = theme === "dark" || (theme === "system" && osDark) ? "dark" : "light";

  useEffect(() => {
    applyTheme(theme, resolved === "dark");
  }, [theme, resolved]);

  const setTheme = useCallback((next: Theme, options?: { persistRemote?: boolean }) => {
    writeStoredTheme(next);
    if (options?.persistRemote !== false) {
      api.put("/settings", { theme: next }).catch(() => undefined);
    }
  }, []);

  const value = useMemo(() => ({ theme, resolved, setTheme }), [theme, resolved, setTheme]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used inside ThemeProvider");
  return ctx;
}
