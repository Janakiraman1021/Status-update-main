"use client";

import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import Link from "next/link";

import type { PageMeta } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDateTime, formatShort } from "@/lib/date";
import { useDebouncedValue, usePageState, usePagedApi } from "@/lib/hooks";
import type { EodHistoryRow } from "@/types/eod";
import type { Project } from "@/types/project";
import { WORK_CATEGORIES, WORK_STATUSES, type WorkEntry } from "@/types/work";
import EmptyState from "./EmptyState";
import EodStatus from "./EodStatus";
import ErrorState from "./ErrorState";
import LoadingState from "./LoadingState";
import StatusBadge, { CategoryTag } from "./StatusBadge";
import { Button, Input, Select } from "./ui";

export function Pagination({ meta, onPage }: { meta: PageMeta; onPage: (page: number) => void }) {
  if (meta.total === 0) return null;
  const from = (meta.page - 1) * meta.limit + 1;
  const to = Math.min(meta.page * meta.limit, meta.total);
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between gap-2 border-t border-line px-4 py-2.5 text-[13px] text-muted">
      <span>{from}–{to} of {meta.total}</span>
      <div className="flex items-center gap-1.5">
        <Button size="sm" variant="secondary" disabled={meta.page <= 1} onClick={() => onPage(meta.page - 1)} icon={<ChevronLeft className="h-4 w-4" />} aria-label="Previous page" />
        <span aria-current="page">Page {meta.page} of {meta.pages}</span>
        <Button size="sm" variant="secondary" disabled={meta.page >= meta.pages} onClick={() => onPage(meta.page + 1)} icon={<ChevronRight className="h-4 w-4" />} aria-label="Next page" />
      </div>
    </nav>
  );
}

export interface WorkFilters {
  q: string;
  from: string;
  to: string;
  project_id: string;
  category: string;
  status: string;
}

export const EMPTY_WORK_FILTERS: WorkFilters = { q: "", from: "", to: "", project_id: "", category: "", status: "" };

export function WorkHistoryFilters({ filters, onChange, projects }: { filters: WorkFilters; onChange: (f: WorkFilters) => void; projects: Project[] }) {
  return (
    <div className="grid gap-2 border-b border-line p-3 sm:grid-cols-2 lg:grid-cols-6">
      <div className="relative sm:col-span-2">
        <label htmlFor="history-search" className="sr-only">Search work history</label>
        <Search aria-hidden className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-subtle" />
        <Input id="history-search" type="search" value={filters.q} onChange={(e) => onChange({ ...filters, q: e.target.value })} placeholder="Search work, projects, blockers…" className="pl-8" />
      </div>
      <div>
        <label htmlFor="history-from" className="sr-only">From date</label>
        <Input id="history-from" type="date" value={filters.from} onChange={(e) => onChange({ ...filters, from: e.target.value })} aria-label="From date" />
      </div>
      <div>
        <label htmlFor="history-to" className="sr-only">To date</label>
        <Input id="history-to" type="date" value={filters.to} onChange={(e) => onChange({ ...filters, to: e.target.value })} aria-label="To date" />
      </div>
      <Select aria-label="Project" value={filters.project_id} onChange={(e) => onChange({ ...filters, project_id: e.target.value })}>
        <option value="">All projects</option>
        {projects.map((p) => <option key={p.id} value={p.id}>{p.name}{p.status === "Archived" ? " (archived)" : ""}</option>)}
      </Select>
      <div className="grid grid-cols-2 gap-2">
        <Select aria-label="Category" value={filters.category} onChange={(e) => onChange({ ...filters, category: e.target.value })}>
          <option value="">Any category</option>
          {WORK_CATEGORIES.map((c) => <option key={c}>{c}</option>)}
        </Select>
        <Select aria-label="Status" value={filters.status} onChange={(e) => onChange({ ...filters, status: e.target.value })}>
          <option value="">Any status</option>
          {WORK_STATUSES.map((s) => <option key={s}>{s}</option>)}
        </Select>
      </div>
    </div>
  );
}

