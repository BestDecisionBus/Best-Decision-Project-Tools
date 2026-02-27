# BDB Tools — Reusable Components & Patterns

Reference for patterns used consistently across the codebase. Follow these when adding new features.

---

## Blueprint Pattern

Every route module follows the same structure:

```python
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import current_user, login_required
import database

my_bp = Blueprint('my_module', __name__)

# Lazy import to avoid circular imports with app.py
def _helpers():
    import app as _app
    return _app

@my_bp.route("/admin/my-page")
@login_required
def my_page():
    _app = _helpers()
    tokens = _app._get_tokens_for_user()
    ...
```

Register in `app.py`:
```python
from routes.my_module import my_bp
app.register_blueprint(my_bp)
```

---

## Database Connection Pattern

One connection per function. Never share connections between requests.

```python
def get_something(id):
    conn = get_db()
    row = conn.execute("SELECT * FROM table WHERE id = ?", (id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_something(field1, field2, token_str):
    conn = get_db()
    now = datetime.now().isoformat()
    cur = conn.execute(
        "INSERT INTO table (field1, field2, token, created_at) VALUES (?, ?, ?, ?)",
        (field1, field2, token_str, now),
    )
    conn.commit()
    conn.close()
    return cur.lastrowid
```

**Always filter by token** for tenant-scoped tables:
```python
rows = conn.execute(
    "SELECT * FROM table WHERE token = ? AND is_active = 1",
    (token_str,)
).fetchall()
```

---

## Token Access Control Pattern

Used at the top of every admin route that touches company data:

```python
@my_bp.route("/admin/my-page")
@login_required
def my_page():
    _app = _helpers()
    tokens = _app._get_tokens_for_user()

    # BDB users pick token from query param; company users always use their own
    if not current_user.is_bdb:
        token_str = current_user.token
    else:
        token_str = request.args.get("token", "")
        if not token_str and tokens:
            token_str = tokens[0]["token"]

    selected_token = database.get_token(token_str) if token_str else None
    ...
```

For POST handlers, verify access before writing:
```python
if request.method == "POST":
    _app._verify_token_access(token_str)
    # ... write to database
```

---

## Employee Session Check Pattern

Employee-facing routes check `session` instead of `current_user`:

```python
@my_bp.route("/my-tool")
def my_tool():
    employee_id = session.get("employee_id")
    token_str = session.get("token")
    if not employee_id or not token_str:
        return redirect(url_for("timekeeper.company_home", token_str=token_str or ""))
    ...
```

---

## Multi-Company Selector (BDB Admin)

Standard pattern for pages where BDB admins can switch between companies:

**Template:**
```html
{% if current_user.is_bdb %}
    {% if tokens|length > 1 %}
    <div class="form-group" style="max-width: 300px; margin-bottom: 24px;">
        <label for="token-select">Company</label>
        <select id="token-select" onchange="window.location.href='?token=' + this.value">
            {% for t in tokens %}
            <option value="{{ t.token }}"
                {% if selected_token and selected_token.token == t.token %}selected{% endif %}>
                {{ t.company_name }}
            </option>
            {% endfor %}
        </select>
    </div>
    {% endif %}
{% else %}
    {% if selected_token %}
    <p style="font-size: 14px; color: var(--gray-500); margin-bottom: 16px;">
        Company: <strong>{{ selected_token.company_name }}</strong>
    </p>
    {% endif %}
{% endif %}
```

---

## Flash Messages

Always use categories `success` or `error`:

```python
flash("Record saved.", "success")
flash("All fields are required.", "error")
```

Template (include in every admin template that handles forms):
```html
{% with messages = get_flashed_messages(with_categories=true) %}
{% for category, message in messages %}
<div class="flash flash-{{ category }}">{{ message }}</div>
{% endfor %}
{% endwith %}
```

---

## Adding a New Database Column

In `database.py`, inside `init_db()`, after existing `_add_column_if_missing` calls:

```python
_add_column_if_missing(conn, "table_name", "new_column", "TEXT DEFAULT ''")
_add_column_if_missing(conn, "table_name", "new_number", "REAL DEFAULT 0")
_add_column_if_missing(conn, "table_name", "new_flag", "INTEGER DEFAULT 0")
```

This runs on every startup and is idempotent — safe to deploy without downtime.

---

## Audit Log Pattern

Used for time entry changes. Call after any modification:

```python
conn.execute(
    """INSERT INTO audit_log
       (time_entry_id, token, action, field_changed, old_value, new_value,
        changed_by, reason, timestamp)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    (entry_id, token_str, "field_updated", "field_name",
     str(old_value), str(new_value), current_user.username, reason, now),
)
```

Common action strings: `manual_entry_created`, `time_override`, `status_change`, `entry_deleted`, `notes_updated`.

