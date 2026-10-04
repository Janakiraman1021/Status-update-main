"use client";

import { FileText } from "lucide-react";
import Link from "next/link";

import EodStatus from "@/components/EodStatus";
import { EodHistoryTable } from "@/components/HistoryTables";
import { Card, CardHeader, PageHeader } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { formatLong, todayIn } from "@/lib/date";
import { useApi } from "@/lib/hooks";
import type { EodView } from "@/types/eod";

export default function EodReportsPage() {
  const { timezone } = useAuth();
  const today = todayIn(timezone);
  const { data: todayView } = useApi<EodView>(`/eod/${today}`);

  return (
    <>
      <PageHeader
        title="EOD reports"
        description="Generate, review and send your end-of-day reports."
        actions={(
          <Link href={`/eod/${today}`} className="inline-flex h-9 items-center gap-1.5 rounded-md bg-primary px-3.5 text-sm font-medium text-primary-text shadow-sm hover:bg-primary-hover">
            <FileText aria-hidden className="h-4 w-4" /> Today&apos;s EOD
          </Link>
        )}
      />
      {todayView && (
        <Card className="mb-5">
          <CardHeader
            title={`Today · ${formatLong(today)}`}
            description={todayView.has_work ? "Work has been logged today." : "No work logged yet today."}
            actions={<EodStatus status={todayView.report?.status ?? "NOT_GENERATED"} />}
          />
        </Card>
      )}
      <Card>
        <CardHeader title="All reports" />
        <EodHistoryTable />
      </Card>
    </>
  );
}
