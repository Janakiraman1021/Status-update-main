export type EodStatusValue = "NOT_GENERATED" | "GENERATING" | "GENERATED" | "SENDING" | "SENT" | "FAILED";

export type EodLength = "short" | "standard" | "long" | "detailed";
export type EodTone = "professional" | "executive" | "corporate";

export interface EodOptions {
  length: EodLength;
  tone: EodTone;
}

export const EOD_LENGTH_OPTIONS: { value: EodLength; label: string; hint: string }[] = [
  { value: "short", label: "Short", hint: "One-line snapshot, crisp bullets" },
  { value: "standard", label: "Medium", hint: "Balanced report for your manager" },
  { value: "long", label: "Long", hint: "Full bullets with context, grouped by workstream" },
  { value: "detailed", label: "Detailed", hint: "Comprehensive, every recorded detail" },
];

export const EOD_TONE_OPTIONS: { value: EodTone; label: string; hint: string }[] = [
  { value: "executive", label: "Executive", hint: "Polished senior corporate language" },
  { value: "professional", label: "Professional", hint: "Clear, plain business English" },
  { value: "corporate", label: "Corporate", hint: "Full corporate jargon: circling back, level-set, move the needle, north star" },
];

export interface Recipients {
  to: string[];
  cc: string[];
  bcc: string[];
}

export interface EodError {
  stage: "GENERATION" | "EMAIL";
  code: string;
  message: string;
  at: string;
}

export interface EodReport {
  id: string;
  user_id: string;
  work_date: string;
  status: EodStatusValue;
  current_version: number;
  sent_version: number | null;
  subject: string | null;
  body: string | null;
  project_label: string | null;
  recipients: Recipients;
  generated_at: string | null;
  generated_by: string | null;
  sent_at: string | null;
  sent_time_label?: string;
  sent_to?: Recipients;
  sent_by?: string;
  warnings?: string[];
  last_error: EodError | null;
  has_unsent_changes: boolean;
  options?: EodOptions;
}

export interface EodVersionSummary {
  id: string;
  version: number;
  source: "generated" | "regenerated" | "edited";
  is_current: boolean;
  created_at: string;
  created_by: string;
  sent_at: string | null;
  subject: string;
  ai_provider?: string;
  ai_model?: string;
  based_on_version?: number;
  options?: EodOptions;
}

export interface EodVersion extends EodVersionSummary {
  body: string;
  warnings?: string[];
}

export interface EodDelivery {
  id: string;
  created_at: string;
  success: boolean;
  to: string[];
  cc: string[];
  bcc: string[];
  error: string | null;
  provider: string;
  reference: { version?: number };
}

export interface EodSourceInputs {
  quick_notes?: string;
  next_steps?: string;
  learnings?: string;
  meetings?: string;
  metrics?: string;
  entries?: { time?: string; description: string; project?: string | null; category?: string | null; status?: string | null }[];
  blockers?: { description: string; status: string; dependency?: string | null; expected_resolution?: string | null }[];
  dependencies?: { description: string; type: string; owner?: string | null; status: string }[];
}

export interface EodView {
  work_date: string;
  date_label: string;
  has_work: boolean;
  source_inputs: EodSourceInputs;
  default_recipients: Recipients;
  default_options: EodOptions;
  ai_provider: string;
  report: EodReport | null;
  versions: EodVersionSummary[];
  current: EodVersion | null;
  deliveries: EodDelivery[];
  outdated: boolean;
}

export interface EodHistoryRow {
  id: string;
  work_date: string;
  status: EodStatusValue;
  subject: string | null;
  project_label: string | null;
  current_version: number;
  sent_version: number | null;
  generated_at: string | null;
  sent_at: string | null;
  generated_time_label: string | null;
  sent_time_label: string | null;
  last_error: EodError | null;
}
