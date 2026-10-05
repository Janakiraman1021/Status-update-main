"use client";

import { Check, Pencil, Plus, Trash2, X } from "lucide-react";
import { useState } from "react";

import { ApiError, api, errorMessage } from "@/lib/api";
import { useToast } from "@/lib/toast";
import type { Project } from "@/types/project";
import { WORK_CATEGORIES, WORK_STATUSES, type WorkEntry as Entry, type WorkCategory, type WorkStatus } from "@/types/work";
import ProjectSelector from "./ProjectSelector";
import StatusBadge, { CategoryTag } from "./StatusBadge";
import { Button, ConfirmDialog, Input, Select } from "./ui";

interface EntryDraft {
  description: string;
  time: string;
  category: WorkCategory | "";
  status: WorkStatus | "";
  project_id: string | null;
}

function EntryFields({ draft, setDraft, projects, idPrefix, autoFocus }: {
  draft: EntryDraft; setDraft: (d: EntryDraft) => void; projects: Project[]; idPrefix: string; autoFocus?: boolean;
}) {
  return (
    <div className="grid min-w-0 gap-2 sm:grid-cols-[6.5rem_minmax(0,1fr)]">
      <div className="min-w-0">
        <label htmlFor={`${idPrefix}-time`} className="sr-only">Time</label>
        <Input id={`${idPrefix}-time`} type="time" value={draft.time} onChange={(e) => setDraft({ ...draft, time: e.target.value })} aria-describedby={`${idPrefix}-time-hint`} />
        <span id={`${idPrefix}-time-hint`} className="sr-only">Optional. Defaults to the current time.</span>
      </div>
      <div className="min-w-0">
        <label htmlFor={`${idPrefix}-desc`} className="sr-only">What did you do?</label>
        <Input
          id={`${idPrefix}-desc`}
          value={draft.description}
          autoFocus={autoFocus}
          maxLength={2000}
          placeholder="What did you do? e.g. Removed statement selector"
          onChange={(e) => setDraft({ ...draft, description: e.target.value })}
        />
      </div>
      <div className="grid min-w-0 grid-cols-1 gap-2 sm:col-span-2 sm:grid-cols-2 2xl:grid-cols-3">
        <div className="min-w-0">
          <label htmlFor={`${idPrefix}-cat`} className="mb-1 block text-xs text-muted">Category</label>
          <Select id={`${idPrefix}-cat`} value={draft.category} onChange={(e) => setDraft({ ...draft, category: e.target.value as WorkCategory | "" })}>
            <option value="">Choose category</option>
            {WORK_CATEGORIES.map((c) => <option key={c}>{c}</option>)}
          </Select>
        </div>
        <div className="min-w-0">
          <label htmlFor={`${idPrefix}-status`} className="mb-1 block text-xs text-muted">Status</label>
          <Select id={`${idPrefix}-status`} value={draft.status} onChange={(e) => setDraft({ ...draft, status: e.target.value as WorkStatus | "" })}>
            <option value="">Choose status</option>
            {WORK_STATUSES.map((s) => <option key={s}>{s}</option>)}
          </Select>
        </div>
        <div className="min-w-0">
          <label htmlFor={`${idPrefix}-project`} className="mb-1 block text-xs text-muted">Project</label>
          <ProjectSelector id={`${idPrefix}-project`} projects={projects} value={draft.project_id} onChange={(project_id) => setDraft({ ...draft, project_id })} placeholder="Day default" />
        </div>
      </div>
    </div>
  );
}

export function EntryComposer({ date, projects, onAdded }: { date: string; projects: Project[]; onAdded: (entry: Entry) => void }) {
  const toast = useToast();
  const empty: EntryDraft = { description: "", time: "", category: "", status: "", project_id: null };
  const [draft, setDraft] = useState<EntryDraft>(empty);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!draft.description.trim()) {
      setError("Describe the work before adding it.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const entry = await api.post<Entry>("/work-items", {
        work_date: date,
        description: draft.description.trim(),
        time: draft.time || undefined,
        category: draft.category || undefined,
        status: draft.status || undefined,
        project_id: draft.project_id || undefined,
      });
      onAdded(entry);
      setDraft({ ...empty, category: "", status: "", project_id: draft.project_id });
      toast("Entry added");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to save your entry.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-2" aria-label="Add work entry">
      <EntryFields draft={draft} setDraft={setDraft} projects={projects} idPrefix="new-entry" />
      {error && <p role="alert" className="text-[12.5px] text-danger">{error}</p>}
      <div className="flex justify-end">
        <Button type="submit" variant="primary" size="sm" loading={saving} icon={<Plus aria-hidden className="h-4 w-4" />}>Add entry</Button>
      </div>
    </form>
  );
}

