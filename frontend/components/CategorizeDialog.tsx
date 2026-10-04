"use client";

import { useEffect, useState } from "react";

import { api, errorMessage } from "@/lib/api";
import { useToast } from "@/lib/toast";
import { WORK_CATEGORIES, WORK_STATUSES, type CategorizedSuggestion, type WorkCategory, type WorkStatus } from "@/types/work";
import LoadingState from "./LoadingState";
import { Alert, Button, Dialog, Input, Select } from "./ui";

interface Row extends CategorizedSuggestion {
  selected: boolean;
}

/**
 * Turns free-form notes into structured entries. Suggestions are reviewed before anything is saved.
 * Mount it only while open (the parent renders it conditionally), so each opening starts fresh.
 */
export default function CategorizeDialog({ notes, date, onClose, onCreated }: {
  notes: string; date: string; onClose: () => void; onCreated: (remainingNotes: string | null) => void;
}) {
  const toast = useToast();
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [removeFromNotes, setRemoveFromNotes] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api.post<{ items: CategorizedSuggestion[] }>("/work-items/categorize", { text: notes })
      .then((res) => !cancelled && setRows(res.items.map((i) => ({ ...i, selected: true }))))
      .catch((err) => !cancelled && setError(errorMessage(err, "Unable to analyse your notes.")))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [notes]);

  const selected = rows.filter((r) => r.selected && r.description.trim());

  async function create() {
    setSaving(true);
    try {
      await api.post("/work-items/bulk", {
        work_date: date,
        items: selected.map((r) => ({ description: r.description.trim(), category: r.category || undefined, status: r.status || undefined })),
      });
      toast(`${selected.length} entr${selected.length === 1 ? "y" : "ies"} added`);
      if (removeFromNotes) {
        // Keep only the note lines that were not converted, so the EOD does not repeat them.
        const converted = new Set(selected.map((r) => r.description.trim().toLowerCase().replace(/[.\s]+$/, "")));
        const remaining = notes
          .split("\n")
          .filter((line) => !converted.has(line.replace(/^\s*(?:[-*•]+|\d+[.)])\s*/, "").trim().toLowerCase().replace(/[.\s]+$/, "")))
          .join("\n")
          .trim();
        onCreated(remaining);
      } else {
        onCreated(null);
      }
    } catch (err) {
      setError(errorMessage(err, "Unable to create entries."));
    } finally {
      setSaving(false);
    }
  }

  function update(index: number, patch: Partial<Row>) {
    setRows((list) => list.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  }

  function applyToSelected(patch: Partial<Row>) {
    const count = selected.length;
    setRows((list) => list.map((r) => (r.selected ? { ...r, ...patch } : r)));
    const [field, value] = Object.entries(patch)[0];
    toast(`${field === "status" ? "Status" : "Category"} set to ${value ?? "none"} for ${count} entr${count === 1 ? "y" : "ies"}`, "info");
  }

  return (
    <Dialog
      open
      onClose={onClose}
      size="lg"
      title="Convert notes to entries"
      description="Review the suggested entries. Nothing is saved until you confirm."
      footer={
        <>
          <label className="mr-auto flex items-center gap-2 text-[13px] text-muted">
            <input type="checkbox" checked={removeFromNotes} onChange={(e) => setRemoveFromNotes(e.target.checked)} className="h-4 w-4 accent-[var(--primary)]" />
            Remove converted lines from notes
          </label>
          <Button onClick={onClose} disabled={saving}>Cancel</Button>
          <Button variant="primary" onClick={create} loading={saving} disabled={!selected.length || loading}>
            Add {selected.length} entr{selected.length === 1 ? "y" : "ies"}
          </Button>
        </>
      }
    >
      {loading && <LoadingState label="Analysing notes…" />}
      {error && <Alert tone="danger">{error}</Alert>}
      {!loading && !error && rows.length === 0 && <p className="text-[13px] text-muted">No entries found in your notes.</p>}
      {!loading && rows.length > 0 && (
        <div className="sticky top-0 z-10 -mx-5 -mt-4 mb-3 flex flex-wrap items-center gap-2 border-b border-line bg-surface px-5 py-2.5"
          role="toolbar" aria-label="Bulk actions">
          <label className="mr-auto flex items-center gap-2 text-[13px] font-medium text-text">
            <input
              type="checkbox"
              ref={(el) => {
                if (el) el.indeterminate = selected.length > 0 && selected.length < rows.length;
              }}
              checked={rows.length > 0 && rows.every((r) => r.selected)}
              onChange={(e) => setRows((list) => list.map((r) => ({ ...r, selected: e.target.checked })))}
              aria-label="Select all"
              className="h-4 w-4 accent-[var(--primary)]"
            />
            Select all
            <span className="font-normal text-muted">({selected.length} of {rows.length} selected)</span>
          </label>
          <Select value="" disabled={!selected.length} aria-label="Set category for selected entries" className="w-auto min-w-44"
            onChange={(e) => applyToSelected({ category: (e.target.value === "__none" ? null : e.target.value) as WorkCategory | null })}>
            <option value="" disabled>Set category for selected…</option>
            {WORK_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            <option value="__none">No category</option>
          </Select>
          <Select value="" disabled={!selected.length} aria-label="Set status for selected entries" className="w-auto min-w-44"
            onChange={(e) => applyToSelected({ status: (e.target.value === "__none" ? null : e.target.value) as WorkStatus | null })}>
            <option value="" disabled>Set status for selected…</option>
            {WORK_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            <option value="__none">No status</option>
          </Select>
        </div>
      )}
      {!loading && rows.length > 0 && (
        <ul className="space-y-2">
          {rows.map((row, i) => (
            <li key={i} className="grid items-center gap-2 rounded-md border border-line p-2 sm:grid-cols-[auto_1fr_9rem_8.5rem]">
              <input type="checkbox" checked={row.selected} onChange={(e) => update(i, { selected: e.target.checked })}
                aria-label={`Include "${row.description}"`} className="h-4 w-4 accent-[var(--primary)]" />
              <Input value={row.description} onChange={(e) => update(i, { description: e.target.value })} aria-label="Description" />
              <Select value={row.category ?? ""} onChange={(e) => update(i, { category: (e.target.value || null) as WorkCategory | null })} aria-label="Category">
                <option value="">No category</option>
                {WORK_CATEGORIES.map((c) => <option key={c}>{c}</option>)}
              </Select>
              <Select value={row.status ?? ""} onChange={(e) => update(i, { status: (e.target.value || null) as WorkStatus | null })} aria-label="Status">
                <option value="">No status</option>
                {WORK_STATUSES.map((s) => <option key={s}>{s}</option>)}
              </Select>
            </li>
          ))}
        </ul>
      )}
    </Dialog>
  );
}
