# BDB Tools

A multi-tenant web application that gives field service companies four essential operational tools — time tracking, receipt capture, employee scheduling, and job site photo documentation — all accessible from a mobile browser with no app install required.

---

## Features

**Timekeeper**
- GPS-tracked clock in/out from any mobile browser
- Job assignment per punch
- Manual time overrides with full audit trail
- Weekly payroll estimates with labor burden calculation
- Excel and PDF export

**Receipt Capture**
- Photograph receipts via camera or photo library
- Record voice memos describing expenses
- Automatic transcription via OpenAI Whisper
- Combined PDF generation (image + transcription + metadata)
- Job and expense category tagging

**Scheduling**
- Drag-and-drop weekly schedule builder
- Shift presets (full day, morning, afternoon, custom)
- Employee-facing schedule view (upcoming 14 days)
- Dedicated scheduler role with limited access

**Job Photos**
- Single photo capture or multi-select batch upload from device library
- Automatic EXIF orientation correction and GPS geotagging
- Photos organized by job and week
- Download as ZIP or PDF report with GPS coordinates
- Thumbnail generation for fast browsing

**Platform**
- Multi-tenant architecture — each company gets a unique URL token
- Dual authentication: Flask-Login for admins, Flask session for employees
- Six user roles: BDB Admin, BDB Viewer, Company Admin, Company Viewer, Scheduler, Employee
- Company branding (logo on all employee-facing pages)
- Context-aware admin guide (company admins see only their relevant sections)
- Comprehensive employee help page
- Security headers, rate limiting, file validation via magic bytes

---

## Tech Stack

| Component | Technology | Version |
|---|---|---|
| Language | Python | 3.12 |
| Web Framework | Flask | 3.1.0 |
| Authentication | Flask-Login | 0.6.3 |
| WSGI Server | Gunicorn | 23.0.0 |
| Database | SQLite | (stdlib) |
| Password Hashing | Werkzeug | 3.1.3 |
| Audio Transcription | OpenAI Whisper | 20250625 |
| PDF Generation | fpdf2 | 2.8.3 |
| Image Processing | Pillow | 12.1.1 |
| EXIF Manipulation | piexif | 1.1.3 |
| Spreadsheet Export | openpyxl | 3.1.5 |
| Environment Config | python-dotenv | 1.0.1 |
| Frontend | Vanilla HTML/CSS/JS | — |
| Maps | Leaflet + OpenStreetMap | — |
| Reverse Proxy | Cloudflare Tunnel | — |
| Process Manager | systemd | — |

---

## Prerequisites

- **Python 3.10+** (tested on 3.12)
- **pip** (included with Python)
- **Linux** (Ubuntu 22.04+ recommended; tested on Ubuntu 24.04 aarch64)
- **FFmpeg** (optional, improves Whisper audio handling)
- **~2 GB RAM** minimum (Whisper `base` model uses ~1 GB; increase for larger models)
- **~500 MB disk** for Python dependencies + Whisper model (plus storage for uploaded files)

For production:
- **Cloudflare Tunnel** (or another HTTPS reverse proxy)
- **systemd** (for process management)

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/BestDecisionBus/Best-Decision-Business-Tools.git
cd Best-Decision-Business-Tools
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

> Whisper downloads its model file on first use (~140 MB for `base`). This happens automatically.

### 4. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your values (see [Configuration](#configuration) below). At minimum, set a strong `SECRET_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 5. Verify Setup

```bash
python -c "import app; print('OK')"
```

This creates the database at `instance/bdb_tools.db` and seeds the default admin/viewer users.

### 6. Run the Application

**Development:**

```bash
flask run --host=0.0.0.0 --port=5003 --debug
```

**Production:**

```bash
gunicorn -c gunicorn.conf.py app:app
```

The app is now running at `http://localhost:5003`.

---

## Configuration

