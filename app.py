import json
import math
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, Response, abort, flash, jsonify, redirect, render_template, request,
    send_from_directory, session, url_for,
)
from flask_login import (
    LoginManager, UserMixin, current_user, login_required, login_user,
    logout_user,
)
from flask_wtf.csrf import CSRFProtect, generate_csrf

import config
import database

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_MB * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = True

csrf = CSRFProtect(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

_cache_bust = str(int(time.time()))


# ---------------------------------------------------------------------------
# PWA / home screen icon routes
# ---------------------------------------------------------------------------

@app.route("/apple-touch-icon.png")
@app.route("/apple-touch-icon-precomposed.png")
def apple_touch_icon():
    return send_from_directory("static/icons", "apple-touch-icon.png")


@app.route("/favicon.ico")
def favicon():
    return send_from_directory("static/icons", "apple-touch-icon.png")


@app.route("/sw.js")
def service_worker():
    response = send_from_directory("static", "sw.js")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Content-Type"] = "application/javascript"
    return response


@app.route("/c/<token_str>/manifest.json")
def company_manifest(token_str):
    token_data = database.get_token(token_str)
    if not token_data or not token_data["is_active"]:
        return jsonify({}), 404
    manifest = {
        "name": token_data["company_name"],
        "short_name": token_data["company_name"],
        "start_url": f"/c/{token_str}",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#ffffff",
        "icons": [
            {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
        ],
    }
    return Response(json.dumps(manifest), mimetype="application/manifest+json")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class User(UserMixin):
    def __init__(self, user_row):
        self.id = user_row["id"]
        self.username = user_row["username"]
        self.role = user_row["role"]
        self.token = user_row.get("token")

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_bdb(self):
        return self.token is None

    @property
    def is_scheduler(self):
        return self.role == "scheduler"


@login_manager.user_loader
def load_user(user_id):
    row = database.get_user_by_id(int(user_id))
    if not row:
        return None
    if row.get("token"):
        token_data = database.get_token(row["token"])
        if not token_data or not token_data["is_active"]:
            return None
    return User(row)


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def bdb_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_bdb:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def scheduler_allowed(f):
    """Allow admin, scheduler, or BDB users."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin and not current_user.is_scheduler and not current_user.is_bdb:
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

_rate_limits = defaultdict(list)
_login_attempts = defaultdict(list)


def _is_rate_limited(key, store, max_requests, window_minutes):
    now = datetime.now()
    cutoff = now - timedelta(minutes=window_minutes)
    store[key] = [t for t in store[key] if t > cutoff]
    if len(store[key]) >= max_requests:
        return True
    store[key].append(now)
    return False


# ---------------------------------------------------------------------------
# Context processors & middleware
# ---------------------------------------------------------------------------

@app.template_filter("time12")
def time12_filter(value):
    """Convert 24h time string like '17:00' to '5:00 PM'."""
    if not value:
        return ""
    parts = value.split(":")
    h = int(parts[0])
    m = parts[1] if len(parts) > 1 else "00"
    ampm = "PM" if h >= 12 else "AM"
    h = h % 12 or 12
    return f"{h}:{m} {ampm}"


@app.template_filter("weekday")
def weekday_filter(date_str):
    """Convert YYYY-MM-DD date string to weekday name like 'Monday'."""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.strftime("%A")
    except Exception:
        return ""


@app.template_filter("monthday")
def monthday_filter(date_str):
    """Convert YYYY-MM-DD to MM-DD."""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.strftime("%m-%d")
    except Exception:
        return date_str


@app.template_filter("fmt_time")
def fmt_time_filter(value):
    """Extract 12-hour time from ISO timestamp: '2026-02-17 14:30:00' -> '2:30 PM'."""
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(str(value)[:19])
        h = dt.hour % 12 or 12
        return f"{h}:{dt.minute:02d} {'PM' if dt.hour >= 12 else 'AM'}"
    except Exception:
        return str(value)


@app.template_filter("fmt_date")
def fmt_date_filter(value):
    """Extract friendly date from ISO timestamp: '2026-02-17 14:30:00' -> 'Feb 17, 2026'."""
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(str(value)[:19])
        return f"{dt.strftime('%b')} {dt.day}, {dt.year}"
    except Exception:
        return str(value)[:10]


@app.template_filter("fmt_datetime")
def fmt_datetime_filter(value):
    """Format ISO timestamp as friendly datetime: 'Feb 17, 2026 2:30 PM'."""
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(str(value)[:19])
        h = dt.hour % 12 or 12
        ampm = "PM" if dt.hour >= 12 else "AM"
        return f"{dt.strftime('%b')} {dt.day}, {dt.year} {h}:{dt.minute:02d} {ampm}"
    except Exception:
        return str(value)


@app.template_filter("fmt_ts")
def fmt_ts_filter(value):
    """Format ISO timestamp with seconds: 'Feb 17, 2026 2:30:15 PM'."""
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(str(value)[:19])
        h = dt.hour % 12 or 12
        ampm = "PM" if dt.hour >= 12 else "AM"
        return f"{dt.strftime('%b')} {dt.day}, {dt.year} {h}:{dt.minute:02d}:{dt.second:02d} {ampm}"
    except Exception:
        return str(value)


@app.context_processor
def inject_cache_bust():
    return {"cache_bust": _cache_bust}


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://unpkg.com; "
        "img-src 'self' data: https://*.tile.openstreetmap.org; "
        "font-src 'self'; "
        "media-src 'self' blob:; "
        "worker-src 'self'; "
        "connect-src 'self';"
    )
    if request.path.startswith("/admin") or request.path.startswith("/scheduler"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# ---------------------------------------------------------------------------
# CSRF auto-injection into HTML responses
# ---------------------------------------------------------------------------

_FORM_POST_RE = re.compile(
    r'(<form\b[^>]*method=["\']POST["\'][^>]*>)', re.IGNORECASE
)

_CSRF_FETCH_SCRIPT = """<script>(function(){var o=window.fetch;window.fetch=function(u,p){p=p||{};if(p.method&&p.method.toUpperCase()!=='GET'){p.headers=p.headers||{};var m=document.querySelector('meta[name="csrf-token"]');if(m&&!(p.headers instanceof Headers)){p.headers['X-CSRFToken']=p.headers['X-CSRFToken']||m.content;}else if(m&&p.headers instanceof Headers&&!p.headers.has('X-CSRFToken')){p.headers.set('X-CSRFToken',m.content);}}return o.call(this,u,p);};})();</script>"""


@app.after_request
def inject_csrf_tokens(response):
    if (
        response.content_type
        and "text/html" in response.content_type
        and response.status_code < 500
    ):
        token = generate_csrf()
        html = response.get_data(as_text=True)
        csrf_meta = f'<meta name="csrf-token" content="{token}">'
        csrf_input = f'<input type="hidden" name="csrf_token" value="{token}">'
        # Inject meta tag into <head> (case-insensitive)
        head_idx = html.lower().find("<head>")
        if head_idx >= 0:
            html = html[:head_idx + 6] + csrf_meta + html[head_idx + 6:]
        # Inject hidden input into all POST forms
        html = _FORM_POST_RE.sub(rf"\1{csrf_input}", html)
        # Inject fetch interceptor before </body> (case-insensitive)
        body_idx = html.lower().rfind("</body>")
        if body_idx >= 0:
            html = html[:body_idx] + _CSRF_FETCH_SCRIPT + html[body_idx:]
        response.set_data(html)
    return response


# ---------------------------------------------------------------------------
# GPS distance calculation
# ---------------------------------------------------------------------------

def haversine_miles(lat1, lng1, lat2, lng2):
    if any(v is None for v in (lat1, lng1, lat2, lng2)):
        return None
    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Admin helpers (shared across route files)
# ---------------------------------------------------------------------------

def _get_tokens_for_user():
    if current_user.is_bdb:
        return database.get_all_tokens()
    tokens = database.get_tokens_for_user(current_user.id)
    if tokens:
        return tokens
    # Fallback for users not yet in user_tokens (should not occur after migration)
    token_data = database.get_token(current_user.token)
    return [token_data] if token_data else []


def _get_selected_token(tokens):
    # Single-company users: always their one token, no switcher needed
    if not current_user.is_bdb and len(tokens) == 1:
        token_data = tokens[0] if tokens else None
        token_str = token_data["token"] if token_data else ""
        return token_str, token_data

    # BDB users and multi-token company users: allow switching via URL param or session
    valid_token_strs = {t["token"] for t in tokens}

    if "token" in request.args:
        token_str = request.args["token"]
        if token_str == "":
            session.pop("admin_selected_token", None)
            return "", None
        if token_str in valid_token_strs:
            session["admin_selected_token"] = token_str
        else:
            token_str = session.get("admin_selected_token", "")
    else:
        token_str = session.get("admin_selected_token", "")

    # Clear stale session token if no longer in allowed set
    if token_str and token_str not in valid_token_strs:
        session.pop("admin_selected_token", None)
        token_str = ""

    # Multi-token company users default to their primary token if nothing selected
    if not token_str and not current_user.is_bdb and current_user.token:
        token_str = current_user.token
        session["admin_selected_token"] = token_str

    selected = database.get_token(token_str) if token_str else None
    return token_str, selected


def _verify_token_access(token_str):
    if current_user.is_bdb:
        return
    allowed = {t["token"] for t in database.get_tokens_for_user(current_user.id)}
    if not allowed:
        allowed = {current_user.token}
    if token_str not in allowed:
        abort(403)


def _check_feature(token_str, feature_name):
    """Returns True if a feature is enabled for this company."""
    token_data = database.get_token(token_str)
    if not token_data:
        return False
    if feature_name == "dashboard":
        return token_data.get("dashboard_tier", "none") != "none"
    return bool(token_data.get(feature_name, 0))


# ---------------------------------------------------------------------------
# Login / Logout
# ---------------------------------------------------------------------------

@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if current_user.is_scheduler and not current_user.is_admin:
            return redirect(url_for("scheduling.scheduler_dashboard"))
        return redirect(url_for("admin.admin_dashboard"))
    if request.method == "POST":
        if _is_rate_limited(request.remote_addr, _login_attempts, 10, 15):
            flash("Too many login attempts. Try again later.", "error")
            return render_template("admin/login.html"), 429

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = database.verify_user(username, password)
        if user:
            if user.get("token"):
                token_data = database.get_token(user["token"])
                if not token_data or not token_data["is_active"]:
                    flash("Your company account is currently deactivated.", "error")
                    return render_template("admin/login.html")
            login_user(User(user))
            if user["role"] == "scheduler":
                return redirect(url_for("scheduling.scheduler_dashboard"))
            return redirect(url_for("admin.admin_dashboard"))
        flash("Invalid credentials.", "error")
    return render_template("admin/login.html")


@app.route("/admin/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Company Admin Login
# ---------------------------------------------------------------------------

@app.route("/company-admin")
@app.route("/company-admin/")
def company_admin_index():
    return redirect(url_for("company_admin_login"))


@app.route("/company-admin/login", methods=["GET", "POST"])
def company_admin_login():
    if request.method == "POST":
        if _is_rate_limited(request.remote_addr + ":ca", _login_attempts, 10, 15):
            flash("Too many login attempts. Try again later.", "error")
            return render_template("company_admin_login.html"), 429

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = database.verify_user(username, password)
        if user:
            if not user.get("token"):
                flash("This login is for company admins only.", "error")
                return render_template("company_admin_login.html")
            token_data = database.get_token(user["token"])
            if not token_data or not token_data["is_active"]:
                flash("Your company account is currently deactivated.", "error")
                return render_template("company_admin_login.html")
            login_user(User(user))
            if user["role"] == "scheduler":
                return redirect(url_for("time_admin.admin_time_entries"))
            return redirect(url_for("admin.admin_dashboard"))
        flash("Invalid credentials.", "error")

    return render_template("company_admin_login.html")


# ---------------------------------------------------------------------------
# Company Home Screen
# ---------------------------------------------------------------------------

@app.route("/c/<token_str>", methods=["GET", "POST"])
def company_home(token_str):
    token_data = database.get_token(token_str)
    if not token_data or not token_data["is_active"]:
        return render_template("errors/invalid_token.html"), 404

    # Check if employee is already logged in for this token
    emp_id = session.get("employee_id")
    emp_token = session.get("employee_token")
    if emp_id and emp_token == token_str:
        employee = database.get_employee(emp_id)
        if employee and employee["is_active"] and employee["token"] == token_str:
            is_admin = session.get("admin_as_employee", False)
            return render_template("company_home.html", token=token_data,
                                   employee=employee, admin_session=is_admin)

    # Handle login POST
    if request.method == "POST":
        if _is_rate_limited(request.remote_addr + ":emp", _login_attempts, 10, 15):
            flash("Too many login attempts. Try again later.", "error")
            return render_template("company_home.html", token=token_data, employee=None), 429

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        employee = database.verify_employee(username, password, token_str)
        if employee:
            if not employee["is_active"]:
                flash("Your account has been deactivated.", "error")
                return render_template("company_home.html", token=token_data, employee=None)
            session["employee_id"] = employee["id"]
            session["employee_token"] = token_str
            session["employee_name"] = employee["name"]
            return render_template("company_home.html", token=token_data, employee=employee)

        # Fallback: try admin user credentials
        user = database.verify_user(username, password)
        if user:
            # BDB admin: token is None, allow any company.
            # Company admin: token must be in their list of accessible companies (primary or extra).
            user_token_set = {t["token"] for t in database.get_tokens_for_user(user["id"])} if user["token"] else set()
            if user["token"] is None or token_str in user_token_set:
                employee = database.get_or_create_admin_employee(
                    user["username"], user["password_hash"], token_str
                )
                if employee:
                    session["employee_id"] = employee["id"]
                    session["employee_token"] = token_str
                    session["employee_name"] = employee["name"]
                    session["admin_as_employee"] = True
                    return render_template("company_home.html",
                        token=token_data, employee=employee, admin_session=True)

        flash("Invalid username or password.", "error")

    return render_template("company_home.html", token=token_data, employee=None)


@app.route("/c/<token_str>/logout")
def company_logout(token_str):
    session.pop("employee_id", None)
    session.pop("employee_token", None)
    session.pop("employee_name", None)
    session.pop("admin_as_employee", None)
    return redirect(url_for("company_home", token_str=token_str))


def _require_employee_session(token_str):
    """Check employee session matches token. Returns employee or None."""
    emp_id = session.get("employee_id")
    emp_token = session.get("employee_token")
    if not emp_id or emp_token != token_str:
        return None
    employee = database.get_employee(emp_id)
    if not employee or not employee["is_active"] or employee["token"] != token_str:
        session.pop("employee_id", None)
        session.pop("employee_token", None)
        session.pop("employee_name", None)
        return None
    return employee


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _geocode_address(address):
    """Geocode *address* via Mapbox.  Returns (result_dict, status_code)."""
    import urllib.parse
    import urllib.request
    from config import MAPBOX_TOKEN

    if not MAPBOX_TOKEN:
        return {"error": "Geocoding not configured"}, 500
    encoded = urllib.parse.quote(address)
    url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{encoded}.json?access_token={MAPBOX_TOKEN}&limit=1"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
            features = data.get("features", [])
            if features:
                lng, lat = features[0]["center"]
                return {
                    "lat": lat,
                    "lng": lng,
                    "display": features[0].get("place_name", ""),
                }, 200
            return {"error": "Address not found"}, 404
    except Exception:
        return {"error": "Geocoding service unavailable"}, 500


# ---------------------------------------------------------------------------
# Shared API endpoints
# ---------------------------------------------------------------------------

@app.route("/api/geocode")
@login_required
def api_geocode():
    address = request.args.get("address", "")
    if not address:
        return jsonify({"error": "Address required"}), 400
    result, status = _geocode_address(address)
    return jsonify(result), status


def _check_token_api_access(token_str):
    """Verify token-based API access for admin or employee. Returns token_data or None."""
    if not token_str:
        return None
    if not current_user.is_authenticated and not _require_employee_session(token_str):
        return False  # explicit auth failure
    token_data = database.get_token(token_str)
    if not token_data or not token_data["is_active"]:
        return None
    return token_data


@app.route("/api/jobs")
def api_jobs():
    token_str = request.args.get("token", "")
    access = _check_token_api_access(token_str)
    if access is False:
        return jsonify({"error": "Not authorized"}), 403
    if not access:
        return jsonify([])
    jobs = database.get_jobs_by_token(token_str, active_only=True)
    return jsonify([{"id": j["id"], "name": j["job_name"]} for j in jobs])


@app.route("/api/categories")
def api_categories():
    token_str = request.args.get("token", "")
    access = _check_token_api_access(token_str)
    if access is False:
        return jsonify({"error": "Not authorized"}), 403
    if not access:
        return jsonify([])
    cats = database.get_categories_by_token(token_str, active_only=True)
    return jsonify([{"id": c["id"], "name": c["name"]} for c in cats])


@app.route("/api/common-tasks")
def api_common_tasks():
    token_str = request.args.get("token", "")
    access = _check_token_api_access(token_str)
    if access is False:
        return jsonify({"error": "Not authorized"}), 403
    if not access:
        return jsonify([])
    tasks = database.get_common_tasks_by_token(token_str, active_only=True)
    return jsonify([{"id": t["id"], "name": t["name"]} for t in tasks])


@app.route("/api/job-tasks")
def api_job_tasks():
    job_id = request.args.get("job_id", type=int)
    if not job_id:
        return jsonify([])
    if not current_user.is_authenticated:
        job = database.get_job(job_id)
        if not job or not _require_employee_session(job["token"]):
            return jsonify({"error": "Not authorized"}), 403
    tasks = database.get_job_tasks(job_id, active_only=True)
    return jsonify([{"id": t["id"], "name": t["name"]} for t in tasks])


@app.route("/api/check-username")
@login_required
def api_check_username():
    username = request.args.get("username", "").strip()
    if not username:
        return jsonify({"available": False, "error": "Username required"})
    available = not database.is_username_taken(username)
    return jsonify({"available": available})


# ---------------------------------------------------------------------------
# Legal pages (required by Intuit for QBO integration)
# ---------------------------------------------------------------------------

@app.route("/legal/eula")
def legal_eula():
    return render_template("legal/eula.html")


@app.route("/legal/privacy")
def legal_privacy():
    return render_template("legal/privacy.html")


# ---------------------------------------------------------------------------
# Error Handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return render_template("errors/404.html"), 404


@app.errorhandler(403)
def forbidden(e):
    return render_template("errors/invalid_token.html"), 403


# ---------------------------------------------------------------------------
# Register Blueprints
# ---------------------------------------------------------------------------

from routes.admin import admin_bp
from routes.timekeeper import timekeeper_bp
from routes.time_admin import time_admin_bp
from routes.receipts import receipts_bp
from routes.receipt_admin import receipt_admin_bp
from routes.scheduling import scheduling_bp
from routes.job_photos import job_photos_bp
from routes.estimates import estimates_bp
from routes.finance import finance_bp
from routes.customers import customers_bp
from routes.task_templates import task_templates_bp
from routes.invoices import invoices_bp
from routes.notifications import notifications_bp
from routes.qbo import qbo_bp

app.register_blueprint(admin_bp)
app.register_blueprint(timekeeper_bp)
app.register_blueprint(time_admin_bp)
app.register_blueprint(receipts_bp)
app.register_blueprint(receipt_admin_bp)
app.register_blueprint(scheduling_bp)
app.register_blueprint(job_photos_bp)
app.register_blueprint(estimates_bp)
app.register_blueprint(finance_bp)
app.register_blueprint(customers_bp)
app.register_blueprint(task_templates_bp)
app.register_blueprint(invoices_bp)
app.register_blueprint(notifications_bp)
app.register_blueprint(qbo_bp)


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

database.init_db()

# Start background task queue worker (for transcription, etc.)
import task_queue
task_queue.start_worker()

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5050)
