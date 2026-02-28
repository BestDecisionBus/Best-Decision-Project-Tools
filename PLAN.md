# BDB Tools — Project Plan & Roadmap

## Current State (as of February 2026)

BDB Tools is a fully deployed, production-grade multi-tenant field service operations platform. All five core modules are live and in use.

---

## Completed Features

### Core Platform
- [x] Multi-tenant architecture with token-based company isolation
- [x] Six-role auth system (BDB Admin, BDB Viewer, Company Admin, Company Viewer, Scheduler, Employee)
- [x] Flask-Login for admin users + Flask session for employees
- [x] Company branding (logo upload, auto-resize, displayed on employee pages)
- [x] Security headers, rate limiting, file validation via magic bytes
- [x] Cloudflare Tunnel integration for HTTPS
- [x] systemd service for production process management
- [x] PWA manifest support ("Add to Home Screen" on iOS/Android)
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
- [x] Employee 14-day schedule view
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
- [x] Employee management with per-employee access control (receipt, estimate)
- [x] Job management with geocoding
- [x] Expense categories (with optional GL/account code field)
- [x] Common tasks (schedule note presets)
- [x] Shift types (custom schedule time presets)
- [x] Products & services catalog (with taxable flag)
- [x] Message snippets
- [x] Bulk CSV import for all 5 admin lists (append or deactivate-and-replace mode)
- [x] Inline sort order editing on all 5 list tables (auto-saves on change, no page reload)
- [x] Column resize handles on all admin list tables
- [x] Click-to-sort column headers on all admin list tables

---

## Known Gaps / Future Work

### High Priority

- [ ] **Email delivery of estimates** — send Scope PDF to customer email directly from admin
- [ ] **Employee clock-out notification** — alert admin when an employee has been clocked in for more than X hours without clocking out
- [ ] **Receipt search** — full-text search across transcriptions and metadata
- [ ] **Estimate approval workflow** — send estimate to customer for digital sign-off (link or email)
- [ ] **Photo-to-estimate link** — attach job photos to specific estimates/projects

### Medium Priority

- [ ] **Dashboard date range** — let admin filter the operations dashboard by date range (currently rolling weekly)
- [ ] **Schedule conflict detection** — warn when an employee is double-booked
- [ ] **Bulk employee time export** — export all employees in a single download rather than per-employee
- [ ] **Per-job photo PDF branding** — include company logo on job photo PDF reports
- [ ] **Estimate revision history** — track changes to line items and financial fields over time
- [ ] **Invoice generation** — produce a client invoice PDF from a completed project record

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
| Single CSS file | ~1700 lines; easy to read; no build step; consistent design tokens via CSS custom properties |
| Token URL (not subdomain) | Simpler DNS; single SSL cert; easier Cloudflare Tunnel config |
| `_add_column_if_missing` | Idempotent startup migration; safe for small schema changes without downtime |

---

## Deployment Checklist

### First-time setup
- [ ] Clone repo, create venv, `pip install -r requirements.txt`
- [ ] Copy `.env.example` → `.env`, generate strong `SECRET_KEY`
- [ ] Set strong `ADMIN_PASSWORD` and `VIEWER_PASSWORD`
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
- [ ] `instance/`, `receipts/`, `estimates/`, `job_photos/`, `exports/`, `static/logos/` are writable by the service user
- [ ] Daily database backup cron is active and tested

---

## File Size Reference

Approximate sizes as of February 2026:

| File | Lines | Notes |
|---|---|---|
| `database.py` | ~3200 | All CRUD functions + schema |
| `routes/estimates.py` | ~1600 | Largest blueprint — full estimate lifecycle + reports |
| `static/css/style.css` | ~1780 | Single unified design system |
| `routes/admin.py` | ~1050 | Tokens, users, employees, jobs, config pages, CSV import/export, inline sort endpoints |
| `routes/time_admin.py` | ~700 | Time entries, manual entry, export, audit |
| `app.py` | ~620 | Flask core, auth, middleware |
| `pdf_generator.py` | ~400 | Receipt PDF + image processing |
| `task_queue.py` | ~200 | Background processing worker |
| `task_extractor.py` | ~150 | Ollama LLM task extraction |
| `transcriber.py` | ~50 | Whisper wrapper |
| `config.py` | ~42 | Paths and environment variables |
