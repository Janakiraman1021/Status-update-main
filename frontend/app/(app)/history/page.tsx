"use client";

import { Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { EMPTY_WORK_FILTERS, EodHistoryTable, WorkHistoryFilters, WorkHistoryTable, type WorkFilters } from "@/components/HistoryTables";
import LoadingState from "@/components/LoadingState";
import StatusBadge from "@/components/StatusBadge";
import { Alert, Button, Card, Dialog, Input, PageHeader, Select } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { formatShort } from "@/lib/date";
import { useApi, useDebouncedValue } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import type { Project } from "@/types/project";

interface SearchResults {
  notes: { work_date: string; field: string; snippet: string }[];
  blockers: { id: string; description: string; status: string; identified_date: string }[];
  dependencies: { id: string; description: string; status: string; type: string; created_date: string }[];
  projects: { id: string; name: string; status: string }[];
}

const FIELD_LABEL: Record<string, string> = { quick_notes: "Notes", next_steps: "Next steps", learnings: "Learnings", meetings: "Meetings", metrics: "Testing & metrics" };

function RelatedResults({ q }: { q: string }) {
  const debounced = useDebouncedValue(q.trim(), 400);
  const { data } = useApi<SearchResults>(debounced.length >= 2 ? `/history/search?q=${encodeURIComponent(debounced)}` : null);
  if (!data || debounced.length < 2) return null;
  const total = data.notes.length + data.blockers.length + data.dependencies.length;
  if (!total) return null;
  return (
    <Card className="mt-4">
      <div className="border-b border-line px-4 py-2.5 text-sm font-semibold">Also found in notes, blockers and asks</div>
      <ul className="divide-y divide-line text-[13px]">
        {data.notes.map((n, i) => (
          <li key={`n-${i}`} className="flex gap-3 px-4 py-2">
            <Link href={`/work-log/${n.work_date}`} className="w-24 shrink-0 font-medium text-primary hover:underline">{formatShort(n.work_date)}</Link>
            <span className="w-28 shrink-0 text-muted">{FIELD_LABEL[n.field] ?? n.field}</span>
            <span className="text-text">{n.snippet}</span>
          </li>
        ))}
        {data.blockers.map((b) => (
          <li key={b.id} className="flex flex-wrap gap-3 px-4 py-2">
            <Link href={`/work-log/${b.identified_date}`} className="w-24 shrink-0 font-medium text-primary hover:underline">{formatShort(b.identified_date)}</Link>
            <span className="w-28 shrink-0 text-muted">Blocker</span>
            <span className="flex-1 text-text">{b.description}</span>
            <StatusBadge status={b.status} />
          </li>
        ))}
        {data.dependencies.map((d) => (
          <li key={d.id} className="flex flex-wrap gap-3 px-4 py-2">
            <Link href={`/work-log/${d.created_date}`} className="w-24 shrink-0 font-medium text-primary hover:underline">{formatShort(d.created_date)}</Link>
            <span className="w-28 shrink-0 text-muted">{d.type}</span>
            <span className="flex-1 text-text">{d.description}</span>
            <StatusBadge status={d.status} />
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** Mounted only while open, so every opening fetches a fresh summary. */
function SummaryDialog({ from, to, onClose }: { from: string; to: string; onClose: () => void }) {
  const [state, setState] = useState<{ loading: boolean; summary?: string; count?: number; error?: string }>({ loading: true });
  useEffect(() => {
    let cancelled = false;
    api.get<{ summary: string; entry_count: number }>("/history/summary", { from, to })
      .then((r) => !cancelled && setState({ loading: false, summary: r.summary, count: r.entry_count }))
      .catch((err) => !cancelled && setState({ loading: false, error: errorMessage(err) }));
    return () => {
      cancelled = true;
    };
  }, [from, to]);
  return (
    <Dialog open onClose={onClose} size="lg" title="Period summary" description={`${formatShort(from)} – ${formatShort(to)}`}>
      {state.loading && <LoadingState label="Summarising…" />}
      {state.error && <Alert tone="danger">{state.error}</Alert>}
      {!state.loading && !state.error && (
        state.summary ? (
          <>
            <pre className="whitespace-pre-wrap font-sans text-[13.5px] leading-relaxed text-text">{state.summary}</pre>
            <p className="mt-3 text-xs text-muted">Based on {state.count} entries plus your notes for the period.</p>
          </>
        ) : <p className="text-[13px] text-muted">No work recorded in this period.</p>
      )}
    </Dialog>
  );
}

function HistoryView() {
  const params = useSearchParams();
  const router = useRouter();
  const tab = params.get("tab") === "eod" ? "eod" : "work";
  const [filters, setFilters] = useState<WorkFilters>({ ...EMPTY_WORK_FILTERS, q: params.get("q") ?? "" });
  const [eodStatus, setEodStatus] = useState("");
  const [eodQuery, setEodQuery] = useState("");
  const [summaryOpen, setSummaryOpen] = useState(false);
  const { data: projects } = useApi<Project[]>("/projects?include_archived=true");

  function selectTab(next: "work" | "eod") {
    router.replace(next === "eod" ? "/history?tab=eod" : "/history", { scroll: false });
  }

  const hasRange = Boolean(filters.from && filters.to && filters.from <= filters.to);

  return (
    <>
      <PageHeader
        title="History"
        description="Your documented work and every EOD report, searchable."
        actions={tab === "work" && (
          <Button onClick={() => setSummaryOpen(true)} disabled={!hasRange} icon={<Sparkles aria-hidden className="h-4 w-4" />}
            title={hasRange ? "Summarise the selected period" : "Choose a from and to date first"}>
            Summarise period
          </Button>
        )}
      />
      <div role="tablist" aria-label="History type" className="mb-4 flex gap-1 border-b border-line">
        {(["work", "eod"] as const).map((t) => (
          <button
            key={t}
            role="tab"
            type="button"
            aria-selected={tab === t}
            aria-controls={`panel-${t}`}
            id={`tab-${t}`}
            onClick={() => selectTab(t)}
            className={cn(
              "-mb-px border-b-2 px-3 py-2 text-[13.5px] font-medium",
              tab === t ? "border-primary text-primary" : "border-transparent text-muted hover:text-text",
            )}
          >
            {t === "work" ? "Work history" : "EOD history"}
          </button>
        ))}
      </div>

      {tab === "work" ? (
        <div role="tabpanel" id="panel-work" aria-labelledby="tab-work">
          <Card>
            <WorkHistoryFilters filters={filters} onChange={setFilters} projects={projects ?? []} />
            <WorkHistoryTable filters={filters} />
          </Card>
          <RelatedResults q={filters.q} />
          {hasRange && summaryOpen && <SummaryDialog onClose={() => setSummaryOpen(false)} from={filters.from} to={filters.to} />}
        </div>
      ) : (
        <div role="tabpanel" id="panel-eod" aria-labelledby="tab-eod">
          <Card>
            <div className="grid gap-2 border-b border-line p-3 sm:grid-cols-[1fr_12rem]">
              <Input type="search" aria-label="Search EOD reports" placeholder="Search subject, project or content…" value={eodQuery} onChange={(e) => setEodQuery(e.target.value)} />
              <Select aria-label="Status" value={eodStatus} onChange={(e) => setEodStatus(e.target.value)}>
                <option value="">All statuses</option>
                <option value="SENT">Sent</option>
                <option value="GENERATED">Generated</option>
                <option value="FAILED">Failed</option>
              </Select>
            </div>
            <EodHistoryTable status={eodStatus} q={eodQuery} />
          </Card>
        </div>
      )}
    </>
  );
}

export default function HistoryPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <HistoryView />
    </Suspense>
  );
}
