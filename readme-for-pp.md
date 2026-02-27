# BDB Tools — PowerPoint Presentation Guide

> **How to use this file with the Claude PowerPoint plugin:**
> Open this file in the Claude for PowerPoint add-in (or paste its contents into
> the Claude chat inside PowerPoint). Each `---` divider marks a new slide.
> Image paths are relative to the `reference/` folder — place that folder in the
> same directory as your PowerPoint file, or update the paths before generating.
> Speaker notes appear in `<!-- notes: -->` blocks.
>
> **Screenshot status:** One screenshot is captured (`reference/screenshot-scheduling-add-schedule.png`).
> All other image references are placeholders. See `reference/SCREENSHOTS-NEEDED.md`
> for the full capture checklist.

---

# Slide 1 — Title Slide

## BDB Tools

**Mobile-First Field Service Operations**

*Timekeeper · Receipt Capture · Scheduling · Job Photos · Estimates*

Best Decision Business LLC

<!-- notes: Opening slide. BDB Tools is a unified web platform that replaces
four separate legacy apps and adds a new Estimates/Projects module. No app
install — runs in any mobile browser. -->

---

# Slide 2 — The Problem

## Field Service Companies Juggle Too Many Tools

- Paper time sheets cause payroll errors and disputes
- Receipts get lost before reaching the office
- Schedules live in texts and spreadsheets
- Job site photos have no organized home
- Field estimates written on paper, then re-entered in the office
- Every tool requires a separate app install

**Result:** Lost time, lost money, lost documentation

<!-- notes: Frame the pain points your audience recognizes from daily operations.
Keep this slide to a quick, relatable 30 seconds. -->

---

# Slide 3 — One Platform, Five Tools

## Everything Field Teams Need — One URL

| Tool | What It Does |
|---|---|
| **Timekeeper** | GPS clock in/out from any mobile browser |
| **Receipt Capture** | Photo + voice memo → auto-transcribed PDF |
| **Scheduling** | Drag-and-drop weekly schedule builder |
| **Job Photos** | Batch upload, GPS tagged, downloadable reports |
| **Estimates / Projects** | Field estimate capture → tracked project lifecycle |

- No app install required
- Works on any smartphone browser (iOS & Android)
- Each company gets its own private, branded URL

<!-- notes: This is the executive summary slide. If you only have 2 minutes,
spend most of it here. Emphasize "no app install" — that's the biggest objection
eliminator for field workers. -->

---

# Slide 4 — Employee Experience

## One URL. Open It. Start Working.

![Employee Home Screen](reference/screenshot-employee-home.png)

- Employee opens `yourdomain.com/c/YourToken` on their phone
- Logs in with username + password (set by admin)
- Sees a clean tool grid — tap to use any tool
- Company logo displayed on every page (your brand, not ours)

> **No app store. No install. No updates to manage.**

<!-- notes: Show the actual URL pattern. Stress that employees don't need an
Apple ID or Google account — just a phone and a browser. -->

---

# Slide 5 — Timekeeper

## GPS-Tracked Clock In / Out

![Timekeeper Clock In](reference/screenshot-timekeeper-clockin.png)

- Select a job → tap **CLOCK IN** — GPS captured automatically
- Tap **CLOCK OUT** when done — calculates hours instantly
- GPS flag alerts admin if punch location is far from the job site
- Admin can apply manual overrides with full audit trail
- Export to **Excel** or **PDF** for payroll

<!-- notes: GPS flag distance is configurable per deployment (default 0.5 miles).
All overrides are logged — who changed what, when, and from what value. -->

---

# Slide 6 — Receipt Capture

## Photo + Voice = Automatic PDF Report

![Receipt Capture](reference/screenshot-receipt-capture.png)

- Employee photographs the receipt with their phone camera
- Selects job and expense category (e.g., Materials, Fuel, Meals)
- Records a voice memo describing the purchase
- **OpenAI Whisper** transcribes the audio automatically in the background
- System generates a combined PDF: photo + transcription + metadata
- Admin downloads individual PDFs or a full monthly ZIP

