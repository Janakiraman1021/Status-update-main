export type ProjectStatus = "Active" | "Archived";

export interface Project {
  id: string;
  name: string;
  description: string | null;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
  entry_count?: number;
}
