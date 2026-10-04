/** Work dates are plain YYYY-MM-DD strings in the user's timezone; never pass them through Date parsing with a time zone. */

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const SHORT_MONTHS = MONTHS.map((m) => m.slice(0, 3));
export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function isIsoDate(value: string | undefined | null): value is string {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [y, m, d] = value.split("-").map(Number);
  const date = new Date(Date.UTC(y, m - 1, d));
  return date.getUTCFullYear() === y && date.getUTCMonth() === m - 1 && date.getUTCDate() === d;
}

export function parts(iso: string): { year: number; month: number; day: number } {
  const [year, month, day] = iso.split("-").map(Number);
  return { year, month, day };
}

export function toIso(year: number, month: number, day: number): string {
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

export function addDays(iso: string, days: number): string {
  const { year, month, day } = parts(iso);
  const date = new Date(Date.UTC(year, month - 1, day + days));
  return toIso(date.getUTCFullYear(), date.getUTCMonth() + 1, date.getUTCDate());
}

/** Today's date in an IANA timezone (falls back to the browser's zone). */
export function todayIn(timeZone?: string): string {
  try {
    const fmt = new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" });
    return fmt.format(new Date());
  } catch {
    const now = new Date();
    return toIso(now.getFullYear(), now.getMonth() + 1, now.getDate());
  }
}

export function formatLong(iso: string): string {
  const { year, month, day } = parts(iso);
  return `${String(day).padStart(2, "0")} ${MONTHS[month - 1]} ${year}`;
}

export function formatShort(iso: string): string {
  const { year, month, day } = parts(iso);
  return `${String(day).padStart(2, "0")} ${SHORT_MONTHS[month - 1]} ${year}`;
}

export function weekdayName(iso: string): string {
  const { year, month, day } = parts(iso);
  return new Date(Date.UTC(year, month - 1, day)).toLocaleDateString("en-GB", { weekday: "long", timeZone: "UTC" });
}

export function monthLabel(year: number, month: number): string {
  return `${MONTHS[month - 1]} ${year}`;
}

/** Calendar grid for a month, Monday-first, padded with nulls. */
export function monthGrid(year: number, month: number): (string | null)[] {
  const first = new Date(Date.UTC(year, month - 1, 1));
  const lead = (first.getUTCDay() + 6) % 7;
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const cells: (string | null)[] = Array(lead).fill(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(toIso(year, month, d));
  while (cells.length % 7) cells.push(null);
  return cells;
}

export function shiftMonth(year: number, month: number, delta: number): { year: number; month: number } {
  const index = year * 12 + (month - 1) + delta;
  return { year: Math.floor(index / 12), month: (index % 12) + 1 };
}

/** Format a UTC timestamp in the user's timezone. */
export function formatDateTime(isoTimestamp: string | null | undefined, timeZone?: string): string {
  if (!isoTimestamp) return "—";
  try {
    return new Intl.DateTimeFormat("en-GB", {
      timeZone, day: "2-digit", month: "short", year: "numeric", hour: "numeric", minute: "2-digit", hour12: true,
    }).format(new Date(isoTimestamp));
  } catch {
    return new Date(isoTimestamp).toLocaleString();
  }
}

export function relativeTime(isoTimestamp: string): string {
  const diff = (Date.now() - new Date(isoTimestamp).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`;
  return `${Math.floor(diff / 86400)} d ago`;
}
