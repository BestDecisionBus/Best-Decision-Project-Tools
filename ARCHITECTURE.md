# BDB Tools — Technical Architecture

## Overview

BDB Tools is a multi-tenant Flask web application that serves two distinct audiences:

- **Field employees** — access via mobile browser, no install required, session-based auth
- **Admin / company admin users** — desktop-optimized admin panel, Flask-Login auth

All tenants (companies) share a single database and codebase. Isolation is enforced at the query level via a `token` column on every tenant-scoped table.

---

## Request Lifecycle

```
Browser
  │
  ├── Cloudflare Tunnel (TLS termination, DDoS protection)
  │
  └── Gunicorn (2 pre-fork workers, port 5003)
        │
        ├── Worker 1: Flask app + background thread (task_queue)
        └── Worker 2: Flask app + background thread (task_queue)
                │
                ├── Flask routing (blueprints)
                │     ├── Security headers (after_request)
                │     ├── Rate limiting (in-process, per token)
                │     ├── Auth check (Flask-Login or session)
                │     └── Route handler → database.py → SQLite
                │
                └── Background thread (DB polling, file-lock GPU exclusivity)
                      ├── Receipt processing: transcribe + PDF
                      └── Estimate processing: transcribe + task extraction
```

---

## Application Entry Point

**`app.py`** — The central module. Responsibilities:

| Concern | Implementation |
|---|---|
| Flask app creation | `app = Flask(__name__)` with session/cookie config |
| Auth system | `flask_login.LoginManager` + custom `User(UserMixin)` class |
| Role decorators | `@admin_required`, `@bdb_required`, `@scheduler_allowed` |
| Rate limiting | In-process `defaultdict(list)` per token, sliding window |
| Template filters | `fmt_time`, `fmt_date`, `time12`, `weekday`, `monthday` |
| Security headers | `@after_request` — CSP, X-Frame-Options, X-Content-Type-Options |
| Shared helpers | `_get_tokens_for_user()`, `_verify_token_access()` |
| PWA support | `/c/<token>/manifest.json`, `apple-touch-icon` routes |
| Blueprint registration | 9 blueprints registered at module bottom |

**Blueprint registration order** (`app.py` lines 603–611):
```python
app.register_blueprint(admin_bp)
app.register_blueprint(timekeeper_bp)
app.register_blueprint(time_admin_bp)
app.register_blueprint(receipts_bp)
app.register_blueprint(receipt_admin_bp)
app.register_blueprint(scheduling_bp)
app.register_blueprint(job_photos_bp)
app.register_blueprint(estimates_bp)
app.register_blueprint(finance_bp)
```

---

## Blueprints

| Blueprint | File | URL Prefix | Responsibility |
|---|---|---|---|
| `admin_bp` | `routes/admin.py` | `/admin` | Tokens, users, employees, jobs, categories, shift types, message snippets, common tasks, guide, dashboard |
| `timekeeper_bp` | `routes/timekeeper.py` | `/` | Employee clock in/out, timekeeper page, help |
| `time_admin_bp` | `routes/time_admin.py` | `/admin` | Time entries, manual entry, export, audit log |
| `receipts_bp` | `routes/receipts.py` | `/` | Employee receipt capture, upload API |
| `receipt_admin_bp` | `routes/receipt_admin.py` | `/admin` | Receipt browsing, detail, downloads, deletion |
| `scheduling_bp` | `routes/scheduling.py` | `/` | Schedule CRUD, scheduler dashboard, employee view |
| `job_photos_bp` | `routes/job_photos.py` | `/` | Photo capture, upload API, admin browsing, downloads |
| `estimates_bp` | `routes/estimates.py` | `/` | Field estimate capture, estimate/project admin, reports, job tasks, products/services |
| `finance_bp` | `routes/admin.py` | `/admin` | CFO Dashboard, finance targets |

**Lazy import pattern** — all blueprints import `app` lazily to avoid circular imports:
```python
def _helpers():
    import app as _app
    return _app
```

---

## Authentication & Authorization

### Two parallel auth systems

| System | Used by | Mechanism |
|---|---|---|
| Flask-Login | Admin panel users | `LoginManager`, persistent session cookie, `@login_required` |
| Flask session | Employees | `session["employee_id"]` + `session["token"]` set on company login |

### User roles (Flask-Login users)

| Role | `is_bdb` | `is_admin` | `is_scheduler` | token field |
|---|---|---|---|---|
| BDB Admin | True | True | False | NULL |
| BDB Viewer | True | False | False | NULL |
| Company Admin | False | True | False | set |
| Company Viewer | False | False | False | set |
| Scheduler | False | False | True | set |

`is_bdb` is derived: `return self.token is None` — BDB users have no token and can see all companies.

### Route decorators

```python
@admin_required      # must be logged in AND is_admin
@bdb_required        # must be logged in AND is_bdb
@scheduler_allowed   # must be logged in AND (is_admin OR is_scheduler OR is_bdb)
@login_required      # must be logged in (any role) — from flask_login
```

### Employee session

