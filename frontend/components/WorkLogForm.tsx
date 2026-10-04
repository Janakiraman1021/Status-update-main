"use client";

import { AlertCircle, Check, ChevronDown, Loader2, Save, Sparkles } from "lucide-react";
import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react";

import { api, errorMessage } from "@/lib/api";
import { useUnsavedChangesWarning } from "@/lib/hooks";
import { useToast } from "@/lib/toast";
import { cn, safeStorage } from "@/lib/utils";
import type { WorkLog, WorkLogFields } from "@/types/work";
import { Alert, Button, Kbd, Textarea } from "./ui";

export type SaveStatus = "saved" | "saving" | "dirty" | "error";

export interface WorkLogFormHandle {
  /** Persist pending changes immediately. Resolves once the server has them. */
  flush: () => Promise<void>;
  isDirty: () => boolean;
  replaceNotes: (text: string) => Promise<void>;
}

const FIELDS: { key: keyof WorkLogFields; label: string; placeholder: string }[] = [
  { key: "next_steps", label: "Next steps", placeholder: "What's planned next? One item per line." },
  { key: "meetings", label: "Meetings", placeholder: "Meetings you attended and key outcomes." },
  { key: "metrics", label: "Testing & metrics", placeholder: "e.g. 94 tests passed; response time 210 ms" },
  { key: "learnings", label: "Learnings", placeholder: "Anything you learned today." },
];
const AUTOSAVE_MS = 2000;

function fromLog(log: WorkLog | null): WorkLogFields {
  return {
    quick_notes: log?.quick_notes ?? "",
    next_steps: log?.next_steps ?? "",
    learnings: log?.learnings ?? "",
    meetings: log?.meetings ?? "",
    metrics: log?.metrics ?? "",
  };
}

function same(a: WorkLogFields, b: WorkLogFields) {
  return (Object.keys(a) as (keyof WorkLogFields)[]).every((k) => (a[k] ?? "") === (b[k] ?? ""));
}

function hasExtraSections(f: WorkLogFields) {
  return Boolean(f.next_steps || f.meetings || f.metrics || f.learnings);
}

function initialState(log: WorkLog | null, draftKey: string): { fields: WorkLogFields; restoredAt: string | null } {
  const server = fromLog(log);
  const storage = safeStorage();
  const raw = storage.get(draftKey);
  if (raw) {
    try {
      const draft = JSON.parse(raw) as { fields: WorkLogFields; editedAt: string };
      if (!same(draft.fields, server)) return { fields: { ...server, ...draft.fields }, restoredAt: draft.editedAt };
    } catch {
      /* corrupt draft — fall through and discard it */
    }
    storage.remove(draftKey);
  }
  return { fields: server, restoredAt: null };
}

export function SaveIndicator({ status }: { status: SaveStatus }) {
  const map = {
    saved: { text: "Saved", Icon: Check, className: "text-success" },
    saving: { text: "Saving…", Icon: Loader2, className: "text-muted" },
    dirty: { text: "Unsaved changes", Icon: AlertCircle, className: "text-warning" },
    error: { text: "Not saved", Icon: AlertCircle, className: "text-danger" },
  }[status];
  return (
    <span role="status" aria-live="polite" className={cn("inline-flex items-center gap-1 text-xs font-medium", map.className)}>
      <map.Icon aria-hidden className={cn("h-3.5 w-3.5", status === "saving" && "animate-spin")} />
      {map.text}
    </span>
  );
}

interface Props {
  date: string;
  userId: string;
  log: WorkLog | null;
  onSaved: (log: WorkLog) => void;
  onConvert: (notes: string) => void;
}

