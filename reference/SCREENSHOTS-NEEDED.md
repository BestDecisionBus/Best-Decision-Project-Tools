# BDB Tools — Reference Screenshots for PowerPoint

Use this file as a capture checklist. Each screenshot listed here corresponds to
a slide in `readme-for-pp.md`. Name files exactly as shown so the image links in
the presentation file resolve correctly.

---

## Captured (already in this folder)

| File | Slide | What it shows |
|---|---|---|
| `screenshot-scheduling-add-schedule.png` | Slide 7 – Scheduling | "Add Schedule" dialog: employee/job dropdowns, day-of-week checkboxes, shift preset |

---

## Still Needed

Capture these from a live or demo instance of the app.

**Recommended viewport sizes:**
- Employee-facing screens: Chrome DevTools > Device Toolbar > iPhone 14 (390 × 844)
- Admin screens: Full desktop width (1280 px minimum)
- Blur or replace real employee names, addresses, and dollar amounts before sharing externally

---

### Employee-Facing Screens

| File to save as | URL / path | Slide | What to show |
|---|---|---|---|
| `screenshot-employee-home.png` | `/c/{token}` | Slide 4 | Company landing page with tool-grid icons and company logo |
| `screenshot-timekeeper-clockin.png` | `/timekeeper` | Slide 5 | Clock In screen with job selector and big CLOCK IN button |
| `screenshot-timekeeper-clockout.png` | `/timekeeper` | Slide 5 | Active punch state with elapsed time and CLOCK OUT button |
| `screenshot-receipt-capture.png` | `/capture` | Slide 6 | Receipt capture: camera button, job dropdown, category tags, voice memo button |
| `screenshot-job-photos-capture.png` | `/job-photos` | Slide 8 | Job photos: multi-select file input, caption field, job dropdown |
| `screenshot-estimate-capture.png` | `/estimate` | Slide 9 | Field estimate: job selector, voice memo record button |
| `screenshot-employee-schedule.png` | `/schedule` | — | 14-day schedule list with shift times and job names |

### Admin — Estimates & Projects

| File to save as | URL / path | Slide | What to show |
|---|---|---|---|
| `screenshot-estimates-list.png` | `/admin/estimates` | Slide 11 | Estimates list: status badges, Est/Proj #, value, estimated vs actual cost columns |
| `screenshot-estimate-detail.png` | `/admin/estimates/{id}` | Slide 9 | Estimate detail: line items, customer info, financial fields, approval status |
| `screenshot-estimate-reports.png` | `/admin/estimates/{id}` | Slide 11 | Report buttons section: PDF, XLSX, Scope PDF |

### Admin — CFO Dashboard

| File to save as | URL / path | Slide | What to show |
|---|---|---|---|
| `screenshot-finance-dashboard.png` | `/admin/finance` | Slide 12 | Full CFO Dashboard: configurable targets row + KPI card grid |
| `screenshot-finance-gauges.png` | `/admin/finance` | Slide 13 | The four health gauge dials (scroll down past KPI cards) |

### Admin — Operations

| File to save as | URL / path | Slide | What to show |
|---|---|---|---|
| `screenshot-admin-dashboard.png` | `/admin/` | Slide 14 | Dashboard stat cards (active punches, weekly labor, job cost) |
| `screenshot-admin-time-entries.png` | `/admin/time-entries` | Slide 15 | Time entries list with GPS flag indicators |
| `screenshot-admin-time-entry-detail.png` | `/admin/time-entries/{id}` | Slide 15 | Entry detail with GPS map, manual override fields |
| `screenshot-admin-payroll-export.png` | `/admin/export` | Slide 16 | Payroll export with date range and download buttons |
| `screenshot-admin-receipts-browse.png` | `/admin/receipts/browse` | Slide 17 | Monthly receipt browser |
| `screenshot-admin-receipt-detail.png` | `/admin/receipts/{id}` | Slide 17 | Receipt detail: photo + transcription + metadata side by side |
| `screenshot-admin-job-photos.png` | `/admin/job-photos` | Slide 8 | Weekly photo grid for a job |
| `screenshot-admin-schedules.png` | `/admin/schedules` | Slide 7 | Weekly schedule grid (admin read-only view) |

### Admin — Configuration Pages

| File to save as | URL / path | Slide | What to show |
|---|---|---|---|
| `screenshot-admin-tokens.png` | `/admin/tokens` | Slide 18 | Token list with company names, logos, active/inactive toggle |
| `screenshot-admin-employees.png` | `/admin/employees` | Slide 18 | Employee list with access control toggles |
| `screenshot-admin-products-services.png` | `/admin/products-services` | Appendix B | Products & services catalog list |
| `screenshot-admin-audit-log.png` | `/admin/audit-log` | Slide 19 | Audit log table with old/new value change history |

---

## Capture Workflow

1. **Start the app:** `source venv/bin/activate && flask run --host=0.0.0.0 --port=5003 --debug`
2. **Admin login:** Browse to `/admin/login` — credentials in `.env`
3. **Create a demo company:** Admin > Tokens > add a test company with a logo
4. **Add demo data:** Add 2–3 jobs, 2–3 employees, a few time entries and an estimate
5. **Employee screens:** Open `/c/{token}` in Chrome mobile emulation (390 × 844) and log in as an employee
6. **Admin screens:** Switch back to desktop width for admin panel shots
7. **CFO Dashboard:** Enter some income target and overhead values first so the gauges show non-zero data
8. **Save files** into this `reference/` folder with exact filenames from the table above
