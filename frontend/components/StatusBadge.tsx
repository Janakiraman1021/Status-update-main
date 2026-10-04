import { cn } from "@/lib/utils";

const tones: Record<string, string> = {
  Completed: "border-success/30 bg-success-soft text-success",
  "In Progress": "border-info/30 bg-info-soft text-info",
  Planned: "border-line-strong bg-surface-2 text-muted",
  Blocked: "border-danger/35 bg-danger-soft text-danger",
  Deferred: "border-warning/35 bg-warning-soft text-warning",
  Open: "border-danger/35 bg-danger-soft text-danger",
  Resolved: "border-success/30 bg-success-soft text-success",
  Active: "border-success/30 bg-success-soft text-success",
  Archived: "border-line-strong bg-surface-2 text-muted",
};

export default function StatusBadge({ status, className }: { status: string | null | undefined; className?: string }) {
  if (!status) return null;
  return (
    <span className={cn("inline-flex items-center rounded-full border px-2 py-0.5 text-[11.5px] font-medium", tones[status] ?? tones.Planned, className)}>
      {status}
    </span>
  );
}

export function CategoryTag({ category }: { category: string | null | undefined }) {
  if (!category) return null;
  return <span className="inline-flex items-center rounded border border-line bg-surface-2 px-1.5 py-0.5 text-[11.5px] text-muted">{category}</span>;
}
