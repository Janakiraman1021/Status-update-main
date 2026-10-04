"use client";

import { Loader2, X } from "lucide-react";
import { forwardRef, useEffect, useId, useRef } from "react";

import { cn } from "@/lib/utils";

// ---- Button ----------------------------------------------------------------

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "link";
type ButtonSize = "sm" | "md";

const variants: Record<ButtonVariant, string> = {
  primary: "bg-primary text-primary-text hover:bg-primary-hover border border-transparent shadow-card",
  secondary: "bg-surface text-text border border-line-strong hover:border-primary/40 hover:bg-surface-hover shadow-card",
  ghost: "bg-transparent text-muted hover:bg-surface-hover hover:text-text border border-transparent",
  danger: "bg-danger text-white hover:opacity-90 border border-transparent shadow-sm",
  link: "bg-transparent text-primary hover:underline border border-transparent px-0",
};

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: React.ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", loading, icon, className, children, disabled, type = "button", ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-lg font-semibold transition-all active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-55 disabled:active:scale-100",
        size === "sm" ? "h-8 px-3 text-[13px]" : "h-10 px-4 text-sm",
        variants[variant],
        className,
      )}
      {...props}
    >
      {loading ? <Loader2 aria-hidden className="h-4 w-4 animate-spin" /> : icon}
      {children}
    </button>
  );
});

// ---- Card ------------------------------------------------------------------

export function Card({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("rounded-2xl border border-line bg-surface shadow-card", className)} {...props}>
      {children}
    </div>
  );
}

export function CardHeader({ title, description, actions, id }: { title: React.ReactNode; description?: React.ReactNode; actions?: React.ReactNode; id?: string }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4">
      <div className="min-w-0">
        <h2 id={id} className="text-[15px] font-bold text-text">{title}</h2>
        {description && <p className="mt-0.5 text-[13px] text-muted">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

// ---- Form fields -----------------------------------------------------------

const fieldBase =
  "w-full rounded-lg border border-line-strong bg-surface px-3.5 text-sm text-text placeholder:text-subtle shadow-[inset_0_1px_0_rgba(0,0,0,0.02)] transition-colors focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/25 disabled:cursor-not-allowed disabled:bg-surface-2 disabled:text-muted aria-[invalid=true]:border-danger";

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(function Input({ className, ...props }, ref) {
  return <input ref={ref} className={cn(fieldBase, "h-10", className)} {...props} />;
});

export const Textarea = forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea({ className, ...props }, ref) {
  return <textarea ref={ref} className={cn(fieldBase, "py-2 leading-relaxed", className)} {...props} />;
});

export const Select = forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(function Select({ className, children, ...props }, ref) {
  return (
    <select ref={ref} className={cn(fieldBase, "h-10 pr-8", className)} {...props}>
      {children}
    </select>
  );
});

export function Field({ label, hint, error, children, className, htmlFor, optional }: {
  label: string; hint?: React.ReactNode; error?: string; children: React.ReactNode; className?: string; htmlFor?: string; optional?: boolean;
}) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <label htmlFor={htmlFor} className="block text-[13px] font-medium text-text">
        {label}
        {optional && <span className="ml-1 font-normal text-subtle">(optional)</span>}
      </label>
      {children}
      {error ? (
        <p role="alert" className="text-[12.5px] text-danger">{error}</p>
      ) : hint ? (
        <p className="text-[12.5px] text-muted">{hint}</p>
      ) : null}
    </div>
  );
}

export function Toggle({ checked, onChange, label, description, disabled }: {
  checked: boolean; onChange: (value: boolean) => void; label: string; description?: string; disabled?: boolean;
}) {
  const id = useId();
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <label htmlFor={id} className="text-sm font-medium text-text">{label}</label>
        {description && <p id={`${id}-desc`} className="text-[13px] text-muted">{description}</p>}
      </div>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        aria-describedby={description ? `${id}-desc` : undefined}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative mt-0.5 inline-flex h-5 w-9 shrink-0 items-center rounded-full border transition-colors disabled:opacity-50",
          checked ? "border-primary bg-primary" : "border-line-strong bg-surface-hover",
        )}
      >
        <span className={cn("inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform", checked ? "translate-x-[18px]" : "translate-x-[3px]")} />
        <span className="sr-only">{checked ? "On" : "Off"}</span>
      </button>
    </div>
  );
}

