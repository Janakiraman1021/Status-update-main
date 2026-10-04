"use client";

import { Plus } from "lucide-react";
import { useState } from "react";

import { ApiError, api, errorMessage } from "@/lib/api";
import { useToast } from "@/lib/toast";
import { DEPENDENCY_TYPES, type Blocker, type Dependency, type DependencyType } from "@/types/work";
import BlockerCard, { DependencyCard } from "./BlockerCard";
import { Button, Card, CardHeader, Field, Input, Select, Textarea } from "./ui";

export function BlockersPanel({ date, projectId, blockers, onChange }: {
  date: string; projectId: string | null; blockers: Blocker[]; onChange: () => void;
}) {
  const toast = useToast();
  const [adding, setAdding] = useState(false);
  const [description, setDescription] = useState("");
  const [dependency, setDependency] = useState("");
  const [expected, setExpected] = useState("");
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function add(event: React.FormEvent) {
    event.preventDefault();
    if (!description.trim()) {
      setError("Describe the blocker.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await api.post("/blockers", {
        description: description.trim(), identified_date: date, project_id: projectId || undefined,
        dependency: dependency.trim() || undefined, expected_resolution: expected || undefined,
      });
      setDescription("");
      setDependency("");
      setExpected("");
      setAdding(false);
      toast("Blocker recorded");
      onChange();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to save the blocker.");
    } finally {
      setSaving(false);
    }
  }

  async function setStatus(blocker: Blocker, status: Blocker["status"]) {
    setBusyId(blocker.id);
    try {
      await api.put(`/blockers/${blocker.id}`, { status, ...(status === "Resolved" ? { resolved_date: date } : {}) });
      onChange();
    } catch (err) {
      toast(errorMessage(err, "Unable to update the blocker."), "error");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card>
      <CardHeader
        title="Blockers"
        description="Open blockers carry over until resolved."
        actions={!adding && <Button size="sm" variant="ghost" onClick={() => setAdding(true)} icon={<Plus aria-hidden className="h-4 w-4" />}>Add</Button>}
      />
      <div className="space-y-2 p-3">
        {adding && (
          <form onSubmit={add} className="space-y-2 rounded-md border border-line bg-surface-2 p-3" aria-label="Add blocker">
            <Field label="Blocker" htmlFor="blocker-desc" error={error ?? undefined}>
              <Textarea id="blocker-desc" rows={2} autoFocus value={description} onChange={(e) => setDescription(e.target.value)}
                placeholder="e.g. Need confirmation on which date column should drive the filter." />
            </Field>
            <div className="grid gap-2 sm:grid-cols-2">
              <Field label="Depends on" htmlFor="blocker-dep" optional>
                <Input id="blocker-dep" value={dependency} onChange={(e) => setDependency(e.target.value)} placeholder="Person or team" />
              </Field>
              <Field label="Expected resolution" htmlFor="blocker-exp" optional>
                <Input id="blocker-exp" type="date" value={expected} onChange={(e) => setExpected(e.target.value)} />
              </Field>
            </div>
            <div className="flex justify-end gap-2">
              <Button size="sm" variant="ghost" onClick={() => { setAdding(false); setError(null); }}>Cancel</Button>
              <Button size="sm" variant="primary" type="submit" loading={saving}>Save blocker</Button>
            </div>
          </form>
        )}
        {blockers.length === 0 && !adding && <p className="px-1 py-1.5 text-[13px] text-muted">No blockers for this day.</p>}
        {blockers.map((b) => (
          <BlockerCard key={b.id} blocker={b} busy={busyId === b.id} onStatusChange={(s) => setStatus(b, s)} />
        ))}
      </div>
    </Card>
  );
}

export function DependenciesPanel({ date, projectId, dependencies, onChange }: {
  date: string; projectId: string | null; dependencies: Dependency[]; onChange: () => void;
}) {
  const toast = useToast();
  const [adding, setAdding] = useState(false);
  const [description, setDescription] = useState("");
  const [type, setType] = useState<DependencyType>("Approval");
  const [owner, setOwner] = useState("");
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function add(event: React.FormEvent) {
    event.preventDefault();
    if (!description.trim()) {
      setError("Describe what you need.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await api.post("/dependencies", {
        description: description.trim(), type, owner: owner.trim() || undefined, created_date: date, project_id: projectId || undefined,
      });
      setDescription("");
      setOwner("");
      setAdding(false);
      toast("Ask recorded");
      onChange();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to save.");
    } finally {
      setSaving(false);
    }
  }

  async function setStatus(dep: Dependency, status: Dependency["status"]) {
    setBusyId(dep.id);
    try {
      await api.put(`/dependencies/${dep.id}`, { status });
      onChange();
    } catch (err) {
      toast(errorMessage(err, "Unable to update."), "error");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card>
      <CardHeader
        title="Dependencies & asks"
        description="Approvals, decisions or access needed from others."
        actions={!adding && <Button size="sm" variant="ghost" onClick={() => setAdding(true)} icon={<Plus aria-hidden className="h-4 w-4" />}>Add</Button>}
      />
      <div className="space-y-2 p-3">
        {adding && (
          <form onSubmit={add} className="space-y-2 rounded-md border border-line bg-surface-2 p-3" aria-label="Add dependency or ask">
            <Field label="What do you need?" htmlFor="dep-desc" error={error ?? undefined}>
              <Textarea id="dep-desc" rows={2} autoFocus value={description} onChange={(e) => setDescription(e.target.value)}
                placeholder="e.g. Need stakeholder approval for access governance table design." />
            </Field>
            <div className="grid gap-2 sm:grid-cols-2">
              <Field label="Type" htmlFor="dep-type">
                <Select id="dep-type" value={type} onChange={(e) => setType(e.target.value as DependencyType)}>
                  {DEPENDENCY_TYPES.map((t) => <option key={t}>{t}</option>)}
                </Select>
              </Field>
              <Field label="Owner" htmlFor="dep-owner" optional>
                <Input id="dep-owner" value={owner} onChange={(e) => setOwner(e.target.value)} placeholder="Person or team" />
              </Field>
            </div>
            <div className="flex justify-end gap-2">
              <Button size="sm" variant="ghost" onClick={() => { setAdding(false); setError(null); }}>Cancel</Button>
              <Button size="sm" variant="primary" type="submit" loading={saving}>Save</Button>
            </div>
          </form>
        )}
        {dependencies.length === 0 && !adding && <p className="px-1 py-1.5 text-[13px] text-muted">Nothing pending from others.</p>}
        {dependencies.map((d) => (
          <DependencyCard key={d.id} dependency={d} busy={busyId === d.id} onStatusChange={(s) => setStatus(d, s)} />
        ))}
      </div>
    </Card>
  );
}
