# BDB Tools — Project Plan & Roadmap

## Current State (as of March 2026)

BDB Tools is a fully deployed, production-grade multi-tenant field service operations platform. All core modules are live and in use, with QuickBooks Online integration, push notifications, invoicing, and customer management added in March 2026.

---

## Completed Features

### Core Platform
- [x] Multi-tenant architecture with token-based company isolation
- [x] Six-role auth system (BDB Admin, BDB Viewer, Company Admin, Company Viewer, Scheduler, Employee)
- [x] Flask-Login for admin users + Flask session for employees
- [x] CSRF protection (Flask-WTF with auto-injection into forms and fetch requests)
- [x] Security hardening: HSTS, SESSION_COOKIE_SECURE, auth checks on all shared APIs
- [x] Company branding (logo upload, auto-resize, displayed on employee pages)
- [x] Company Brand Color scheme (6 options, applies uniformly to admin and all employee pages)
- [x] Security headers (CSP, HSTS, X-Frame-Options), rate limiting, file validation via magic bytes
- [x] Cloudflare Tunnel integration for HTTPS
- [x] systemd service for production process management
- [x] PWA manifest support ("Add to Home Screen" on iOS/Android)
- [x] Service worker for push notifications (`sw.js`)
- [x] Shared blueprint helpers (`routes/_shared.py`) — lazy import, feature gates, safe_latin1
- [x] Reusable token selector partial (`_token_selector.html`)
- [x] Generic CRUD helpers in database.py (_get_all_by_token, _get_by_id, _toggle_active, etc.)
- [x] Context-aware admin guide
- [x] Comprehensive employee help page

### Timekeeper
- [x] GPS clock in/out from mobile browser
- [x] Job assignment per punch
- [x] GPS distance flagging (configurable threshold)
- [x] Time entry admin view with filters
- [x] Time entry detail with GPS map (Leaflet + OpenStreetMap)
- [x] Manual time override with audit trail
- [x] Admin manual entry — clock in + clock out, or clock in only
- [x] Entry statuses: active, completed, needs_review, approved, paid
- [x] Weekly payroll estimates with labor burden calculation
- [x] Excel and PDF payroll export
- [x] Audit log for all time entry field changes

### Receipt Capture
- [x] Photo receipt capture via mobile camera or photo library
- [x] Voice memo recording (WebM, M4A, Ogg, WAV supported)
- [x] OpenAI Whisper transcription (background processing)
- [x] Combined PDF generation (photo + transcription + metadata)
- [x] Job and expense category tagging
- [x] Admin receipt browse by company and month
- [x] Receipt detail view
- [x] Individual PDF and monthly ZIP download
- [x] Receipt deletion

### Scheduling
- [x] Drag-and-drop weekly schedule builder
- [x] Customizable shift types per company (name, start/end time)
- [x] Default shift types seeded on new company creation
- [x] Employee 14-day schedule view with collapsible per-shift task lists
- [x] Dedicated Scheduler role with limited access
- [x] Schedule entry with optional job task note
- [x] Admin read-only schedule view
- [x] Per-shift job task association

### Job Photos
- [x] Single photo capture or batch upload from camera roll
- [x] EXIF orientation correction
- [x] GPS geotagging
- [x] Photos organized by job and week
- [x] Admin browse by job and week
- [x] Photo detail with GPS map
- [x] ZIP download (weekly, per job)
- [x] PDF report download with GPS coordinates
- [x] Thumbnail generation for fast mobile browsing

### Estimates / Projects
- [x] Field estimate capture via mobile (voice memo + job selection)
- [x] Whisper transcription of estimate audio (background)
- [x] AI task extraction via local Ollama LLM (non-blocking)
- [x] Markdown vault per job (estimates/{token}/{job}/)
- [x] Estimate/project list with status badges and cost columns
- [x] Full estimate editor (all financial fields, customer info, line items)
- [x] Line item builder (description, qty, unit, price, cost, taxable flag, item type)
- [x] Reusable product/service catalog
- [x] Customer details (name, phone, email, client budget)
- [x] Sales tax rate per estimate
- [x] Approval lifecycle: Pending → Accepted → In Progress → Completed → Declined
- [x] Dual document identity: Est # (pending/declined) → Proj # (accepted+)
- [x] Three report outputs: Internal PDF, Internal XLSX, Client-facing Scope PDF
- [x] Send estimate to job folder
- [x] Per-job task checklists (auto-populated from estimates or manual)
- [x] Append audio — add voice notes to existing estimates
- [x] Employee "My Estimates" view
- [x] Margin and markup targets shown on estimate detail

