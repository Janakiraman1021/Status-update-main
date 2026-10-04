"use client";

import { AlertTriangle, ArrowLeft, History, RefreshCw, Save, Send, Wand2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import EmptyState from "@/components/EmptyState";
import EodEditor, { type RecipientsText } from "@/components/EodEditor";
import EodOptionsPicker, { EodStyleBar } from "@/components/EodOptionsPicker";
import EodStatus from "@/components/EodStatus";
import ErrorState from "@/components/ErrorState";
import LoadingState from "@/components/LoadingState";
import { Alert, Button, Card, CardHeader, ConfirmDialog, Dialog } from "@/components/ui";
import { ApiError, api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDateTime, formatLong } from "@/lib/date";
import { useApi, useUnsavedChangesWarning } from "@/lib/hooks";
import { useToast } from "@/lib/toast";
import { invalidEmails, parseEmails } from "@/lib/utils";
import { EOD_LENGTH_OPTIONS, EOD_TONE_OPTIONS, type EodOptions, type EodVersion, type EodView, type Recipients } from "@/types/eod";

const SOURCE_LABEL = { generated: "Generated", regenerated: "Regenerated", edited: "Edited" } as const;

function toText(r: Recipients): RecipientsText {
  return { to: r.to.join(", "), cc: r.cc.join(", "), bcc: r.bcc.join(", ") };
}

export default function EodPage() {
  const params = useParams<{ date: string }>();
  const { data: view, error, loading, reload, setData } = useApi<EodView>(`/eod/${params.date}`);

  useEffect(() => {
    if (view) document.title = `EOD ${formatLong(view.work_date)} · WorkLog`;
  }, [view]);

  if (loading && !view) return <LoadingState label="Loading EOD…" />;
  if (error || !view) {
    return <ErrorState title={error?.status === 404 ? "EOD not found" : undefined} message={error?.message} onRetry={error?.status === 404 ? undefined : reload} />;
  }
  // Remount the editor whenever a different version becomes current, so its local state starts from the server copy.
  return <EodWorkspace key={`${view.report?.id ?? "new"}:${view.current?.id ?? 0}`} view={view} setData={setData} reload={reload} />;
}

function EodWorkspace({ view, setData, reload }: { view: EodView; setData: (v: EodView) => void; reload: () => Promise<void> }) {
  const router = useRouter();
  const toast = useToast();
  const { user, timezone } = useAuth();

  const [subject, setSubject] = useState(view.current?.subject ?? "");
  const [body, setBody] = useState(view.current?.body ?? "");
  const [recipients, setRecipients] = useState<RecipientsText>(toText(view.report?.recipients ?? view.default_recipients));
  const [busy, setBusy] = useState<null | "generate" | "save" | "send">(null);
  const [confirm, setConfirm] = useState<null | "send" | "resend" | "regenerate">(null);
  const [versionView, setVersionView] = useState<EodVersion | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [options, setOptions] = useState<EodOptions>(view.report?.options ?? view.default_options);
  const [pendingStyle, setPendingStyle] = useState<EodOptions | null>(null);

  const report = view.report;
  const current = view.current;

  // If the report is busy elsewhere (e.g. the scheduler is sending it), poll until it settles.
  useEffect(() => {
    if (!report || (report.status !== "GENERATING" && report.status !== "SENDING")) return;
    const handle = setInterval(() => reload(), 3000);
    return () => clearInterval(handle);
  }, [report, reload]);

  const savedRecipients = useMemo(() => (report ? toText(report.recipients) : null), [report]);
  const contentDirty = Boolean(current) && (subject !== current?.subject || body !== current?.body);
  const recipientsDirty = Boolean(savedRecipients) && JSON.stringify(recipients) !== JSON.stringify(savedRecipients);
  const dirty = contentDirty || recipientsDirty;
  useUnsavedChangesWarning(dirty);

  const recipientLists = {
    to: parseEmails(recipients.to),
    cc: parseEmails(recipients.cc),
    bcc: parseEmails(recipients.bcc),
  };
  const recipientErrors: Partial<Record<keyof RecipientsText, string>> = {};
  (["to", "cc", "bcc"] as const).forEach((field) => {
    const bad = invalidEmails(recipientLists[field]);
    if (bad.length) recipientErrors[field] = `Invalid address: ${bad.join(", ")}`;
  });
  if (!recipientLists.to.length) recipientErrors.to = "Add at least one recipient.";
  const recipientsValid = Object.keys(recipientErrors).length === 0;

  async function run<T>(kind: NonNullable<typeof busy>, action: () => Promise<T>): Promise<T | undefined> {
    setBusy(kind);
    setActionError(null);
    try {
      return await action();
    } catch (err) {
      const message = errorMessage(err);
      const reason = err instanceof ApiError && err.details && typeof err.details === "object" ? (err.details as { reason?: string }).reason : undefined;
      setActionError(reason ? `${message} (${reason})` : message);
      if (err instanceof ApiError && err.status !== 400) await reload();
      return undefined;
    } finally {
      setBusy(null);
    }
  }

  async function generate() {
    const result = await run("generate", () => api.post<EodView>("/eod/generate", { work_date: view.work_date, ...options }));
    if (result) {
      setData(result);
      toast("EOD generated");
    }
  }

  async function regenerate(next: EodOptions = options) {
    setConfirm(null);
    setPendingStyle(null);
    if (!report) return;
    setOptions(next);
    const result = await run("generate", () => api.post<EodView>(`/eod/${report.id}/regenerate`, next));
    if (result) {
      setData(result);
      const length = EOD_LENGTH_OPTIONS.find((o) => o.value === next.length)?.label;
      const tone = EOD_TONE_OPTIONS.find((o) => o.value === next.tone)?.label;
      toast(`Regenerated as version ${result.report?.current_version} (${length} · ${tone})`);
    }
  }

  /** One-click style change from the Length / Tone buttons. Unsaved edits are confirmed first. */
  function changeStyle(next: EodOptions) {
    if (dirty) {
      setPendingStyle(next);
      setConfirm("regenerate");
      return;
    }
    void regenerate(next);
  }

  /** Pending edits as an update payload, or null when the editor content is invalid. */
  function pendingChanges(): Record<string, unknown> | null {
    if (!subject.trim() || !body.trim()) {
      setActionError("Subject and report body cannot be empty.");
      return null;
    }
    const payload: Record<string, unknown> = {};
    if (contentDirty) Object.assign(payload, { subject: subject.trim(), body });
    if (recipientsDirty) payload.recipients = recipientLists;
    return payload;
  }

  async function save() {
    if (!report) return;
    if (recipientsDirty && !recipientsValid) {
      setActionError("Fix the recipient addresses before saving.");
      return;
    }
    const payload = pendingChanges();
    if (!payload || !Object.keys(payload).length) return;
    const result = await run("save", () => api.put<EodView>(`/eod/${report.id}`, payload));
    if (result) {
      setData(result);
      toast(report.status === "SENT" && contentDirty ? "Saved as a new version. The sent version is preserved." : "EOD saved");
    }
  }

  async function send(resend = false) {
    setConfirm(null);
    if (!report) return;
    if (!recipientsValid) {
      setActionError("Fix the recipient addresses before sending.");
      return;
    }
    const payload = pendingChanges();
    if (!payload) return;
    // Save edits and send in one step, so the editor is not remounted halfway through.
    const result = await run("send", async () => {
      if (payload.subject !== undefined) await api.put<EodView>(`/eod/${report.id}`, { subject: payload.subject, body: payload.body });
      return api.post<EodView>(`/eod/${report.id}/send`, { recipients: recipientLists, resend });
    });
    if (result) {
      setData(result);
      toast(`EOD sent to ${recipientLists.to.join(", ")}`);
    }
  }

  async function openVersion(version: number) {
    if (!report) return;
    try {
      setVersionView(await api.get<EodVersion>(`/eod/${report.id}/versions/${version}`));
    } catch (err) {
      toast(errorMessage(err), "error");
    }
  }

  const status = report?.status ?? "NOT_GENERATED";
  const isSent = status === "SENT";
  const failed = status === "FAILED" ? report?.last_error : null;
  const busyElsewhere = status === "GENERATING" || status === "SENDING";
  const previewUrl = report?.current_version ? `/api/eod/${report.id}/preview?v=${report.current_version}-${encodeURIComponent(current?.subject ?? "")}-${body === current?.body ? "s" : "d"}` : null;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link href={`/work-log/${view.work_date}`} className="mb-1 inline-flex items-center gap-1 text-[13px] text-muted hover:text-text">
            <ArrowLeft aria-hidden className="h-3.5 w-3.5" /> Work log for {formatLong(view.work_date)}
          </Link>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-semibold tracking-tight">EOD · {formatLong(view.work_date)}</h1>
            <EodStatus status={status} />
            {report?.current_version ? <span className="text-xs text-muted">Version {report.current_version}</span> : null}
            {report?.options ? (
              <span className="rounded border border-line bg-surface-2 px-1.5 py-0.5 text-[11.5px] text-muted">
                {EOD_LENGTH_OPTIONS.find((o) => o.value === report.options?.length)?.label} · {EOD_TONE_OPTIONS.find((o) => o.value === report.options?.tone)?.label}
              </span>
            ) : null}
          </div>
          {isSent && report?.sent_at && (
            <p className="mt-1 text-[13px] text-muted">
              Sent {formatDateTime(report.sent_at, timezone)}{report.sent_by === "scheduler" ? " automatically" : ""} (version {report.sent_version})
              {report.sent_to?.to?.length ? ` to ${report.sent_to.to.join(", ")}` : ""}
            </p>
          )}
        </div>
        {report?.current_version ? (
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => setConfirm("regenerate")} loading={busy === "generate"} disabled={Boolean(busy) || busyElsewhere} icon={<RefreshCw aria-hidden className="h-4 w-4" />}>
              Regenerate
            </Button>
            <Button onClick={() => save()} loading={busy === "save"} disabled={!dirty || Boolean(busy) || busyElsewhere} icon={<Save aria-hidden className="h-4 w-4" />}>
              Save
            </Button>
            <Button
              variant="primary"
              onClick={() => setConfirm(isSent ? "resend" : "send")}
              loading={busy === "send"}
              disabled={Boolean(busy) || busyElsewhere || !recipientsValid}
              icon={<Send aria-hidden className="h-4 w-4" />}
            >
              {isSent ? "Resend email" : "Send email"}
            </Button>
          </div>
        ) : null}
      </div>

      {report?.current_version ? (
        <EodStyleBar
          value={options}
          onSelect={changeStyle}
          disabled={Boolean(busy) || busyElsewhere}
          pending={busy === "generate" ? options : null}
          localProvider={view.ai_provider === "local"}
        />
      ) : null}

      {actionError && <Alert tone="danger" title="Action failed">{actionError}</Alert>}

      {failed && (
        <Alert
          tone="danger"
          title={failed.stage === "EMAIL" ? "Unable to send EOD. Retry." : "Unable to generate EOD. Retry."}
          action={
            <Button size="sm" variant="primary" onClick={() => (failed.stage === "EMAIL" ? setConfirm("send") : generate())} loading={Boolean(busy)}
              icon={<RefreshCw aria-hidden className="h-3.5 w-3.5" />}>
              Retry
            </Button>
          }
        >
          {failed.message}
        </Alert>
      )}
      {report?.last_error && status !== "FAILED" && report.last_error.stage === "GENERATION" && (
        <Alert tone="warning" title="The last regeneration failed">{report.last_error.message} Your previous version is unchanged.</Alert>
      )}
      {busyElsewhere && <Alert tone="info" title={status === "SENDING" ? "Sending in progress…" : "Generating…"}>This page refreshes automatically.</Alert>}
      {view.outdated && report?.current_version ? (
        <Alert tone="warning" title="Your work log changed after this report was generated"
          action={<Button size="sm" onClick={() => setConfirm("regenerate")}>Regenerate</Button>}>
          Regenerate to include the latest entries, or edit the report manually.
        </Alert>
      ) : null}
      {report?.has_unsent_changes && (
        <Alert tone="info" title="Unsent changes">
          Version {report.current_version} has changes made after version {report.sent_version} was sent. The sent version is preserved in the history below.
        </Alert>
      )}
      {current?.warnings && current.warnings.length > 0 && (
        <Alert tone="warning" title="Please verify before sending">
          <ul className="list-disc pl-4">
            {current.warnings.map((w) => <li key={w}>{w}</li>)}
          </ul>
        </Alert>
      )}

      {!report?.current_version ? (
        <Card>
          <EmptyState
            icon={<Wand2 className="h-5 w-5" />}
            title={view.has_work ? "Ready to generate your EOD" : "No work logged for this day"}
            description={
              view.has_work
                ? "Your documented work will be turned into a professional EOD report. You can review and edit it before sending."
                : "Add notes or entries to the work log first. The report is written only from what you record."
            }
            action={
              view.has_work ? (
                <div className="flex flex-col items-center gap-4">
                  <div className="rounded-md border border-line bg-surface-2 px-4 py-3 text-left">
                    <EodOptionsPicker value={options} onChange={setOptions} disabled={busy === "generate"} localProvider={view.ai_provider === "local"} />
                  </div>
                  <Button variant="primary" onClick={generate} loading={busy === "generate"} disabled={busyElsewhere} icon={<Wand2 aria-hidden className="h-4 w-4" />}>
                    {busy === "generate" ? "Generating…" : "Generate EOD"}
                  </Button>
                </div>
              ) : (
                <Button onClick={() => router.push(`/work-log/${view.work_date}`)}>Open work log</Button>
              )
            }
          />
        </Card>
      ) : (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_19rem]">
          <Card className="p-4">
            <EodEditor
              subject={subject}
              body={body}
              recipients={recipients}
              onSubjectChange={setSubject}
              onBodyChange={setBody}
              onRecipientsChange={setRecipients}
              recipientErrors={recipientsDirty || !recipientsValid ? recipientErrors : {}}
              previewUrl={previewUrl}
              previewStale={contentDirty}
              disabled={busyElsewhere}
            />
          </Card>

          <aside className="space-y-5" aria-label="Report history">
            <Card>
              <CardHeader title="Versions" description="Every version is kept." />
              <ol className="divide-y divide-line">
                {view.versions.map((v) => (
                  <li key={v.id}>
                    <button type="button" onClick={() => openVersion(v.version)} className="flex w-full items-start justify-between gap-2 px-4 py-2.5 text-left hover:bg-surface-hover">
                      <span>
                        <span className="block text-[13px] font-medium text-text">
                          Version {v.version} {v.is_current && <span className="text-xs font-normal text-primary">(current)</span>}
                        </span>
                        <span className="block text-xs text-muted">
                          {SOURCE_LABEL[v.source]} {v.created_by === "scheduler" ? "by scheduler" : v.created_by === user?.id ? "by you" : ""} · {formatDateTime(v.created_at, timezone)}
                        </span>
                      </span>
                      {v.sent_at && <EodStatus status="SENT" prefix={false} />}
                    </button>
                  </li>
                ))}
              </ol>
            </Card>

            <Card>
              <CardHeader title="Delivery log" />
              {view.deliveries.length === 0 ? (
                <p className="px-4 py-3 text-[13px] text-muted">Not sent yet.</p>
              ) : (
                <ul className="divide-y divide-line">
                  {view.deliveries.map((d) => (
                    <li key={d.id} className="px-4 py-2.5 text-xs">
                      <p className={d.success ? "font-medium text-success" : "font-medium text-danger"}>
                        {d.success ? "Delivered" : "Failed"} · v{d.reference?.version ?? "?"}
                      </p>
                      <p className="text-muted">{formatDateTime(d.created_at, timezone)} via {d.provider}</p>
                      <p className="truncate text-muted" title={d.to.join(", ")}>To: {d.to.join(", ")}</p>
                      {d.error && <p className="mt-0.5 text-danger">{d.error}</p>}
                    </li>
                  ))}
                </ul>
              )}
            </Card>
            {report.generated_at && (
              <p className="flex items-center gap-1.5 px-1 text-xs text-muted">
                <History aria-hidden className="h-3.5 w-3.5" /> Last generated {formatDateTime(report.generated_at, timezone)}
              </p>
            )}
          </aside>
        </div>
      )}

      <ConfirmDialog
        open={confirm === "send" || confirm === "resend"}
        title={confirm === "resend" ? "Send this EOD again?" : "Send EOD email?"}
        description={confirm === "resend" ? "This EOD was already sent. Recipients will receive another email." : undefined}
        confirmLabel={confirm === "resend" ? "Resend" : "Send email"}
        loading={busy === "send"}
        onCancel={() => setConfirm(null)}
        onConfirm={() => send(confirm === "resend")}
      >
        <dl className="space-y-1.5 text-[13px]">
          <div><dt className="inline font-medium">To: </dt><dd className="inline text-muted">{recipientLists.to.join(", ") || "—"}</dd></div>
          {recipientLists.cc.length > 0 && <div><dt className="inline font-medium">CC: </dt><dd className="inline text-muted">{recipientLists.cc.join(", ")}</dd></div>}
          {recipientLists.bcc.length > 0 && <div><dt className="inline font-medium">BCC: </dt><dd className="inline text-muted">{recipientLists.bcc.join(", ")}</dd></div>}
          <div><dt className="inline font-medium">Subject: </dt><dd className="inline text-muted">{subject}</dd></div>
        </dl>
        {contentDirty && <p className="mt-3 text-xs text-muted">Your unsaved edits will be saved first.</p>}
      </ConfirmDialog>

      <ConfirmDialog
        open={confirm === "regenerate"}
        title="Regenerate this EOD?"
        description="A new version is created from your current work log. Earlier versions, including any edits, stay in the history."
        confirmLabel="Regenerate"
        loading={busy === "generate"}
        onCancel={() => { setConfirm(null); setPendingStyle(null); }}
        onConfirm={() => regenerate(pendingStyle ?? options)}
      >
        <p className="mb-2 text-[13px] text-muted">
          Style: <span className="font-medium text-text">
            {EOD_LENGTH_OPTIONS.find((o) => o.value === (pendingStyle ?? options).length)?.label} · {EOD_TONE_OPTIONS.find((o) => o.value === (pendingStyle ?? options).tone)?.label}
          </span>
        </p>
        {dirty && (
          <p className="flex items-start gap-1.5 text-[13px] text-warning">
            <AlertTriangle aria-hidden className="mt-0.5 h-4 w-4 shrink-0" /> You have unsaved edits that will be discarded.
          </p>
        )}
      </ConfirmDialog>

      <Dialog open={Boolean(versionView)} onClose={() => setVersionView(null)} size="lg"
        title={versionView ? `Version ${versionView.version}` : ""}
        description={versionView ? `${SOURCE_LABEL[versionView.source]} · ${formatDateTime(versionView.created_at, timezone)}${versionView.sent_at ? ` · Sent ${formatDateTime(versionView.sent_at, timezone)}` : ""}` : undefined}
        footer={versionView && !versionView.is_current ? (
          <Button onClick={() => { setSubject(versionView.subject); setBody(versionView.body); setVersionView(null); toast("Loaded into the editor. Save to make it current.", "info"); }}>
            Load into editor
          </Button>
        ) : undefined}
      >
        {versionView && (
          <>
            <p className="mb-2 text-[13px] font-medium">{versionView.subject}</p>
            <pre className="whitespace-pre-wrap rounded-md border border-line bg-surface-2 p-3 font-mono text-[12.5px] leading-relaxed text-text">{versionView.body}</pre>
          </>
        )}
      </Dialog>
    </div>
  );
}