All configuration is via environment variables in `.env`:

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `dev-secret-change-me` | Flask session encryption key. **Must change in production.** Generate with `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `ADMIN_USERNAME` | `admin` | Default BDB admin username (created on first run) |
| `ADMIN_PASSWORD` | `admin` | Default BDB admin password. **Change immediately after first login.** |
| `VIEWER_USERNAME` | `viewer` | Default BDB viewer username |
| `VIEWER_PASSWORD` | `viewer` | Default BDB viewer password |
| `WHISPER_MODEL` | `base` | Whisper model size: `tiny` (fast, less accurate), `base` (balanced), `small`, `medium`, `large` (slow, most accurate) |
| `RATE_LIMIT` | `60` | Maximum API requests per minute per token |
| `MAX_UPLOAD_MB` | `30` | Maximum file upload size in megabytes |
| `GPS_FLAG_DISTANCE_MILES` | `0.5` | Distance threshold (miles) between a clock punch and the job site before flagging for review |

---

## Usage

### Admin Panel

**Access:** Navigate to `/admin/login` and log in with the credentials from your `.env` file.

**First-time setup:**

1. **Create a company token** — Go to Admin > Tokens > enter company name and optional logo. The system generates a 12-character token (e.g., `HB53OA964SK8`).
2. **Add jobs** — Go to Jobs > enter job name and address. Click "Geocode" to populate GPS coordinates.
3. **Add employees** — Go to Employees > enter name, ID, and optional login credentials (username/password).
4. **Share the employee URL** — Give employees the link: `https://your-domain.com/c/HB53OA964SK8`

**Key admin workflows:**

| Task | Navigation |
|---|---|
| View active clock-ins | Dashboard > "Active Punches" card |
| Correct a time entry | Employees > Time Entries > click entry > Manual Time Override |
| Create a manual entry | Employees > Time Entries > "Add Manual Entry" |
| Export payroll | Employees > Payroll Export > select date range > Download |
| Review receipts | Receipts > click submission for detail |
| Download receipt PDFs | Receipts > Browse > select month > "Download ZIP" |
| Build a schedule | Employees > Schedules > click cells to add shifts |
| Browse job photos | Jobs > Job Photos > select job > select week |
| View audit trail | Admin > Audit Log |

**Company admin portal:** Company-specific admins log in at `/company-admin/login`. They see only their own company's data and do not have access to Tokens or Users management.

### Employee Interface

**Access:** Employees open the company URL in their mobile browser: `/c/{token}` (e.g., `/c/HB53OA964SK8`).

**Login:** Enter the username and password set by the admin. Usernames are case-sensitive.

**Available tools after login:**

| Tool | How to Use |
|---|---|
| **Timekeeper** | Select a job > tap CLOCK IN. When done, return and tap CLOCK OUT. GPS is captured automatically if allowed. |
| **Receipt Capture** | Take a photo or select from library > select job and categories > record a voice memo > submit. Available only if admin has granted receipt access. |
| **Your Schedule** | View upcoming shifts for the next 14 days. |
| **Job Photos** | Select a job > take a photo or select multiple from library > add optional captions > submit. |
| **Help** | Detailed instructions for all tools, GPS setup, and common scenarios (forgot to clock out, etc.) |

**Supported file formats:**

| Type | Formats |
|---|---|
| Images | JPEG, PNG, WebP (validated via magic bytes) |
| Audio | WebM, MP4/M4A (iOS), Ogg, WAV |

---

## Project Structure

