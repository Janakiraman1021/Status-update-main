"use client";

import { Mail, Monitor, Moon, Save, Sun } from "lucide-react";
import { useMemo, useState } from "react";

import EodOptionsPicker from "@/components/EodOptionsPicker";
import ErrorState from "@/components/ErrorState";
import LoadingState from "@/components/LoadingState";
import ProjectSelector from "@/components/ProjectSelector";
import { Alert, Button, Card, CardHeader, Field, Input, PageHeader, Select, Toggle } from "@/components/ui";
import { ApiError, api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi, useUnsavedChangesWarning } from "@/lib/hooks";
import { useTheme } from "@/lib/theme";
import { useToast } from "@/lib/toast";
import { cn, invalidEmails, parseEmails } from "@/lib/utils";
import type { Theme } from "@/types/auth";
import type { EodLength, EodTone, Recipients } from "@/types/eod";
import type { Project } from "@/types/project";

interface SettingsPayload {
  profile: { id: string; name: string; email: string };
  preferences: {
    timezone: string; default_project_id: string | null; eod_time: string; auto_eod_enabled: boolean; reminder_enabled: boolean;
    reminder_minutes_before: number; recipients: Recipients; eod_length: EodLength; eod_tone: EodTone; theme: Theme;
    signature_name: string | null;
  };
  email: { provider: string; sender: string; configured: boolean; host?: string; port?: number; outbox?: string };
  ai: { provider: string; model: string };
  scheduler: { enabled: boolean; interval_seconds: number };
}

interface FormState {
  name: string;
  signature_name: string;
  timezone: string;
  default_project_id: string | null;
  eod_time: string;
  auto_eod_enabled: boolean;
  reminder_enabled: boolean;
  reminder_minutes_before: number;
  to: string;
  cc: string;
  bcc: string;
  eod_length: EodLength;
  eod_tone: EodTone;
}

function toForm(s: SettingsPayload): FormState {
  const p = s.preferences;
  return {
    name: s.profile.name, signature_name: p.signature_name ?? "", timezone: p.timezone, default_project_id: p.default_project_id,
    eod_time: p.eod_time, auto_eod_enabled: p.auto_eod_enabled, reminder_enabled: p.reminder_enabled,
    reminder_minutes_before: p.reminder_minutes_before, to: p.recipients.to.join(", "), cc: p.recipients.cc.join(", "),
    bcc: p.recipients.bcc.join(", "), eod_length: p.eod_length, eod_tone: p.eod_tone,
  };
}

function Section({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader title={title} description={description} />
      <div className="space-y-4 p-4">{children}</div>
    </Card>
  );
}

const THEMES: { value: Theme; label: string; Icon: typeof Sun }[] = [
  { value: "light", label: "Light", Icon: Sun },
  { value: "dark", label: "Dark", Icon: Moon },
  { value: "system", label: "System", Icon: Monitor },
];

export default function SettingsPage() {
  const { data, error, loading, reload, setData } = useApi<SettingsPayload>("/settings");
  if (loading && !data) return <LoadingState label="Loading settings…" />;
  if (error || !data) return <ErrorState message={error?.message} onRetry={reload} />;
  // Re-key on the saved values so the form resets to exactly what the server stored after each save.
  return <SettingsForm key={JSON.stringify(toForm(data))} data={data} setData={setData} />;
}

