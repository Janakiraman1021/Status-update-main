"use client";

import { CheckCircle2, RotateCcw } from "lucide-react";
import Link from "next/link";

import { formatShort } from "@/lib/date";
import type { Blocker, Dependency } from "@/types/work";
import StatusBadge from "./StatusBadge";
import { Button } from "./ui";

export default function BlockerCard({ blocker, onStatusChange, busy, showDateLink = false }: {
  blocker: Blocker; onStatusChange?: (status: Blocker["status"]) => void; busy?: boolean; showDateLink?: boolean;
}) {
  const resolved = blocker.status === "Resolved";
  return (
    <article className="rounded-md border border-line bg-surface px-3 py-2.5" aria-label={`Blocker: ${blocker.description}`}>
      <div className="flex items-start justify-between gap-2">
        <p className={resolved ? "text-[13px] text-muted line-through" : "text-[13px] text-text"}>{blocker.description}</p>
        <StatusBadge status={blocker.status} className="shrink-0" />
      </div>
      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
        <span>
          Since{" "}
          {showDateLink ? (
            <Link className="text-primary hover:underline" href={`/work-log/${blocker.identified_date}`}>{formatShort(blocker.identified_date)}</Link>
          ) : (
            formatShort(blocker.identified_date)
          )}
        </span>
        {blocker.project_name && <span>{blocker.project_name}</span>}
        {blocker.dependency && <span>Depends on: {blocker.dependency}</span>}
        {blocker.expected_resolution && <span>Expected: {formatShort(blocker.expected_resolution)}</span>}
        {blocker.resolved_date && <span>Resolved {formatShort(blocker.resolved_date)}</span>}
      </div>
      {onStatusChange && (
        <div className="mt-2 flex gap-1.5">
          {resolved ? (
            <Button size="sm" variant="ghost" disabled={busy} onClick={() => onStatusChange("Open")} icon={<RotateCcw aria-hidden className="h-3.5 w-3.5" />}>Reopen</Button>
          ) : (
            <>
              <Button size="sm" variant="ghost" disabled={busy} onClick={() => onStatusChange("Resolved")} icon={<CheckCircle2 aria-hidden className="h-3.5 w-3.5" />}>Mark resolved</Button>
              {blocker.status === "Open" && (
                <Button size="sm" variant="ghost" disabled={busy} onClick={() => onStatusChange("In Progress")}>Working on it</Button>
              )}
            </>
          )}
        </div>
      )}
    </article>
  );
}

export function DependencyCard({ dependency, onStatusChange, busy }: {
  dependency: Dependency; onStatusChange?: (status: Dependency["status"]) => void; busy?: boolean;
}) {
  const resolved = dependency.status === "Resolved";
  return (
    <article className="rounded-md border border-line bg-surface px-3 py-2.5" aria-label={`${dependency.type}: ${dependency.description}`}>
      <div className="flex items-start justify-between gap-2">
        <p className={resolved ? "text-[13px] text-muted line-through" : "text-[13px] text-text"}>{dependency.description}</p>
        <StatusBadge status={dependency.status} className="shrink-0" />
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
        <span className="font-medium text-text/80">{dependency.type}</span>
        {dependency.owner && <span>Owner: {dependency.owner}</span>}
        <span>Raised {formatShort(dependency.created_date)}</span>
        {dependency.project_name && <span>{dependency.project_name}</span>}
      </div>
      {onStatusChange && (
        <div className="mt-2">
          <Button size="sm" variant="ghost" disabled={busy} onClick={() => onStatusChange(resolved ? "Open" : "Resolved")}
            icon={resolved ? <RotateCcw aria-hidden className="h-3.5 w-3.5" /> : <CheckCircle2 aria-hidden className="h-3.5 w-3.5" />}>
            {resolved ? "Reopen" : "Mark resolved"}
          </Button>
        </div>
      )}
    </article>
  );
}
