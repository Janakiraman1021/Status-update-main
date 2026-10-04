"use client";

import { ArrowRight, CalendarClock, Check, FileText, NotebookPen, Send, Sparkles } from "lucide-react";
import Link from "next/link";

import BlockerCard from "@/components/BlockerCard";
import DashboardStats from "@/components/DashboardStats";
import EmptyState from "@/components/EmptyState";
import EodStatus from "@/components/EodStatus";
import ErrorState from "@/components/ErrorState";
import LoadingState from "@/components/LoadingState";
import StatusBadge from "@/components/StatusBadge";
import { Card, CardHeader } from "@/components/ui";
import { formatShort, weekdayName } from "@/lib/date";
import { useApi } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import type { DashboardData } from "@/types/work";

const linkButton = "inline-flex h-10 items-center gap-2 rounded-lg px-4 text-sm font-semibold transition-all active:scale-[0.98]";

/** Today's EOD journey: logged → generated → sent. */
function EodProgress({ data }: { data: DashboardData }) {
  const status = data.eod.status;
  const generated = data.eod.current_version > 0;
  const sent = status === "SENT";
  const steps = [
    { label: "Work logged", done: data.has_work, Icon: NotebookPen, href: `/work-log/${data.today}` },
    { label: "EOD generated", done: generated, Icon: Sparkles, href: `/eod/${data.today}` },
    { label: "EOD sent", done: sent, Icon: Send, href: `/eod/${data.today}` },
  ];
  const current = steps.findIndex((s) => !s.done);
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-[15px] font-bold">Today&apos;s EOD</h2>
          <p className="mt-0.5 flex items-center gap-1.5 text-[13px] text-muted">
            <CalendarClock aria-hidden className="h-3.5 w-3.5" />
            Due {data.eod_time} · auto-send {data.auto_eod_enabled ? "on" : "off"}
          </p>
        </div>
        <EodStatus status={status} />
      </div>
      <ol className="mt-5 space-y-1" aria-label="EOD progress">
        {steps.map((step, index) => {
          const active = index === current;
          return (
            <li key={step.label} className="relative flex items-center gap-3">
              {index < steps.length - 1 && (
                <span aria-hidden className={cn("absolute left-[17px] top-9 h-[calc(100%-12px)] w-0.5", step.done ? "bg-primary" : "bg-line")} />
              )}
              <span aria-hidden className={cn(
                "relative z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-2 transition-colors",
                step.done ? "border-primary bg-primary text-primary-text" : active ? "border-primary bg-primary-soft text-primary" : "border-line bg-surface text-subtle",
              )}>
                {step.done ? <Check className="h-4 w-4" strokeWidth={3} /> : <step.Icon className="h-4 w-4" />}
              </span>
              <Link href={step.href} className="flex flex-1 items-center justify-between rounded-lg py-2.5 pr-1 text-sm hover:text-primary">
                <span className={cn("font-semibold", step.done ? "text-text" : active ? "text-primary" : "text-muted")}>{step.label}</span>
                <span className="text-xs text-subtle">{step.done ? "Done" : active ? "Next" : ""}</span>
              </Link>
            </li>
          );
        })}
      </ol>
    </Card>
  );
}