### CFO Dashboard
- [x] Configurable targets: Income Target %, Monthly Overhead $, Cash on Hand $
- [x] Calculated: Overhead %, Margin Target, Markup Required
- [x] KPI cards: Pipeline Value, Contracted Revenue, Cash Collected, Earned Revenue, Unearned Liability, Total Costs, Net Income ($), Net Income (%), Days Cash on Hand, Billing Position
- [x] Health gauges: Overall Margin, WIP Income vs Progress, WIP Costs vs Progress, Budget Consumption
- [x] Per-job financial breakdown table

### Admin Configuration
- [x] Tokens (company) management with logo upload
- [x] BDB user management
- [x] Company admin / viewer user management
- [x] Employee management with per-employee access control (receipt, estimate, tasks)
- [x] Job management with geocoding (Mapbox)
- [x] Expense categories (with optional GL/account code field)
- [x] Common tasks (schedule note presets)
- [x] Shift types (custom schedule time presets)
- [x] Products & services catalog (with taxable flag)
- [x] Message snippets
- [x] Bulk CSV import for all 5 admin lists (append or deactivate-and-replace mode)
- [x] Inline sort order editing on all 5 list tables (auto-saves on change, no page reload)
- [x] Column resize handles on all admin list tables
- [x] Click-to-sort column headers on all admin list tables
- [x] Company Brand Color scheme selector (6 colors: blue, green, teal, purple, orange, red) — affects both admin and employee sides universally
- [x] Settings page (Admin → Settings) for brand color and future company-wide settings
- [x] Task templates — named checklists of tasks assignable to jobs
- [x] Task completion history with configurable retention (per-company `task_retention_days`)
- [x] Task uncheck permission — per-employee `task_uncheck_access` flag with reset tracking

### Customer Management
- [x] Customer CRUD with contact details (name, company, phone, email)
- [x] Customer linked to estimates and invoices
- [x] Customer sync to QuickBooks Online (auto-create, handles duplicates)

### Invoicing
- [x] Invoice creation from estimates/projects with automatic line item import
- [x] Invoice lifecycle: Draft → Sent → Paid → Void
- [x] Drag-and-drop line item reordering
- [x] Client-facing invoice PDF generation
- [x] Push invoices to QuickBooks Online

### Push Notifications
- [x] Web Push via VAPID protocol + service worker (no app install required)
- [x] Admin and employee notification bells with unread counts
- [x] Feature-gated per company (`tokens.feature_push_notify`)
- [x] Configurable quiet hours (notify_window_start/end)
- [x] Employee notification preferences — per-category opt-in/out
- [x] Notification categories: job updates, shift reminders, schedule changes, chat
- [x] Helper functions: `notify_admins()`, `notify_employee()`, `notify_clocked_in_employees()`

### QuickBooks Online Integration
- [x] OAuth2 connect/disconnect from admin settings
- [x] Push estimates to QBO with line items and customer sync
- [x] Push invoices to QBO with line items and customer sync
- [x] Automatic token refresh (refresh on 401, pre-refresh within 5 min of expiry)
- [x] Encrypted token storage at rest (Fernet via `qbo_crypto.py`)
- [x] Default "Services" item auto-creation in QBO for line item references
- [x] Sandbox and production environment support
- [x] QBO Setup Guide documentation (`QBO_SETUP_GUIDE.md`)

---

## Known Gaps / Future Work

### High Priority

- [ ] **Email delivery of estimates/invoices** — send Scope PDF or invoice to customer email directly from admin
- [ ] **Receipt search** — full-text search across transcriptions and metadata
- [ ] **Estimate approval workflow** — send estimate to customer for digital sign-off (link or email)
- [ ] **Photo-to-estimate link** — attach job photos to specific estimates/projects
- [ ] **QBO two-way sync** — pull payments and customer updates from QBO back into BDB Tools

### Medium Priority

- [ ] **Dashboard date range** — let admin filter the operations dashboard by date range (currently rolling weekly)
- [ ] **Schedule conflict detection** — warn when an employee is double-booked
- [ ] **Bulk employee time export** — export all employees in a single download rather than per-employee
- [ ] **Per-job photo PDF branding** — include company logo on job photo PDF reports
- [ ] **Estimate revision history** — track changes to line items and financial fields over time
- [ ] **Push notification analytics** — delivery rates, read rates, opt-out trends per company

### Low Priority / Nice to Have

- [ ] **Two-factor auth for admin panel** — TOTP or email-based
- [ ] **Scheduled report emails** — weekly payroll summary or job cost summary to company admin
- [ ] **Mobile PWA offline support** — cache timekeeper for use in areas without signal
- [ ] **Alembic migrations** — replace `_add_column_if_missing` with proper schema migrations
- [ ] **SQLite → PostgreSQL** — for teams requiring higher write concurrency
- [ ] **Dark mode** — CSS custom property toggle

---

## Architecture Decisions

