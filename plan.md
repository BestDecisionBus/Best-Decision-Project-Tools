# Customer Master Record Implementation Plan

## Context

BDB Tools currently stores customer contact info as flat fields on `estimates` (`customer_name`, `customer_phone`, `customer_email`, `customer_message`). The goal is to promote customers to a first-class master record linked to both jobs and estimates, enabling relationship management, history tracking, and cleaner data entry — without breaking any existing production functionality.

---

## Pre-Flight (Operator)

```bash
cp instance/bdb_tools.db instance/bdb_tools_BACKUP_$(date +%Y%m%d_%H%M%S).db
```

Confirm backup exists before writing any code.

---

## Phase 1 — Database Schema

**File:** `database.py`

Add inside `init_db()`, after all existing `CREATE TABLE IF NOT EXISTS` blocks:

```python
conn.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        token         TEXT NOT NULL,
        company_name  TEXT NOT NULL,
        customer_name TEXT NOT NULL DEFAULT '',
        phone         TEXT DEFAULT '',
        email         TEXT DEFAULT '',
        notes         TEXT DEFAULT '',
        is_active     INTEGER DEFAULT 1,
        sort_order    INTEGER DEFAULT 0,
        created_at    TEXT NOT NULL,
        FOREIGN KEY (token) REFERENCES tokens(token)
    )
""")
conn.execute(
    "CREATE INDEX IF NOT EXISTS idx_customers_token ON customers(token)"
)
```

Add after all existing `_add_column_if_missing` calls:

```python
_add_column_if_missing(conn, "jobs",      "customer_id", "INTEGER DEFAULT NULL")
_add_column_if_missing(conn, "estimates", "customer_id", "INTEGER DEFAULT NULL")
```

**Verify:**
- [ ] `python3 -c "import app; print('OK')"`
- [ ] `python3 -c "import database; database.init_db(); print('schema OK')"`
- [ ] `sqlite3 instance/bdb_tools.db ".schema customers"` — full CREATE TABLE shown
- [ ] `sqlite3 instance/bdb_tools.db ".schema jobs"` — `customer_id` column present
- [ ] `sqlite3 instance/bdb_tools.db ".schema estimates"` — `customer_id` column present
- [ ] Restart app — existing pages (admin dashboard, timekeeper, receipts, schedule, estimates list) all load

---

## Phase 2 — Database CRUD Functions

**File:** `database.py`

Add all customer CRUD functions following the existing one-connection-per-function pattern.

### New functions to add:

**`_normalize_customer_company(company_name, customer_name) -> str`**
- If company_name is blank, return customer_name as company_name

**`get_customers_by_token(token_str, active_only=False) -> list`**
- Filter by token, optionally filter `is_active = 1`
- Order by `sort_order ASC, company_name ASC`

**`get_customer(customer_id, token_str=None) -> dict | None`**
- Optionally filter by token for security

**`create_customer(company_name, customer_name, phone, email, notes, token_str, sort_order=0) -> int`**
- Apply `_normalize_customer_company` before INSERT
- Return `lastrowid`

**`update_customer(customer_id, company_name, customer_name, phone, email, notes, token_str) -> None`**
- `WHERE id = ? AND token = ?` (token guard in SQL, not just route layer)

**`toggle_customer(customer_id, token_str) -> None`**
- `SET is_active = 1 - is_active WHERE id = ? AND token = ?`

**`update_customer_sort_order(customer_id, sort_order, token_str) -> None`**
- `WHERE id = ? AND token = ?`

**`delete_customer(customer_id, token_str) -> bool`**
- Count linked jobs AND estimates scoped to token before deleting
- Return `False` if either count > 0
- `DELETE WHERE id = ? AND token = ?`

**`get_jobs_by_customer(customer_id, token_str) -> list`**
- `ORDER BY job_name ASC` (column is `job_name`, not `name`)

**`get_estimates_by_customer(customer_id, token_str) -> list`**
- `ORDER BY created_at DESC`

**`link_job_to_customer(job_id, customer_id, token_str) -> None`**

**`link_estimate_to_customer(estimate_id, customer_id, token_str) -> None`**

**`get_jobs_with_customer(token_str, active_only=False) -> list`**
- LEFT JOIN customers to add `customer_company_name`, `customer_contact_name`
- `ORDER BY j.sort_order ASC, j.job_name ASC` (column is `job_name`, not `name`)

### Modify existing functions:

**`create_job()`** — add `customer_id=None` parameter, include in INSERT, return `lastrowid`

