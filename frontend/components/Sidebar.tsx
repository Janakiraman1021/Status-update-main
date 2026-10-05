"use client";

import {
  CalendarDays, FileText, FolderKanban, History, LayoutDashboard, LogOut, NotebookPen, Settings, ChartNoAxesCombined, X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

export const NAV_SECTIONS = [
  {
    label: "Workspace",
    items: [
      { href: "/dashboard", label: "Dashboard", short: "Home", Icon: LayoutDashboard },
      { href: "/calendar", label: "Calendar", short: "Calendar", Icon: CalendarDays },
      { href: "/work-log", label: "Work Log", short: "Work Log", Icon: NotebookPen },
      { href: "/project-status", label: "Project Status", short: "Status", Icon: ChartNoAxesCombined },
    ],
  },
  {
    label: "Reporting",
    items: [
      { href: "/eod", label: "EOD Reports", short: "EOD", Icon: FileText },
      { href: "/history", label: "History", short: "History", Icon: History },
    ],
  },
  {
    label: "Manage",
    items: [
      { href: "/projects", label: "Projects", short: "Projects", Icon: FolderKanban },
      { href: "/settings", label: "Settings", short: "Settings", Icon: Settings },
    ],
  },
];

export const NAV_ITEMS = NAV_SECTIONS.flatMap((section) => section.items);

export function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link href="/dashboard" className="flex items-center gap-2.5" aria-label="WorkLog home">
      <span aria-hidden className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-nav-accent text-[15px] font-extrabold text-nav">
        W
        <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full border-2 border-nav bg-accent" />
      </span>
      {!compact && (
        <span className="leading-tight">
          <span className="block text-[16px] font-extrabold tracking-tight text-nav-strong">WorkLog</span>
          <span className="block text-[11px] font-medium text-nav-text">Daily work & EOD</span>
        </span>
      )}
    </Link>
  );
}

function NavList({ rail = false, onNavigate }: { rail?: boolean; onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <div className="space-y-5">
      {NAV_SECTIONS.map((section) => (
        <div key={section.label}>
          {rail ? (
            <div className="mx-auto mb-2 h-px w-6 bg-nav-line" aria-hidden />
          ) : (
            <p className="mb-1.5 px-3 text-[10.5px] font-bold uppercase tracking-[0.12em] text-nav-text/70">{section.label}</p>
          )}
          <ul className="space-y-1">
            {section.items.map(({ href, label, Icon }) => {
              const active = isActive(pathname, href);
              return (
                <li key={href}>
                  <Link
                    href={href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    title={rail ? label : undefined}
                    className={cn(
                      "group relative flex items-center rounded-xl text-[14px] font-semibold transition-colors",
                      rail ? "h-11 w-11 justify-center" : "gap-3 px-3 py-2.5",
                      active ? "bg-nav-active text-nav-strong" : "text-nav-text hover:bg-nav-active/60 hover:text-nav-strong",
                    )}
                  >
                    {active && <span aria-hidden className={cn("absolute rounded-full bg-nav-accent", rail ? "-left-2.5 h-5 w-1" : "-left-3 h-6 w-1")} />}
                    <Icon aria-hidden className={cn("h-[18px] w-[18px] shrink-0", active ? "text-nav-accent" : "")} />
                    <span className={rail ? "sr-only" : ""}>{label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}

function UserCard({ rail = false }: { rail?: boolean }) {
  const { user, logout } = useAuth();
  if (!user) return null;
  const initials = user.name.split(/\s+/).map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  if (rail) {
    return (
      <button type="button" onClick={() => logout()} title="Log out" aria-label="Log out"
        className="flex h-11 w-11 items-center justify-center rounded-xl text-nav-text hover:bg-nav-active hover:text-nav-strong">
        <LogOut className="h-[18px] w-[18px]" />
      </button>
    );
  }
  return (
    <div className="flex items-center gap-3 rounded-xl bg-nav-active/60 p-2.5">
      <span aria-hidden className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-nav-accent/20 text-[13px] font-bold text-nav-accent">{initials}</span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-[13px] font-semibold text-nav-strong">{user.name}</p>
        <p className="truncate text-[11.5px] text-nav-text">{user.email}</p>
      </div>
      <button type="button" onClick={() => logout()} aria-label="Log out" title="Log out"
        className="rounded-lg p-1.5 text-nav-text hover:bg-nav-active hover:text-nav-strong">
        <LogOut className="h-4 w-4" />
      </button>
    </div>
  );
}

/**
 * Desktop (≥1280px): full sidebar. Tablet (768–1279px): icon rail. Phones use the bottom tab bar
 * (MobileNav) plus this drawer for the full menu.
 */
export default function Sidebar({ mobileOpen, onClose }: { mobileOpen: boolean; onClose: () => void }) {
  useEffect(() => {
    if (!mobileOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mobileOpen, onClose]);

  return (
    <>
      {/* Full sidebar */}
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-nav-line bg-nav xl:flex">
        <div className="px-5 pb-6 pt-6">
          <Brand />
        </div>
        <nav aria-label="Main navigation" className="flex-1 overflow-y-auto px-4">
          <NavList />
        </nav>
        <div className="border-t border-nav-line p-4">
          <UserCard />
        </div>
      </aside>

      {/* Icon rail */}
      <aside className="sticky top-0 hidden h-screen w-[76px] shrink-0 flex-col items-center border-r border-nav-line bg-nav md:flex xl:hidden">
        <div className="py-5">
          <Brand compact />
        </div>
        <nav aria-label="Main navigation" className="flex-1 overflow-y-auto px-3">
          <NavList rail />
        </nav>
        <div className="py-4">
          <UserCard rail />
        </div>
      </aside>

      {/* Drawer (phones: opened from the "More" tab or the header menu button) */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-[2px]" onClick={onClose} aria-hidden />
          <aside className="animate-fade-up absolute inset-y-0 left-0 flex w-[84%] max-w-xs flex-col bg-nav shadow-2xl">
            <div className="flex items-center justify-between px-5 pb-5 pt-5">
              <Brand />
              <button type="button" onClick={onClose} className="rounded-lg p-2 text-nav-text hover:bg-nav-active hover:text-nav-strong" aria-label="Close navigation">
                <X className="h-5 w-5" />
              </button>
            </div>
            <nav aria-label="Main navigation" className="flex-1 overflow-y-auto px-4">
              <NavList onNavigate={onClose} />
            </nav>
            <div className="safe-bottom border-t border-nav-line p-4">
              <UserCard />
            </div>
          </aside>
        </div>
      )}
    </>
  );
}
