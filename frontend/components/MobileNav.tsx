"use client";

import { CalendarDays, FileText, LayoutDashboard, Menu, NotebookPen } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";
import { isActive } from "./Sidebar";

const TABS = [
  { href: "/dashboard", label: "Home", Icon: LayoutDashboard },
  { href: "/calendar", label: "Calendar", Icon: CalendarDays },
  { href: "/work-log", label: "Work Log", Icon: NotebookPen },
  { href: "/eod", label: "EOD", Icon: FileText },
];

/** Bottom tab bar for phones; "More" opens the full navigation drawer. */
export default function MobileNav({ onMore }: { onMore: () => void }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Mobile navigation"
      className="safe-bottom fixed inset-x-0 bottom-0 z-40 border-t border-line bg-surface/95 shadow-[0_-4px_16px_-8px_rgba(0,0,0,0.15)] backdrop-blur md:hidden">
      <ul className="grid grid-cols-5">
        {TABS.map(({ href, label, Icon }) => {
          const active = isActive(pathname, href);
          return (
            <li key={href}>
              <Link href={href} aria-current={active ? "page" : undefined}
                className={cn("flex flex-col items-center gap-0.5 pb-2 pt-2.5 text-[11px] font-semibold transition-colors",
                  active ? "text-primary" : "text-subtle hover:text-text")}>
                <span className={cn("flex h-7 w-12 items-center justify-center rounded-full transition-colors", active && "bg-primary-soft")}>
                  <Icon aria-hidden className="h-[19px] w-[19px]" />
                </span>
                {label}
              </Link>
            </li>
          );
        })}
        <li>
          <button type="button" onClick={onMore}
            className="flex w-full flex-col items-center gap-0.5 pb-2 pt-2.5 text-[11px] font-semibold text-subtle hover:text-text">
            <span className="flex h-7 w-12 items-center justify-center rounded-full">
              <Menu aria-hidden className="h-[19px] w-[19px]" />
            </span>
            More
          </button>
        </li>
      </ul>
    </nav>
  );
}
