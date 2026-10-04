"use client";

import { Loader2 } from "lucide-react";
import { useId } from "react";

import { cn } from "@/lib/utils";
import { EOD_LENGTH_OPTIONS, EOD_TONE_OPTIONS, type EodOptions } from "@/types/eod";

function Segmented<T extends string>({ label, value, options, onChange, disabled }: {
  label: string; value: T; options: { value: T; label: string; hint: string }[]; onChange: (v: T) => void; disabled?: boolean;
}) {
  const id = useId();
  const current = options.find((o) => o.value === value);
  return (
    <fieldset className="min-w-0" disabled={disabled}>
      <legend id={id} className="mb-1 text-xs font-medium text-muted">{label}</legend>
      <div role="radiogroup" aria-labelledby={id} className="inline-flex flex-wrap rounded-md border border-line bg-surface-2 p-0.5">
        {options.map((option) => (
          <label
            key={option.value}
            title={option.hint}
            className={cn(
              "cursor-pointer rounded px-3 py-1 text-[13px] font-medium transition-colors has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-[var(--focus)]",
              value === option.value ? "bg-surface text-primary shadow-sm" : "text-muted hover:text-text",
              disabled && "cursor-not-allowed opacity-60",
            )}
          >
            <input type="radio" className="sr-only" name={id} value={option.value} checked={value === option.value}
              onChange={() => onChange(option.value)} />
            {option.label}
          </label>
        ))}
      </div>
      {current && <p className="mt-1 text-xs text-subtle">{current.hint}</p>}
    </fieldset>
  );
}

function ButtonGroup<T extends string>({ label, value, options, onSelect, disabled, pending }: {
  label: string; value: T; options: { value: T; label: string; hint: string }[]; onSelect: (v: T) => void;
  disabled?: boolean; pending?: T | null;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs font-semibold uppercase tracking-wide text-subtle">{label}</span>
      <div role="group" aria-label={label} className="inline-flex flex-wrap gap-1">
        {options.map((option) => {
          const active = value === option.value;
          return (
            <button
              key={option.value}
              type="button"
              title={option.hint}
              aria-pressed={active}
              disabled={disabled}
              onClick={() => !active && onSelect(option.value)}
              className={cn(
                "inline-flex h-8 items-center gap-1.5 rounded-md border px-3 text-[13px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60",
                active
                  ? "border-primary bg-primary text-primary-text shadow-sm"
                  : "border-line-strong bg-surface text-text hover:border-primary hover:text-primary",
              )}
            >
              {pending === option.value && <Loader2 aria-hidden className="h-3.5 w-3.5 animate-spin" />}
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Length and tone as one-click buttons. Picking a different option regenerates the report in that style.
 */
export function EodStyleBar({ value, onSelect, disabled, pending, localProvider }: {
  value: EodOptions; onSelect: (value: EodOptions) => void; disabled?: boolean; pending?: Partial<EodOptions> | null; localProvider?: boolean;
}) {
  return (
    <div className="rounded-lg border border-line bg-surface px-4 py-3">
      <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
        <ButtonGroup label="Length" value={value.length} options={EOD_LENGTH_OPTIONS} disabled={disabled}
          pending={pending?.length ?? null} onSelect={(length) => onSelect({ ...value, length })} />
        <ButtonGroup label="Tone" value={value.tone} options={EOD_TONE_OPTIONS} disabled={disabled}
          pending={pending?.tone ?? null} onSelect={(tone) => onSelect({ ...value, tone })} />
      </div>
      <p className="mt-2 text-xs text-muted">
        Click an option to regenerate the report in that style. Every version is kept in the history.
        {localProvider && value.tone === "corporate" &&
          " Corporate adds jargon framing (circling back, level-set, move the needle, north star). Fact-based terms such as go-live, T-1 or maker-checker need the Groq AI provider, which uses them only when your notes support them."}
        {localProvider && value.tone === "executive" &&
          " The built-in writer uses your own wording with formal verbs; set AI_PROVIDER=groq (Qwen) for full executive rewriting."}
      </p>
    </div>
  );
}

export default function EodOptionsPicker({ value, onChange, disabled, localProvider }: {
  value: EodOptions; onChange: (value: EodOptions) => void; disabled?: boolean; localProvider?: boolean;
}) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-x-6 gap-y-3">
        <Segmented label="Length" value={value.length} options={EOD_LENGTH_OPTIONS} disabled={disabled}
          onChange={(length) => onChange({ ...value, length })} />
        <Segmented label="Tone" value={value.tone} options={EOD_TONE_OPTIONS} disabled={disabled}
          onChange={(tone) => onChange({ ...value, tone })} />
      </div>
      {localProvider && value.tone !== "professional" && (
        <p className="text-xs text-warning">
          The built-in writer keeps your own wording and adds {value.tone === "corporate" ? "jargon framing" : "formal verbs"}.
          Full rewriting needs the Groq AI provider (AI_PROVIDER=groq and AI_API_KEY in backend/.env).
        </p>
      )}
    </div>
  );
}
