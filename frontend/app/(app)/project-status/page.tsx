"use client";

import { Check, Clipboard, FileText, RotateCcw } from "lucide-react";
import { useState } from "react";

import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import LoadingState from "@/components/LoadingState";
import ProjectSelector from "@/components/ProjectSelector";
import { Alert, Button, Card, CardHeader, Field, Input, PageHeader, Select, Textarea } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatLong, todayIn } from "@/lib/date";
import { useApi } from "@/lib/hooks";
import { useToast } from "@/lib/toast";
import type { Project } from "@/types/project";
import type { ProjectProgress, ProjectStatus } from "@/types/project-status";

const STATUS_OPTIONS: ProjectProgress[] = ["On track", "Needs help", "Delayed", "Done"];

function buildText(kind: "summary" | "report", project: string, date: string, status: ProjectProgress, update: string, next: string, help: string) {
  const lines = [
    `${project} — ${formatLong(date)}`,
    `Status: ${status}`,
    kind === "summary" ? update.trim() : `\nToday\n${update.trim()}`,
  ];
  if (next.trim()) lines.push(kind === "summary" ? `Next: ${next.trim()}` : `\nNext\n${next.trim()}`);
  if (help.trim()) lines.push(kind === "summary" ? `Need help with: ${help.trim()}` : `\nNeed help with\n${help.trim()}`);
  return lines.join("\n");
}

function StatusEditor({ project, date, initial, onSaved }: {
  project: Project;
  date: string;
  initial: ProjectStatus | null;
  onSaved: (status: ProjectStatus) => void;
}) {
  const toast = useToast();
  const [status, setStatus] = useState<ProjectProgress>(initial?.status ?? "On track");
  const [update, setUpdate] = useState(initial?.daily_update ?? "");
  const [next, setNext] = useState(initial?.next_step ?? "");
  const [help, setHelp] = useState(initial?.help_needed ?? "");
  const [output, setOutput] = useState("");
  const [saving, setSaving] = useState(false);
  const [copied, setCopied] = useState(false);

  async function save() {
    if (!update.trim()) {
      toast("Add what changed today before saving.", "error");
      return;
    }
    setSaving(true);
    try {
      const saved = await api.post<ProjectStatus>("/project-statuses", {
        project_id: project.id,
        work_date: date,
        status,
        daily_update: update.trim(),
        next_step: next.trim() || null,
        help_needed: help.trim() || null,
      });
      onSaved(saved);
      toast("Daily update saved");
    } catch (error) {
      toast(errorMessage(error, "Could not save this update. Please try again."), "error");
    } finally {
      setSaving(false);
    }
  }

  async function copyOutput() {
    try {
      await navigator.clipboard.writeText(output);
      setCopied(true);
      toast("Copied. You can paste it anywhere.");
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      toast("Could not copy. Select the text and copy it instead.", "error");
    }
  }

  return (
    <>
      <Card>
        <CardHeader title="Today's update" description="Write it in your own words. You can change it later." />
        <div className="space-y-4 p-5">
          <Field label="How is it going?" htmlFor="project-progress">
            <Select id="project-progress" value={status} onChange={(event) => {
              const selected = STATUS_OPTIONS.find((option) => option === event.target.value);
              if (selected) setStatus(selected);
            }}>
              {STATUS_OPTIONS.map((item) => <option key={item}>{item}</option>)}
            </Select>
          </Field>
          <Field label="What changed today?" htmlFor="project-update" hint="A few short sentences or bullet points are enough.">
            <Textarea id="project-update" rows={5} maxLength={20000} value={update} onChange={(event) => setUpdate(event.target.value)}
              placeholder="What did you finish? What are you working on?" />
          </Field>
          <Field label="What will you do next?" htmlFor="project-next" optional>
            <Textarea id="project-next" rows={2} maxLength={20000} value={next} onChange={(event) => setNext(event.target.value)}
              placeholder="The next thing you plan to work on" />
          </Field>
          <Field label="Do you need help with anything?" htmlFor="project-help" optional>
            <Textarea id="project-help" rows={2} maxLength={20000} value={help} onChange={(event) => setHelp(event.target.value)}
              placeholder="Leave blank if you are not blocked" />
          </Field>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
            <p className="text-xs text-muted">Saved updates stay with this project and date.</p>
            <Button variant="primary" onClick={save} loading={saving} icon={<Check aria-hidden className="h-4 w-4" />}>Save update</Button>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader title="Make something you can share" description="These use your words and keep the language simple." />
        <div className="space-y-4 p-5">
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => setOutput(buildText("summary", project.name, date, status, update, next, help))} disabled={!update.trim()}>
              Make summary
            </Button>
            <Button onClick={() => setOutput(buildText("report", project.name, date, status, update, next, help))}
              disabled={!update.trim()} icon={<FileText aria-hidden className="h-4 w-4" />}>
              Make report
            </Button>
          </div>
          {output && (
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-text">Ready to copy</p>
                <Button size="sm" onClick={copyOutput} icon={copied ? <Check aria-hidden className="h-4 w-4" /> : <Clipboard aria-hidden className="h-4 w-4" />}>
                  {copied ? "Copied" : "Copy"}
                </Button>
              </div>
              <Textarea aria-label="Generated summary or report" readOnly rows={Math.min(12, output.split("\n").length + 1)} value={output} />
            </div>
          )}
        </div>
      </Card>
    </>
  );
}

