# WorkLog

WorkLog is a personal work-documentation platform. You log what you actually worked on during the day, and WorkLog keeps your work history, writes a professional corporate EOD report from your own notes, and emails it — manually or automatically at your configured EOD time.

```
LOGIN → CALENDAR → SELECT DATE → ENTER WORK → SAVE → GENERATE EOD → EDIT → SEND EMAIL → HISTORY
                                                         ↑
                         SCHEDULER (EOD time) ───────────┘  generate if needed → send → record delivery
```

---

## Contents

1. [Architecture](#architecture)
2. [Tech stack](#tech-stack)
3. [Folder structure](#folder-structure)
4. [Quick start (local)](#quick-start-local)
5. [MongoDB setup](#mongodb-setup)
6. [Environment variables](#environment-variables)
7. [Running tests](#running-tests)
8. [Scheduler](#scheduler)
9. [Email setup](#email-setup)
10. [AI setup](#ai-setup)
11. [Data model](#data-model)
12. [API reference](#api-reference)
13. [Security](#security)
14. [Production deployment](#production-deployment)
15. [Troubleshooting](#troubleshooting)

---

## Architecture

```
Browser ──► Next.js (App Router, :3000) ──/api/* rewrite──► Flask API (:5000) ──► MongoDB
                                                              ├── AI service      (local | groq)    
                                                              ├── Email service   (smtp | console)
                                                              └── Scheduler       (APScheduler, every 60 s)
```

- **The browser only talks to the Next.js origin.** `next.config.ts` rewrites `/api/*` to Flask, so the HttpOnly session cookie is first-party and no CORS is involved in the browser.
- **Flask is layered:** `routes` (HTTP + validation) → `services` (business rules) → `repositories` (MongoDB, every query scoped by the authenticated user).
- **The backend enforces everything.** `proxy.ts` in Next.js only redirects visitors without a session cookie to `/login` as a UX shortcut; every API call is authenticated and authorized by Flask.

### Key behaviours

| Concern | How it works |
|---|---|
| No fabricated work | Strict system prompt (spec §19/§55), structured JSON output, and a guard that flags any number in the report that does not appear in your notes. The default `local` provider only rearranges your own words. |
| EOD versioning | Every generation, regeneration and post-send edit creates an immutable version (`is_current` marks the latest). Consecutive unsent manual edits update the same edit version. |
| Historical integrity | A sent version is never modified. After sending, the report stays `SENT`; later edits are new versions shown as "unsent changes", and only an explicit **Resend** emails again. |
| Duplicate email protection | One report per user per date (unique index). Sending is an atomic `GENERATED/FAILED → SENDING` claim, so a double-click, a second scheduler process or a re-run tick cannot send twice. Scheduler attempts are reserved with an atomic upsert on the same unique index. |
| Failure handling | AI failure → `FAILED` with `EOD_GENERATION_FAILED` (work is untouched, retry from the UI). Email failure → `FAILED` with `EMAIL_FAILED`; retry re-sends the existing version without regenerating. A crash mid-send is detected after 15 min and marked `EMAIL_DELIVERY_UNKNOWN` — never auto-retried, to avoid duplicates. |
| Timezones | Timestamps are stored in UTC. Work dates are the user's local `YYYY-MM-DD`. Entry times, calendar, and EOD scheduling use the user's timezone (default `Asia/Kolkata`). |
| Draft protection | Quick notes autosave 2 s after you stop typing, and every keystroke is mirrored to `localStorage`. After a refresh or crash the unsaved draft is restored with a banner. MongoDB remains the source of truth. |

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS v4, lucide-react |
| Backend | Python 3.11+ (tested on 3.13), Flask 3, Pydantic 2 validation, bcrypt |
| Database | MongoDB 6+ / MongoDB Atlas, PyMongo |
| AI | Provider abstraction: `local` (offline) or `groq` (Qwen and other open models on Groq) |
| Email | Provider abstraction: `smtp` or `console` (writes `.eml` files) |
| Scheduler | APScheduler (in-process) or a standalone worker |
| Tests | pytest + mongomock (backend), Vitest + Testing Library (components), Playwright (browser E2E) |

---

## Folder structure

```
backend/
  app/
    __init__.py            app factory (create_app)
    config/settings.py     environment configuration
    db.py                  Mongo client + index creation
    constants.py           categories, statuses, EOD states
    routes/                auth, dashboard, calendar, work_logs, work_items, projects,
                           blockers, dependencies, eod, history, settings, email, health
    services/              auth, settings, project, work_log, tracking, dashboard, eod,
                           eod_renderer, ai, email, history, scheduler
    repositories/          user/session, project, work_log/work_item, tracking, eod, email, settings/locks
    middleware/            auth.py (session + CSRF), error_handler.py
    utils/                 security, validators, datetime_utils, logging, serialization, responses, errors
    scheduler/jobs.py      APScheduler wiring + standalone worker entry point
  scripts/                 seed.py (dev data), create_user.py
  tests/                   pytest suite (87 tests, incl. end-to-end scenario)
  requirements.txt / requirements-dev.txt / run.py / .env.example
frontend/
  app/
    login/                 sign-in page
    (app)/                 authenticated shell (sidebar + header)
      dashboard/ calendar/ work-log/[date]/ eod/ eod/[date]/ projects/ history/ settings/
  components/              Sidebar, Header, Calendar, WorkLogForm, WorkEntry, ProjectSelector,
                           BlockerCard, TrackingPanels, CategorizeDialog, EodEditor, EodStatus,
                           DashboardStats, HistoryTables, LoadingState, EmptyState, ErrorState, ui
  lib/                     api.ts, auth.tsx, theme.tsx, hooks.ts, date.ts, toast.tsx, utils.ts
  types/                   auth.ts, work.ts, project.ts, eod.ts
  proxy.ts                 optimistic route protection (Next.js 16 replacement for middleware)
  tests/                   Vitest component tests
  e2e/                     Playwright acceptance test
```

---

## Quick start (local)

Prerequisites: Python 3.11+, Node.js 20.9+ (22 recommended), and a MongoDB (local server or Atlas).

### 1. Backend

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements-dev.txt     # or requirements.txt for production only
cp .env.example .env                    # Windows: copy .env.example .env
```

Edit `backend/.env`: set `SECRET_KEY`, `SESSION_SECRET` (generate with
`python -c "import secrets; print(secrets.token_urlsafe(48))"`), `MONGODB_URI`, and **your login**:

```
APP_USER_NAME=Your Name
APP_USER_EMAIL=you@company.com
APP_USER_PASSWORD=<at least 8 characters>
```

WorkLog runs as a single-user app: this is the only account that can sign in. It is created when the
backend starts, and editing these values then restarting the backend updates it — a new password replaces
the old one and signs out existing sessions; a new email renames the same account, so your history is kept.
MongoDB only stores a bcrypt hash of the password. Your display name can also be changed later in Settings.

```bash
python -m scripts.seed          # optional sample data for your account (refuses to run when FLASK_ENV=production)
python run.py                   # API on http://127.0.0.1:5000 (+ scheduler)
```

Without `APP_USER_EMAIL`, WorkLog falls back to multi-user mode: `scripts.seed` creates
**demo@example.com / WorkLog@2026** and `python -m scripts.create_user` adds accounts.

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local      # NEXT_PUBLIC_API_URL=http://localhost:5000
npm run dev                     # http://localhost:3000
```

Open http://localhost:3000 and sign in.

> No MongoDB at hand? Set `MONGODB_URI=mongomock://` in `backend/.env` for an in-memory demo (data is lost on restart).

---

## MongoDB setup

### MongoDB Atlas

1. Create a cluster and a database user (Database Access).
2. **Network Access → add your IP address** (or your server's IP). Without this the driver fails during the TLS handshake — see [Troubleshooting](#troubleshooting).
3. Copy the connection string into `backend/.env` only:
   ```
   MONGODB_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
   MONGODB_DATABASE=worklog
   ```
   URL-encode special characters in the password.

### Local MongoDB

Install MongoDB Community (or run `docker run -d -p 27017:27017 mongo:8`) and use `MONGODB_URI=mongodb://localhost:27017`.

### Collections and indexes

Indexes are created automatically at startup (`app/db.py`):

| Collection | Purpose | Key indexes |
|---|---|---|
| `users` | accounts (bcrypt hashes) | `email` unique |
| `sessions` | server-side sessions (keyed token hash, CSRF token) | `token_hash` unique, TTL on `expires_at` |
| `projects` | projects (Active / Archived) | `user_id+name_lower` unique |
| `work_logs` | one doc per user per date: quick notes, next steps, meetings, learnings, metrics | `user_id+work_date` unique |
| `work_items` | timestamped entries with category / status | `user_id+work_date+timestamp` |
| `blockers` | blockers (Open / In Progress / Resolved) | `user_id+status+identified_date` |
| `dependencies` | asks & dependencies (Approval, Information, Dependency, Decision, Access) | `user_id+status+created_date` |
| `eod_reports` | one report per user per date + status | `user_id+work_date` unique |
| `eod_versions` | immutable report versions | `eod_id+version` unique |
| `email_logs` | every delivery attempt | `user_id+created_at` |
| `settings` | per-user preferences | `user_id` unique |
| `job_locks` | insert-once locks (e.g. one reminder per day) | `key` unique, TTL |

---

## Environment variables

### `backend/.env`

| Variable | Default | Description |
|---|---|---|
| `FLASK_ENV` | `development` | `production` enables secure cookies and strict secret checks |
| `SECRET_KEY` | — | Flask secret (required in production) |
| `SESSION_SECRET` | — | HMAC key for stored session tokens (≥ 32 chars in production) |
| `APP_USER_EMAIL` / `APP_USER_PASSWORD` / `APP_USER_NAME` | — | The single login account (password ≥ 8 chars); synced at startup |
| `MONGODB_URI` / `MONGODB_DATABASE` | `mongodb://localhost:27017` / `worklog` | Database |
| `SESSION_TTL_HOURS` / `REMEMBER_TTL_DAYS` | `12` / `30` | Session lifetime without / with "remember me" |
| `COOKIE_SECURE` | auto (true in production) | Require HTTPS for the session cookie |
| `TRUST_PROXY` | `false` | Trust `X-Forwarded-For` for rate limiting (only behind your own proxy) |
| `LOGIN_MAX_ATTEMPTS` / `LOGIN_WINDOW_SECONDS` | `5` / `900` | Failed-login rate limit |
| `AI_PROVIDER` | `local` | `local` or `groq` |
| `AI_API_KEY` / `AI_MODEL` / `AI_BASE_URL` | — / `qwen/qwen3.8-27b` / Groq | Groq API key, model id and endpoint |
| `AI_REASONING_EFFORT` / `AI_TIMEOUT_SECONDS` | `none` / `120` | Qwen thinking effort (none, default, low, medium, high) and request timeout |
| `EMAIL_PROVIDER` | `console` | `smtp` or `console` |
| `EMAIL_FROM` / `EMAIL_FROM_NAME` | — / `WorkLog` | Sender address and display name |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USERNAME` / `SMTP_PASSWORD` | — / `587` | SMTP server |
| `SMTP_USE_TLS` / `SMTP_USE_SSL` | `true` / `false` | STARTTLS (587) or implicit TLS (465) |
| `OUTBOX_DIR` | `outbox` | Where the console provider writes `.eml` files |
| `DEFAULT_TIMEZONE` / `EOD_DEFAULT_TIME` | `Asia/Kolkata` / `18:30` | Defaults for new users |
| `SCHEDULER_ENABLED` / `SCHEDULER_INTERVAL_SECONDS` | `true` / `60` | Run the in-process scheduler |
| `EOD_MAX_AUTO_ATTEMPTS` / `EOD_AUTO_RETRY_MINUTES` | `3` / `10` | Automatic retry policy |
| `FRONTEND_URL` | `http://localhost:3000` | Allowed CORS origin; used in reminder links |
| `LOG_LEVEL` | `INFO` | Structured JSON logs |

### `frontend/.env.local`

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:5000` | Flask URL the Next.js server proxies `/api/*` to |

**Never commit `.env` / `.env.local`.** Only the `.env.example` templates belong in git, and they must contain placeholders only. Credentials are read by the backend alone — nothing secret is exposed to the browser.

---

## Running tests

```bash
# Backend — 87 tests: auth, CRUD, EOD versioning & sending, AI (mocked), scheduler idempotency,
# timezones, history/search, and the full end-to-end scenario from the spec.
cd backend
python -m pytest -q

# Same suite against a real MongoDB server (each test uses a throwaway database)
TEST_MONGODB_URI=mongodb://localhost:27017 python -m pytest -q      # PowerShell: $env:TEST_MONGODB_URI="..."

# Frontend
cd frontend
npm run lint
npm run typecheck
npm test                 # Vitest component tests: login, calendar, work entry, save/draft, EOD editor, history
npm run test:e2e         # Playwright acceptance test (needs the API + MongoDB running)
```

The Playwright run resets the demo user (`python -m scripts.seed --reset`) and then performs the acceptance scenario in a real browser: login → dashboard → calendar → select today → enter the notes → save (verified after reload) → generate EOD → edit one sentence → preview → send → duplicate send refused → history shows **Sent** → calendar shows **work logged, EOD sent**. First run: `npx playwright install chromium`.

---

## Scheduler

Every `SCHEDULER_INTERVAL_SECONDS` the scheduler checks users with automation enabled (Settings → EOD):

1. At *EOD time − reminder minutes*, if nothing is logged today and reminders are on, email a reminder (once per day).
2. At or after *EOD time* (user's timezone), if automatic EOD is on:
   - skip if today's EOD is already `SENT` (or being sent);
   - skip if no work is logged;
   - reserve an attempt atomically (max 3 per day, 10 minutes apart);
   - generate a report only if none exists — a report you generated or edited yourself is sent as-is;
   - send to your default recipients (or your own address) and record the result.

Running it:

- **Development / single server:** enabled by default inside `python run.py`.
- **Production with several web workers:** set `SCHEDULER_ENABLED=false` on the web processes and run one worker:
  ```bash
  python -m app.scheduler.jobs
  ```
  Running more than one scheduler is still safe — all side effects are guarded by database claims — it is just wasteful.

---

## Email setup

`EMAIL_PROVIDER=console` (default) writes each email to `backend/outbox/*.eml`; open them in Outlook or any mail client. To send real email:

```
EMAIL_PROVIDER=smtp
EMAIL_FROM=you@company.com
SMTP_HOST=smtp.office365.com      # Gmail: smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=you@company.com
SMTP_PASSWORD=<app password>
SMTP_USE_TLS=true
```

Use Settings → Email → **Send test email to me** to verify. EOD emails are multipart: inline-styled HTML (table layout that renders in Outlook and Gmail) plus a plain-text fallback, with `Reply-To` set to your address. Microsoft Graph or another provider can be added by implementing `EmailProvider` in `app/services/email_service.py` and registering it in `create_email_provider`.

---

## AI setup

| Provider | Configuration | Notes |
|---|---|---|
| `local` (default) | none | Deterministic, offline. Groups your lines into sections without adding anything. |
| `groq` | `AI_PROVIDER=groq`, `AI_API_KEY=gsk_...` (from console.groq.com/keys), optional `AI_MODEL` (default `qwen/qwen3.8-27b`; `llama-3.1-8b-instant` is smaller and faster) | OpenAI-compatible chat API with JSON output, Qwen reasoning hidden, a strict no-fabrication system prompt, and automatic retry if the model drifts from valid JSON. |

The AI is used for EOD generation, "Convert to entries" (splits notes into categorised entries for you to review), and History → **Summarise period**. Settings → AI → *Generation style* switches between standard, concise and detailed.

Whatever the provider, every report is reviewed and editable before sending, and any number not present in your notes is flagged with a warning. Add a provider by subclassing `AIProvider` in `app/services/ai_service.py` and registering it in `create_ai_provider`.

---

## Data model

EOD report states: `NOT_GENERATED → GENERATING → GENERATED → SENDING → SENT`, with `FAILED` (and `last_error.code` = `EOD_GENERATION_FAILED`, `EMAIL_FAILED` or `EMAIL_DELIVERY_UNKNOWN`).

Work statuses: Planned, In Progress, Completed, Blocked, Deferred. Categories: Development, Enhancement, Bug Fix, Investigation, Research, Testing, Deployment, Documentation, Meeting, Support, Learning, Planning. Neither is required — raw notes are enough.

Projects cannot be deleted; archiving hides them from selectors while history keeps them.

---

## API reference

All responses use `{"success": true, "data": ...}` or `{"success": false, "error": {"code", "message", "details?"}}`. List endpoints accept `?page=1&limit=20` (max 100) and return `meta`.

| Area | Endpoints |
|---|---|
| Auth | `POST /api/auth/login` · `POST /api/auth/logout` · `GET /api/auth/me` |
| Dashboard | `GET /api/dashboard` |
| Calendar | `GET /api/calendar?year=2026&month=10` |
| Work logs | `GET /api/work-logs/:date` · `POST /api/work-logs` (upsert by date) · `PUT /api/work-logs/:id` · `DELETE /api/work-logs/:id` |
| Work items | `POST /api/work-items` · `POST /api/work-items/bulk` · `PUT /api/work-items/:id` · `DELETE /api/work-items/:id` · `POST /api/work-items/categorize` |
| Projects | `GET /api/projects[?include_archived=true]` · `GET/PUT /api/projects/:id` · `POST /api/projects` · `POST /api/projects/:id/archive` |
| Blockers | `GET /api/blockers[?status=&open=true]` · `POST /api/blockers` · `PUT /api/blockers/:id` |
| Dependencies | `GET /api/dependencies[?status=&type=&open=true]` · `POST /api/dependencies` · `PUT /api/dependencies/:id` |
| EOD | `POST /api/eod/generate` · `GET /api/eod/:date-or-id` · `PUT /api/eod/:id` · `POST /api/eod/:id/regenerate` · `POST /api/eod/:id/send` (`{"resend": true}` to send again) · `GET /api/eod/:id/versions/:n` · `GET /api/eod/:id/preview` |
| History | `GET /api/history/work?from=&to=&project_id=&category=&status=&q=` · `GET /api/history/eod?status=&q=` · `GET /api/history/search?q=` · `GET /api/history/summary?from=&to=` |
| Settings | `GET /api/settings` · `PUT /api/settings` · `GET /api/settings/timezones` |
| Email | `GET /api/email/status` · `POST /api/email/test` |
| Health | `GET /api/health` |

---

## Security

- Passwords hashed with bcrypt (cost 12); constant-time comparison; generic "Invalid email or password."
- Sessions: random 256-bit token in an **HttpOnly, SameSite=Lax** cookie (`Secure` in production); only an HMAC of the token is stored; logout and expiry revoke server-side.
- CSRF: per-session token required in `X-CSRF-Token` on every write, plus JSON-only request bodies.
- Authorization: the user ID always comes from the session; every repository query is scoped by it. Cross-user access returns 404.
- Validation: Pydantic schemas reject unknown fields, malformed dates/IDs/emails and oversized input; 1 MB request limit.
- Login rate limiting per email+IP and per IP.
- Structured JSON logs with automatic redaction of password/token/secret/cookie fields; no stack traces in API responses.
- Security headers on API and frontend; the EOD preview is served with a restrictive CSP inside a sandboxed iframe.

---

## Production deployment

1. **MongoDB Atlas** with the server's IP allow-listed.
2. **Backend** (`FLASK_ENV=production`, strong `SECRET_KEY`/`SESSION_SECRET`, `EMAIL_PROVIDER=smtp`, `FRONTEND_URL=https://worklog.example.com`):
   ```bash
   pip install -r requirements.txt
   # Linux
   gunicorn -w 2 -b 0.0.0.0:5000 "app:create_app()"
   # Windows
   waitress-serve --listen=0.0.0.0:5000 --call app:create_app
   ```
   With more than one worker, set `SCHEDULER_ENABLED=false` and run `python -m app.scheduler.jobs` as a separate service.
3. **Frontend**:
   ```bash
   npm ci
   NEXT_PUBLIC_API_URL=http://<internal-backend-host>:5000 npm run build
   npm start            # serves on :3000
   ```
   `NEXT_PUBLIC_API_URL` is read at build time for the rewrite.
4. Put both behind HTTPS (reverse proxy or platform TLS). Only the Next.js origin needs to be public; keep Flask on a private network. Set `TRUST_PROXY=true` only if your proxy sets `X-Forwarded-For`.
5. Do not run `scripts/seed.py` in production (it refuses when `FLASK_ENV=production`).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `SSL handshake failed ... TLSV1_ALERT_INTERNAL_ERROR` connecting to Atlas | Your IP is not on the Atlas **Network Access** list. Add it (or `0.0.0.0/0` for testing only). |
| `ServerSelectionTimeoutError` to localhost | MongoDB is not running, or `MONGODB_URI` is wrong. `GET /api/health` reports database status. |
| Login works but every page bounces to `/login` | The frontend is not reaching Flask through the rewrite. Check `NEXT_PUBLIC_API_URL` and that `python run.py` is running; restart `npm run dev` after changing it. |
| "Your session security token is missing or invalid" | The page was open across a logout/expiry. Reload the page. |
| No emails arrive | With `EMAIL_PROVIDER=console` they are files in `backend/outbox/`. For SMTP, use Settings → *Send test email*; the error (e.g. authentication) is shown and recorded in the delivery log. Office 365/Gmail usually require an app password. |
| Automatic EOD did not send | Check Settings → EOD (automatic EOD on, time, timezone), that work is logged for today, that `SCHEDULER_ENABLED=true` on exactly one process, and the `scheduler.tick` lines in the backend log. |
| EOD shows "FAILED" | Use **Retry** on the EOD page. Generation failures keep your work; email failures re-send the same version. `EMAIL_DELIVERY_UNKNOWN` means a send was interrupted — check your sent mail before retrying. |
| `EADDRINUSE :3000` | Another dev server is already running on port 3000; stop it or use `npm run dev -- -p 3001`. |
