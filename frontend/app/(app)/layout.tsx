"use client";

import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import Header from "@/components/Header";
import LoadingState from "@/components/LoadingState";
import MobileNav from "@/components/MobileNav";
import Sidebar from "@/components/Sidebar";
import { useAuth } from "@/lib/auth";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = useCallback(() => setMenuOpen(false), []);

  useEffect(() => {
    if (status === "unauthenticated") router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [status, router, pathname]);

  if (status !== "authenticated") {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <LoadingState label="Loading your workspace…" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <a href="#main" className="sr-only-focusable fixed left-2 top-2 z-[70] rounded-lg bg-primary px-3 py-2 text-sm text-primary-text">
        Skip to content
      </a>
      <Sidebar mobileOpen={menuOpen} onClose={closeMenu} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header />
        {/* Bottom padding on phones keeps content clear of the tab bar. */}
        <main id="main" className="mx-auto w-full max-w-[1400px] flex-1 px-4 pb-28 pt-6 sm:px-6 md:pb-10 lg:px-8">
          <div key={pathname} className="animate-fade-up">{children}</div>
        </main>
      </div>
      <MobileNav onMore={() => setMenuOpen(true)} />
    </div>
  );
}