```
Best-Decision-Business-Tools/
│
├── app.py                  # Flask app, auth system, middleware, shared routes, blueprint registration
├── config.py               # Paths, environment variables, directory creation
├── database.py             # SQLite schema, migrations, all CRUD functions (1750 lines)
├── gunicorn.conf.py        # Gunicorn config: 2 workers, 300s timeout, task queue startup
├── task_queue.py           # Background worker: DB polling, file-lock GPU exclusivity, receipt processing
├── transcriber.py          # Whisper model loader and transcription
├── pdf_generator.py        # Receipt PDF generation, EXIF orientation fix, thumbnail creation
├── requirements.txt        # Python dependencies
├── bdb-tools.service       # systemd unit file for production
├── .env                    # Environment variables (not committed)
│
├── routes/
│   ├── admin.py            # Dashboard, tokens, users, employees, jobs, categories, common tasks, guide
│   ├── time_admin.py       # Time entries, manual entries, export, payroll reports, audit log
│   ├── timekeeper.py       # Employee clock in/out API, timekeeper page, help page
│   ├── receipts.py         # Receipt capture page, upload API with file validation
│   ├── receipt_admin.py    # Receipt browsing, detail view, downloads, deletion
│   ├── scheduling.py       # Schedule CRUD API, scheduler dashboard, employee schedule view
│   └── job_photos.py       # Photo capture, upload API, admin browsing, ZIP/PDF downloads
│
├── templates/
│   ├── _footer.html        # Shared footer
│   ├── capture.html        # Receipt capture (employee)
│   ├── company_home.html   # Company landing page with login and tool grid
│   ├── company_admin_login.html
│   ├── admin/              # 20+ admin panel templates
│   │   ├── _nav.html       # Two-tier navigation (main tabs + sub-nav)
│   │   ├── dashboard.html  # Stat cards, active entries, schedule, payroll, job costs
│   │   ├── guide.html      # Context-aware admin guide (BDB vs company)
│   │   └── ...             # time_entries, employees, jobs, receipts, schedules, etc.
│   ├── employee/           # Employee-facing templates
│   │   ├── timekeeper.html # Clock in/out interface
│   │   ├── help.html       # Comprehensive help with all tools documented
│   │   └── my_schedule.html
│   ├── job_photos/
│   │   └── capture.html    # Photo capture with batch upload support
│   ├── scheduler/          # Scheduler-specific views
│   └── errors/             # 404, invalid token
│
├── static/
│   ├── css/style.css       # Unified design system (single file, ~1700 lines)
│   └── logos/              # Company logos (auto-resized on upload, max 800px)
│
├── instance/
│   └── bdb_tools.db        # SQLite database (auto-created)
│
├── receipts/               # Receipt files: receipts/{token}/{YYYY-MM}/*.{jpg,webm,pdf}
├── job_photos/             # Job photos: job_photos/{token}/{job-name}/{YYYY-Www}/*.jpg
├── exports/                # Temporary export files (XLSX)
│
├── ARCHITECTURE.md         # Technical architecture documentation
├── REUSABLE_COMPONENTS.md  # Patterns and reusable code reference
├── CODE_REFERENCE.md       # Copyable code snippets by category
├── PLAN.md                 # Implementation roadmap and project plan
└── README.md               # This file
```

---

## Deployment

### Development

```bash
source venv/bin/activate
flask run --host=0.0.0.0 --port=5003 --debug
```

### Production with Gunicorn

```bash
source venv/bin/activate
gunicorn -c gunicorn.conf.py app:app
```

Gunicorn configuration (`gunicorn.conf.py`):

| Setting | Value | Notes |
|---|---|---|
| bind | `0.0.0.0:5003` | All interfaces, port 5003 |
| workers | `2` | Pre-fork workers (each loads Whisper model) |
| timeout | `300` | 5 minutes, accommodates large uploads and Whisper processing |
| post_fork | starts task_queue | Background worker for receipt transcription |

### systemd Service

Install and enable the service:

```bash
sudo cp bdb-tools.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable bdb-tools
sudo systemctl start bdb-tools
```

Check status:

```bash
sudo systemctl status bdb-tools
```

View logs:

```bash
journalctl -u bdb-tools -f
```

Restart after code changes:

```bash
sudo systemctl restart bdb-tools
```

### Important Production Notes

**Passwords:** Change `ADMIN_PASSWORD` and `VIEWER_PASSWORD` in `.env` immediately after first run. The defaults are `admin` and `viewer`.

**SECRET_KEY:** Generate a strong random key. If this changes, all existing sessions are invalidated.

**HTTPS:** Use Cloudflare Tunnel or another reverse proxy. Never run without HTTPS in production — sessions and passwords are transmitted over the network.

**Backups:** The database is a single SQLite file. Set up a daily cron job:

```bash
# Add to crontab: crontab -e
0 3 * * * cp ~/Best-Decision-Business-Tools/instance/bdb_tools.db ~/backups/bdb_tools_$(date +\%Y\%m\%d).db
0 4 * * 0 tar czf ~/backups/bdb_files_$(date +\%Y\%m\%d).tar.gz ~/Best-Decision-Business-Tools/receipts ~/Best-Decision-Business-Tools/job_photos ~/Best-Decision-Business-Tools/static/logos
```