| Decision | Rationale |
|---|---|
| SQLite over PostgreSQL | Single-server deployment; WAL mode handles concurrent reads/writes acceptably for current scale |
| Vanilla JS over React | Employee pages must load fast on slow mobile connections; no build step; fewer dependencies |
| Whisper local over API | Audio transcriptions stay private; no ongoing API cost; runs on existing hardware |
| Ollama for task extraction | Local LLM; no API cost; non-blocking failure (estimates work even if Ollama is down) |
| File lock for GPU exclusivity | Prevents two Whisper jobs from loading models simultaneously on limited-RAM hardware |
| DB-backed task queue | Works correctly with Gunicorn pre-fork workers; no Redis dependency; survives restarts |
| Single CSS file | Easy to read; no build step; consistent design tokens via CSS custom properties |
| Token URL (not subdomain) | Simpler DNS; single SSL cert; easier Cloudflare Tunnel config |
| `_add_column_if_missing` | Idempotent startup migration; safe for small schema changes without downtime |
| CSRF auto-injection | No manual token handling in templates/JS; after-request handler injects meta, hidden inputs, and fetch interceptor |
| Fernet for QBO tokens | Industry-standard symmetric encryption; tokens encrypted at rest, decrypted only for API calls |
| Mapbox over Nominatim | More reliable geocoding; better rate limits; Nominatim TOS prohibit heavy usage |
| Web Push over email | No email infrastructure needed; instant delivery; works on mobile without app install |

---

## Deployment Checklist

### First-time setup
- [ ] Clone repo, create venv, `pip install -r requirements.txt`
- [ ] Copy `.env.example` → `.env`, generate strong `SECRET_KEY`
- [ ] Set strong `ADMIN_PASSWORD` and `VIEWER_PASSWORD`
- [ ] Set `MAPBOX_TOKEN` for geocoding
- [ ] (Optional) Set `VAPID_PRIVATE_KEY` / `VAPID_PUBLIC_KEY` for push notifications
- [ ] (Optional) Set `QBO_*` vars for QuickBooks integration (see `QBO_SETUP_GUIDE.md`)
- [ ] Run `python3 -c "import app; print('OK')"` to verify
- [ ] Configure Cloudflare Tunnel pointing to `localhost:5003`
- [ ] Install systemd service: `sudo cp bdpt.service /etc/systemd/system/`
- [ ] Enable and start: `sudo systemctl enable bdpt && sudo systemctl start bdpt`
- [ ] Set up daily DB backup cron (see CODE_REFERENCE.md)

### After each code change
- [ ] `python3 -c "import app; print('OK')"` — verify clean import
- [ ] `sudo systemctl restart bdpt` — apply changes
- [ ] Check logs: `journalctl -u bdpt -f`

### Security checklist (production)
- [ ] `SECRET_KEY` is a 64-character random hex string (not the default)
- [ ] `ADMIN_PASSWORD` and `VIEWER_PASSWORD` changed from defaults
- [ ] HTTPS enforced via Cloudflare Tunnel (never run on plain HTTP)
- [ ] `QBO_ENCRYPTION_KEY` set if using QBO integration (generate with `Fernet.generate_key()`)
- [ ] VAPID keys generated and set if using push notifications
- [ ] `instance/`, `receipts/`, `estimates/`, `job_photos/`, `exports/`, `static/logos/` are writable by the service user
- [ ] Daily database backup cron is active and tested

---

## File Size Reference

Approximate sizes as of March 2026:

| File | Lines | Notes |
|---|---|---|
| `database.py` | ~5150 | All CRUD functions + schema + generic helpers |
| `routes/time_admin.py` | ~2430 | Time entries, manual entry, export, audit, job templates |
| `static/css/style.css` | ~2260 | Single unified design system |
| `routes/estimates.py` | ~1860 | Full estimate lifecycle + reports |
| `routes/admin.py` | ~1400 | Tokens, users, employees, jobs, config pages, CSV import/export |
| `pdf_generator.py` | ~820 | Receipt/estimate/invoice PDF + image processing |
| `app.py` | ~760 | Flask core, auth, CSRF, middleware, geocoding |
| `qbo_service.py` | ~410 | QBO API: token refresh, customer/estimate/invoice push |
| `routes/invoices.py` | ~360 | Invoice CRUD, line items |
| `routes/notifications.py` | ~280 | Push notifications: subscriptions, bell, prefs |
| `routes/customers.py` | ~280 | Customer CRUD |
| `task_queue.py` | ~280 | Background processing worker |
| `routes/qbo.py` | ~230 | QBO OAuth2 routes |
| `task_extractor.py` | ~150 | Ollama LLM task extraction |
| `config.py` | ~62 | Paths, env vars (VAPID, QBO, Mapbox) |
| `routes/_shared.py` | ~46 | Shared blueprint helpers |
| `qbo_crypto.py` | ~30 | Fernet encrypt/decrypt for QBO tokens |
| `transcriber.py` | ~50 | Whisper wrapper |
