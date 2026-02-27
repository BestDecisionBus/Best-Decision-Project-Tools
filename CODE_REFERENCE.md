# BDB Tools — Code Reference

Copyable snippets organized by category. All examples are drawn from or consistent with existing production code.

---

## Database — Common Query Patterns

### Get all active records for a company
```python
def get_items_by_token(token_str, active_only=False):
    conn = get_db()
    query = "SELECT * FROM items WHERE token = ?"
    params = [token_str]
    if active_only:
        query += " AND is_active = 1"
    query += " ORDER BY sort_order ASC, name ASC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]
```

### Get single record by ID with tenant check
```python
def get_item(item_id, token_str=None):
    conn = get_db()
    query = "SELECT * FROM items WHERE id = ?"
    params = [item_id]
    if token_str:
        query += " AND token = ?"
        params.append(token_str)
    row = conn.execute(query, params).fetchone()
    conn.close()
    return dict(row) if row else None
```

### Create with audit timestamp
```python
def create_item(name, token_str, sort_order=0):
    conn = get_db()
    now = datetime.now().isoformat()
    cur = conn.execute(
        "INSERT INTO items (name, token, sort_order, is_active, created_at) VALUES (?, ?, ?, 1, ?)",
        (name, token_str, sort_order, now),
    )
    conn.commit()
    conn.close()
    return cur.lastrowid
```

### Update with **kwargs (flexible field update)
```python
def update_item(item_id, **kwargs):
    if not kwargs:
        return
    conn = get_db()
    allowed = {"name", "sort_order", "is_active"}  # whitelist
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        conn.close()
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [item_id]
    conn.execute(f"UPDATE items SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()
```

### Toggle active/inactive
```python
def toggle_item(item_id):
    conn = get_db()
    conn.execute("UPDATE items SET is_active = 1 - is_active WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
```

### Delete with cascade safety check
```python
def delete_item(item_id):
    conn = get_db()
    # Check for dependent records before deleting
    in_use = conn.execute(
        "SELECT 1 FROM dependents WHERE item_id = ? LIMIT 1", (item_id,)
    ).fetchone()
    if in_use:
        conn.close()
        return False
    conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return True
```

---

## Database — Schema Migration

### Add a column safely (idempotent)
```python
# In init_db(), after CREATE TABLE statements:
_add_column_if_missing(conn, "table_name", "new_column_name", "TEXT DEFAULT ''")
_add_column_if_missing(conn, "table_name", "new_amount",      "REAL DEFAULT 0")
_add_column_if_missing(conn, "table_name", "new_flag",        "INTEGER DEFAULT 0")
```

### Create a new table
```python
conn.execute("""
    CREATE TABLE IF NOT EXISTS new_table (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        name       TEXT NOT NULL,
        token      TEXT NOT NULL,
        is_active  INTEGER DEFAULT 1,
        sort_order INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (token) REFERENCES tokens(token)
    )
""")
conn.execute("CREATE INDEX IF NOT EXISTS idx_new_table_token ON new_table(token)")
```

---

## Routes — Standard CRUD Blueprint

```python
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required
import database

items_bp = Blueprint('items', __name__)

def _helpers():
    import app as _app
    return _app


@items_bp.route("/admin/items")
@login_required
def admin_items():
    _app = _helpers()
    tokens = _app._get_tokens_for_user()
    if not current_user.is_bdb:
        token_str = current_user.token
    else:
        token_str = request.args.get("token", "")
        if not token_str and tokens:
            token_str = tokens[0]["token"]
    selected_token = database.get_token(token_str) if token_str else None
    items = database.get_items_by_token(token_str) if token_str else []
    return render_template("admin/items.html",
                           tokens=tokens, selected_token=selected_token, items=items)


@items_bp.route("/admin/items/create", methods=["POST"])
@login_required
def admin_item_create():
    _app = _helpers()
    token_str = request.form.get("token", "")
    _app._verify_token_access(token_str)
    name = request.form.get("name", "").strip()
    if not name:
        flash("Name is required.", "error")
    else:
        database.create_item(name, token_str)
        flash("Item created.", "success")
    return redirect(url_for("items.admin_items", token=token_str))


@items_bp.route("/admin/items/<int:item_id>/toggle", methods=["POST"])
@login_required
def admin_item_toggle(item_id):
    database.toggle_item(item_id)
    token_str = request.form.get("token", "")
    return redirect(url_for("items.admin_items", token=token_str))


@items_bp.route("/admin/items/<int:item_id>/delete", methods=["POST"])
@login_required
def admin_item_delete(item_id):
    token_str = request.form.get("token", "")
    success = database.delete_item(item_id)
    if not success:
        flash("Cannot delete — item is in use.", "error")
    else:
        flash("Item deleted.", "success")
    return redirect(url_for("items.admin_items", token=token_str))
```

