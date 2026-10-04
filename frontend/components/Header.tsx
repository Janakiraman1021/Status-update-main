"use client";

import { LogOut, Monitor, Moon, Settings, Sun } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/lib/auth";
import { formatLong, todayIn, weekdayName } from "@/lib/date";
import { useTheme } from "@/lib/theme";
import type { Theme } from "@/types/auth";
import { NAV_ITEMS, isActive } from "./Sidebar";

const THEME_ORDER: Theme[] = ["light", "dark", "system"];
const THEME_META: Record<Theme, { label: string; Icon: typeof Sun }> = {
  light: { label: "Light", Icon: Sun },
  dark: { label: "Dark", Icon: Moon },
  system: { label: "System", Icon: Monitor },
};

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const next = THEME_ORDER[(THEME_ORDER.indexOf(theme) + 1) % THEME_ORDER.length];
  const { Icon, label } = THEME_META[theme];
  return (
    <button
      type="button"
      onClick={() => setTheme(next)}
      className="flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-surface text-muted shadow-card hover:border-primary/40 hover:text-primary"
      aria-label={`Theme: ${label}. Switch to ${THEME_META[next].label}.`}
      title={`Theme: ${label}`}
    >
      <Icon aria-hidden className="h-4 w-4" />
    </button>
  );
}

function UserMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!user) return null;
  const initials = user.name.split(/\s+/).map((p) => p[0]).slice(0, 2).join("").toUpperCase();

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-2 rounded-lg border border-transparent px-1.5 py-1 hover:border-line hover:bg-surface"
      >
        <span aria-hidden className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-xs font-bold text-primary-text">{initials}</span>
        <span className="hidden text-[13px] font-medium text-text sm:inline">{user.name}</span>
      </button>
      {open && (
        <div role="menu" className="animate-fade-up absolute right-0 z-40 mt-2 w-60 rounded-xl border border-line bg-surface py-1.5 shadow-raised">
          <div className="border-b border-line px-3 py-2">
            <p className="truncate text-[13px] font-medium text-text">{user.name}</p>
            <p className="truncate text-xs text-muted">{user.email}</p>
          </div>
          <Link role="menuitem" href="/settings" onClick={() => setOpen(false)} className="flex items-center gap-2 px-3 py-2 text-[13px] text-text hover:bg-surface-hover">
            <Settings aria-hidden className="h-4 w-4 text-muted" /> Profile & settings
          </Link>
          <button role="menuitem" type="button" onClick={() => logout()} className="flex w-full items-center gap-2 px-3 py-2 text-left text-[13px] text-text hover:bg-surface-hover">
            <LogOut aria-hidden className="h-4 w-4 text-muted" /> Log out
          </button>
        </div>
      )}
    </div>
  );
}

function sectionTitle(pathname: string): string {
  const match = NAV_ITEMS.find((item) => isActive(pathname, item.href));
  return match?.label ?? "WorkLog";
}

export default function Header() {
  const { timezone } = useAuth();
  const pathname = usePathname();
  // The app shell only renders client-side after authentication, so reading the clock here is safe.
  const today = todayIn(timezone);

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-line bg-bg/80 px-4 backdrop-blur-md sm:px-6 lg:px-8">
      <span className="md:hidden">
        <span aria-hidden className="flex h-8 w-8 items-center justify-center rounded-lg bg-nav text-[13px] font-extrabold text-nav-accent">W</span>
      </span>
      <div className="min-w-0">
        <p className="truncate text-[15px] font-bold text-text">{sectionTitle(pathname)}</p>
        <p className="hidden text-xs text-muted sm:block">
          {weekdayName(today)}, {formatLong(today)}
        </p>
      </div>
      <div className="ml-auto flex items-center gap-1.5">
        <ThemeToggle />
        <UserMenu />
      </div>
    </header>
  );
}
