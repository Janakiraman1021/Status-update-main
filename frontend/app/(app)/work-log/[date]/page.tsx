"use client";

import { ChevronLeft, ChevronRight, FileText, Wand2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import CategorizeDialog from "@/components/CategorizeDialog";
import EmptyState from "@/components/EmptyState";
import EodStatus from "@/components/EodStatus";
import ErrorState from "@/components/ErrorState";
import LoadingState from "@/components/LoadingState";
import ProjectSelector from "@/components/ProjectSelector";
import { BlockersPanel, DependenciesPanel } from "@/components/TrackingPanels";
import WorkEntry, { EntryComposer } from "@/components/WorkEntry";
import WorkLogForm, { type WorkLogFormHandle } from "@/components/WorkLogForm";
import { Button, Card, CardHeader, Input } from "@/components/ui";
import { ApiError, api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { addDays, formatLong, isIsoDate, todayIn, weekdayName } from "@/lib/date";
import { useApi } from "@/lib/hooks";
import { useToast } from "@/lib/toast";
import type { Project } from "@/types/project";
import type { DayView, WorkEntry as Entry, WorkLog } from "@/types/work";

function SummaryItem({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="text-[15px] font-semibold tabular-nums text-text">{value}</dd>
    </div>
  );
}

export default function WorkLogDayPage() {
  const params = useParams<{ date: string }>();
  const date = params.date;
  const router = useRouter();
  const toast = useToast();
  const { user, timezone } = useAuth();
  const valid = isIsoDate(date);
  const { data: day, error, loading, reload, setData } = useApi<DayView>(valid ? `/work-logs/${date}` : null);
  const { data: projects } = useApi<Project[]>("/projects?include_archived=true");
  const formRef = useRef<WorkLogFormHandle>(null);
  const [generating, setGenerating] = useState(false);
  const [convertOpen, setConvertOpen] = useState(false);
  const [convertNotes, setConvertNotes] = useState("");
  const [savingProject, setSavingProject] = useState(false);
  const today = todayIn(timezone);

  const refreshDay = useCallback(async () => {
    try {
      const fresh = await api.get<DayView>(`/work-logs/${date}`);
      setData(fresh);
    } catch {
      /* keep current view; individual actions report their own errors */
    }
  }, [date, setData]);

  useEffect(() => {
    if (day) document.title = `${formatLong(day.work_date)} · WorkLog`;
  }, [day]);

  const onLogSaved = useCallback(
    (log: WorkLog) => {
      setData((d) => (d ? { ...d, log, has_work: d.has_work || Boolean(log.quick_notes) } : d));
    },
    [setData],
  );

  async function goTo(target: string) {
    if (formRef.current?.isDirty()) {
      try {
        await formRef.current.flush();
      } catch {
        return;
      }
    }
    router.push(`/work-log/${target}`);
  }

  async function changeProject(projectId: string | null) {
    setSavingProject(true);
    try {
      await api.post("/work-logs", { work_date: date, project_id: projectId });
      await refreshDay();
      toast("Project updated");
    } catch (err) {
      toast(errorMessage(err, "Unable to update the project."), "error");
    } finally {
      setSavingProject(false);
    }
  }

  async function generateEod() {
    setGenerating(true);
    try {
      await formRef.current?.flush();
      await api.post("/eod/generate", { work_date: date });
      router.push(`/eod/${date}`);
    } catch (err) {
      if (err instanceof ApiError && err.code === "EOD_BUSY") router.push(`/eod/${date}`);
      else toast(errorMessage(err, "Unable to generate the EOD."), "error");
      setGenerating(false);
    }
  }

  if (!valid) {
    return <ErrorState title="Invalid date" message="Dates must look like 2026-10-03." onRetry={() => router.push(`/work-log/${today}`)} />;
  }
  if (loading && !day) return <LoadingState label="Loading work log…" />;
  if (error || !day || !user) return <ErrorState message={error?.message} onRetry={reload} />;

  const entries = day.entries;
  const hasEod = day.eod.current_version > 0;
  const isFuture = date > today;

  return (
    <div className="space-y-5">
      {/* Day header & summary */}
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
          <div className="flex items-center gap-2">
            <Button size="sm" variant="ghost" onClick={() => goTo(addDays(date, -1))} aria-label="Previous day" icon={<ChevronLeft className="h-4 w-4" />} />
            <div>
              <h1 className="text-lg font-semibold tracking-tight">{formatLong(date)}</h1>
              <p className="text-xs text-muted">
                {weekdayName(date)}
                {date === today && " · Today"}
                {isFuture && " · Future date"}
              </p>
            </div>
            <Button size="sm" variant="ghost" onClick={() => goTo(addDays(date, 1))} aria-label="Next day" icon={<ChevronRight className="h-4 w-4" />} />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label htmlFor="jump-date" className="sr-only">Go to date</label>
            <Input id="jump-date" type="date" value={date} className="h-8 w-[9.5rem]" onChange={(e) => isIsoDate(e.target.value) && goTo(e.target.value)} />
            {date !== today && <Button size="sm" onClick={() => goTo(today)}>Today</Button>}
          </div>
        </div>
        <div className="grid gap-4 px-4 py-3 md:grid-cols-[minmax(0,18rem)_minmax(0,1fr)] md:items-center 2xl:grid-cols-[minmax(0,18rem)_minmax(0,1fr)_auto]">
          <div className="min-w-0">
            <label htmlFor="day-project" className="mb-1 block text-xs text-muted">Project</label>
            <ProjectSelector id="day-project" projects={projects ?? []} value={day.project_id} onChange={changeProject} disabled={savingProject} />
          </div>
          <dl className="grid min-w-0 grid-cols-2 gap-3 min-[480px]:grid-cols-3 2xl:grid-cols-5">
            <SummaryItem label="Completed" value={day.summary.completed} />
            <SummaryItem label="In progress" value={day.summary.in_progress} />
            <SummaryItem label="Blockers" value={day.summary.blockers} />
            <SummaryItem label="Entries" value={day.summary.total_entries} />
            <div>
              <dt className="text-xs text-muted">EOD</dt>
              <dd className="mt-0.5"><EodStatus status={day.eod.status} /></dd>
            </div>
          </dl>
          <div className="flex min-w-0 gap-2 md:col-span-2 md:justify-end 2xl:col-span-1">
            {hasEod ? (
              <Link href={`/eod/${date}`} className="inline-flex h-9 items-center gap-1.5 rounded-md border border-line-strong bg-surface px-3.5 text-sm font-medium text-text shadow-sm hover:bg-surface-hover">
                <FileText aria-hidden className="h-4 w-4" /> Open EOD
              </Link>
            ) : (
              <Button variant="primary" onClick={generateEod} loading={generating} icon={<Wand2 aria-hidden className="h-4 w-4" />}>
                {generating ? "Generating…" : "Generate EOD"}
              </Button>
            )}
          </div>
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-5">
          <Card>
            <CardHeader title="Quick notes" description="Capture what you did in your own words." />
            <div className="p-4">
              <WorkLogForm
                key={date}
                ref={formRef}
                date={date}
                userId={user.id}
                log={day.log}
                onSaved={onLogSaved}
                onConvert={(notes) => {
                  setConvertNotes(notes);
                  setConvertOpen(true);
                }}
              />
            </div>
          </Card>

          <Card>
            <CardHeader title="Work entries" description={`${entries.length} entr${entries.length === 1 ? "y" : "ies"}, in chronological order`} />
            <div className="space-y-3 p-4">
              <EntryComposer
                date={date}
                projects={projects ?? []}
                onAdded={() => refreshDay()}
              />
              {entries.length === 0 ? (
                <EmptyState title="No entries yet" description="Add entries as you go, or convert your quick notes into entries." />
              ) : (
                <ol className="divide-y divide-line border-t border-line pt-1" aria-label="Work entries">
                  {entries.map((entry: Entry) => (
                    <WorkEntry key={entry.id} entry={entry} projects={projects ?? []} onChanged={() => refreshDay()} onDeleted={() => refreshDay()} />
                  ))}
                </ol>
              )}
            </div>
          </Card>
        </div>

        <aside className="space-y-5" aria-label="Blockers and dependencies">
          <BlockersPanel date={date} projectId={day.project_id} blockers={day.blockers} onChange={refreshDay} />
          <DependenciesPanel date={date} projectId={day.project_id} dependencies={day.dependencies} onChange={refreshDay} />
        </aside>
      </div>

      {convertOpen && (
        <CategorizeDialog
          notes={convertNotes}
          date={date}
          onClose={() => setConvertOpen(false)}
          onCreated={async (remaining) => {
            setConvertOpen(false);
            if (remaining !== null) await formRef.current?.replaceNotes(remaining).catch(() => undefined);
            await refreshDay();
          }}
        />
      )}
    </div>
  );
}