**`update_job()`** — add `customer_id=None` parameter, include in UPDATE

**`update_estimate()`** — add `"customer_id"` to the `allowed` set (whitelist)

**Smoke test:**
```python
import database
cid = database.create_customer("", "John Smith", "555-1234", "j@example.com", "", "TEST_TOKEN")
c = database.get_customer(cid)
assert c["company_name"] == "John Smith"
database.delete_customer(cid, "TEST_TOKEN")
print("Phase 2 OK")
```

**Verify:**
- [ ] `python3 -c "import app; print('OK')"` — no errors
- [ ] Smoke test passes
- [ ] Restart app — all existing pages still load

---

## Phase 3 — Customers Blueprint

**New file:** `routes/customers.py`

Follow the exact blueprint pattern from existing route files (lazy `_helpers()` import, `@login_required`, `_app._verify_token_access(token_str)` on all writes).

**Token selection in `admin_customers`:** Use `_app._get_selected_token(tokens)` (already in `app.py` lines 310–343). Do NOT re-implement this logic manually — it handles session persistence, URL params, multi-token users, and stale-token clearing.

### Routes:

| Method | Path | Handler |
|---|---|---|
| GET | `/admin/customers` | `admin_customers` — list with company selector |
| POST | `/admin/customers/create` | `admin_customer_create` |
| GET | `/admin/customers/<id>` | `admin_customer_detail` |
| POST | `/admin/customers/<id>/edit` | `admin_customer_edit` |
| POST | `/admin/customers/<id>/toggle` | `admin_customer_toggle` |
| POST | `/admin/customers/<id>/delete` | `admin_customer_delete` |
| POST | `/admin/customers/<id>/sort` | `admin_customer_sort` (returns 204) |
| POST | `/admin/customers/link-job` | `admin_link_job_to_customer` |
| POST | `/admin/customers/link-estimate` | `admin_link_estimate_to_customer` |
| GET | `/admin/customers/<id>/json` | `admin_customer_json` (returns JSON dict) |

**Register in `app.py`:**
```python
from routes.customers import customers_bp
app.register_blueprint(customers_bp)
```

**Verify:**
- [ ] `python3 -c "import app; print('OK')"` — no errors, no circular imports
- [ ] All existing admin routes still respond correctly

---

## Phase 4 — Templates

Templates are **standalone HTML files** — they do NOT use `extends`. They `{% include 'admin/_nav.html' %}` at the top. Follow the exact structure of `templates/admin/employees.html` or `categories.html`.

### New file: `templates/admin/customers.html`

- `{% include 'admin/_nav.html' %}`
- Flash messages block (`get_flashed_messages(with_categories=true)`)
- Company selector (BDB multi-company pattern — show dropdown only if `current_user.is_bdb or tokens|length > 1`)
- Add Customer form in a `<div class="meta-card">` with `form-row` / `form-group` layout:
  - Company / Client Name (`company_name`) — helper text: "If left blank, contact name will be used"
  - Contact Name (`customer_name`) — required, red asterisk
  - Phone, Email, Notes (textarea)
- Customer list: `<table class="resizable sortable">`
  - Columns: Company/Client Name (link to detail), Contact Name, Phone, Email, Sort Order, Status badge, Actions (`data-no-sort`)
  - Sort Order: `<input class="sort-input" data-endpoint="/admin/customers/{{ c.id }}/sort">`
  - Status: `<span class="badge badge-active/badge-inactive">`
  - Actions: View (`btn-blue btn-sm`), Toggle (`btn-orange btn-sm`)

### New file: `templates/admin/customer_detail.html`

- Customer info card with edit form (POST to `admin_customer_edit`)
- Linked Jobs section — table of linked jobs + inline form to link additional jobs (filter: same token, not already linked to this customer)
- Linked Estimates section — table of linked estimates + inline form to link additional estimates (same filter)
- Danger Zone card — Delete button (`onsubmit="return confirm(...)"`) and Toggle Active/Inactive

**Verify:**
- [ ] `/admin/customers` renders — no Jinja2 errors
- [ ] Create customer with no company name → `company_name` auto-populated (check DB)
- [ ] Create customer with both fields → `company_name` saved as entered
- [ ] Detail page renders
- [ ] Edit saves, redirects to detail
- [ ] Toggle updates badge
- [ ] Delete with no linked records → success
- [ ] Delete with linked records → blocked, error flash
- [ ] Sort order saves without page reload (204)
- [ ] All existing admin pages still load

---