**File permissions:** The Gunicorn process runs as the user specified in the service file. Ensure that user has read/write access to `instance/`, `receipts/`, `job_photos/`, `exports/`, and `static/logos/`.

---

## API Endpoints

### Public / Employee APIs

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/c/<token>` | None | Company home page (employee login) |
| POST | `/c/<token>` | None | Employee login form submission |
| GET | `/c/<token>/logout` | Session | Employee logout |
| GET | `/timekeeper` | Session | Timekeeper page |
| POST | `/api/clock-in` | Session | Clock in (JSON: `employee_id`, `job_id`, `latitude`, `longitude`) |
| POST | `/api/clock-out` | Session | Clock out (JSON: `employee_id`, `latitude`, `longitude`) |
| GET | `/api/employee-status` | Session | Active entry + today's entries |
| GET | `/capture` | Session | Receipt capture page |
| POST | `/api/upload` | Token | Upload receipt (FormData: `token`, `image`, `audio`, `job_id`, categories) |
| GET | `/api/status/<id>` | None | Check receipt processing status |
| GET | `/job-photos` | Session | Job photos capture page |
| POST | `/api/job-photos/upload` | Token | Upload photo (FormData: `token`, `job_id`, `image`, `caption`, GPS) |
| GET | `/api/job-photos/<id>` | None | Serve photo (add `?thumb=1` for thumbnail) |
| GET | `/schedule` | Session | Employee schedule view |
| GET | `/help` | None | Employee help page |

### Shared Data APIs

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/jobs?token=X` | Token | List active jobs for a company |
| GET | `/api/categories?token=X` | Token | List active expense categories |
| GET | `/api/common-tasks?token=X` | Token | List active common tasks |
| GET | `/api/check-username?username=X` | Login | Check if username is available |
| GET | `/api/geocode?address=X` | Login | Geocode an address via Nominatim |

### Admin Routes

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET/POST | `/admin/login` | None | Admin login |
| GET/POST | `/company-admin/login` | None | Company admin login |
| GET | `/admin/logout` | Login | Admin logout |
| GET | `/admin/` | Admin | Dashboard |
| GET/POST | `/admin/tokens` | BDB | Token (company) management |
| GET/POST | `/admin/users` | BDB Admin | BDB user management |
| GET/POST | `/admin/employees` | Admin | Employee management |
| GET/POST | `/admin/jobs` | Admin | Job management |
| GET/POST | `/admin/categories` | Admin | Expense category management |
| GET/POST | `/admin/common-tasks` | Admin | Common task management |
| GET | `/admin/time-entries` | Admin | Time entries list with filters |
| GET | `/admin/time-entries/<id>` | Admin | Time entry detail with GPS map |
| POST | `/admin/time-entries/<id>/notes` | Admin | Update admin notes |
| POST | `/admin/time-entries/<id>/status` | Admin | Change entry status |
| POST | `/admin/time-entries/<id>/manual-times` | Admin | Set manual time overrides |
| POST | `/admin/time-entries/<id>/delete` | Admin | Delete entry (with audit log) |
| GET/POST | `/admin/manual-entry` | Admin | Create manual time entry |
| GET | `/admin/export` | Admin | Payroll export page |
| GET | `/admin/audit-log` | Login | View audit trail |
| GET | `/admin/receipts` | Admin | Receipt dashboard |
| GET | `/admin/receipts/browse` | Admin | Browse receipts by company/month |
| GET | `/admin/receipts/<id>` | Admin | Receipt detail |
| GET | `/admin/receipts/download/<id>/<type>` | Admin | Download receipt file (image/audio/pdf) |
| GET | `/admin/receipts/download-zip/<token>/<month>` | Admin | Download monthly receipt ZIP |
| GET | `/admin/job-photos` | Login | Browse job photos |
| GET | `/admin/job-photos/<id>/detail` | Login | Photo detail with GPS |
| GET | `/admin/job-photos/download-zip/<job_id>/<week>` | Login | Download weekly photo ZIP |
| GET | `/admin/job-photos/download-pdf/<job_id>/<week>` | Login | Download weekly photo PDF report |
| GET | `/admin/schedules` | Login | Admin schedule view |
| GET | `/admin/guide` | Admin | Admin guide (context-aware) |

