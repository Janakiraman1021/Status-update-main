export type Theme = "light" | "dark" | "system";

export interface User {
  id: string;
  name: string;
  email: string;
}

export interface SessionInfo {
  user: User;
  csrf_token: string;
  expires_at: string;
  settings: { theme: Theme; timezone: string };
}
