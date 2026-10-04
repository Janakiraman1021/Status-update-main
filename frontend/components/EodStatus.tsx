import { AlertCircle, CheckCircle2, CircleDashed, FileText, Loader2, Send } from "lucide-react";

import { cn } from "@/lib/utils";
import type { EodStatusValue } from "@/types/eod";

const config: Record<EodStatusValue, { label: string; className: string; Icon: typeof FileText; spin?: boolean }> = {
  NOT_GENERATED: { label: "Not generated", className: "border-line-strong bg-surface-2 text-muted", Icon: CircleDashed },
  GENERATING: { label: "Generating", className: "border-info/30 bg-info-soft text-info", Icon: Loader2, spin: true },
  GENERATED: { label: "Generated", className: "border-primary/30 bg-primary-soft text-primary", Icon: FileText },
  SENDING: { label: "Sending", className: "border-info/30 bg-info-soft text-info", Icon: Send },
  SENT: { label: "Sent", className: "border-success/30 bg-success-soft text-success", Icon: CheckCircle2 },
  FAILED: { label: "Failed", className: "border-danger/35 bg-danger-soft text-danger", Icon: AlertCircle },
};

/** Status is conveyed by text and icon, not by colour alone. */
export default function EodStatus({ status, className, prefix = true }: { status: EodStatusValue; className?: string; prefix?: boolean }) {
  const { label, className: tone, Icon, spin } = config[status] ?? config.NOT_GENERATED;
  return (
    <span className={cn("inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium", tone, className)}>
      <Icon aria-hidden className={cn("h-3.5 w-3.5", spin && "animate-spin")} />
      {prefix && <span className="sr-only">EOD status:</span>}
      {label}
    </span>
  );
}