const WorkLogForm = forwardRef<WorkLogFormHandle, Props>(function WorkLogForm({ date, userId, log, onSaved, onConvert }, ref) {
  const toast = useToast();
  const storage = safeStorage();
  const draftKey = `worklog:draft:${userId}:${date}`;
  // Computed once per mount (the parent keys this component by date): server state, or a newer
  // local draft that survived a refresh or crash.
  const [initial] = useState(() => initialState(log, draftKey));
  const [fields, setFieldsState] = useState<WorkLogFields>(initial.fields);
  const [status, setStatus] = useState<SaveStatus>(initial.restoredAt ? "dirty" : "saved");
  const [restoredAt, setRestoredAt] = useState<string | null>(initial.restoredAt);
  const [showMore, setShowMore] = useState(hasExtraSections(initial.fields));
  const serverRef = useRef<WorkLogFields>(fromLog(log));
  const fieldsRef = useRef(initial.fields);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inflight = useRef<Promise<void> | null>(null);

  const setFields = useCallback((next: WorkLogFields) => {
    fieldsRef.current = next;
    setFieldsState(next);
  }, []);

  const save = useCallback(async () => {
    if (timer.current) clearTimeout(timer.current);
    const snapshot = fieldsRef.current;
    if (same(snapshot, serverRef.current)) {
      setStatus("saved");
      storage.remove(draftKey);
      return;
    }
    setStatus("saving");
    const run = (async () => {
      try {
        const saved = await api.post<WorkLog>("/work-logs", { work_date: date, ...snapshot });
        serverRef.current = fromLog(saved);
        onSaved(saved);
        if (same(fieldsRef.current, snapshot)) {
          storage.remove(draftKey);
          setStatus("saved");
          setRestoredAt(null);
        } else {
          setStatus("dirty");
        }
      } catch (err) {
        setStatus("error");
        toast(errorMessage(err, "Unable to save your work log."), "error");
        throw err;
      }
    })();
    inflight.current = run;
    try {
      await run;
    } finally {
      inflight.current = null;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [date, draftKey, onSaved, toast]);

  useImperativeHandle(ref, () => ({
    flush: async () => {
      if (inflight.current) await inflight.current.catch(() => undefined);
      await save();
    },
    isDirty: () => !same(fieldsRef.current, serverRef.current),
    replaceNotes: async (text: string) => {
      setFields({ ...fieldsRef.current, quick_notes: text });
      await save();
    },
  }), [save, setFields]);

  function update(key: keyof WorkLogFields, value: string) {
    const next = { ...fieldsRef.current, [key]: value };
    setFields(next);
    setStatus(same(next, serverRef.current) ? "saved" : "dirty");
    storage.set(draftKey, JSON.stringify({ fields: next, editedAt: new Date().toISOString() }));
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      save().catch(() => undefined);
    }, AUTOSAVE_MS);
  }

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  useUnsavedChangesWarning(status === "dirty" || status === "saving" || status === "error");

  function discardDraft() {
    storage.remove(draftKey);
    setFields(serverRef.current);
    setStatus("saved");
    setRestoredAt(null);
  }

  function onKeyDown(event: React.KeyboardEvent) {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      save().catch(() => undefined);
    }
  }

  return (
    <div onKeyDown={onKeyDown} className="space-y-3">
      {restoredAt && (
        <Alert
          tone="warning"
          title="Unsaved draft restored"
          action={
            <div className="flex gap-2">
              <Button size="sm" variant="secondary" onClick={discardDraft}>Discard draft</Button>
              <Button size="sm" variant="primary" onClick={() => save().catch(() => undefined)}>Save now</Button>
            </div>
          }
        >
          We recovered changes from {new Date(restoredAt).toLocaleString()} that were not saved.
        </Alert>
      )}

      <div>
        <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
          <label htmlFor="quick-notes" className="text-sm font-medium text-text">What did you work on today?</label>
          <SaveIndicator status={status} />
        </div>
        <Textarea
          id="quick-notes"
          rows={9}
          value={fields.quick_notes ?? ""}
          onChange={(e) => update("quick_notes", e.target.value)}
          placeholder={"Write informally, one item per line. For example:\nremoved selector\nadded dark mode\nfixed date validation\n94 tests passed\nneed DBA approval"}
          aria-describedby="quick-notes-hint"
          className="min-h-48 font-[450]"
        />
        <p id="quick-notes-hint" className="mt-1 text-xs text-muted">
          Plain notes are fine — the EOD is written from them. Changes save automatically; press <Kbd>Ctrl</Kbd>+<Kbd>S</Kbd> to save now.
        </p>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => setShowMore((v) => !v)}
          aria-expanded={showMore}
          aria-controls="more-sections"
          className="inline-flex items-center gap-1 text-[13px] font-medium text-primary hover:underline"
        >
          <ChevronDown aria-hidden className={cn("h-4 w-4 transition-transform", showMore && "rotate-180")} />
          {showMore ? "Hide" : "Show"} next steps, meetings, testing & learnings
        </button>
        <div className="flex gap-2">
          <Button size="sm" variant="secondary" disabled={!fields.quick_notes?.trim()} onClick={() => onConvert(fields.quick_notes ?? "")}
            icon={<Sparkles aria-hidden className="h-3.5 w-3.5" />} title="Split notes into categorised entries">
            Convert to entries
          </Button>
          <Button size="sm" variant="primary" onClick={() => save().catch(() => undefined)} loading={status === "saving"}
            disabled={status === "saved"} icon={<Save aria-hidden className="h-3.5 w-3.5" />}>
            Save
          </Button>
        </div>
      </div>

      {showMore && (
        <div id="more-sections" className="grid gap-3 md:grid-cols-2">
          {FIELDS.map((f) => (
            <div key={f.key}>
              <label htmlFor={`field-${f.key}`} className="mb-1 block text-[13px] font-medium text-text">{f.label}</label>
              <Textarea id={`field-${f.key}`} rows={3} value={fields[f.key] ?? ""} placeholder={f.placeholder} onChange={(e) => update(f.key, e.target.value)} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
});

export default WorkLogForm;
