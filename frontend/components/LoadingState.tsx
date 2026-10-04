import { Loader2 } from "lucide-react";

export default function LoadingState({ label = "Loading…", rows = 0 }: { label?: string; rows?: number }) {
  if (rows > 0) {
    return (
      <div role="status" aria-label={label} className="space-y-2">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="h-10 animate-pulse rounded-md bg-surface-hover" />
        ))}
        <span className="sr-only">{label}</span>
      </div>
    );
  }
  return (
    <div role="status" className="flex items-center justify-center gap-2 py-12 text-sm text-muted">
      <Loader2 aria-hidden className="h-4 w-4 animate-spin" />
      {label}
    </div>
  );
}
