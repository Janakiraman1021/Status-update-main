import { execSync } from "node:child_process";
import path from "node:path";

/**
 * Resets the test account's data so the acceptance scenario starts from a clean day.
 *
 * Safety: the reset deletes that account's work logs and reports, so it only runs against a local
 * database. Set MONGODB_URI (e.g. mongodb://127.0.0.1:27017) for the test run; it overrides backend/.env.
 * The backend under test must use the same database and the APP_USER_* account the test logs in with.
 */
export default function globalSetup() {
  if (process.env.E2E_SKIP_RESET) return;
  const uri = process.env.MONGODB_URI ?? "";
  if (!/^(mongodb:\/\/(localhost|127\.0\.0\.1)(:\d+)?(\/|$)|mongomock:\/\/)/.test(uri)) {
    throw new Error(
      "Refusing to reset data: set MONGODB_URI to a local database (mongodb://127.0.0.1:27017) for E2E runs, " +
        "or E2E_SKIP_RESET=1 to run without resetting. Never point E2E tests at your real database.",
    );
  }
  const backend = path.resolve(__dirname, "..", "..", "backend");
  const python = process.platform === "win32" ? path.join(backend, "venv", "Scripts", "python.exe") : path.join(backend, "venv", "bin", "python");
  execSync(`"${python}" -m scripts.seed --reset`, { cwd: backend, stdio: "inherit", env: process.env });
}
