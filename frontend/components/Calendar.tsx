"use client";

import { AlertCircle, CheckCircle2, ChevronLeft, ChevronRight, FileText } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { WEEKDAYS, addDays, formatLong, isHoliday, monthGrid, monthLabel, parts } from "@/lib/date";
import { cn } from "@/lib/utils";
import type { CalendarDay } from "@/types/work";
import { Button } from "./ui";

interface CalendarProps {
  year: number;
  month: number;
  today: string;
  days: CalendarDay[];
  selected?: string | null;
  onSelect: (date: string) => void;
  onMonthChange: (year: number, month: number) => void;
  onToday: () => void;
  loading?: boolean;
}

function describe(date: string, info: CalendarDay | undefined, today: string): string {
  const bits = [formatLong(date)];
  if (date === today) bits.push("today");
  if (info?.is_holiday ?? isHoliday(date)) bits.push("holiday");
  if (info?.has_work) bits.push("work logged");
  if (info?.eod_sent) bits.push("EOD sent");
  else if (info?.eod_failed) bits.push("EOD failed");
  else if (info?.eod_generated) bits.push("EOD generated");
  if (info?.has_blocker) bits.push("blocker raised");
  return bits.join(", ");
}

export default function Calendar({ year, month, today, days, selected, onSelect, onMonthChange, onToday, loading }: CalendarProps) {
  const byDate = new Map(days.map((d) => [d.date, d]));
  const cells = monthGrid(year, month);
  const firstOfMonth = cells.find(Boolean) as string;
  const todayInMonth = parts(today).year === year && parts(today).month === month;
  const [focusedState, setFocused] = useState<string>(selected && byDate.has(selected) ? selected : todayInMonth ? today : firstOfMonth);
  // The roving-tabindex day falls back to today / the 1st when the month changes.
  const inMonth = parts(focusedState).year === year && parts(focusedState).month === month;
  const focused = inMonth ? focusedState : todayInMonth ? today : firstOfMonth;
  const gridRef = useRef<HTMLDivElement>(null);
  const pendingFocus = useRef(false);

  useEffect(() => {
    if (!pendingFocus.current) return;
    pendingFocus.current = false;
    gridRef.current?.querySelector<HTMLButtonElement>(`[data-date="${focused}"]`)?.focus();
  }, [focused, year, month]);

  function move(target: string) {
    const p = parts(target);
    pendingFocus.current = true;
    if (p.year !== year || p.month !== month) onMonthChange(p.year, p.month);
    setFocused(target);
  }

  function onKeyDown(event: React.KeyboardEvent, date: string) {
    const offsets: Record<string, number> = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };
    if (event.key in offsets) {
      event.preventDefault();
      move(addDays(date, offsets[event.key]));
    } else if (event.key === "Home" || event.key === "End") {
      event.preventDefault();
      const weekday = (new Date(`${date}T00:00:00Z`).getUTCDay() + 6) % 7;
      move(addDays(date, event.key === "Home" ? -weekday : 6 - weekday));
    } else if (event.key === "PageUp" || event.key === "PageDown") {
      event.preventDefault();
      const delta = event.key === "PageUp" ? -1 : 1;
      const p = parts(date);
      const target = new Date(Date.UTC(p.year, p.month - 1 + delta, 1));
      const daysInTarget = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0)).getUTCDate();
      move(`${target.getUTCFullYear()}-${String(target.getUTCMonth() + 1).padStart(2, "0")}-${String(Math.min(p.day, daysInTarget)).padStart(2, "0")}`);
    }
  }

  const prev = month === 1 ? { y: year - 1, m: 12 } : { y: year, m: month - 1 };
  const next = month === 12 ? { y: year + 1, m: 1 } : { y: year, m: month + 1 };

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold tracking-tight" aria-live="polite">{monthLabel(year, month)}</h2>
        <div className="flex items-center gap-1.5">
          <Button size="sm" variant="secondary" onClick={() => onMonthChange(prev.y, prev.m)} aria-label="Previous month" icon={<ChevronLeft className="h-4 w-4" />} />
          <Button size="sm" variant="secondary" onClick={onToday}>Today</Button>
          <Button size="sm" variant="secondary" onClick={() => onMonthChange(next.y, next.m)} aria-label="Next month" icon={<ChevronRight className="h-4 w-4" />} />
        </div>
      </div>

      <div ref={gridRef} role="grid" aria-label={monthLabel(year, month)} aria-busy={loading} className={cn("overflow-hidden rounded-lg border border-line bg-surface", loading && "opacity-70")}>
        <div role="row" className="grid grid-cols-7 border-b border-line bg-surface-2">
          {WEEKDAYS.map((d) => (
            <div key={d} role="columnheader" className="px-2 py-2 text-center text-[11.5px] font-semibold uppercase tracking-wide text-subtle">
              <abbr title={d} className="no-underline">{d}</abbr>
            </div>
          ))}
        </div>
        {Array.from({ length: cells.length / 7 }).map((_, row) => (
          <div role="row" key={row} className="grid grid-cols-7 border-b border-line last:border-b-0">
            {cells.slice(row * 7, row * 7 + 7).map((date, col) => {
              if (!date) return <div role="gridcell" key={`empty-${row}-${col}`} className="min-h-16 border-r border-line bg-surface-2/50 last:border-r-0 sm:min-h-24" />;
              const info = byDate.get(date);
              const isToday = date === today;
              const holiday = info?.is_holiday ?? isHoliday(date);
              const isSelected = date === selected;
              const isFuture = date > today;
              return (
                <div role="gridcell" key={date} aria-selected={isSelected} className="border-r border-line last:border-r-0">
                  <button
                    type="button"
                    data-date={date}
                    tabIndex={date === focused ? 0 : -1}
                    onClick={() => {
                      if (!holiday) onSelect(date);
                    }}
                    onKeyDown={(e) => onKeyDown(e, date)}
                    onFocus={() => setFocused(date)}
                    aria-label={describe(date, info, today)}
                    aria-disabled={holiday}
                    aria-current={isToday ? "date" : undefined}
                    className={cn(
                      "group flex h-full min-h-16 w-full flex-col items-start gap-1 p-1.5 text-left transition-colors hover:bg-surface-hover focus-visible:z-10 sm:min-h-24 sm:p-2",
                      holiday && "bg-danger-soft",
                      isSelected && "bg-primary-soft",
                    )}
                  >
                    <span
                      className={cn(
                        "flex h-6 min-w-6 items-center justify-center rounded-full px-1 text-[13px] tabular-nums",
                        isToday ? "bg-primary font-semibold text-primary-text" : holiday ? "text-danger" : isFuture ? "text-subtle" : "text-text",
                      )}
                    >
                      {parts(date).day}
                    </span>
                    <span className="flex flex-wrap items-center gap-1" aria-hidden>
                      {holiday && <span className="rounded bg-surface px-1 text-[10px] font-medium text-danger">Holiday</span>}
                      {info?.has_work && <span className="h-2 w-2 rounded-full bg-primary" title="Work logged" />}
                      {info?.eod_sent ? (
                        <CheckCircle2 className="h-3.5 w-3.5 text-success" />
                      ) : info?.eod_failed ? (
                        <AlertCircle className="h-3.5 w-3.5 text-danger" />
                      ) : info?.eod_generated ? (
                        <FileText className="h-3.5 w-3.5 text-primary" />
                      ) : null}
                      {info?.has_blocker && <span className="h-2 w-2 rotate-45 bg-warning" title="Blocker raised" />}
                    </span>
                    {info && (info.has_work || info.eod_generated) && (
                      <span className="hidden text-[11px] leading-tight text-muted sm:block" aria-hidden>
                        {info.eod_sent ? "EOD sent" : info.eod_failed ? "EOD failed" : info.eod_generated ? "EOD ready" : "Logged"}
                      </span>
                    )}
                  </button>
                </div>
              );
            })}
          </div>
        ))}
      </div>

      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted" aria-label="Legend">
        <li className="flex items-center gap-1.5"><span className="rounded bg-danger-soft px-1 text-[10px] font-medium text-danger" aria-hidden>H</span> Holiday (Sunday and 2nd/4th Saturday)</li>
        <li className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-primary" aria-hidden /> Work logged</li>
        <li className="flex items-center gap-1.5"><FileText aria-hidden className="h-3.5 w-3.5 text-primary" /> EOD generated</li>
        <li className="flex items-center gap-1.5"><CheckCircle2 aria-hidden className="h-3.5 w-3.5 text-success" /> EOD sent</li>
        <li className="flex items-center gap-1.5"><AlertCircle aria-hidden className="h-3.5 w-3.5 text-danger" /> EOD failed</li>
        <li className="flex items-center gap-1.5"><span className="h-2 w-2 rotate-45 bg-warning" aria-hidden /> Blocker raised</li>
        <li className="flex items-center gap-1.5"><span className="flex h-4 w-4 items-center justify-center rounded-full bg-primary text-[9px] font-semibold text-primary-text" aria-hidden>1</span> Today</li>
      </ul>
      <p className="mt-2 text-xs text-subtle">Use arrow keys to move between days and Enter to open a day.</p>
    </div>
  );
}