Employees log in at `/c/<token>` via a plain POST form. On success:
```python
session["employee_id"] = employee["id"]
session["token"] = token_str
session["employee_name"] = employee["name"]
```
Routes check `session.get("employee_id")` and redirect to `/c/<token>` if missing.

---

## Multi-Tenancy

Every tenant-scoped table has a `token TEXT NOT NULL` column referencing `tokens.token`. Data isolation is enforced at the query level — every CRUD function accepts and filters by `token_str`.

`_verify_token_access(token_str)` in `app.py` is called at the start of all write operations to ensure the logged-in user owns that token (BDB users pass any token; company users are checked against their own).

`_get_tokens_for_user()` returns the list of tokens the current user can see: all tokens for BDB users, or a single-element list for company users.

---

## Database

**Engine:** SQLite with WAL journal mode for safe concurrent reads/writes.

**File:** `instance/bdb_tools.db` (auto-created by `database.py:init_db()` on startup).

**Connection model:** One connection per function call — `get_db()` opens, function commits and closes. No connection pooling. Appropriate for SQLite's concurrency model.

**Schema migrations:** `_add_column_if_missing(conn, table, column, definition)` is called in `init_db()` on every startup. It is idempotent — safe to run repeatedly. No migration framework is used.

### All 18 tables

| Table | Tenant-scoped | Purpose |
|---|---|---|
| `tokens` | No (is the tenant) | Company tenants — URL token, branding, financial targets |
| `users` | Partial (token NULL = BDB) | Admin panel logins |
| `employees` | Yes | Field workers with access control flags |
| `jobs` | Yes | Job sites with geocoded coordinates |
| `categories` | Yes | Expense categories for receipt tagging |
| `common_tasks` | Yes | Preset note text for schedule entries |
| `shift_types` | Yes | Named shift time ranges (e.g., Full Day 7am–5pm) |
| `time_entries` | Yes | Clock records with GPS, manual overrides, status |
| `submissions` | Yes | Receipt uploads — image, audio, PDF, transcription |
| `submission_categories` | No (join) | Receipt → expense category many-to-many join |
| `schedules` | Yes | Employee shift assignments with optional job task |
| `job_photos` | Yes | GPS-tagged site photos organized by job + week |
| `estimates` | Yes | Estimate/project records with full financial tracking |
| `estimate_items` | Yes | Line items: description, qty, unit, price, cost, taxable |
| `products_services` | Yes | Reusable product/service catalog for estimate line items |
| `message_snippets` | Yes | Reusable text blocks for estimate customer messages |
| `job_tasks` | Yes | Per-job task checklists |
| `audit_log` | Yes | Field-level change history for time entries |

### Key `estimates` columns (beyond CREATE TABLE)

Added via `_add_column_if_missing`:

| Column | Type | Purpose |
|---|---|---|
| `notes` | TEXT | Internal admin notes |
| `approval_status` | TEXT | pending / accepted / in_progress / completed / declined |
| `estimate_value` | REAL | Contract price to customer |
| `est_materials_cost` | REAL | Budgeted materials cost |
| `est_labor_cost` | REAL | Budgeted labor cost |
| `actual_materials_cost` | REAL | Actual materials spent |
| `actual_labor_cost` | REAL | Actual labor spent |
| `actual_collected` | REAL | Payments received |
| `est_labor_hours` | REAL | Budgeted hours |
| `actual_labor_hours` | REAL | Actual hours worked |
| `completion_pct` | REAL | WIP % complete |
| `customer_name/phone/email` | TEXT | Customer contact info |
| `customer_message` | TEXT | Message shown on client-facing PDF |
| `estimate_number` | TEXT | Custom numbering (e.g., "2026-001") |
| `date_accepted` | TEXT | Date customer accepted |
| `expected_completion` | TEXT | Target completion date |
| `completed_at` | TEXT | Actual completion date |
| `sales_tax_rate` | REAL | Tax rate for taxable line items |
| `client_budget` | REAL | Customer's stated budget |
| `append_audio_file` | TEXT | Path to supplemental audio (for append transcription) |

---

## Background Task Queue

**`task_queue.py`** runs a background thread in each Gunicorn worker. A file lock (`instance/gpu_worker.lock`) ensures only one thread across all workers runs GPU-bound Whisper work at a time.

**Poll interval:** 2 seconds.

**Processing order per poll cycle:**
1. Pending receipt submission (`claim_next_pending`) — transcribe audio + generate PDF
2. Pending estimate (`claim_next_pending_estimate`) — transcribe audio + run AI task extraction
3. Pending append transcription (`claim_next_appending_estimate`) — append voice note to existing estimate

**AI task extraction** (`task_extractor.py`):
- Uses a local Ollama LLM (default: `mistral:7b-instruct`) to extract actionable tasks from estimate transcriptions
- Writes per-estimate and per-job summary markdown files to `estimates/{token}/{job_name}/`
- Non-blocking on failure — if Ollama is unavailable the estimate still processes normally

---

## File Storage

All file paths are defined in `config.py` and created on import:

