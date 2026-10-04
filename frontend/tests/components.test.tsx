import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import Calendar from "@/components/Calendar";
import EodEditor from "@/components/EodEditor";
import EodStatus from "@/components/EodStatus";
import { EodHistoryTable } from "@/components/HistoryTables";
import { EntryComposer } from "@/components/WorkEntry";
import WorkLogForm from "@/components/WorkLogForm";
import { setCsrfToken } from "@/lib/api";
import type { CalendarDay } from "@/types/work";
import { fail, mockApi, ok, renderWithProviders } from "./helpers";

const push = vi.fn();
const replace = vi.fn();
let searchParams = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace }),
  usePathname: () => "/login",
  useSearchParams: () => searchParams,
}));
vi.mock("@/lib/auth", async () => {
  const actual = await vi.importActual<typeof import("@/lib/auth")>("@/lib/auth");
  return { ...actual, useAuth: () => mockAuth };
});
const mockAuth = {
  user: { id: "u1", name: "Janakiraman", email: "demo@example.com" },
  timezone: "Asia/Kolkata",
  status: "unauthenticated" as const,
  login: vi.fn(),
  logout: vi.fn(),
  refresh: vi.fn(),
  setUser: vi.fn(),
  setTimezone: vi.fn(),
};

describe("Login", () => {
  it("validates, reports invalid credentials and logs in", async () => {
    const { default: LoginForm } = await import("@/components/LoginForm");
    searchParams = new URLSearchParams("next=/calendar");
    const user = userEvent.setup();
    const { ApiError } = await import("@/lib/api");
    mockAuth.login.mockRejectedValueOnce(new ApiError("INVALID_CREDENTIALS", "Invalid email or password.", 401));
    mockAuth.login.mockResolvedValueOnce(undefined);
    renderWithProviders(<LoginForm />);

    await user.click(screen.getByRole("button", { name: "Log in" }));
    expect(screen.getByText("Enter your email address.")).toBeInTheDocument();
    expect(mockAuth.login).not.toHaveBeenCalled();

    await user.type(screen.getByLabelText("Email"), "demo@example.com");
    const password = screen.getByLabelText("Password");
    await user.type(password, "wrong");
    expect(password).toHaveAttribute("type", "password");
    await user.click(screen.getByRole("button", { name: "Show password" }));
    expect(password).toHaveAttribute("type", "text");

    await user.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByText("Invalid email or password.")).toBeInTheDocument();

    await user.click(screen.getByLabelText(/Remember this device/));
    await user.click(screen.getByRole("button", { name: "Log in" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/calendar"));
    expect(mockAuth.login).toHaveBeenLastCalledWith("demo@example.com", "wrong", true);
  });

  it("shows a network error message", async () => {
    const { default: LoginForm } = await import("@/components/LoginForm");
    const { ApiError } = await import("@/lib/api");
    mockAuth.login.mockRejectedValueOnce(new ApiError("NETWORK_ERROR", "x", 0));
    const user = userEvent.setup();
    renderWithProviders(<LoginForm />);
    await user.type(screen.getByLabelText("Email"), "demo@example.com");
    await user.type(screen.getByLabelText("Password"), "secret");
    await user.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByText(/Unable to reach WorkLog/)).toBeInTheDocument();
  });
});

describe("Calendar", () => {
  const days: CalendarDay[] = [
    { date: "2026-10-03", has_work: true, eod_status: "SENT", eod_generated: true, eod_sent: true, eod_failed: false, has_blocker: false },
    { date: "2026-10-02", has_work: true, eod_status: "GENERATED", eod_generated: true, eod_sent: false, eod_failed: false, has_blocker: true },
  ];

  it("labels days with their state and supports keyboard navigation", async () => {
    const onSelect = vi.fn();
    const onMonthChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <Calendar year={2026} month={10} today="2026-10-03" days={days} onSelect={onSelect} onMonthChange={onMonthChange} onToday={vi.fn()} />,
    );
    expect(screen.getByText("October 2026")).toBeInTheDocument();
    const today = screen.getByRole("button", { name: "03 October 2026, today, work logged, EOD sent" });
    expect(today).toHaveAttribute("aria-current", "date");
    expect(screen.getByRole("button", { name: "02 October 2026, work logged, EOD generated, blocker raised" })).toBeInTheDocument();

    today.focus();
    await user.keyboard("{ArrowLeft}");
    expect(screen.getByRole("button", { name: /^02 October 2026/ })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(onSelect).toHaveBeenCalledWith("2026-10-02");

    await user.click(screen.getByRole("button", { name: "Next month" }));
    expect(onMonthChange).toHaveBeenCalledWith(2026, 11);
    await user.click(screen.getByRole("button", { name: "Previous month" }));
    expect(onMonthChange).toHaveBeenCalledWith(2026, 9);
  });
});

describe("Work entry", () => {
  it("adds an entry with optional category and status", async () => {
    setCsrfToken("csrf-123");
    const { calls } = mockApi({
      "POST /work-items": (body) => ok({ id: "w1", ...(body as object), time_label: "10:00 AM", timestamp: "", time: "10:00", project_name: null, updated_at: "" }),
    });
    const onAdded = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<EntryComposer date="2026-10-03" projects={[]} onAdded={onAdded} />);

    await user.click(screen.getByRole("button", { name: "Add entry" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Describe the work before adding it.");

    await user.type(screen.getByLabelText("What did you do?"), "Removed statement selector");
    await user.selectOptions(screen.getByLabelText("Category"), "Enhancement");
    await user.selectOptions(screen.getByLabelText("Status"), "Completed");
    await user.click(screen.getByRole("button", { name: "Add entry" }));

    await waitFor(() => expect(onAdded).toHaveBeenCalled());
    expect(calls[0].body).toEqual({ work_date: "2026-10-03", description: "Removed statement selector", category: "Enhancement", status: "Completed" });
    expect(calls[0].headers["X-CSRF-Token"]).toBe("csrf-123");
    expect(screen.getByLabelText("What did you do?")).toHaveValue("");
  });
});

describe("Work log notes", () => {
  it("tracks unsaved changes, saves to the server and keeps a local draft", async () => {
    const { calls } = mockApi({
      "POST /work-logs": (body) => ok({ id: "l1", work_date: "2026-10-03", project_id: null, updated_at: "", ...(body as object) }),
    });
    const onSaved = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<WorkLogForm date="2026-10-03" userId="u1" log={null} onSaved={onSaved} onConvert={vi.fn()} />);

    expect(screen.getByRole("status")).toHaveTextContent("Saved");
    await user.type(screen.getByLabelText("What did you work on today?"), "removed selector");
    expect(screen.getByRole("status")).toHaveTextContent("Unsaved changes");
    expect(localStorage.getItem("worklog:draft:u1:2026-10-03")).toContain("removed selector");

    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Saved"));
    expect(calls.at(-1)?.body).toMatchObject({ work_date: "2026-10-03", quick_notes: "removed selector" });
    expect(onSaved).toHaveBeenCalled();
    expect(localStorage.getItem("worklog:draft:u1:2026-10-03")).toBeNull();
  });

  it("restores an unsaved draft after a refresh", () => {
    localStorage.setItem("worklog:draft:u1:2026-10-03", JSON.stringify({
      fields: { quick_notes: "typed before refresh", next_steps: "", learnings: "", meetings: "", metrics: "" },
      editedAt: new Date().toISOString(),
    }));
    renderWithProviders(<WorkLogForm date="2026-10-03" userId="u1" log={null} onSaved={vi.fn()} onConvert={vi.fn()} />);
    expect(screen.getByText("Unsaved draft restored")).toBeInTheDocument();
    expect(screen.getByLabelText("What did you work on today?")).toHaveValue("typed before refresh");
  });

  it("shows an error state when saving fails", async () => {
    mockApi({ "POST /work-logs": () => fail(503, "DATABASE_ERROR", "The database is temporarily unavailable.") });
    const user = userEvent.setup();
    renderWithProviders(<WorkLogForm date="2026-10-03" userId="u1" log={null} onSaved={vi.fn()} onConvert={vi.fn()} />);
    await user.type(screen.getByLabelText("What did you work on today?"), "x");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Not saved")).toBeInTheDocument();
    expect(await screen.findByText("The database is temporarily unavailable.")).toBeInTheDocument();
  });
});

describe("Convert notes to entries", () => {
  it("applies status and category to selected suggestions in bulk", async () => {
    const { default: CategorizeDialog } = await import("@/components/CategorizeDialog");
    const { calls } = mockApi({
      "POST /work-items/categorize": () => ok({ items: [
        { description: "Removed selector", category: null, status: null },
        { description: "Added dark mode", category: null, status: null },
        { description: "Looked into Azure", category: "Investigation", status: "In Progress" },
      ] }),
      "POST /work-items/bulk": () => ok([]),
    });
    const user = userEvent.setup();
    renderWithProviders(<CategorizeDialog notes="x" date="2026-10-03" onClose={vi.fn()} onCreated={vi.fn()} />);
    await screen.findByDisplayValue("Removed selector");

    // Leave the third suggestion out of the bulk change
    await user.click(screen.getByLabelText('Include "Looked into Azure"'));
    expect(screen.getByText("(2 of 3 selected)")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Set status for selected entries"), "Completed");
    await user.selectOptions(screen.getByLabelText("Set category for selected entries"), "Development");

    await user.click(screen.getByLabelText("Select all"));
    expect(screen.getByText("(3 of 3 selected)")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Add 3 entries" }));
    await waitFor(() => expect(calls.some((c) => c.url.includes("/work-items/bulk"))).toBe(true));
    const bulk = calls.find((c) => c.url.includes("/work-items/bulk"))!.body as { items: { status?: string; category?: string }[] };
    expect(bulk.items.map((i) => [i.category, i.status])).toEqual([
      ["Development", "Completed"], ["Development", "Completed"], ["Investigation", "In Progress"],
    ]);
  });
});

describe("EOD style buttons", () => {
  it("regenerates in the clicked length and tone with one click", async () => {
    const { EodStyleBar } = await import("@/components/EodOptionsPicker");
    const onSelect = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<EodStyleBar value={{ length: "short", tone: "professional" }} onSelect={onSelect} />);

    const length = screen.getByRole("group", { name: "Length" });
    expect(within(length).getAllByRole("button").map((b) => b.textContent)).toEqual(["Short", "Medium", "Long", "Detailed"]);
    expect(within(screen.getByRole("group", { name: "Tone" })).getAllByRole("button").map((b) => b.textContent)).toEqual(["Executive", "Professional", "Corporate"]);
    expect(within(length).getByRole("button", { name: "Short" })).toHaveAttribute("aria-pressed", "true");

    await user.click(within(length).getByRole("button", { name: "Long" }));
    expect(onSelect).toHaveBeenLastCalledWith({ length: "long", tone: "professional" });
    await user.click(within(screen.getByRole("group", { name: "Tone" })).getByRole("button", { name: "Executive" }));
    expect(onSelect).toHaveBeenLastCalledWith({ length: "short", tone: "executive" });

    onSelect.mockClear();
    await user.click(within(length).getByRole("button", { name: "Short" })); // already active: no regeneration
    expect(onSelect).not.toHaveBeenCalled();
  });
});

describe("EOD editor and status", () => {
  it("edits subject, body and recipients and shows the preview", async () => {
    const onBody = vi.fn();
    const onRecipients = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <EodEditor subject="EOD Status Update – 03 Oct 2026" body={"Hi,\n\nEXECUTIVE SNAPSHOT\nDone."} recipients={{ to: "", cc: "", bcc: "" }}
        onSubjectChange={vi.fn()} onBodyChange={onBody} onRecipientsChange={onRecipients}
        recipientErrors={{ to: "Add at least one recipient." }} previewUrl="/api/eod/1/preview" previewStale={false} />,
    );
    expect(screen.getByText("Add at least one recipient.")).toBeInTheDocument();
    await user.type(screen.getByLabelText("To"), "m");
    expect(onRecipients).toHaveBeenCalledWith({ to: "m", cc: "", bcc: "" });
    await user.type(screen.getByLabelText("Report body"), "!");
    expect(onBody).toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Add CC / BCC" }));
    expect(screen.getByLabelText(/^CC/)).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Email preview" }));
    expect(screen.getByTitle("Email preview")).toHaveAttribute("src", "/api/eod/1/preview");
  });

  it("conveys status with text, not colour alone", () => {
    renderWithProviders(<><EodStatus status="SENT" /><EodStatus status="FAILED" /><EodStatus status="NOT_GENERATED" /></>);
    expect(screen.getByText("Sent")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("Not generated")).toBeInTheDocument();
  });
});

describe("History", () => {
  it("renders paginated EOD history from the server", async () => {
    const { calls } = mockApi({
      "GET /history/eod": (_b, url) => {
        const page = Number(new URL(url, "http://x").searchParams.get("page"));
        return ok(
          [{ id: `e${page}`, work_date: page === 1 ? "2026-10-03" : "2026-09-01", status: page === 1 ? "SENT" : "GENERATED", subject: "s", project_label: "Dashboard",
            current_version: 2, sent_version: page === 1 ? 2 : null, generated_at: "2026-10-03T10:00:00Z", sent_at: page === 1 ? "2026-10-03T12:00:00Z" : null,
            generated_time_label: "3:30 PM", sent_time_label: page === 1 ? "5:30 PM" : null, last_error: null }],
          { page, limit: 1, total: 2, pages: 2 },
        );
      },
    });
    const user = userEvent.setup();
    renderWithProviders(<EodHistoryTable limit={1} />);
    const table = await screen.findByRole("table");
    expect(within(table).getByRole("link", { name: "03 Oct 2026" })).toHaveAttribute("href", "/eod/e1");
    expect(within(table).getByText("Sent", { selector: "td span" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(await screen.findByRole("link", { name: "01 Sep 2026" })).toBeInTheDocument();
    expect(calls.map((c) => new URL(c.url, "http://x").searchParams.get("page"))).toEqual(["1", "2"]);
  });
});