---

## File Upload Validation

Magic byte check before saving any uploaded file:

```python
JPEG_SIG = b'\xff\xd8\xff'
PNG_SIG = b'\x89PNG'
WEBP_SIG = b'RIFF'

def _validate_image(file_obj):
    header = file_obj.read(12)
    file_obj.seek(0)
    return (
        header[:3] == JPEG_SIG or
        header[:4] == PNG_SIG or
        (header[:4] == WEBP_SIG and header[8:12] == b'WEBP')
    )
```

Audio format validation follows the same pattern — see `routes/receipts.py` and `routes/estimates.py` for the full `AUDIO_SIGNATURES` list.

---

## Admin Table Pattern

Standard responsive table with action buttons:

```html
<div class="table-responsive">
    <table class="admin-table">
        <thead>
            <tr>
                <th>Name</th>
                <th>Status</th>
                <th></th>
            </tr>
        </thead>
        <tbody>
            {% for item in items %}
            <tr>
                <td>{{ item.name }}</td>
                <td>
                    {% if item.is_active %}
                    <span class="badge badge-active">Active</span>
                    {% else %}
                    <span class="badge badge-inactive">Inactive</span>
                    {% endif %}
                </td>
                <td style="display: flex; gap: 6px;">
                    <a href="{{ url_for('module.detail', id=item.id) }}"
                       class="btn btn-blue btn-sm">View</a>
                    <form method="POST"
                          action="{{ url_for('module.toggle', id=item.id) }}"
                          style="display: inline;">
                        <button type="submit" class="btn btn-sm">
                            {{ 'Deactivate' if item.is_active else 'Activate' }}
                        </button>
                    </form>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
```

---

## Badge CSS Classes

| Class | Color | Use for |
|---|---|---|
| `badge-active` | Green | Active status, completed |
| `badge-inactive` | Gray | Inactive, disabled |
| `badge-review` | Yellow/amber | Needs review, pending |
| `badge-complete` | Green | Completed time entries |
| `badge-manual` | Blue | Manual clock method |
| `badge-gps` | Blue-gray | GPS clock method |

---

## Button CSS Classes

| Class | Color | Use for |
|---|---|---|
| `btn btn-blue` | Blue | Primary action, view/navigate |
| `btn btn-green` | Green | Create, save, confirm |
| `btn btn-red` | Red | Delete, destructive actions |
| `btn btn-sm` | — | Modifier — smaller button for tables |

---

## Form Row Layout

```html
<div class="form-row">
    <div class="form-group" style="flex: 1;">
        <label for="field1">Label <span style="color: var(--red);">*</span></label>
        <input type="text" id="field1" name="field1" required>
    </div>
    <div class="form-group" style="flex: 1;">
        <label for="field2">Optional Label</label>
        <input type="text" id="field2" name="field2">
    </div>
    <div class="form-group" style="align-self: flex-end;">
        <button type="submit" class="btn btn-green">Save</button>
    </div>
</div>
```

---

## Estimate / Project Status Helpers

Check `approval_status` to determine how to display an estimate:

```python
# Is it a project (accepted or further)?
is_project = estimate["approval_status"] not in ("pending", "declined")

# Document label
doc_type = "Project" if is_project else "Estimate"
doc_number = estimate["estimate_number"] or estimate["id"]
label = f"{doc_type} #{doc_number}"
```

In Jinja2:
```html
{% set is_project = estimate.approval_status not in ('pending', 'declined') %}
<span>{% if is_project %}Proj{% else %}Est{% endif %} #{{ estimate.estimate_number or estimate.id }}</span>
```

---

## GPS Distance Calculation

Haversine formula used in clock-in handler and available for reuse:

```python
import math

def haversine_miles(lat1, lon1, lat2, lon2):
    R = 3958.8  # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon/2)**2)
    return R * 2 * math.asin(math.sqrt(a))
```

---

## Background Processing — Submitting Work

To queue a receipt for processing, set `status = 'pending'` on insert. The task queue polls for this and picks it up within 2 seconds.

To queue an estimate for transcription, set `status = 'processing'` on insert. Same polling mechanism.

Do not call `transcriber.transcribe()` directly from a request handler — it blocks for several seconds and will time out on mobile connections.

---

## Geocoding

Uses Nominatim (OpenStreetMap) via the `/api/geocode` endpoint:

```javascript
fetch(`/api/geocode?address=${encodeURIComponent(address)}`)
  .then(r => r.json())
  .then(data => {
    if (data.lat) {
      document.getElementById('lat').value = data.lat;
      document.getElementById('lng').value = data.lng;
    }
  });
```

Do not call Nominatim directly from templates — route the request through the backend endpoint to respect rate limiting and avoid CORS issues.
