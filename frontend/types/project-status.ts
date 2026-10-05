export type ProjectProgress = "On track" | "Needs help" | "Delayed" | "Done";

export interface ProjectStatus {
  id: string;
  project_id: string;
  work_date: string;
  status: ProjectProgress;
  daily_update: string;
  next_step: string | null;
  help_needed: string | null;
  created_at: string;
  updated_at: string;
}