export default function WorkEntry({ entry, projects, onChanged, onDeleted }: {
  entry: Entry; projects: Project[]; onChanged: (entry: Entry) => void; onDeleted: (id: string) => void;
}) {
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<EntryDraft>({
    description: entry.description, time: entry.time, category: entry.category ?? "", status: entry.status ?? "", project_id: entry.project_id,
  });

  async function save() {
    if (!draft.description.trim()) {
      toast("Description cannot be empty.", "error");
      return;
    }
    setBusy(true);
    try {
      const updated = await api.put<Entry>(`/work-items/${entry.id}`, {
        description: draft.description.trim(), time: draft.time || undefined,
        category: draft.category || null, status: draft.status || null, project_id: draft.project_id,
      });
      onChanged(updated);
      setEditing(false);
      toast("Entry updated");
    } catch (err) {
      toast(errorMessage(err, "Unable to update the entry."), "error");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await api.del(`/work-items/${entry.id}`);
      onDeleted(entry.id);
      toast("Entry deleted");
    } catch (err) {
      toast(errorMessage(err, "Unable to delete the entry."), "error");
      setBusy(false);
    }
  }

  if (editing) {
    return (
      <li className="rounded-md border border-primary/40 bg-primary-soft/40 p-2.5">
        <EntryFields draft={draft} setDraft={setDraft} projects={projects} idPrefix={`entry-${entry.id}`} autoFocus />
        <div className="mt-2 flex justify-end gap-2">
          <Button size="sm" variant="ghost" onClick={() => setEditing(false)} icon={<X aria-hidden className="h-3.5 w-3.5" />}>Cancel</Button>
          <Button size="sm" variant="primary" onClick={save} loading={busy} icon={<Check aria-hidden className="h-3.5 w-3.5" />}>Save</Button>
        </div>
      </li>
    );
  }

  return (
    <li className="group flex items-start gap-3 rounded-md px-2 py-2 hover:bg-surface-hover">
      <time dateTime={entry.timestamp} className="w-16 shrink-0 pt-0.5 text-xs font-medium tabular-nums text-subtle">{entry.time_label}</time>
      <div className="min-w-0 flex-1">
        <p className="text-[13.5px] text-text">{entry.description}</p>
        <div className="mt-1 flex flex-wrap items-center gap-1.5">
          <StatusBadge status={entry.status} />
          <CategoryTag category={entry.category} />
          {entry.project_name && <span className="text-xs text-muted">{entry.project_name}</span>}
        </div>
      </div>
      <div className="flex shrink-0 gap-0.5 opacity-100 sm:opacity-0 sm:group-focus-within:opacity-100 sm:group-hover:opacity-100">
        <button type="button" onClick={() => setEditing(true)} className="rounded p-1.5 text-subtle hover:bg-surface hover:text-text" aria-label={`Edit entry: ${entry.description}`}>
          <Pencil className="h-3.5 w-3.5" />
        </button>
        <button type="button" onClick={() => setConfirmDelete(true)} className="rounded p-1.5 text-subtle hover:bg-surface hover:text-danger" aria-label={`Delete entry: ${entry.description}`}>
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
      <ConfirmDialog
        open={confirmDelete}
        title="Delete this entry?"
        description={<span>&ldquo;{entry.description}&rdquo; will be removed from this day.</span>}
        confirmLabel="Delete"
        tone="danger"
        loading={busy}
        onCancel={() => setConfirmDelete(false)}
        onConfirm={remove}
      />
    </li>
  );
}
