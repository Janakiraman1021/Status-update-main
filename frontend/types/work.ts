import type { EodStatusValue } from "./eod";

export const WORK_CATEGORIES = [
  "Development", "Enhancement", "Bug Fix", "Investigation", "Research", "Testing",
  "Deployment", "Documentation", "Meeting", "Support", "Learning", "Planning",
] as const;
export const WORK_STATUSES = ["Planned", "In Progress", "Completed", "Blocked", "Deferred"] as const;
export const BLOCKER_STATUSES = ["Open", "In Progress", "Resolved"] as const;
export const DEPENDENCY_TYPES = ["Approval", "Information", "Dependency", "Decision", "Access"] as const;

export type WorkCategory = (typeof WORK_CATEGORIES)[number];
export type WorkStatus = (typeof WORK_STATUSES)[number];
export type BlockerStatus = (typeof BLOCKER_STATUSES)[number];
export type DependencyType = (typeof DEPENDENCY_TYPES)[number];

export interface WorkLog {
  id: string;
  work_date: string;
  project_id: string | null;
  quick_notes: string | null;
  next_steps: string | null;
  learnings: string | null;
  meetings: string | null;
  metrics: string | null;
  updated_at: string;
}

export type WorkLogFields = Pick<WorkLog, "quick_notes" | "next_steps" | "learnings" | "meetings" | "metrics">;

export interface WorkEntry {
  id: string;
  work_date: string;
  description: string;
  timestamp: string;
  time: string;
  time_label: string;
  project_id: string | null;
  project_name: string | null;
  category: WorkCategory | null;
  status: WorkStatus | null;
  updated_at: string;
}

export interface Blocker {
  id: string;
  description: string;
  project_id: string | null;
  project_name?: string | null;
  identified_date: string;
  status: BlockerStatus;
  dependency: string | null;
  expected_resolution: string | null;
  resolved_date: string | null;
}

export interface Dependency {
  id: string;
  description: string;
  type: DependencyType;
  owner: string | null;
  status: BlockerStatus;
  project_id: string | null;
  project_name?: string | null;
  created_date: string;
  resolved_at: string | null;
}

export interface DaySummary {
  completed: number;
  in_progress: number;
  blocked: number;
  planned: number;
  blockers: number;
  open_asks: number;
  total_entries: number;
}

export interface DayView {
  work_date: string;
  date_label: string;
  log: WorkLog | null;
  project_id: string | null;
  project_name: string | null;
  entries: WorkEntry[];
  blockers: Blocker[];
  dependencies: Dependency[];
  summary: DaySummary;
  eod: { id: string | null; status: EodStatusValue; sent_at: string | null; current_version: number };
  has_work: boolean;
}

export interface CalendarDay {
  date: string;
  has_work: boolean;
  eod_status: EodStatusValue;
  eod_generated: boolean;
  eod_sent: boolean;
  eod_failed: boolean;
  has_blocker: boolean;
}

export interface CalendarMonth {
  year: number;
  month: number;
  today: string;
  timezone: string;
  days: CalendarDay[];
}

export interface DashboardData {
  greeting: string;
  user_name: string;
  today: string;
  today_label: string;
  timezone: string;
  project_name: string | null;
  summary: DaySummary;
  has_work: boolean;
  eod: DayView["eod"];
  eod_time: string;
  auto_eod_enabled: boolean;
  open_blockers: Blocker[];
  open_blocker_count: number;
  open_ask_count: number;
  recent_activity: {
    id: string; description: string; work_date: string; status: WorkStatus | null; category: WorkCategory | null;
    project_name: string | null; time_label: string; updated_at: string;
  }[];
  recent_eods: {
    id: string; work_date: string; status: EodStatusValue; subject: string | null; project_label: string | null;
    sent_at: string | null; sent_time_label: string | null;
  }[];
  days_logged_this_week: number;
}

export interface CategorizedSuggestion {
  description: string;
  category: WorkCategory | null;
  status: WorkStatus | null;
}