function SettingsForm({ data, setData }: { data: SettingsPayload; setData: (s: SettingsPayload) => void }) {
  const toast = useToast();
  const { setUser, setTimezone, user } = useAuth();
  const { theme, setTheme } = useTheme();
  const { data: projects } = useApi<Project[]>("/projects?include_archived=true");
  const { data: timezones } = useApi<string[]>("/settings/timezones");
  const [form, setForm] = useState<FormState>(() => toForm(data));
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const dirty = useMemo(() => JSON.stringify(toForm(data)) !== JSON.stringify(form), [data, form]);
  useUnsavedChangesWarning(dirty);

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => setForm((f) => ({ ...f, [key]: value }));

  async function save() {
    const errors: Record<string, string> = {};
    if (!form.name.trim()) errors.name = "Name is required.";
    (["to", "cc", "bcc"] as const).forEach((k) => {
      const bad = invalidEmails(parseEmails(form[k]));
      if (bad.length) errors[k] = `Invalid address: ${bad.join(", ")}`;
    });
    setFieldErrors(errors);
    if (Object.keys(errors).length) return;

    setSaving(true);
    try {
      const result = await api.put<SettingsPayload>("/settings", {
        name: form.name.trim(),
        signature_name: form.signature_name.trim() || null,
        timezone: form.timezone,
        default_project_id: form.default_project_id,
        eod_time: form.eod_time,
        auto_eod_enabled: form.auto_eod_enabled,
        reminder_enabled: form.reminder_enabled,
        reminder_minutes_before: Number(form.reminder_minutes_before),
        recipients: { to: parseEmails(form.to), cc: parseEmails(form.cc), bcc: parseEmails(form.bcc) },
        eod_length: form.eod_length,
        eod_tone: form.eod_tone,
      });
      setData(result);
      if (user) setUser({ ...user, name: result.profile.name });
      setTimezone(result.preferences.timezone);
      toast("Settings saved");
    } catch (err) {
      if (err instanceof ApiError) setFieldErrors(err.fieldErrors);
      toast(errorMessage(err, "Unable to save settings."), "error");
    } finally {
      setSaving(false);
    }
  }

  async function sendTestEmail() {
    setTesting(true);
    try {
      const result = await api.post<{ to: string; provider: string }>("/email/test", {});
      toast(result.provider === "console" ? `Test email written to the outbox (console provider) for ${result.to}` : `Test email sent to ${result.to}`);
    } catch (err) {
      toast(errorMessage(err, "Test email failed."), "error");
    } finally {
      setTesting(false);
    }
  }

  const email = data.email;

  return (
    <div className="pb-20">
      <PageHeader title="Settings" description="Profile, EOD automation, email and appearance." />
      <div className="grid gap-5 lg:grid-cols-2">
        <Section title="Profile">
          <Field label="Name" htmlFor="s-name" error={fieldErrors.name}>
            <Input id="s-name" value={form.name} onChange={(e) => set("name", e.target.value)} aria-invalid={Boolean(fieldErrors.name)} />
          </Field>
          <Field label="Email" htmlFor="s-email" hint="Contact your administrator to change your sign-in email.">
            <Input id="s-email" value={data.profile.email} disabled />
          </Field>
          <Field label="Signature name" htmlFor="s-sig" optional hint="Used after “Thanks and regards,” in EOD emails. Defaults to your name.">
            <Input id="s-sig" value={form.signature_name} onChange={(e) => set("signature_name", e.target.value)} placeholder={form.name} />
          </Field>
        </Section>

        <Section title="Work">
          <Field label="Default project" htmlFor="s-project" hint="Pre-selected on new days.">
            <ProjectSelector id="s-project" projects={projects ?? []} value={form.default_project_id} onChange={(v) => set("default_project_id", v)} />
          </Field>
          <Field label="Timezone" htmlFor="s-tz" hint="Work dates, entry times and EOD scheduling use this timezone.">
            <Select id="s-tz" value={form.timezone} onChange={(e) => set("timezone", e.target.value)}>
              {(timezones ?? [form.timezone]).map((tz) => <option key={tz} value={tz}>{tz}</option>)}
            </Select>
          </Field>
        </Section>

        <Section title="EOD" description="When and to whom your EOD goes out.">
          <Field label="EOD time" htmlFor="s-eod-time" hint={`Local time in ${form.timezone}.`}>
            <Input id="s-eod-time" type="time" value={form.eod_time} onChange={(e) => set("eod_time", e.target.value)} className="w-36" />
          </Field>
          <Toggle
            label="Automatic EOD"
            description="At EOD time, generate (if needed) and send today's report. Skipped if nothing was logged or it was already sent."
            checked={form.auto_eod_enabled}
            onChange={(v) => set("auto_eod_enabled", v)}
          />
          {!data.scheduler.enabled && form.auto_eod_enabled && (
            <Alert tone="warning">The scheduler is disabled on the server (SCHEDULER_ENABLED=false), so automatic EODs will not run.</Alert>
          )}
          <Toggle
            label="Reminder"
            description="Email me if nothing is logged shortly before EOD time."
            checked={form.reminder_enabled}
            onChange={(v) => set("reminder_enabled", v)}
          />
          {form.reminder_enabled && (
            <Field label="Remind me this many minutes before" htmlFor="s-remind">
              <Input id="s-remind" type="number" min={5} max={240} value={form.reminder_minutes_before}
                onChange={(e) => set("reminder_minutes_before", Number(e.target.value))} className="w-28" />
            </Field>
          )}
          <Field label="Default recipients (To)" htmlFor="s-to" error={fieldErrors.to} hint="Comma-separated. If empty, EODs go to your own address.">
            <Input id="s-to" value={form.to} onChange={(e) => set("to", e.target.value)} placeholder="manager@company.com" aria-invalid={Boolean(fieldErrors.to)} />
          </Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="CC" htmlFor="s-cc" error={fieldErrors.cc} optional>
              <Input id="s-cc" value={form.cc} onChange={(e) => set("cc", e.target.value)} aria-invalid={Boolean(fieldErrors.cc)} />
            </Field>
            <Field label="BCC" htmlFor="s-bcc" error={fieldErrors.bcc} optional>
              <Input id="s-bcc" value={form.bcc} onChange={(e) => set("bcc", e.target.value)} aria-invalid={Boolean(fieldErrors.bcc)} />
            </Field>
          </div>
        </Section>

        <div className="space-y-5">
          <Section title="Email" description="Delivery is configured on the server; credentials are never sent to the browser.">
            <dl className="grid grid-cols-[8rem_1fr] gap-y-1.5 text-[13px]">
              <dt className="text-muted">Provider</dt><dd className="font-medium uppercase">{email.provider}</dd>
              <dt className="text-muted">Status</dt>
              <dd className={email.configured ? "font-medium text-success" : "font-medium text-danger"}>{email.configured ? "Configured" : "Not configured"}</dd>
              <dt className="text-muted">Sender</dt><dd>{email.sender || "—"}</dd>
              {email.host && (<><dt className="text-muted">SMTP server</dt><dd>{email.host}:{email.port}</dd></>)}
              {email.outbox && (<><dt className="text-muted">Outbox folder</dt><dd className="break-all">{email.outbox}</dd></>)}
            </dl>
            {email.provider === "console" && (
              <Alert tone="info">Development mode: emails are written as .eml files to the outbox folder instead of being delivered. Set EMAIL_PROVIDER=smtp to send real email.</Alert>
            )}
            <Button onClick={sendTestEmail} loading={testing} icon={<Mail aria-hidden className="h-4 w-4" />}>Send test email to me</Button>
          </Section>

          <Section title="AI">
            <dl className="grid grid-cols-[8rem_1fr] gap-y-1.5 text-[13px]">
              <dt className="text-muted">Provider</dt><dd className="font-medium">{data.ai.provider}</dd>
              <dt className="text-muted">Model</dt><dd>{data.ai.model}</dd>
            </dl>
            <div>
              <p className="mb-2 text-[13px] font-medium">Default EOD options</p>
              <EodOptionsPicker
                value={{ length: form.eod_length, tone: form.eod_tone }}
                onChange={(o) => setForm((f) => ({ ...f, eod_length: o.length, eod_tone: o.tone }))}
                localProvider={data.ai.provider === "local"}
              />
              <p className="mt-2 text-xs text-muted">Pre-selected on the EOD page and used by automatic EODs. Reports never include anything you did not record, and contain no em or en dashes.</p>
            </div>
          </Section>

          <Section title="Appearance">
            <fieldset>
              <legend className="mb-2 text-[13px] font-medium">Theme</legend>
              <div className="grid grid-cols-3 gap-2">
                {THEMES.map(({ value, label, Icon }) => (
                  <label key={value} className={cn(
                    "flex cursor-pointer items-center justify-center gap-2 rounded-md border px-3 py-2.5 text-[13px] font-medium has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-[var(--focus)]",
                    theme === value ? "border-primary bg-primary-soft text-primary" : "border-line-strong text-muted hover:bg-surface-hover",
                  )}>
                    <input type="radio" name="theme" value={value} checked={theme === value} onChange={() => setTheme(value)} className="sr-only" />
                    <Icon aria-hidden className="h-4 w-4" /> {label}
                  </label>
                ))}
              </div>
              <p className="mt-2 text-xs text-muted">Applied immediately and saved to your profile.</p>
            </fieldset>
          </Section>
        </div>
      </div>

      <div className={cn("fixed inset-x-0 bottom-0 z-20 border-t border-line bg-surface/95 px-4 py-3 backdrop-blur transition-transform lg:pl-60", dirty ? "translate-y-0" : "translate-y-full")}
        aria-hidden={!dirty}>
        <div className="mx-auto flex max-w-7xl items-center justify-end gap-2">
          <span className="mr-auto text-[13px] text-warning">You have unsaved changes</span>
          <Button onClick={() => setForm(toForm(data))} disabled={saving} tabIndex={dirty ? 0 : -1}>Discard</Button>
          <Button variant="primary" onClick={save} loading={saving} icon={<Save aria-hidden className="h-4 w-4" />} tabIndex={dirty ? 0 : -1}>Save changes</Button>
        </div>
      </div>
    </div>
  );
}