### Scheduler APIs

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/scheduler` | Scheduler | Scheduler dashboard |
| GET | `/scheduler/api/schedules` | Login | List schedules for date range |
| POST | `/scheduler/api/schedules` | Scheduler | Create schedule |
| PUT | `/scheduler/api/schedules/<id>` | Scheduler | Update schedule |
| DELETE | `/scheduler/api/schedules/<id>` | Scheduler | Delete schedule |
| POST | `/scheduler/api/employees` | Scheduler | Quick-add employee |
| POST | `/scheduler/api/jobs` | Scheduler | Quick-add job |

---

## Database Schema

11 tables with token-based multi-tenant isolation:

```
tokens ─────┬── users
             ├── employees ──── time_entries ──── audit_log
             ├── jobs ─────────┬── time_entries
             │                 ├── schedules
             │                 ├── job_photos
             │                 └── submissions
             ├── categories ──── submissions
             ├── common_tasks
             └── submissions
```

| Table | Purpose | Key Columns |
|---|---|---|
| `tokens` | Company tenants | token, company_name, logo_file, labor_burden_pct, is_active |
| `users` | Admin panel users | username, password_hash, role, token (NULL = BDB user) |
| `employees` | Company workers | name, employee_id, token, username, hourly_wage, receipt_access |
| `jobs` | Job sites | job_name, job_address, latitude, longitude, token |
| `categories` | Expense categories | name, token, sort_order |
| `time_entries` | Clock records | employee_id, job_id, clock_in/out times + GPS, manual overrides, status |
| `submissions` | Receipt uploads | token, image_file, audio_file, pdf_file, transcription, status |
| `schedules` | Work schedules | employee_id, job_id, date, start_time, end_time, shift_type |
| `job_photos` | Site photos | job_id, week_folder, image_file, thumb_file, caption, GPS |
| `common_tasks` | Schedule note presets | name, token, sort_order |
| `audit_log` | Change history | time_entry_id, action, field_changed, old_value, new_value, changed_by |

For full schema details including column types, indexes, and constraints, see [ARCHITECTURE.md](ARCHITECTURE.md#database-schema).

---

## Development

### Running in Development Mode

```bash
source venv/bin/activate
flask run --host=0.0.0.0 --port=5003 --debug
```

Debug mode enables auto-reload on file changes and detailed error pages.

### Verifying the App Loads

After any code change, verify the app can import cleanly:

```bash
python -c "import app; print('OK')"
```

### Code Style

- Python: standard library style, no formatter enforced. Functions and variables use `snake_case`.
- Templates: Jinja2 with 4-space indentation.
- CSS: single file (`static/css/style.css`), organized by section comments.
- JavaScript: vanilla ES5 (no transpilation), inline `<script>` blocks in templates.

### Database Migrations

New columns are added via `_add_column_if_missing()` in `database.py:init_db()`. This runs on every startup and is idempotent.

To add a new column:

```python
# In database.py init_db(), after the existing _add_column_if_missing calls:
_add_column_if_missing(conn, "table_name", "new_column", "TEXT DEFAULT ''")
```

No migration framework is used. For complex schema changes, consider adding [Alembic](https://alembic.sqlalchemy.org/).

### Adding a New Blueprint

1. Create `routes/new_module.py` with a Blueprint
2. Use the lazy import pattern: `def _helpers(): import app as _app; return _app`
3. Register in `app.py`: `from routes.new_module import new_bp; app.register_blueprint(new_bp)`

---

## Troubleshooting

### App fails to start with import error

```bash
# Check that all dependencies are installed
source venv/bin/activate
pip install -r requirements.txt

# Verify clean import
python -c "import app; print('OK')"
```

### Database locked errors

SQLite can report "database is locked" under heavy write concurrency. The WAL journal mode mitigates this, but if it persists:

```bash
# Check for stuck processes
fuser instance/bdb_tools.db

# Restart the service
sudo systemctl restart bdb-tools
```

### Whisper model download hangs

The Whisper model downloads on first transcription. If it hangs:

```bash
# Force download manually
python -c "import whisper; whisper.load_model('base')"
```

### Receipt stuck in "processing" status

The background task queue may have stalled:

```bash
# Check for the GPU lock file
ls -la instance/gpu_worker.lock

