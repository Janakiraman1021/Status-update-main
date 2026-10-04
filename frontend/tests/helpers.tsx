import { render } from "@testing-library/react";
import { vi } from "vitest";

import { ToastProvider } from "@/lib/toast";

/** A fetch mock that answers /api/* calls from a route table: { "POST /work-items": handler }. */
export function mockApi(routes: Record<string, (body: unknown, url: string) => { status?: number; body: unknown }>) {
  const calls: { method: string; url: string; body: unknown; headers: Record<string, string> }[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, url, body, headers: (init?.headers ?? {}) as Record<string, string> });
    const path = url.replace(/^\/api/, "").split("?")[0];
    const key = Object.keys(routes).find((k) => {
      const [m, pattern] = k.split(" ");
      return m === method && new RegExp(`^${pattern.replace(/:\w+/g, "[^/]+")}$`).test(path);
    });
    if (!key) return new Response(JSON.stringify({ success: false, error: { code: "NOT_FOUND", message: `No mock for ${method} ${path}` } }), { status: 404 });
    const result = routes[key](body, url);
    return new Response(JSON.stringify(result.body), { status: result.status ?? 200, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  return { calls, fetchMock };
}

export const ok = (data: unknown, meta?: unknown) => ({ body: { success: true, data, ...(meta ? { meta } : {}) } });
export const fail = (status: number, code: string, message: string) => ({ status, body: { success: false, error: { code, message } } });

export function renderWithProviders(ui: React.ReactElement) {
  return render(<ToastProvider>{ui}</ToastProvider>);
}