export default function ProjectStatusPage() {
  const { timezone } = useAuth();
  const today = todayIn(timezone);
  const [date, setDate] = useState(today);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const { data: projects, loading: projectsLoading, error: projectsError, reload: reloadProjects } = useApi<Project[]>("/projects?include_archived=true");
  const projectId = selectedProjectId || projects?.find((item) => item.status === "Active")?.id || projects?.[0]?.id || "";
  const project = projects?.find((item) => item.id === projectId) ?? null;
  const statusPath = projectId ? `/project-statuses?project_id=${encodeURIComponent(projectId)}&work_date=${date}` : null;
  const historyPath = projectId ? `/project-statuses?project_id=${encodeURIComponent(projectId)}` : null;
  const { data: status, loading: statusLoading, error: statusError, reload: reloadStatus, setData: setStatus } = useApi<ProjectStatus | null>(statusPath);
  const { data: history, loading: historyLoading, error: historyError, reload: reloadHistory } = useApi<ProjectStatus[]>(historyPath);

  async function saveStatus(saved: ProjectStatus) {
    setStatus(saved);
    await reloadHistory();
  }

  return (
    <>
      <PageHeader title="Project Status" description="Add a short update each day, then make a summary or report you can copy." />
      {projectsLoading && !projects ? <LoadingState label="Loading projects…" /> : projectsError ? (
        <ErrorState message={projectsError.message} onRetry={reloadProjects} />
      ) : !projects?.length ? (
        <EmptyState title="No projects yet" description="Create a project first, then come back here to add daily updates." />
      ) : (
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_18rem]">
          <div className="space-y-5">
            <Card>
              <div className="grid gap-4 p-5 sm:grid-cols-[minmax(0,1fr)_12rem_auto] sm:items-end">
                <Field label="Project" htmlFor="status-project">
                  <ProjectSelector id="status-project" projects={projects} value={projectId || null} onChange={(value) => setSelectedProjectId(value ?? "")} />
                </Field>
                <Field label="Update for" htmlFor="status-date">
                  <Input id="status-date" type="date" value={date} max={today} onChange={(event) => event.target.value && setDate(event.target.value)} />
                </Field>
                {date !== today && <Button onClick={() => setDate(today)} icon={<RotateCcw aria-hidden className="h-4 w-4" />}>Today</Button>}
              </div>
            </Card>
            {statusLoading ? <LoadingState label="Loading this day's update…" /> : statusError ? (
              <ErrorState message={statusError.message} onRetry={reloadStatus} />
            ) : project ? (
              <StatusEditor key={`${project.id}:${date}`} project={project} date={date} initial={status} onSaved={saveStatus} />
            ) : null}
          </div>

          <Card className="h-fit">
            <CardHeader title="Recent days" description={project?.name ?? "Choose a project"} />
            {historyLoading ? <div className="p-4"><LoadingState label="Loading updates…" /></div> : historyError ? (
              <div className="p-4"><Alert tone="danger" title="Could not load recent updates">{historyError.message}</Alert></div>
            ) : history?.length ? (
              <ul className="divide-y divide-line">
                {history.map((item) => (
                  <li key={item.id}>
                    <button type="button" onClick={() => setDate(item.work_date)}
                      aria-current={item.work_date === date ? "date" : undefined}
                      className={`w-full px-4 py-3 text-left hover:bg-surface-hover ${item.work_date === date ? "bg-primary-soft" : ""}`}>
                      <span className="block text-[13px] font-semibold text-text">{formatLong(item.work_date)}</span>
                      <span className="mt-0.5 block truncate text-xs text-muted">{item.status} · {item.daily_update}</span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="px-4 py-5 text-[13px] text-muted">Your saved daily updates will show up here.</p>
            )}
          </Card>
        </div>
      )}
    </>
  );
}