# Restart the service to reset workers
sudo systemctl restart bdb-tools

# If a specific submission is stuck, check the logs
journalctl -u bdb-tools --since "1 hour ago" | grep "submission"
```

### Photos not showing thumbnails on mobile

The app uses `FileReader.readAsDataURL()` for client-side thumbnails. If thumbnails don't appear:

- Verify Content Security Policy allows `img-src 'self' data:` (this is set in `app.py`)
- Ensure the file input's `value` is not cleared before the FileReader finishes
- Check browser console for CSP violations

### Logo loads slowly

Logos are auto-resized to max 800px on upload. If an old logo is still large:

```bash
# Check file sizes
ls -lh static/logos/

# Resize manually with Python
python3 -c "
from PIL import Image, ImageOps
img = Image.open('static/logos/FILENAME.png')
img = ImageOps.exif_transpose(img) or img
img.thumbnail((800, 800), Image.LANCZOS)
img.save('static/logos/FILENAME.png')
"
```

### Port already in use

```bash
# Find what's using port 5003
sudo lsof -i :5003

# Or use a different port
gunicorn -c gunicorn.conf.py -b 0.0.0.0:5004 app:app
```

### Employee can't log in

- Usernames are **case-sensitive**
- Verify the employee's token matches the company URL
- Check that the employee account is active (not deactivated)
- Check that the company token is active

---

## Related Projects

BDB Tools is a unified replacement for these standalone applications:

| App | Port | Status |
|---|---|---|
| [Timekeeper](https://github.com/BestDecisionBus/timekeeper-app) (legacy) | 5002 | Running alongside BDB Tools |
| [Receipt Capture](https://github.com/BestDecisionBus/receipt-capture) (legacy) | 5000 | Running alongside BDB Tools |
| [Statement Scanner](https://github.com/BestDecisionBus/statement-scanner) (legacy) | 5001 | Running alongside BDB Tools |

All apps share similar patterns (Flask, SQLite, Gunicorn, systemd, Cloudflare Tunnel) and are documented in the same style.

---

## Contributing

This is a private repository for Best Decision Business. To contribute:

1. **Bug reports** — Open an issue on [GitHub Issues](https://github.com/BestDecisionBus/Best-Decision-Business-Tools/issues) with steps to reproduce, expected behavior, and actual behavior.

2. **Feature requests** — Open an issue describing the use case, who it benefits, and how it should work.

3. **Pull requests** — Fork the repo, create a feature branch, make changes, and open a PR. Include:
   - Clear description of what changed and why
   - Test evidence (screenshots for UI changes, manual test results)
   - No breaking changes to existing URLs or APIs without discussion

4. **Code guidelines:**
   - Follow existing patterns (lazy imports, connection-per-function, etc.)
   - Keep employee-facing pages fast and simple (no heavy JS frameworks)
   - All database queries must filter by token for multi-tenant isolation
   - Add `_add_column_if_missing()` calls for new database columns
   - Test with `python -c "import app; print('OK')"` before pushing

---

## License

This project is proprietary software owned by Best Decision Business LLC. All rights reserved. Unauthorized copying, distribution, or modification is prohibited without express written permission.

---

## Contact & Support

**Company:** Best Decision Business LLC

**GitHub:** [BestDecisionBus](https://github.com/BestDecisionBus)

**Issues:** [GitHub Issues](https://github.com/BestDecisionBus/Best-Decision-Business-Tools/issues)

For urgent production issues, contact the system administrator directly.

---

## Acknowledgments

**Libraries and frameworks:**
- [Flask](https://flask.palletsprojects.com/) — Web framework
- [OpenAI Whisper](https://github.com/openai/whisper) — Speech-to-text transcription
- [fpdf2](https://py-pdf.github.io/fpdf2/) — PDF generation
- [Pillow](https://pillow.readthedocs.io/) — Image processing
- [Leaflet](https://leafletjs.com/) — Interactive maps in the admin panel
- [OpenStreetMap](https://www.openstreetmap.org/) — Map tiles and geocoding via Nominatim

**Design:**
- Color system inspired by [Tailwind CSS](https://tailwindcss.com/) color palette
- System font stack for native-feeling typography across all platforms