## Phase 5 — Job Management: Add Customer Selector

**File: `routes/time_admin.py`** — ⚠️ NOT `routes/admin.py`. Job routes live in `time_admin_bp`.

In `admin_job_create` (~line 343, POST handler):
```python
customer_id = request.form.get("customer_id", type=int)
database.create_job(job_name, job_address, latitude, longitude, token_str, customer_id=customer_id)
```

In `admin_job_update` (~line 365, POST handler):
```python
# Form POST path:
customer_id = request.form.get("customer_id", type=int)
# JSON path (data dict):
customer_id = data.get("customer_id", type=int)  # if applicable
database.update_job(job_id, job_name, job_address, latitude, longitude, customer_id=customer_id)
```

Pass to template:
```python
customers = database.get_customers_by_token(token_str, active_only=True)
```

Switch job list query from `get_jobs_by_token` → `get_jobs_with_customer` to include customer name.

**File: `templates/admin/jobs.html`**
- Add Customer column to job list table (show `customer_company_name` or "—")
- Add customer `<select>` to create form
- Add customer `<select>` to inline edit row; update `saveJob()` JS to include `customer_id` in JSON payload

**Verify:**
- [ ] Job list shows Customer column, existing jobs show "—"
- [ ] Create job with customer → `customer_id` in DB
- [ ] Create job without customer → `customer_id = NULL`, no error
- [ ] Inline edit assigns customer correctly
- [ ] Customer detail shows linked job
- [ ] All existing job functionality works (geocoding, activate/deactivate, sort)

---

## Phase 6 — Estimates: Add Customer Selector

**File: `routes/estimates.py`**

In estimate create route (~line 534):
```python
customer_id = request.form.get("customer_id", type=int)
if customer_id:
    database.link_estimate_to_customer(est["id"], customer_id, token_str)
```