---

## Routes — JSON API Endpoint

```python
@my_bp.route("/api/my-resource", methods=["POST"])
def api_my_resource():
    token_str = request.form.get("token") or request.json.get("token")
    token_data = database.get_token(token_str)
    if not token_data or not token_data["is_active"]:
        return jsonify({"error": "Invalid token"}), 403

    # Rate limiting
    _app = _helpers()
    if _app._is_rate_limited(token_str, _app._rate_limits, config.RATE_LIMIT, 1):
        return jsonify({"error": "Rate limit exceeded"}), 429

    # Process request
    data = request.form.get("field", "").strip()
    if not data:
        return jsonify({"error": "field is required"}), 400

    result_id = database.create_something(data, token_str)
    return jsonify({"id": result_id, "status": "ok"})
```

---

## Templates — Admin Page Shell

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Page Title — BDB Tools</title>
    <link rel="stylesheet" href="/static/css/style.css?v={{ cache_bust }}">
    <link rel="apple-touch-icon" href="/static/icons/apple-touch-icon.png">
    <link rel="manifest" href="/static/manifest-admin.json">
    <meta name="theme-color" content="#ffffff">
</head>
<body>
    <div class="admin-layout">
        {% include 'admin/_nav.html' %}

        {% with messages = get_flashed_messages(with_categories=true) %}
        {% for category, message in messages %}
        <div class="flash flash-{{ category }}">{{ message }}</div>
        {% endfor %}
        {% endwith %}

        {# BDB company selector #}
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
        {% endif %}

        <h2>Page Title</h2>

        {# Page content here #}

    </div>
    {% include '_footer.html' %}
    <script src="/static/js/admin.js?v={{ cache_bust }}"></script>
</body>
</html>
```

---

## Templates — Create Form (inside meta-card)

```html
<div class="meta-card" style="margin-bottom: 24px;">
    <h3 style="margin-top: 0;">Add Item</h3>
    <form method="POST" action="{{ url_for('items.admin_item_create') }}">
        <input type="hidden" name="token" value="{{ selected_token.token }}">
        <div class="form-row">
            <div class="form-group" style="flex: 1;">
                <label for="name">Name <span style="color: var(--red);">*</span></label>
                <input type="text" id="name" name="name" required placeholder="Item name">
            </div>
            <div class="form-group" style="align-self: flex-end;">
                <button type="submit" class="btn btn-green">Add</button>
            </div>
        </div>
    </form>
</div>
```

---

## Templates — Status Badge

```html
{% if item.approval_status == 'accepted' %}
<span class="badge" style="background: #dbeafe; color: #1d4ed8;">Accepted</span>
{% elif item.approval_status == 'in_progress' %}
<span class="badge" style="background: #e0e7ff; color: #3730a3;">In Progress</span>
{% elif item.approval_status == 'completed' %}
<span class="badge badge-active">Completed</span>
{% elif item.approval_status == 'declined' %}
<span class="badge" style="background: #fee2e2; color: #991b1b;">Declined</span>
{% else %}
<span class="badge" style="background: #fef3c7; color: #92400e;">Pending</span>
{% endif %}
```

---

## Templates — Confirm-Before-Delete Form

```html
<form method="POST"
      action="{{ url_for('items.admin_item_delete', item_id=item.id) }}"
      onsubmit="return confirm('Delete {{ item.name }}? This cannot be undone.')"
      style="display: inline;">
    <input type="hidden" name="token" value="{{ selected_token.token }}">
    <button type="submit" class="btn btn-red btn-sm">Delete</button>
</form>
```

---

## JavaScript — Fetch POST (JSON)

```javascript
async function saveData(payload) {
    try {
        const resp = await fetch('/api/my-endpoint', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const data = await resp.json();
        if (!resp.ok) {
            console.error('Save failed:', data.error);
        }
        return data;
    } catch (e) {
        console.error('Network error:', e);
    }
}
```

---

## JavaScript — Fetch POST (FormData / file upload)

```javascript
async function uploadFile(formEl) {
    const fd = new FormData(formEl);
    const resp = await fetch('/api/upload', { method: 'POST', body: fd });
    const data = await resp.json();
    return data;
}
```

---

## JavaScript — Poll for Background Job Status

```javascript
function pollStatus(id, url, onComplete, intervalMs = 2000) {
    const interval = setInterval(async () => {
        const resp = await fetch(`${url}/${id}`);
        const data = await resp.json();
        if (data.status === 'complete' || data.status === 'error') {
            clearInterval(interval);
            onComplete(data);
        }
    }, intervalMs);
}

// Usage:
pollStatus(estimateId, '/api/estimate/status', (result) => {
    if (result.status === 'complete') {
        window.location.reload();
    }
});
```

---

## PDF Generation — Receipt PDF

```python
from pdf_generator import generate_receipt_pdf

generate_receipt_pdf(
    output_path=Path("path/to/output.pdf"),
    image_path=Path("path/to/image.jpg"),
    transcription="Voice memo transcription text",
    company_name="Acme Co",
    timestamp="2026-02-17 14:30:00",
    token="HB53OA964SK8",
    job_name="Main Street Remodel",
    category_names=["Materials", "Labor"],
)
```

---

## Image Processing — Fix EXIF Orientation + Thumbnail

```python
from pdf_generator import fix_image_orientation, generate_web_thumbnail
from pathlib import Path

image_path = Path("uploads/photo.jpg")

# Fix EXIF rotation in-place
fix_image_orientation(image_path)

# Generate thumbnail (writes to thumb_path)
thumb_path = Path("uploads/photo_thumb.jpg")
generate_web_thumbnail(image_path, thumb_path)
```

---

## Whisper Transcription

```python
from transcriber import transcribe
from pathlib import Path

text = transcribe(Path("audio/recording.webm"))
# Returns transcribed string, or empty string on failure
```

Do not call this directly from a request handler. Queue it via the background worker:
1. Set `status = 'processing'` when creating the estimate/submission
2. The `task_queue` worker picks it up within 2 seconds

---

## Estimate Line Item Total

```python
# In Python (matching the database/template logic):
total = round(quantity * unit_price, 2)
tax_amount = round(total * sales_tax_rate / 100, 2) if taxable else 0
line_total_with_tax = total + tax_amount

# Estimate totals:
subtotal = sum(item["total"] for item in items)
tax_total = sum(
    round(item["total"] * sales_tax_rate / 100, 2)
    for item in items if item.get("taxable")
)
grand_total = subtotal + tax_total
```

---

## CFO KPI Calculations

```python
# Earned revenue (WIP-based)
earned_revenue = sum(
    j["budget"] * j["completion_pct"] / 100
    for j in job_financials
)

# Overhead as % of earned revenue
overhead_pct = round((monthly_overhead * 12) / earned_revenue * 100, 1) \
    if earned_revenue > 0 else 0

# Margin target = overhead % + income target %
margin_target = round(overhead_pct + income_target_pct, 1)

# Markup required to achieve margin
markup_required = round(margin_target / (100 - margin_target) * 100, 1) \
    if margin_target < 100 else 0

# Days cash on hand
daily_overhead = monthly_overhead / 30
days_cash = round(cash_on_hand / daily_overhead, 1) if daily_overhead > 0 else 0
```

---

## Security — File Magic Byte Validation

```python
JPEG_SIG = b'\xff\xd8\xff'
PNG_SIG  = b'\x89PNG\r\n\x1a\n'
WEBP_SIG = b'RIFF'

def validate_image(file_obj):
    header = file_obj.read(12)
    file_obj.seek(0)
    return (
        header[:3] == JPEG_SIG or
        header[:8] == PNG_SIG or
        (header[:4] == WEBP_SIG and header[8:12] == b'WEBP')
    )
```

---

## Backup Cron (Production)

```bash
# Daily database backup (runs at 3am)
0 3 * * * cp ~/bdb-tools/instance/bdb_tools.db ~/backups/bdb_tools_$(date +\%Y\%m\%d).db

# Weekly file backup (runs Sunday at 4am)
0 4 * * 0 tar czf ~/backups/bdb_files_$(date +\%Y\%m\%d).tar.gz \
    ~/bdb-tools/receipts \
    ~/bdb-tools/estimates \
    ~/bdb-tools/job_photos \
    ~/bdb-tools/static/logos
```

---

## Systemd — Service Management

```bash
# Install
sudo cp bdpt.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable bdpt
sudo systemctl start bdpt

# Day-to-day
sudo systemctl status bdpt
sudo systemctl restart bdpt
journalctl -u bdpt -f             # live logs
journalctl -u bdpt --since "1h ago"  # last hour

# After code changes
sudo systemctl restart bdpt
python3 -c "import app; print('OK')"  # verify before restart
```