// ---- Alert -----------------------------------------------------------------

export function Alert({ tone = "info", title, children, action, className }: {
  tone?: "info" | "success" | "warning" | "danger"; title?: string; children?: React.ReactNode; action?: React.ReactNode; className?: string;
}) {
  const tones = {
    info: "border-info/30 bg-info-soft",
    success: "border-success/30 bg-success-soft",
    warning: "border-warning/35 bg-warning-soft",
    danger: "border-danger/35 bg-danger-soft",
  };
  const titleTone = { info: "text-info", success: "text-success", warning: "text-warning", danger: "text-danger" };
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={cn("flex flex-wrap items-start justify-between gap-3 rounded-xl border px-4 py-3 text-[13px]", tones[tone], className)}>
      <div className="min-w-0 flex-1">
        {title && <p className={cn("font-semibold", titleTone[tone])}>{title}</p>}
        {children && <div className="mt-0.5 text-text">{children}</div>}
      </div>
      {action}
    </div>
  );
}

// ---- Dialog ----------------------------------------------------------------

export function Dialog({ open, onClose, title, description, children, footer, size = "md" }: {
  open: boolean; onClose: () => void; title: string; description?: React.ReactNode; children?: React.ReactNode;
  footer?: React.ReactNode; size?: "md" | "lg";
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onClose={onClose}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
      className={cn(
        "m-auto w-[calc(100%-2rem)] rounded-2xl border border-line bg-surface p-0 text-text shadow-2xl backdrop:bg-black/50 backdrop:backdrop-blur-sm",
        size === "lg" ? "max-w-3xl" : "max-w-lg",
      )}
    >
      {open && (
        <div className="flex max-h-[85vh] flex-col">
          <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
            <div>
              <h2 id={titleId} className="text-base font-semibold">{title}</h2>
              {description && <div className="mt-1 text-[13px] text-muted">{description}</div>}
            </div>
            <button type="button" onClick={onClose} className="rounded p-1 text-subtle hover:bg-surface-hover hover:text-text" aria-label="Close dialog">
              <X className="h-4 w-4" />
            </button>
          </div>
          {children && <div className="overflow-y-auto px-5 py-4">{children}</div>}
          {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-line px-5 py-3">{footer}</div>}
        </div>
      )}
    </dialog>
  );
}

export function ConfirmDialog({ open, onCancel, onConfirm, title, description, confirmLabel = "Confirm", tone = "primary", loading, children }: {
  open: boolean; onCancel: () => void; onConfirm: () => void; title: string; description?: React.ReactNode; confirmLabel?: string;
  tone?: "primary" | "danger"; loading?: boolean; children?: React.ReactNode;
}) {
  return (
    <Dialog
      open={open}
      onClose={onCancel}
      title={title}
      description={description}
      footer={
        <>
          <Button onClick={onCancel} disabled={loading}>Cancel</Button>
          <Button variant={tone === "danger" ? "danger" : "primary"} onClick={onConfirm} loading={loading}>{confirmLabel}</Button>
        </>
      }
    >
      {children}
    </Dialog>
  );
}

// ---- Misc ------------------------------------------------------------------

export function Kbd({ children }: { children: React.ReactNode }) {
  return <kbd className="rounded border border-line-strong bg-surface-2 px-1 font-mono text-[11px] text-muted">{children}</kbd>;
}

export function PageHeader({ title, description, actions }: { title: React.ReactNode; description?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-2xl font-extrabold tracking-tight text-text sm:text-[28px]">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
