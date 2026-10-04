import { AlertOctagon, CheckCircle2, ListChecks, Timer } from "lucide-react";

import { cn } from "@/lib/utils";
import type { DaySummary } from "@/types/work";

export default function DashboardStats({ summary, compact = false }: { summary: DaySummary; compact?: boolean }) {
  const stats = [
    { label: "Completed", value: summary.completed, Icon: CheckCircle2, tone: "bg-success-soft text-success" },
    { label: "In progress", value: summary.in_progress, Icon: Timer, tone: "bg-info-soft text-info" },
    {
      label: summary.blockers === 1 ? "Blocker" : "Blockers", value: summary.blockers, Icon: AlertOctagon,
      tone: summary.blockers ? "bg-danger-soft text-danger" : "bg-surface-hover text-subtle",
    },
    { label: "Total entries", value: summary.total_entries, Icon: ListChecks, tone: "bg-accent-soft text-accent" },
  ];
  return (
    <dl className={cn("grid grid-cols-2 gap-3", !compact && "lg:grid-cols-4")}>
      {stats.map(({ label, value, Icon, tone }) => (
        <div key={label} className="flex items-center gap-3 rounded-2xl border border-line bg-surface p-4 shadow-card">
          <span aria-hidden className={cn("flex h-11 w-11 shrink-0 items-center justify-center rounded-xl", tone)}>
            <Icon className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <dt className="truncate text-[12.5px] font-medium text-muted">{label}</dt>
            <dd className="text-2xl font-extrabold tabular-nums leading-tight text-text">{value}</dd>
          </div>
        </div>
      ))}
    </dl>
  );
}
