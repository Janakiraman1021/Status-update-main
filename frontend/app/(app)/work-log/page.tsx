"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import LoadingState from "@/components/LoadingState";
import { useAuth } from "@/lib/auth";
import { todayIn } from "@/lib/date";

export default function WorkLogIndex() {
  const router = useRouter();
  const { timezone } = useAuth();
  useEffect(() => {
    router.replace(`/work-log/${todayIn(timezone)}`);
  }, [router, timezone]);
  return <LoadingState label="Opening today's work log…" />;
}