<!-- notes: The voice memo step is the key differentiator — no typing on a
small screen. Whisper handles accented speech and background noise well.
Transcription happens in the background; employee doesn't wait. -->

---

# Slide 7 — Scheduling

## Drag-and-Drop Weekly Schedules

![Add Schedule Dialog](reference/screenshot-scheduling-add-schedule.png)

- Admin or scheduler builds the week in the drag-and-drop grid
- **Customizable shift types** — Full Day, Morning, Afternoon, or any named custom range
- Apply one shift to multiple days of the week in one click
- Attach a job task note to any shift
- Employees see their upcoming **14-day schedule** on their phone
- Dedicated **Scheduler role** — can manage schedules without seeing payroll data

<!-- notes: The "Apply to days" checkboxes let you schedule Mon–Fri in one
form submission. Scheduler role is perfect for a foreman or office coordinator
who shouldn't have full admin access. Shift types are fully customizable per
company in Admin > Shift Types. -->

---

# Slide 8 — Job Photos

## Organized, GPS-Tagged Site Documentation

![Job Photos Capture](reference/screenshot-job-photos-capture.png)

- Employee selects a job → photographs or batch-selects from camera roll
- **EXIF orientation** corrected automatically — photos always right-side-up
- GPS coordinates embedded in every photo
- Admin browses photos **by job and by week**
- One-click download as **ZIP** (individual files) or **PDF report** (with GPS coordinates printed)

<!-- notes: This replaces the "text me photos" workflow. Photos are organized
from the moment they're uploaded — no manual sorting. PDF report is suitable
for project close-out documentation or subcontractor invoicing. -->

---

# Slide 9 — Estimates / Projects

## From Job Site Voice Note to Tracked Project

![Field Estimate Capture](reference/screenshot-estimate-capture.png)

**In the field — employee workflow:**
- Select job → record a voice memo describing the scope of work
- Whisper transcribes automatically — no typing required
- Admin receives the transcription as a starting point for the estimate

**In the office — admin workflow:**
- Add line items: description, quantity, unit, unit price, taxable flag
- Enter customer details (name, phone, email, client budget)
- Set sales tax rate, admin notes, and customer message

<!-- notes: The employee capture eliminates the "phone call to the office"
step. The transcription gives the estimator a head start instead of a blank
form. -->

---

# Slide 10 — Estimate Lifecycle

## Pending Estimate → Active Project → Completed Job

- **Pending** — estimate created, awaiting customer decision
- **Accepted** — customer approved; document becomes `Proj #` instead of `Est #`
- **In Progress** — work underway; WIP tracking begins
- **Completed** — job finished; final cost vs estimate comparison available
- **Declined** — estimate not accepted; kept for records

**Financial columns tracked throughout:**

| Column | Description |
|---|---|
| Estimate Value | Contract price to customer |
| Est. Materials / Labor | Budgeted cost to complete |
| Actual Materials / Labor | Real costs incurred |
| Collected | Payments received from customer |
| WIP % | Completion percentage |