| Directory | Contents | Structure |
|---|---|---|
| `instance/` | SQLite DB, GPU lock file | flat |
| `receipts/` | Receipt images, audio, PDFs | `{token}/{YYYY-MM}/{filename}` |
| `receipts/{token}/estimates/` | Estimate audio files | flat per token |
| `job_photos/` | Site photos + thumbnails | `{token}/{job-name}/{YYYY-Www}/{filename}` |
| `estimates/` | Estimate markdown vault | `{token}/{job-name}/estimate_YYYY-MM-DD_{id}.md` |
| `exports/` | Temporary XLSX payroll exports | flat, auto-cleaned |
| `static/logos/` | Company logos (max 800px) | flat |

---

## Security

| Mechanism | Implementation |
|---|---|
| HTTPS | Cloudflare Tunnel (TLS termination externally) |
| Session encryption | `SECRET_KEY` from `.env` |
| Password hashing | `werkzeug.security.generate_password_hash` (pbkdf2) |
| Rate limiting | Sliding-window in-process, per token, `config.RATE_LIMIT` req/min |
| File validation | Magic byte check before saving uploads (JPEG, PNG, WebP, audio formats) |
| Max upload size | `app.config["MAX_CONTENT_LENGTH"]` = `MAX_UPLOAD_MB` × 1024² |
| Content Security Policy | `after_request` header; `img-src 'self' data: blob:` for camera/thumbnails |
| X-Frame-Options | `DENY` — prevents clickjacking |
| X-Content-Type-Options | `nosniff` |
| Session cookie flags | `HttpOnly=True`, `SameSite=Lax` |
| Audit trail | Every time-entry field change logged to `audit_log` with old/new values |

---

## PWA Support

BDB Tools supports "Add to Home Screen" on iOS and Android:

- `/c/<token>/manifest.json` — dynamically generated per-company manifest with company name as app name
- `apple-touch-icon.png` routes — served from `static/icons/`
- Three manifests in `static/`: `manifest-admin.json`, `manifest-scheduler.json`, `manifest-timekeeper.json`

---

## Jinja2 Template Filters (defined in `app.py`)

| Filter | Input | Output | Example |
|---|---|---|---|
| `fmt_time` | ISO timestamp string | 12-hour time | `"2026-02-17 14:30:00"` → `"2:30 PM"` |
| `fmt_date` | ISO timestamp string | Friendly date | `"2026-02-17 14:30:00"` → `"Feb 17, 2026"` |
| `time12` | `"HH:MM"` string | 12-hour time | `"17:00"` → `"5:00 PM"` |
| `weekday` | `"YYYY-MM-DD"` string | Day name | `"2026-02-17"` → `"Tuesday"` |
| `monthday` | `"YYYY-MM-DD"` string | `MM-DD` | `"2026-02-17"` → `"02-17"` |

---

## CFO Dashboard Calculations

All computed in `routes/estimates.py:_compute_finance_targets()` and the `admin_finance_dashboard` route:

| KPI | Formula |
|---|---|
| Overhead % | `(monthly_overhead × 12) ÷ earned_revenue × 100` |
| Margin Target | `overhead_pct + income_target_pct` |
| Markup Required | `margin_target ÷ (100 − margin_target) × 100` |
| Earned Revenue | `Σ (budget × completion_pct / 100)` across active projects |
| Unearned Liability | `cash_collected − earned_revenue` |
| Net Income | `earned_revenue − total_actual_costs − (monthly_overhead × 12)` |
| Net Income % | `net_income ÷ earned_revenue × 100` |
| Days Cash on Hand | `cash_on_hand ÷ (monthly_overhead ÷ 30)` |
| Billing Position | `cash_collected − earned_revenue` (positive = overbilled) |

---

## GPS Flagging

Time entries are flagged (`clock_in_flagged = 1`) when the Haversine distance between the clock-in GPS coordinates and the job site's geocoded coordinates exceeds `GPS_FLAG_DISTANCE_MILES` (default 0.5 miles). Calculation runs at clock-in time inside the `/api/clock-in` handler.

---

## Estimate Lifecycle State Machine

```
[field capture / admin create]
         │
         ▼
    status="processing"  ← audio transcription in progress
         │
         ▼ (task_queue completes)
    status="complete"
    approval_status="pending"
         │
         ├─► approval_status="declined"  (not accepted)
         │
         └─► approval_status="accepted"   (Est # → Proj #)
                    │
                    ▼
             approval_status="in_progress"
                    │
                    ▼
             approval_status="completed"
```

Document identity: `approval_status in ('pending', 'declined')` → shown as `Est #`; otherwise shown as `Proj #`.

---

## Manual Time Entry — Clock-In-Only Mode

`database.create_manual_entry()` accepts an optional `manual_time_out`:

- **With clock-out:** `status="completed"`, `total_hours` calculated, all clock-out fields set
- **Without clock-out:** `status="active"`, `total_hours=NULL`, clock-out fields `NULL` — entry appears as an active punch the employee can clock out of normally via the Timekeeper
