"use client";

import type { Project } from "@/types/project";
import { Select } from "./ui";

export default function ProjectSelector({ projects, value, onChange, id, disabled, placeholder = "No project", includeArchivedValue = true, className }: {
  projects: Project[]; value: string | null; onChange: (projectId: string | null) => void; id?: string; disabled?: boolean;
  placeholder?: string; includeArchivedValue?: boolean; className?: string;
}) {
  const active = projects.filter((p) => p.status === "Active");
  // Keep an archived project visible when it is the current value (historical days).
  const current = includeArchivedValue ? projects.find((p) => p.id === value && p.status === "Archived") : undefined;
  return (
    <Select id={id} value={value ?? ""} disabled={disabled} onChange={(e) => onChange(e.target.value || null)} className={className}>
      <option value="">{placeholder}</option>
      {active.map((p) => (
        <option key={p.id} value={p.id}>{p.name}</option>
      ))}
      {current && <option value={current.id}>{current.name} (archived)</option>}
    </Select>
  );
}