<!-- notes: The dual identity (Est # vs Proj #) keeps estimates and active
projects visually distinct in the list without needing separate modules. -->

---

# Slide 11 — Estimate Reports

## Three Report Formats for Every Audience

![Estimates List](reference/screenshot-estimates-list.png)

| Report | Audience | Format | Contents |
|---|---|---|---|
| **Internal PDF** | Admin / owner | PDF | All cost fields, actual vs estimated, notes |
| **Internal XLSX** | Admin / accountant | Excel | Full financial breakdown, line items, variance |
| **Scope PDF** | Customer | PDF | Line items, customer message, no internal costs |

- **Save to job folder** — links the estimate file into the job's photo/document system
- **Product catalog** — save line items for reuse across future estimates
- **Job task checklist** — auto-populated from estimate items or added manually

<!-- notes: The Scope PDF is the document you hand or email to the customer.
It shows what's included in the price without revealing your cost margins.
The Internal XLSX is ideal for bookkeepers reconciling job costs. -->

---

# Slide 12 — CFO Dashboard

## Real-Time Financial Health at a Glance

![CFO Dashboard](reference/screenshot-finance-dashboard.png)

**Configurable targets (per company):**
- Income Target % — your goal for net income as % of revenue
- Monthly Overhead $ — rent, insurance, trucks, office staff
- Cash on Hand $ — total liquid across all accounts

**Calculated automatically:**
- Overhead %, Margin Target, Markup Required

**Executive KPI cards:**
Pipeline Value · Contracted Revenue · Cash Collected · Earned Revenue · Unearned Liability · Total Costs · Net Income · Net Income % · Days Cash on Hand · Billing Position (Overbilled / Underbilled)

<!-- notes: The "Days Cash on Hand" card turns red below 30 days — an
early warning. "Billing Position" tells you instantly if you're ahead
of the work (overbilled) or behind it (underbilled / uninvoiced work). -->

---

# Slide 13 — CFO Dashboard Gauges

## Four Visual Health Indicators

![CFO Dashboard Gauges](reference/screenshot-finance-gauges.png)

| Gauge | Center = Healthy | Red = Problem |
|---|---|---|
| **Overall Margin** | ≥ 35% margin | Margin < 30% |
| **WIP Income vs Progress** | Collected = % complete | Undercollected for work done |
| **WIP Costs vs Progress** | Costs = % complete | Over budget for stage |
| **Budget Consumption** | Costs ≤ budget | Costs exceeding budget |

> All gauges update automatically as estimates are marked complete and costs are entered.

<!-- notes: The gauge view gives an owner a 5-second read on company health
without needing to interpret a table. Red needles left, green needles right. -->

---

# Slide 14 — Admin Dashboard

## Operations at a Glance

![Admin Dashboard](reference/screenshot-admin-dashboard.png)

- **Active Punches** — see who is clocked in right now
- **Weekly Labor Cost** — running total with labor burden applied
- **Job Cost Summary** — labor cost broken down by job
- **Schedule Preview** — today's and upcoming shifts
- **Payroll Estimates** — weekly estimates ready for export

<!-- notes: The operations dashboard is for daily use by the office manager.
The CFO Dashboard (separate page) is for the owner's weekly financial review. -->

---

# Slide 15 — Time Entry Management

## Full Visibility and Control Over Every Punch

![Time Entries List](reference/screenshot-admin-time-entries.png)

- Filter by employee, job, date range, or status
- GPS flag indicators highlight location anomalies
- Click any entry → view GPS map of clock-in/out location
- **Manual override:** correct times with a reason logged to audit trail
- **Statuses:** Pending → Reviewed → Approved → Paid

![Time Entry Detail with Map](reference/screenshot-admin-time-entry-detail.png)

<!-- notes: The audit log captures every field change: old value, new value,
who changed it, and when. This is your paper trail for disputes. -->

---

# Slide 16 — Payroll Export

## From Punches to Payroll in One Click

![Payroll Export](reference/screenshot-admin-payroll-export.png)

- Select employee(s) and date range
- Download **Excel** for import into payroll software
- Download **PDF** for printed payroll records
- Labor burden percentage automatically applied to estimates
- Manual entries included alongside GPS-verified punches

<!-- notes: The export includes clock-in/out times, total hours, hourly wage,
labor burden estimate, and job breakdown. Format is compatible with most
small-business payroll workflows. -->

---

# Slide 17 — Receipt Management

## From Phone to Filing Cabinet in Minutes

![Receipt Browse](reference/screenshot-admin-receipts-browse.png)

- Browse receipts by company and month
- Click any submission — see photo, transcription, and metadata side by side
- Download individual PDF or full monthly ZIP
- Category totals visible at a glance for expense reporting

![Receipt Detail](reference/screenshot-admin-receipt-detail.png)

<!-- notes: The combined PDF (image + auto-transcription + metadata) is the
output most accountants and bookkeepers want. No re-typing from paper. -->

---

# Slide 18 — Multi-Tenant Architecture

## One Platform, Many Companies

- Each client company gets a **unique 12-character token** (e.g., `HB53OA964SK8`)
- Their URL: `yourdomain.com/c/HB53OA964SK8`
- **Complete data isolation** — each company only sees its own employees, jobs, estimates, and records
- Upload your **company logo** — it appears on all employee-facing pages

**Six user roles:**

| Role | Access |
|---|---|
| BDB Admin | Everything — all companies |
| BDB Viewer | Read-only — all companies |
| Company Admin | Full access — their company only |
| Company Viewer | Read-only — their company only |
| Scheduler | Schedule management only |
| Employee | Mobile tools only |

<!-- notes: BDB Admin and BDB Viewer are for your internal team. Company Admin
and Company Viewer are for the client company's management. Employees just
need the mobile URL. -->

---

# Slide 19 — Security & Reliability

## Built for Production from Day One

- **HTTPS enforced** via Cloudflare Tunnel — no open ports
- **Rate limiting** — prevents abuse of upload endpoints
- **File validation** via magic bytes — blocks disguised malicious files
- **Session-based auth** for employees, Flask-Login for admins
- **Full audit log** — every time-entry change is recorded with old/new values
- **SQLite WAL mode** — safe concurrent reads/writes
- **Systemd service** — auto-restarts after server reboots

<!-- notes: Cloudflare Tunnel means you don't expose any ports to the internet
directly. The tunnel handles TLS termination and DDoS protection at no extra
infra cost. -->

---

# Slide 20 — Tech Stack

## Modern, Lean, Maintainable

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Web Framework | Flask 3.1 |
| Database | SQLite (WAL mode) |
| Audio Transcription | OpenAI Whisper (runs locally) |
| PDF Generation | fpdf2 |
| Image Processing | Pillow + piexif |
| Spreadsheet Export | openpyxl |
| Reverse Proxy | Cloudflare Tunnel |
| Process Manager | systemd |
| Frontend | Vanilla HTML / CSS / JS |
| Maps | Leaflet + OpenStreetMap |

> **No heavy frameworks. No paid cloud services. Audio never leaves your server.**

<!-- notes: The vanilla frontend keeps all employee pages extremely fast on
slow mobile connections. No React build step, no CDN dependency for the UI.
Whisper runs locally — transcription is private, no API key required. -->

---

# Slide 21 — Getting Started

## Up and Running in Under an Hour

**Requirements:**
- Linux server (Ubuntu 22.04+), Python 3.10+, ~2 GB RAM
- Cloudflare account (free tier) for HTTPS tunnel

**Steps:**
1. Clone the repo and create a Python virtual environment
2. `pip install -r requirements.txt`
3. Copy `.env.example` → `.env`, set a strong `SECRET_KEY`
4. `gunicorn -c gunicorn.conf.py app:app`
5. Connect Cloudflare Tunnel to port 5003
6. Log in to `/admin/login` → create first company token → add jobs and employees → share the URL

**Employees can start clocking in within minutes of setup.**

<!-- notes: First-time Whisper model download is ~140 MB and happens automatically
on the first receipt or estimate submission. Everything else is local. -->

---

# Slide 22 — Summary

## Why BDB Tools

| Challenge | Solution |
|---|---|
| Paper time sheets | GPS clock in/out — verified, auditable |
| Lost receipts | Photo + voice → auto-transcribed PDF |
| Schedule chaos | Drag-and-drop builder + 14-day employee view |
| Disorganized site photos | GPS-tagged, weekly-organized, PDF-reportable |
| Paper field estimates | Voice capture → auto-transcribed → tracked project |
| No job cost visibility | CFO Dashboard — live margin, WIP, cash position |
| Multiple app logins | One URL — any smartphone browser |

**Result:** Less admin overhead. More accurate payroll. Complete job cost visibility.

<!-- notes: This is your closing argument slide. If there's time for questions,
leave it here while you discuss. -->

---

# Slide 23 — Contact & Next Steps

## Ready to Get Started?

**Best Decision Business LLC**

GitHub: [BestDecisionBus](https://github.com/BestDecisionBus)

Issues & Feature Requests: GitHub Issues

---

*For a live demo, create a test company token and share the employee URL.
The full experience — clock in, receipt, estimate, photos, schedule — is
visible in under 10 minutes.*

<!-- notes: Offer a live walkthrough if the audience wants to see it in action.
A demo company token can be created and deleted in the admin panel in under
a minute. The employee URL works on any phone in the room. -->

---

## Appendix A — Full Employee Tool List

| Tool | URL | Access Control |
|---|---|---|
| Company Home / Login | `/c/{token}` | Public |
| Timekeeper | `/timekeeper` | All employees |
| Receipt Capture | `/capture` | Admin-granted per employee |
| Job Photos | `/job-photos` | All employees |
| Field Estimate | `/estimate` | Admin-granted per employee |
| My Estimates | `/my-estimates` | Admin-granted per employee |
| My Schedule | `/schedule` | All employees |
| Help | `/help` | Public |

---

## Appendix B — Admin Module Reference

| Module | URL | Notes |
|---|---|---|
| Dashboard | `/admin/` | Operations overview |
| CFO Dashboard | `/admin/finance` | Financial KPIs and gauges |
| Estimates / Projects | `/admin/estimates` | Full lifecycle management |
| Time Entries | `/admin/time-entries` | GPS-verified punch records |
| Payroll Export | `/admin/export` | Excel / PDF download |
| Receipts | `/admin/receipts` | Browse, detail, ZIP download |
| Job Photos | `/admin/job-photos` | Weekly browse, ZIP/PDF download |
| Schedules | `/admin/schedules` | Read-only admin view |
| Scheduler Dashboard | `/scheduler` | Edit view (Scheduler role) |
| Employees | `/admin/employees` | Add, edit, access control |
| Jobs | `/admin/jobs` | Add, geocode, manage |
| Products & Services | `/admin/products-services` | Estimate line-item catalog |
| Shift Types | `/admin/shift-types` | Custom schedule presets |
| Categories | `/admin/categories` | Receipt expense categories |
| Common Tasks | `/admin/common-tasks` | Schedule note presets |
| Message Snippets | `/admin/message-snippets` | Reusable text blocks |
| Tokens | `/admin/tokens` | Company management (BDB only) |
| Users | `/admin/users` | Admin user management (BDB only) |
| Audit Log | `/admin/audit-log` | Time entry change history |
| Admin Guide | `/admin/guide` | Context-aware help |

---

## Appendix C — Database Tables (18 total)

| Table | Purpose |
|---|---|
| `tokens` | Company tenants with branding and finance targets |
| `users` | Admin panel users (BDB and company) |
| `employees` | Company workers with access control flags |
| `jobs` | Job sites with geocoded GPS coordinates |
| `categories` | Expense categories for receipt tagging |
| `common_tasks` | Preset notes for schedule entries |
| `shift_types` | Named shift time ranges per company |
| `time_entries` | Clock records with GPS and manual overrides |
| `submissions` | Receipt uploads with transcription status |
| `submission_categories` | Receipt → expense category join |
| `schedules` | Employee schedule assignments |
| `job_photos` | GPS-tagged site photos by job and week |
| `estimates` | Estimate/project records with full financial columns |
| `estimate_items` | Line items with price, cost, quantity, taxable flag |
| `products_services` | Reusable product/service catalog for estimates |
| `message_snippets` | Reusable text blocks for estimate messages |
| `job_tasks` | Per-job task checklists tied to estimates |
| `audit_log` | Field-level change history for time entries |

---

## Appendix D — Screenshot Reference

All images live in the `reference/` folder alongside this file.
See `reference/SCREENSHOTS-NEEDED.md` for the full capture checklist,
recommended viewport sizes, and URL paths.

**Captured:**

| File | Content |
|---|---|
| `reference/screenshot-scheduling-add-schedule.png` | Add Schedule dialog — scheduling module |

**Placeholders (23 screenshots still needed)** — see `reference/SCREENSHOTS-NEEDED.md`
