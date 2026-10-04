"use client";

import { Eye, EyeOff, LogIn } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Alert, Button, Field, Input } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { EMAIL_RE } from "@/lib/utils";

function safeNext(value: string | null): string {
  // Only allow same-site relative paths to avoid open redirects.
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/dashboard";
}

export default function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { login, status } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({});
  const next = safeNext(params.get("next"));

  useEffect(() => {
    if (status === "authenticated") router.replace(next);
  }, [status, router, next]);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    const errors: typeof fieldErrors = {};
    if (!email.trim()) errors.email = "Enter your email address.";
    else if (!EMAIL_RE.test(email.trim())) errors.email = "Enter a valid email address.";
    if (!password) errors.password = "Enter your password.";
    setFieldErrors(errors);
    setError(null);
    if (Object.keys(errors).length) return;

    setSubmitting(true);
    try {
      await login(email.trim(), password, remember);
      router.replace(next);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.code === "NETWORK_ERROR" ? "Unable to reach WorkLog. Check your connection and that the server is running." : err.message);
      } else {
        setError("Something went wrong. Please try again.");
      }
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4" aria-describedby={error ? "login-error" : undefined}>
      {params.get("expired") && !error && <Alert tone="info">Your session has ended. Please sign in again.</Alert>}
      {error && (
        <div id="login-error">
          <Alert tone="danger">{error}</Alert>
        </div>
      )}
      <Field label="Email" htmlFor="email" error={fieldErrors.email}>
        <Input
          id="email"
          type="email"
          autoComplete="username"
          inputMode="email"
          autoFocus
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          aria-invalid={Boolean(fieldErrors.email)}
          placeholder="you@company.com"
        />
      </Field>
      <Field label="Password" htmlFor="password" error={fieldErrors.password}>
        <div className="relative">
          <Input
            id="password"
            type={showPassword ? "text" : "password"}
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            aria-invalid={Boolean(fieldErrors.password)}
            className="pr-10"
          />
          <button
            type="button"
            onClick={() => setShowPassword((v) => !v)}
            className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-subtle hover:text-text"
            aria-label={showPassword ? "Hide password" : "Show password"}
            aria-pressed={showPassword}
          >
            {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
      </Field>
      <label className="flex items-center gap-2 text-[13px] text-muted">
        <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="h-4 w-4 rounded border-line-strong accent-[var(--primary)]" />
        Remember this device for 30 days
      </label>
      <Button type="submit" variant="primary" className="w-full" loading={submitting} icon={<LogIn aria-hidden className="h-4 w-4" />}>
        {submitting ? "Signing in…" : "Log in"}
      </Button>
    </form>
  );
}
