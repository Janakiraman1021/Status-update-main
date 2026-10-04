import { CalendarCheck2, FileCheck2, ShieldCheck } from "lucide-react";
import { Suspense } from "react";

import { ThemeToggle } from "@/components/Header";
import LoginForm from "@/components/LoginForm";

const FEATURES = [
  { Icon: CalendarCheck2, title: "Log as you go", text: "Capture work in plain notes, any time of the day." },
  { Icon: FileCheck2, title: "EOD in one click", text: "A polished report written only from what you recorded." },
  { Icon: ShieldCheck, title: "Never miss EOD", text: "Sent on time automatically, and never twice." },
];

export default function LoginPage() {
  return (
    <div className="grid min-h-screen lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
      {/* Brand panel */}
      <aside className="relative hidden overflow-hidden bg-nav px-12 py-12 text-nav-strong lg:flex lg:flex-col">
        <div aria-hidden className="pointer-events-none absolute -right-24 top-24 h-80 w-80 rounded-full border-[40px] border-nav-accent/10" />
        <div aria-hidden className="pointer-events-none absolute -bottom-24 -left-16 h-72 w-72 rounded-full bg-accent/10" />
        <div className="relative flex items-center gap-2.5">
          <span aria-hidden className="flex h-10 w-10 items-center justify-center rounded-xl bg-nav-accent text-lg font-extrabold text-nav">W</span>
          <span className="text-lg font-extrabold tracking-tight">WorkLog</span>
        </div>
        <div className="relative my-auto max-w-md">
          <h2 className="text-[34px] font-extrabold leading-[1.15] tracking-tight">
            Your workday, documented.<br />
            <span className="text-nav-accent">Your EOD, handled.</span>
          </h2>
          <ul className="mt-10 space-y-6">
            {FEATURES.map(({ Icon, title, text }) => (
              <li key={title} className="flex gap-4">
                <span aria-hidden className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/5 text-nav-accent ring-1 ring-white/10">
                  <Icon className="h-5 w-5" />
                </span>
                <div>
                  <p className="font-bold">{title}</p>
                  <p className="text-sm text-nav-text">{text}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-nav-text">Samunnati · Internal productivity tool</p>
      </aside>

      {/* Sign-in */}
      <div className="relative flex items-center justify-center px-5 py-12 sm:px-10">
        <div className="absolute right-4 top-4">
          <ThemeToggle />
        </div>
        <main className="w-full max-w-[400px]">
          <div className="mb-8">
            <span aria-hidden className="mb-6 flex h-11 w-11 items-center justify-center rounded-xl bg-nav text-lg font-extrabold text-nav-accent lg:hidden">W</span>
            <h1 className="text-[28px] font-extrabold tracking-tight">Sign in to WorkLog</h1>
            <p className="mt-1.5 text-sm text-muted">Welcome back. Pick up where you left off.</p>
          </div>
          <div className="rounded-2xl border border-line bg-surface p-6 shadow-raised sm:p-7">
            <Suspense fallback={null}>
              <LoginForm />
            </Suspense>
          </div>
        </main>
      </div>
    </div>
  );
}
