"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import Calendar from "@/components/Calendar";
import ErrorState from "@/components/ErrorState";
import LoadingState from "@/components/LoadingState";
import { Card, PageHeader } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { parts, todayIn } from "@/lib/date";
import { useApi } from "@/lib/hooks";
import type { CalendarMonth } from "@/types/work";

function CalendarView() {
  const router = useRouter();
  const params = useSearchParams();
  const { timezone } = useAuth();
  const today = todayIn(timezone);

  // The visible month lives in the URL (?year=&month=) so it survives reloads and back/forward.
  const qYear = Number(params.get("year"));
  const qMonth = Number(params.get("month"));
  const month = qYear && qMonth >= 1 && qMonth <= 12 ? { year: qYear, month: qMonth } : { year: parts(today).year, month: parts(today).month };

  const { data, error, loading, reload } = useApi<CalendarMonth>(`/calendar?year=${month.year}&month=${month.month}`);

  function changeMonth(year: number, m: number) {
    router.replace(`/calendar?year=${year}&month=${m}`, { scroll: false });
  }

  if (error && !data) return <ErrorState message={error.message} onRetry={reload} />;

  const days = data?.days ?? [];
  const serverToday = data?.today ?? today;
  const logged = days.filter((d) => d.has_work).length;
  const sent = days.filter((d) => d.eod_sent).length;

  return (
    <>
      <PageHeader
        title="Calendar"
        description={data ? `${logged} day${logged === 1 ? "" : "s"} logged · ${sent} EOD${sent === 1 ? "" : "s"} sent this month` : "Loading…"}
      />
      <Card className="p-3 sm:p-4">
        <Calendar
          year={month.year}
          month={month.month}
          today={serverToday}
          days={days}
          loading={loading}
          onSelect={(date) => router.push(`/work-log/${date}`)}
          onMonthChange={changeMonth}
          onToday={() => {
            const t = parts(serverToday);
            changeMonth(t.year, t.month);
          }}
        />
      </Card>
    </>
  );
}

export default function CalendarPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading calendar…" />}>
      <CalendarView />
    </Suspense>
  );
}
