export function cn(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

export function parseEmails(value: string): string[] {
  return value
    .split(/[,;\s]+/)
    .map((v) => v.trim())
    .filter(Boolean);
}

export const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function invalidEmails(list: string[]): string[] {
  return list.filter((email) => !EMAIL_RE.test(email));
}

export function safeStorage() {
  return {
    get(key: string): string | null {
      try {
        return window.localStorage.getItem(key);
      } catch {
        return null;
      }
    },
    set(key: string, value: string) {
      try {
        window.localStorage.setItem(key, value);
      } catch {
        /* storage unavailable (private mode, quota) — drafts are best effort */
      }
    },
    remove(key: string) {
      try {
        window.localStorage.removeItem(key);
      } catch {
        /* ignore */
      }
    },
  };
}