In estimate update route (~line 628): add `customer_id` to the `updates` dict (it's already in the `allowed` set from Phase 2):
```python
if "customer_id" in data:
    raw = data["customer_id"]
    updates["customer_id"] = int(raw) if raw else None
```

Pass to template context:
```python
customers = database.get_customers_by_token(token_str, active_only=True)
```

**File: `templates/admin/estimate_detail.html`**
- Add customer `<select>` ABOVE the existing customer contact fields
- `onchange="onCustomerSelect(this)"` — fetch `/admin/customers/<id>/json` and auto-fill `customer_name`, `customer_phone`, `customer_email` **only if those fields are currently blank** (never overwrite)
- Include `customer_id` in `saveEstimate()` JSON payload

**Verify:**
- [ ] Customer dropdown visible on estimate edit
- [ ] Auto-fill works on blank fields; does NOT overwrite existing data
- [ ] `customer_id` persists after save (check DB)
- [ ] Customer detail shows linked estimate
- [ ] Estimate list still loads
- [ ] PDF generation still works
- [ ] CFO dashboard still loads
- [ ] Approval status workflows unaffected

---

## Phase 7 — Navigation

**File: `templates/admin/_nav.html`** — ⚠️ NOT `admin_base.html`

Add Customers link near the Jobs group. Use the existing `turl()` macro and `ep` variable (already in this file):

```jinja2
<a href="{{ turl('customers.admin_customers') }}"
   {% if ep and ep.startswith('customers.') %}class="active"{% endif %}>
    Customers
</a>
```

**Verify:**
- [ ] "Customers" link appears for all user roles
- [ ] Active state highlights on any `customers.*` route
- [ ] Link passes current token correctly for BDB users
- [ ] All other nav links still work

---

## Phase 8 — Final Integration Test

### Scenario A — Full Customer Lifecycle
1. Log in as Company Admin
2. Navigate to Customers — list is empty
3. Create customer with only Contact Name = "Bob Johnson" (no company name)
   - Verify `company_name = "Bob Johnson"` in DB
4. Create "Smith Roofing" / "Jim Smith"
5. Navigate to Jobs — assign "Smith Roofing" to an existing job
6. Navigate to Estimates — link "Smith Roofing" to an existing estimate
7. Customer detail for "Smith Roofing" — verify job and estimate appear
8. Edit customer — change phone/email — verify saves
9. Attempt delete of "Smith Roofing" — blocked (has linked records)
10. Delete "Bob Johnson" — success

### Scenario B — Existing Data Unaffected
- [ ] Clock employee in/out — no errors
- [ ] Upload receipt — processing completes
- [ ] View schedule — loads
- [ ] View job photos — loads
- [ ] CFO Dashboard — all KPIs display
- [ ] Existing estimate — all fields and PDF work
- [ ] Payroll export — XLSX downloads

### Scenario C — Multi-Tenant Isolation
- [ ] Log in as BDB Admin — switch between two companies
- [ ] Company A customers do NOT appear in Company B list
- [ ] Job linked to Company A customer not visible in Company B

### Final Checklist
- [ ] All Scenario A steps pass
- [ ] All Scenario B steps pass
- [ ] All Scenario C steps pass
- [ ] `journalctl -u bdpt -f` — no errors during test run
- [ ] `python3 -c "import app; print('OK')"` — still prints OK
- [ ] Database backup exists from before Phase 1

---

## Rollback

```bash
sudo systemctl stop bdpt
cp instance/bdb_tools_BACKUP_[timestamp].db instance/bdb_tools.db
git stash  # or git checkout -- .
sudo systemctl start bdpt
python3 -c "import app; print('OK')"
```

---

## Critical Files Reference

| File | Change |
|---|---|
| `database.py` | Add `customers` table in `init_db()`, all CRUD functions, update `create_job`/`update_job`, add `customer_id` to `update_estimate` allowed set |
| `routes/customers.py` | **New file** — full CRUD blueprint |
| `routes/time_admin.py` | Job create/edit routes — add `customer_id` |
| `routes/estimates.py` | Estimate create/update routes — add `customer_id` |
| `app.py` | Register `customers_bp` |
| `templates/admin/customers.html` | **New** — customer list |
| `templates/admin/customer_detail.html` | **New** — customer detail/edit |
| `templates/admin/jobs.html` | Add Customer column and selector |
| `templates/admin/estimate_detail.html` | Add customer selector + JS auto-fill |
| `templates/admin/_nav.html` | Add Customers nav link |

## Do Not Touch

`routes/timekeeper.py`, `routes/time_admin.py` (except job routes), `routes/receipts.py`, `routes/receipt_admin.py`, `routes/scheduling.py`, `routes/job_photos.py`, `task_queue.py`, `task_extractor.py`, `transcriber.py`, `pdf_generator.py`, `config.py`

---

## Notes vs. Original Prompt

These are corrections relative to the source prompt. Review before executing.

### 1. CRITICAL: Job routes are in `routes/time_admin.py`, not `routes/admin.py`
The prompt's Appendix and Phase 5 both say `routes/admin.py`. The actual job routes (`admin_job_create`, `admin_job_update`) live in `routes/time_admin.py` registered as `time_admin_bp`. Editing `routes/admin.py` would have no effect.

### 2. CRITICAL: Column name is `job_name`, not `name`
The prompt's `get_jobs_with_customer` uses `ORDER BY j.name ASC` and `get_jobs_by_customer` uses `ORDER BY name ASC`. The column is `job_name`. Both would throw `OperationalError: no such column: name` at runtime.

### 3. Nav template is `_nav.html`, not `admin_base.html`
Templates do not use Jinja2 `extends`. They `{% include 'admin/_nav.html' %}`. Phase 7 must target `templates/admin/_nav.html` and use the `turl()` macro and `ep` variable already present there.

### 4. All mutating DB functions should include `token` in WHERE clause
The prompt's versions of `update_customer`, `toggle_customer`, `delete_customer`, and `update_customer_sort_order` filter only by `customer_id`. Adding `AND token = ?` to every mutating query provides defense-in-depth — even if a route's `_verify_token_access` call were bypassed, the DB layer wouldn't cross tenant boundaries. `delete_customer` also needs token-scoped counts to avoid false blocking across tenants.

### 5. Use `_get_selected_token()` — don't re-implement token selection
The prompt's `admin_customers` route manually re-implements BDB/company token selection logic. `app.py` already has `_get_selected_token(tokens)` (lines 310–343) that handles session persistence, URL params, multi-token company users, and stale-token clearing. The blueprint should call it to match every other admin section's behavior.

### 6. `create_job()` should accept `customer_id` directly in INSERT
The prompt suggests creating the job then calling `link_job_to_customer()`. Simpler to add `customer_id=None` directly to `create_job()`'s signature and INSERT. Consistent with how estimates handle `customer_id`.

### 7. `update_estimate_customer()` is redundant
The prompt adds a separate `update_estimate_customer()` function. `update_estimate()` already uses a kwargs + whitelist pattern. Adding `"customer_id"` to the existing `allowed` set is sufficient and keeps all estimate field updates in one place.