export default function DashboardPage() {
  const { data, error, loading, reload } = useApi<DashboardData>("/dashboard");

  if (loading && !data) return <LoadingState label="Loading dashboard…" />;
  if (error || !data) return <ErrorState message={error?.message} onRetry={reload} />;

  const firstName = data.user_name.split(" ")[0];
  const eodReady = data.eod.current_version > 0;

  return (
    <div className="space-y-6">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-3xl bg-nav px-6 py-7 text-nav-strong shadow-raised dark:bg-nav-2 dark:ring-1 dark:ring-nav-line sm:px-8 sm:py-8">
        <div aria-hidden className="pointer-events-none absolute -right-16 -top-24 h-64 w-64 rounded-full border-[28px] border-nav-accent/10" />
        <div aria-hidden className="pointer-events-none absolute -bottom-20 right-24 h-40 w-40 rounded-full bg-accent/10" />
        <div className="relative flex flex-wrap items-end justify-between gap-6">
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-nav-accent">{weekdayName(data.today)} · {data.today_label}</p>
            <h1 className="mt-2 text-[26px] font-extrabold leading-tight tracking-tight sm:text-[32px]">
              {data.greeting}, {firstName}
            </h1>
            <p className="mt-1.5 text-sm text-nav-text">
              {data.project_name ? <>Focus project: <span className="font-semibold text-nav-strong">{data.project_name}</span></> : "No project selected for today"}
              {" · "}{data.days_logged_this_week} day{data.days_logged_this_week === 1 ? "" : "s"} logged this week
            </p>
          </div>
          <div className="flex flex-wrap gap-2.5">
            <Link href={`/work-log/${data.today}`} className={`${linkButton} bg-nav-accent text-nav hover:brightness-110`}>
              <NotebookPen aria-hidden className="h-4 w-4" /> Open today&apos;s work
            </Link>
            <Link href={`/eod/${data.today}`} className={`${linkButton} border border-white/15 bg-white/5 text-nav-strong hover:bg-white/10`}>
              <FileText aria-hidden className="h-4 w-4" /> {eodReady ? "View EOD" : "Generate EOD"}
            </Link>
          </div>
        </div>
      </section>

      <DashboardStats summary={data.summary} />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <section aria-labelledby="activity-heading" className="min-w-0">
          <Card>
            <CardHeader id="activity-heading" title="Recent activity" description="Your latest work entries"
              actions={<Link href="/history" className="text-[13px] font-semibold text-primary hover:underline">View history</Link>} />
            {data.recent_activity.length === 0 ? (
              <EmptyState title="No activity yet" description="Work entries you add will appear here."
                action={<Link href={`/work-log/${data.today}`} className="text-sm font-semibold text-primary hover:underline">Add your first note</Link>} />
            ) : (
              <ul className="divide-y divide-line">
                {data.recent_activity.map((item) => (
                  <li key={item.id}>
                    <Link href={`/work-log/${item.work_date}`} className="flex items-start gap-4 px-5 py-3.5 transition-colors hover:bg-surface-2">
                      <span className="w-[4.5rem] shrink-0 pt-0.5 text-xs font-medium tabular-nums text-subtle">
                        {formatShort(item.work_date).slice(0, 6)}<br />{item.time_label}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-[14px] font-medium text-text">{item.description}</span>
                        {item.project_name && <span className="mt-0.5 block text-xs text-muted">{item.project_name}</span>}
                      </span>
                      <StatusBadge status={item.status} className="hidden sm:inline-flex" />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </section>

        <div className="space-y-6">
          <EodProgress data={data} />

          <section aria-labelledby="blockers-heading">
            <Card>
              <CardHeader id="blockers-heading" title="Open blockers" description={`${data.open_blocker_count} open · ${data.open_ask_count} ask${data.open_ask_count === 1 ? "" : "s"} pending`} />
              <div className="space-y-2.5 p-4">
                {data.open_blockers.length === 0 ? (
                  <p className="py-2 text-center text-[13px] text-muted">Nothing blocking you.</p>
                ) : (
                  data.open_blockers.map((b) => <BlockerCard key={b.id} blocker={b} showDateLink />)
                )}
              </div>
            </Card>
          </section>

          <section aria-labelledby="eods-heading">
            <Card>
              <CardHeader id="eods-heading" title="Recent EOD reports"
                actions={<Link href="/history?tab=eod" className="text-[13px] font-semibold text-primary hover:underline">View all</Link>} />
              {data.recent_eods.length === 0 ? (
                <p className="px-5 py-4 text-[13px] text-muted">No reports yet.</p>
              ) : (
                <ul className="divide-y divide-line">
                  {data.recent_eods.map((eod) => (
                    <li key={eod.id}>
                      <Link href={`/eod/${eod.id}`} className="flex items-center justify-between gap-2 px-5 py-3 transition-colors hover:bg-surface-2">
                        <span className="min-w-0">
                          <span className="block text-[13.5px] font-semibold text-text">{formatShort(eod.work_date)}</span>
                          <span className="block truncate text-xs text-muted">{eod.project_label ?? "—"}</span>
                        </span>
                        <span className="flex items-center gap-1.5">
                          <EodStatus status={eod.status} />
                          <ArrowRight aria-hidden className="h-3.5 w-3.5 text-subtle" />
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </section>
        </div>
      </div>
    </div>
  );
}