export function WorkHistoryTable({ filters }: { filters: WorkFilters }) {
  const q = useDebouncedValue(filters.q.trim(), 350);
  const [page, setPage] = usePageState(JSON.stringify({ ...filters, q }));
  const params = { page, limit: 20, q, from: filters.from, to: filters.to, project_id: filters.project_id, category: filters.category, status: filters.status };
  const { rows, meta, loading, error, retry } = usePagedApi<WorkEntry>("/history/work", params);

  if (error) return <div className="p-4"><ErrorState message={error} onRetry={retry} /></div>;
  if (loading && !meta) return <div className="p-4"><LoadingState rows={6} label="Loading work history…" /></div>;
  if (!rows.length) return <EmptyState title="No matching work" description="Try a different search or clear the filters." />;

  return (
    <div aria-busy={loading}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-[13px]">
          <caption className="sr-only">Work history</caption>
          <thead className="border-b border-line bg-surface-2 text-xs uppercase tracking-wide text-subtle">
            <tr>
              <th scope="col" className="px-4 py-2 font-semibold">Date</th>
              <th scope="col" className="px-4 py-2 font-semibold">Work</th>
              <th scope="col" className="px-4 py-2 font-semibold">Project</th>
              <th scope="col" className="px-4 py-2 font-semibold">Category</th>
              <th scope="col" className="px-4 py-2 font-semibold">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((row) => (
              <tr key={row.id} className="hover:bg-surface-hover">
                <td className="whitespace-nowrap px-4 py-2.5 align-top">
                  <Link href={`/work-log/${row.work_date}`} className="font-medium text-primary hover:underline">{formatShort(row.work_date)}</Link>
                  <div className="text-xs text-subtle">{row.time_label}</div>
                </td>
                <td className="px-4 py-2.5 align-top text-text">{row.description}</td>
                <td className="px-4 py-2.5 align-top text-muted">{row.project_name ?? "—"}</td>
                <td className="px-4 py-2.5 align-top"><CategoryTag category={row.category} /></td>
                <td className="px-4 py-2.5 align-top"><StatusBadge status={row.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {meta && <Pagination meta={meta} onPage={setPage} />}
    </div>
  );
}

export function EodHistoryTable({ status = "", q = "", from = "", to = "", limit = 20 }: { status?: string; q?: string; from?: string; to?: string; limit?: number }) {
  const debounced = useDebouncedValue(q.trim(), 350);
  const [page, setPage] = usePageState(JSON.stringify({ status, debounced, from, to }));
  const { timezone } = useAuth();
  const { rows, meta, loading, error, retry } = usePagedApi<EodHistoryRow>("/history/eod", { page, limit, status, q: debounced, from, to });

  if (error) return <div className="p-4"><ErrorState message={error} onRetry={retry} /></div>;
  if (loading && !meta) return <div className="p-4"><LoadingState rows={5} label="Loading EOD history…" /></div>;
  if (!rows.length) return <EmptyState title="No EOD reports" description="Generated reports will appear here." />;

  return (
    <div aria-busy={loading}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-[13px]">
          <caption className="sr-only">EOD history</caption>
          <thead className="border-b border-line bg-surface-2 text-xs uppercase tracking-wide text-subtle">
            <tr>
              <th scope="col" className="px-4 py-2 font-semibold">Date</th>
              <th scope="col" className="px-4 py-2 font-semibold">Project</th>
              <th scope="col" className="px-4 py-2 font-semibold">Status</th>
              <th scope="col" className="px-4 py-2 font-semibold">Generated</th>
              <th scope="col" className="px-4 py-2 font-semibold">Sent</th>
              <th scope="col" className="px-4 py-2 font-semibold">Version</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((row) => (
              <tr key={row.id} className="hover:bg-surface-hover">
                <td className="whitespace-nowrap px-4 py-2.5">
                  <Link href={`/eod/${row.id}`} className="font-medium text-primary hover:underline">{formatShort(row.work_date)}</Link>
                </td>
                <td className="px-4 py-2.5 text-muted">{row.project_label ?? "—"}</td>
                <td className="px-4 py-2.5"><EodStatus status={row.status} /></td>
                <td className="whitespace-nowrap px-4 py-2.5 text-muted">{row.generated_at ? formatDateTime(row.generated_at, timezone) : "—"}</td>
                <td className="whitespace-nowrap px-4 py-2.5 text-muted">{row.sent_at ? formatDateTime(row.sent_at, timezone) : "—"}</td>
                <td className="px-4 py-2.5 text-muted">
                  v{row.current_version}
                  {row.sent_version && row.sent_version !== row.current_version ? ` (sent v${row.sent_version})` : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {meta && <Pagination meta={meta} onPage={setPage} />}
    </div>
  );
}
