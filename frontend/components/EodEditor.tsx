"use client";

import { Eye, Pencil } from "lucide-react";
import { useId, useState } from "react";

import { cn } from "@/lib/utils";
import { Field, Input, Textarea } from "./ui";

export interface RecipientsText {
  to: string;
  cc: string;
  bcc: string;
}

export interface EodEditorProps {
  subject: string;
  body: string;
  recipients: RecipientsText;
  onSubjectChange: (value: string) => void;
  onBodyChange: (value: string) => void;
  onRecipientsChange: (value: RecipientsText) => void;
  recipientErrors?: Partial<Record<keyof RecipientsText, string>>;
  previewUrl: string | null;
  previewStale: boolean;
  disabled?: boolean;
}

export default function EodEditor({
  subject, body, recipients, onSubjectChange, onBodyChange, onRecipientsChange, recipientErrors = {}, previewUrl, previewStale, disabled,
}: EodEditorProps) {
  const [tab, setTab] = useState<"edit" | "preview">("edit");
  const [showCopies, setShowCopies] = useState(Boolean(recipients.cc || recipients.bcc));
  const baseId = useId();

  return (
    <div className="space-y-4">
      <div className="grid gap-3">
        <Field label="To" htmlFor={`${baseId}-to`} error={recipientErrors.to} hint="Separate addresses with commas.">
          <Input id={`${baseId}-to`} value={recipients.to} disabled={disabled} onChange={(e) => onRecipientsChange({ ...recipients, to: e.target.value })}
            placeholder="manager@company.com" aria-invalid={Boolean(recipientErrors.to)} autoComplete="off" />
        </Field>
        {showCopies ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="CC" htmlFor={`${baseId}-cc`} error={recipientErrors.cc} optional>
              <Input id={`${baseId}-cc`} value={recipients.cc} disabled={disabled} onChange={(e) => onRecipientsChange({ ...recipients, cc: e.target.value })} aria-invalid={Boolean(recipientErrors.cc)} autoComplete="off" />
            </Field>
            <Field label="BCC" htmlFor={`${baseId}-bcc`} error={recipientErrors.bcc} optional>
              <Input id={`${baseId}-bcc`} value={recipients.bcc} disabled={disabled} onChange={(e) => onRecipientsChange({ ...recipients, bcc: e.target.value })} aria-invalid={Boolean(recipientErrors.bcc)} autoComplete="off" />
            </Field>
          </div>
        ) : (
          <button type="button" className="-mt-1 justify-self-start text-[13px] font-medium text-primary hover:underline" onClick={() => setShowCopies(true)}>
            Add CC / BCC
          </button>
        )}
        <Field label="Subject" htmlFor={`${baseId}-subject`}>
          <Input id={`${baseId}-subject`} value={subject} disabled={disabled} maxLength={300} onChange={(e) => onSubjectChange(e.target.value)} />
        </Field>
      </div>

      <div>
        <div role="tablist" aria-label="Report view" className="mb-2 inline-flex rounded-md border border-line bg-surface-2 p-0.5">
          {(["edit", "preview"] as const).map((t) => (
            <button
              key={t}
              role="tab"
              type="button"
              id={`${baseId}-tab-${t}`}
              aria-selected={tab === t}
              aria-controls={`${baseId}-panel-${t}`}
              onClick={() => setTab(t)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded px-3 py-1 text-[13px] font-medium",
                tab === t ? "bg-surface text-text shadow-sm" : "text-muted hover:text-text",
              )}
            >
              {t === "edit" ? <Pencil aria-hidden className="h-3.5 w-3.5" /> : <Eye aria-hidden className="h-3.5 w-3.5" />}
              {t === "edit" ? "Edit" : "Email preview"}
            </button>
          ))}
        </div>

        {tab === "edit" ? (
          <div role="tabpanel" id={`${baseId}-panel-edit`} aria-labelledby={`${baseId}-tab-edit`}>
            <label htmlFor={`${baseId}-body`} className="sr-only">Report body</label>
            <Textarea
              id={`${baseId}-body`}
              value={body}
              disabled={disabled}
              onChange={(e) => onBodyChange(e.target.value)}
              rows={22}
              spellCheck
              className="min-h-[28rem] font-mono text-[13px] leading-relaxed"
            />
            <p className="mt-1 text-xs text-muted">
              Formatting: UPPER-CASE lines become section headings, lines starting with &ldquo;- &rdquo; become bullets, and a line ending in &ldquo;:&rdquo; before bullets becomes a sub-heading.
            </p>
          </div>
        ) : (
          <div role="tabpanel" id={`${baseId}-panel-preview`} aria-labelledby={`${baseId}-tab-preview`} className="space-y-2">
            {previewStale && <p className="text-xs text-warning">You have unsaved edits. Save to refresh the preview.</p>}
            {previewUrl ? (
              <iframe
                title="Email preview"
                src={previewUrl}
                sandbox=""
                className="h-[34rem] w-full rounded-md border border-line bg-white"
              />
            ) : (
              <p className="text-[13px] text-muted">Save the report to see the email preview.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
