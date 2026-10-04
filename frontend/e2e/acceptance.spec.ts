import { expect, test, type Page } from "@playwright/test";

/**
 * Final acceptance scenario (spec section 60), driven through the real UI and API:
 * login → calendar → select date → enter work → save → generate EOD → edit → send → history → calendar.
 */

const EMAIL = process.env.APP_USER_EMAIL || "demo@example.com";
const PASSWORD = process.env.APP_USER_PASSWORD || process.env.DEMO_PASSWORD || "WorkLog@2026";
const NOTES = [
  "Worked on Statements Dashboard.",
  "Removed statement selector.",
  "Added dark mode.",
  "Implemented date validation.",
  "Created access governance schema.",
  "94 tests passed.",
  "Need DBA approval.",
].join("\n");

function todayInKolkata(): { iso: string; day: number; label: string } {
  const iso = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
  const [y, m, d] = iso.split("-").map(Number);
  const months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  return { iso, day: d, label: `${String(d).padStart(2, "0")} ${months[m - 1]} ${y}` };
}

async function shot(page: Page, name: string) {
  await page.screenshot({ path: `e2e-results/${name}.png`, fullPage: true });
}

test("WorkLog acceptance workflow", async ({ page }) => {
  const today = todayInKolkata();

  // 1. Open WorkLog → redirected to login
  await page.goto("/");
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByRole("heading", { name: "Sign in to WorkLog" })).toBeVisible();
  await shot(page, "01-login");

  // Validation and invalid credentials
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByText("Enter your email address.")).toBeVisible();
  await page.getByLabel("Email").fill(EMAIL);
  await page.getByLabel("Password", { exact: true }).fill("wrong-password");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByText("Invalid email or password.")).toBeVisible();

  // 2. Log in
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Log in" }).click();

  // 3. Dashboard
  await expect(page).toHaveURL(/\/dashboard/);
  await expect(page.getByRole("heading", { name: /Good (morning|afternoon|evening), Janakiraman/ })).toBeVisible();
  await expect(page.getByText(today.label).first()).toBeVisible();
  await shot(page, "02-dashboard");

  // 4. Calendar → select today's date
  await page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "Calendar" }).click();
  await expect(page).toHaveURL(/\/calendar/);
  const dayButton = page.getByRole("button", { name: new RegExp(`^${today.label}, today`) });
  await expect(dayButton).toBeVisible();
  await shot(page, "03-calendar");
  await dayButton.click();

  // 5. Work log for the date
  await expect(page).toHaveURL(new RegExp(`/work-log/${today.iso}$`));
  await expect(page.getByRole("heading", { name: today.label })).toBeVisible();
  const notes = page.getByLabel("What did you work on today?");
  await notes.fill(NOTES);
  await expect(page.getByRole("status").filter({ hasText: "Unsaved changes" })).toBeVisible();

  // 6. Save → stored in MongoDB
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: /^Saved$/ })).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("What did you work on today?")).toHaveValue(NOTES);
  await shot(page, "04-work-log");

  // 7. Generate EOD
  await page.getByRole("button", { name: "Generate EOD" }).click();
  await expect(page).toHaveURL(new RegExp(`/eod/${today.iso}$`), { timeout: 60_000 });
  await expect(page.getByText(/^EOD status:\s*Generated$/).first()).toBeVisible();
  const body = page.getByLabel("Report body");
  await expect(body).toHaveValue(/EXECUTIVE SNAPSHOT/);
  await expect(body).toHaveValue(/- Removed statement selector\./);
  await expect(body).toHaveValue(/- 94 tests passed\./);
  await expect(body).toHaveValue(/- Need DBA approval\./);
  await expect(page.getByLabel("Subject")).toHaveValue(`EOD Status Update | ${today.label.replace(/ (\w{3})\w* /, " $1 ")} | Samunnati Statements Dashboard`);
  await expect(page.getByLabel("Report body")).not.toHaveValue(/[–—]/);
  await shot(page, "05-eod-generated");

  // 8. Edit one sentence and save (creates version 2)
  const original = await body.inputValue();
  await body.fill(original.replace("Added dark mode.", "Added light and dark mode support."));
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("Version 2", { exact: true })).toBeVisible();

  // Preview renders the email HTML
  await page.getByRole("tab", { name: "Email preview" }).click();
  const preview = page.frameLocator('iframe[title="Email preview"]');
  await expect(preview.getByRole("heading", { name: "Executive Snapshot" })).toBeVisible();
  await expect(preview.getByText("Added light and dark mode support.")).toBeVisible();
  await page.getByRole("tab", { name: "Edit" }).click();

  // 9. Send email
  await page.getByLabel("To", { exact: true }).fill("manager@example.com");
  await page.getByRole("button", { name: "Send email" }).click();
  const dialog = page.getByRole("dialog", { name: "Send EOD email?" });
  await expect(dialog.getByText("manager@example.com")).toBeVisible();
  await dialog.getByRole("button", { name: "Send email" }).click();
  await expect(page.getByText(/^EOD status:\s*Sent$/).first()).toBeVisible();
  await expect(page.getByText(/Sent .* \(version 2\) to manager@example.com/)).toBeVisible();
  await expect(page.getByText("Delivered · v2")).toBeVisible();
  await shot(page, "06-eod-sent");

  // Sending again without an explicit resend is refused by the server
  const csrf = await page.evaluate(async () => (await (await fetch("/api/auth/me")).json()).data.csrf_token);
  const eodId = await page.evaluate(async (iso) => (await (await fetch(`/api/eod/${iso}`)).json()).data.report.id, today.iso);
  const duplicate = await page.evaluate(async ({ id, token }) => {
    const res = await fetch(`/api/eod/${id}/send`, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": token }, body: "{}" });
    return { status: res.status, body: await res.json() };
  }, { id: eodId, token: csrf });
  expect(duplicate.status).toBe(409);
  expect(duplicate.body.error.code).toBe("EOD_ALREADY_SENT");

  // 10. History shows the report as SENT
  await page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "History" }).click();
  await page.getByRole("tab", { name: "EOD history" }).click();
  const row = page.getByRole("row").filter({ hasText: today.label.replace(/ (\w{3})\w* /, " $1 ") });
  await expect(row.getByText(/^EOD status:\s*Sent$/)).toBeVisible();
  await shot(page, "07-history");

  // 11. Calendar shows WORK LOGGED + EOD SENT
  await page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "Calendar" }).click();
  await expect(page.getByRole("button", { name: `${today.label}, today, work logged, EOD sent` })).toBeVisible();

  // 12. Search works server-side
  await page.goto("/history");
  await page.getByLabel("Search work history").fill("DBA approval");
  await expect(page.getByText("Also found in notes, blockers and asks")).toBeVisible();
});

test("theme toggle applies and persists without a flash", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(EMAIL);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  await page.goto("/settings");
  await page.getByText("Dark", { exact: true }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.goto("/dashboard");
  // The pre-paint script sets the class before React hydrates.
  expect(await page.evaluate(() => document.documentElement.classList.contains("dark"))).toBe(true);
  await expect(page.getByRole("heading", { name: /Janakiraman/ })).toBeVisible();
  await shot(page, "08-dashboard-dark");
  await page.goto("/settings");
  await page.getByText("System", { exact: true }).click();
});
