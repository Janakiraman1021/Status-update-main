"use client";

import { Archive, ArchiveRestore, Pencil, Plus } from "lucide-react";
import { useState } from "react";

import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import LoadingState from "@/components/LoadingState";
import StatusBadge from "@/components/StatusBadge";
import { Button, Card, ConfirmDialog, Dialog, Field, Input, PageHeader, Textarea } from "@/components/ui";
import { ApiError, api, errorMessage } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { useToast } from "@/lib/toast";
import type { Project } from "@/types/project";

function ProjectForm({ initial, onSubmit, onCancel }: {
  initial?: Project; onSubmit: (name: string, description: string) => Promise<void>; onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) {
      setError("Project name is required.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onSubmit(name.trim(), description.trim());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to save the project.");
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <Field label="Name" htmlFor="project-name" error={error ?? undefined}>
        <Input id="project-name" autoFocus maxLength={120} value={name} onChange={(e) => setName(e.target.value)} aria-invalid={Boolean(error)} />
      </Field>
      <Field label="Description" htmlFor="project-desc" optional>
        <Textarea id="project-desc" rows={3} maxLength={2000} value={description} onChange={(e) => setDescription(e.target.value)} />
      </Field>
      <div className="flex justify-end gap-2">
        <Button onClick={onCancel} disabled={saving}>Cancel</Button>
        <Button type="submit" variant="primary" loading={saving}>{initial ? "Save changes" : "Create project"}</Button>
      </div>
    </form>
  );
}

export default function ProjectsPage() {
  const toast = useToast();
  const [showArchived, setShowArchived] = useState(false);
  const { data: projects, error, loading, reload } = useApi<Project[]>("/projects?include_archived=true");
  const [editing, setEditing] = useState<Project | "new" | null>(null);
  const [archiving, setArchiving] = useState<Project | null>(null);
  const [busy, setBusy] = useState(false);

  async function save(name: string, description: string) {
    if (editing === "new") {
      await api.post("/projects", { name, description: description || null });
      toast("Project created");
    } else if (editing) {
      await api.put(`/projects/${editing.id}`, { name, description: description || null });
      toast("Project updated");
    }
    setEditing(null);
    await reload();
  }

  async function archive() {
    if (!archiving) return;
    setBusy(true);
    try {
      await api.post(`/projects/${archiving.id}/archive`);
      toast("Project archived. Its history is kept.");
      setArchiving(null);
      await reload();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusy(false);
    }
  }

  async function restore(project: Project) {
    try {
      await api.put(`/projects/${project.id}`, { status: "Active" });
      toast("Project restored");
      await reload();
    } catch (err) {
      toast(errorMessage(err), "error");
    }
  }

  const visible = (projects ?? []).filter((p) => showArchived || p.status === "Active");
  const archivedCount = (projects ?? []).filter((p) => p.status === "Archived").length;

  return (
    <>
      <PageHeader
        title="Projects"
        description="Group your work. Archived projects keep their full history."
        actions={<Button variant="primary" onClick={() => setEditing("new")} icon={<Plus aria-hidden className="h-4 w-4" />}>New project</Button>}
      />
      {loading && !projects ? (
        <LoadingState label="Loading projects…" />
      ) : error ? (
        <ErrorState message={error.message} onRetry={reload} />
      ) : (
        <Card>
          <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
            <span className="text-[13px] text-muted">{visible.length} project{visible.length === 1 ? "" : "s"}</span>
            {archivedCount > 0 && (
              <label className="flex items-center gap-2 text-[13px] text-muted">
                <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} className="h-4 w-4 accent-[var(--primary)]" />
                Show archived ({archivedCount})
              </label>
            )}
          </div>
          {visible.length === 0 ? (
            <EmptyState title="No projects yet" description="Create a project to group related work and label your EOD reports."
              action={<Button variant="primary" onClick={() => setEditing("new")}>Create your first project</Button>} />
          ) : (
            <ul className="divide-y divide-line">
              {visible.map((p) => (
                <li key={p.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-text">{p.name}</p>
                      <StatusBadge status={p.status} />
                    </div>
                    {p.description && <p className="mt-0.5 text-[13px] text-muted">{p.description}</p>}
                    <p className="mt-0.5 text-xs text-subtle">{p.entry_count ?? 0} work entr{p.entry_count === 1 ? "y" : "ies"}</p>
                  </div>
                  <div className="flex gap-1.5">
                    <Button size="sm" variant="ghost" onClick={() => setEditing(p)} icon={<Pencil aria-hidden className="h-3.5 w-3.5" />} aria-label={`Edit ${p.name}`}>Edit</Button>
                    {p.status === "Active" ? (
                      <Button size="sm" variant="ghost" onClick={() => setArchiving(p)} icon={<Archive aria-hidden className="h-3.5 w-3.5" />} aria-label={`Archive ${p.name}`}>Archive</Button>
                    ) : (
                      <Button size="sm" variant="ghost" onClick={() => restore(p)} icon={<ArchiveRestore aria-hidden className="h-3.5 w-3.5" />} aria-label={`Restore ${p.name}`}>Restore</Button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      <Dialog open={editing !== null} onClose={() => setEditing(null)} title={editing === "new" ? "New project" : "Edit project"}>
        {editing !== null && <ProjectForm initial={editing === "new" ? undefined : editing} onSubmit={save} onCancel={() => setEditing(null)} />}
      </Dialog>
      <ConfirmDialog
        open={Boolean(archiving)}
        title={`Archive ${archiving?.name ?? "project"}?`}
        description="The project is hidden from selectors. All historical entries and reports keep it. You can restore it later."
        confirmLabel="Archive"
        loading={busy}
        onCancel={() => setArchiving(null)}
        onConfirm={archive}
      />
    </>
  );
}
