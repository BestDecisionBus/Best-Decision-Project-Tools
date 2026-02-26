import os
import shutil

from flask import (
    Blueprint, abort, flash, jsonify, redirect, render_template, request,
    url_for,
)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

import config
import database

admin_bp = Blueprint('admin', __name__)


@admin_bp.before_request
def _check_scheduler_access():
    """Block scheduler role from admin blueprint (categories, lists, tokens, etc.)."""
    if not current_user.is_authenticated:
        return
    if current_user.is_scheduler and not current_user.is_bdb:
        if request.endpoint == 'admin.admin_dashboard':
            return redirect(url_for('time_admin.admin_time_entries'))
        abort(403)


# Allowed logo extensions and magic byte signatures
_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg", ".webp"}
_LOGO_SIGNATURES = [
    b"\xff\xd8\xff",        # JPEG
    b"\x89PNG\r\n\x1a\n",   # PNG
    b"RIFF",                 # WebP (RIFF container)
    b"<?xml",                # SVG (XML-based)
    b"<svg",                 # SVG (direct)
]


def _validate_logo(file_storage):
    """Validate logo file: check extension and magic bytes. Returns (ok, ext)."""
    ext = os.path.splitext(secure_filename(file_storage.filename))[1].lower()
    if ext not in _LOGO_EXTENSIONS:
        return False, ext
    header = file_storage.read(16)
    file_storage.seek(0)
    for sig in _LOGO_SIGNATURES:
        if header[:len(sig)] == sig:
            return True, ext
    return False, ext


def _save_logo(file_storage, dest_path):
    """Save logo, resizing raster images if wider than 800px (matches report size)."""
    ext = os.path.splitext(dest_path)[1].lower()
    if ext == ".svg":
        file_storage.save(dest_path)
        return
    from PIL import Image
    img = Image.open(file_storage)
    max_w = 800
    if img.width > max_w:
        ratio = max_w / img.width
        img = img.resize((max_w, int(img.height * ratio)), Image.LANCZOS)
    if img.mode in ("RGBA", "P") and ext in (".jpg", ".jpeg"):
        img = img.convert("RGB")
    save_kwargs = {"optimize": True}
    if ext == ".png":
        save_kwargs["compress_level"] = 9
    elif ext in (".jpg", ".jpeg"):
        save_kwargs["quality"] = 85
    img.save(dest_path, **save_kwargs)


# ---------------------------------------------------------------------------
# Lazy import of app-level helpers to avoid circular imports
# ---------------------------------------------------------------------------

def _helpers():
    import app as _app
    return _app


# ---------------------------------------------------------------------------
# Admin Dashboard
# ---------------------------------------------------------------------------

@admin_bp.route("/admin")
@admin_bp.route("/admin/")
@admin_bp.route("/admin/dashboard")
@login_required
def admin_dashboard():
    h = _helpers()
    tokens = h._get_tokens_for_user()
    token_str, selected_token = h._get_selected_token(tokens)

    # BDB with no token selected -> show company cards
    if current_user.is_bdb and not token_str:
        company_summaries = database.get_all_company_summaries()
        return render_template(
            "admin/dashboard.html",
            tokens=tokens, selected_token=None,
            stats={}, company_summaries=company_summaries,
            active_entries=[], needs_review=[], todays_schedules=[],
            payroll_estimate=None, combined_job_costs=None,
        )

    # Company dashboard — operations view
    stats = {}
    active_entries = []
    needs_review = []
    todays_schedules = []
    payroll_estimate = None
    combined_job_costs = None
    estimate_stats = None
    if token_str:
        stats = database.get_dashboard_stats(token_str)
        active_entries = database.get_active_entries(token_str)
        needs_review = database.get_needs_review_entries(token_str, limit=10)
        todays_schedules = database.get_todays_schedules(token_str)
        payroll_estimate = database.get_weekly_payroll_estimate(token_str)
        weekly_job_costs = database.get_weekly_job_costs(token_str)
        alltime_job_costs = database.get_alltime_job_costs(token_str)
        estimate_stats = database.get_estimate_stats(token_str)
        # Add payroll total to stats for the stat card
        stats["est_weekly_payroll"] = payroll_estimate["total_cost"]

        # Merge weekly and all-time job cost data into a single combined structure
        weekly_by_name = {j["job_name"]: j for j in (weekly_job_costs.get("jobs") or [])}
        alltime_by_name = {j["job_name"]: j for j in (alltime_job_costs.get("jobs") or [])}
        all_job_names = set(weekly_by_name.keys()) | set(alltime_by_name.keys())
        merged_jobs = []
        for name in all_job_names:
            w = weekly_by_name.get(name, {"hours": 0, "total_cost": 0})
            a = alltime_by_name.get(name, {"hours": 0, "total_cost": 0})
            merged_jobs.append({
                "job_name": name,
                "week_hours": w["hours"],
                "week_cost": w["total_cost"],
                "alltime_hours": a["hours"],
                "alltime_cost": a["total_cost"],
            })
        merged_jobs.sort(key=lambda x: x["alltime_hours"], reverse=True)
        combined_job_costs = {
            "jobs": merged_jobs,
            "total_week_hours": weekly_job_costs.get("total_hours", 0),
            "total_week_cost": weekly_job_costs.get("total_cost", 0),
            "total_alltime_hours": alltime_job_costs.get("total_hours", 0),
            "total_alltime_cost": alltime_job_costs.get("total_cost", 0),
        } if merged_jobs else None

    return render_template(
        "admin/dashboard.html",
        tokens=tokens, selected_token=selected_token,
        stats=stats, company_summaries=None,
        active_entries=active_entries,
        needs_review=needs_review,
        todays_schedules=todays_schedules,
        payroll_estimate=payroll_estimate,
        combined_job_costs=combined_job_costs,
        estimate_stats=estimate_stats,
    )


# ---------------------------------------------------------------------------
# BDB User Management (BDB only)
# ---------------------------------------------------------------------------

@admin_bp.route("/admin/users")
@login_required
def admin_users():
    if not current_user.is_bdb or not current_user.is_admin:
        abort(403)
    users = database.get_bdb_users()
    return render_template("admin/users.html", users=users)


@admin_bp.route("/admin/users/create", methods=["POST"])
@login_required
def admin_user_create():
    if not current_user.is_bdb or not current_user.is_admin:
        abort(403)
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    role = request.form.get("role", "admin").strip()
    if role not in ("admin", "viewer"):
        role = "admin"
    if not username or not password:
        flash("Username and password are required.", "error")
    elif database.is_username_taken(username):
        flash(f"Username '{username}' is already taken.", "error")
    else:
        database.create_bdb_user(username, password, role)
        flash(f"User '{username}' created.", "success")
    return redirect(url_for("admin.admin_users"))


@admin_bp.route("/admin/users/<int:user_id>/change-password", methods=["POST"])
@login_required
def admin_user_change_password(user_id):
    if not current_user.is_bdb or not current_user.is_admin:
        abort(403)
    new_password = request.form.get("new_password", "").strip()
    if not new_password:
        flash("New password is required.", "error")
    else:
        database.update_user_password(user_id, new_password)
        flash("Password updated.", "success")
    return redirect(url_for("admin.admin_users"))


@admin_bp.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@login_required
def admin_user_delete(user_id):
    if not current_user.is_bdb or not current_user.is_admin:
        abort(403)
    if user_id == current_user.id:
        flash("You cannot delete your own account.", "error")
    elif not database.delete_bdb_user(user_id):
        flash("Cannot delete the last admin user.", "error")
    else:
        flash("User deleted.", "success")
    return redirect(url_for("admin.admin_users"))


# ---------------------------------------------------------------------------
# Token Management (BDB only)
# ---------------------------------------------------------------------------

@admin_bp.route("/admin/tokens")
@login_required
def admin_tokens():
    if not current_user.is_bdb:
        abort(403)
    tokens = database.get_all_tokens()
    # Build dict of company users keyed by token id
    token_users = {}
    for t in tokens:
        token_users[t["id"]] = database.get_users_by_token(t["token"])
    return render_template("admin/tokens.html", tokens=tokens, token_users=token_users)


@admin_bp.route("/admin/tokens/create", methods=["POST"])
@login_required
def admin_token_create():
    if not current_user.is_bdb:
        abort(403)
    company_name = request.form.get("company_name", "").strip()
    custom_token = request.form.get("custom_token", "").strip().upper() or None
    burden_str = request.form.get("labor_burden_pct", "0").strip()
    try:
        labor_burden_pct = float(burden_str) if burden_str else 0
    except (ValueError, TypeError):
        labor_burden_pct = 0
    if not company_name:
        flash("Company name is required.", "error")
        return redirect(url_for("admin.admin_tokens"))

    logo_file = ""
    logo = request.files.get("logo")
    if logo and logo.filename:
        ok, ext = _validate_logo(logo)
        if not ok:
            flash("Invalid logo file. Allowed: PNG, JPG, SVG, WebP.", "error")
            return redirect(url_for("admin.admin_tokens"))
        token_str = custom_token or database.generate_token_string()
        logo_file = f"{token_str}{ext}"
        _save_logo(logo, str(config.LOGOS_DIR / logo_file))
        if custom_token:
            database.create_token(company_name, logo_file, custom_token,
                                  labor_burden_pct=labor_burden_pct)
        else:
            database.create_token(company_name, logo_file, token_str,
                                  labor_burden_pct=labor_burden_pct)
    else:
        database.create_token(company_name, logo_file, custom_token,
                              labor_burden_pct=labor_burden_pct)

    flash(f"Token created for {company_name}.", "success")
    return redirect(url_for("admin.admin_tokens"))


@admin_bp.route("/admin/tokens/<int:token_id>/update", methods=["POST"])
@login_required
def admin_token_update(token_id):
    if not current_user.is_bdb:
        abort(403)
    company_name = request.form.get("company_name", "").strip()
    if not company_name:
        flash("Company name is required.", "error")
        return redirect(url_for("admin.admin_tokens"))

    logo_file = None
    logo = request.files.get("logo")
    if logo and logo.filename:
        ok, ext = _validate_logo(logo)
        if not ok:
            flash("Invalid logo file. Allowed: PNG, JPG, SVG, WebP.", "error")
            return redirect(url_for("admin.admin_tokens"))
        t = database.get_token_by_id(token_id)
        logo_file = f"{t['token']}{ext}"
        _save_logo(logo, str(config.LOGOS_DIR / logo_file))

    database.update_token(token_id, company_name, logo_file)
    flash("Token updated.", "success")
    return redirect(url_for("admin.admin_tokens"))


@admin_bp.route("/admin/tokens/<int:token_id>/toggle", methods=["POST"])
@login_required
def admin_token_toggle(token_id):
    if not current_user.is_bdb or not current_user.is_admin:
        abort(403)
    new_state = database.toggle_token(token_id)
    status = "activated" if new_state else "deactivated"
    flash(f"Token {status}.", "success")
    return redirect(url_for("admin.admin_tokens"))


@admin_bp.route("/admin/tokens/<int:token_id>/regenerate", methods=["POST"])
@login_required
def admin_token_regenerate(token_id):
    if not current_user.is_bdb or not current_user.is_admin:
        abort(403)
    result = database.regenerate_token(token_id)
    if result:
        new_token, old_token, old_logo_file = result
        # Rename logo file
        for ext in (".png", ".jpg", ".jpeg", ".svg", ".webp"):
            old_logo = config.LOGOS_DIR / f"{old_token}{ext}"
            if old_logo.exists():
                old_logo.rename(config.LOGOS_DIR / f"{new_token}{ext}")
                database.update_token(token_id, None, f"{new_token}{ext}")
                break
        # Rename receipts folder
        old_receipt_dir = config.RECEIPTS_DIR / old_token
        new_receipt_dir = config.RECEIPTS_DIR / new_token
        if old_receipt_dir.exists():
            old_receipt_dir.rename(new_receipt_dir)
        flash("Token regenerated.", "success")
    return redirect(url_for("admin.admin_tokens"))


@admin_bp.route("/admin/tokens/<int:token_id>/delete", methods=["POST"])
@login_required
def admin_token_delete(token_id):
    if not current_user.is_bdb or not current_user.is_admin:
        abort(403)
    t = database.get_token_by_id(token_id)
    if t:
        # Remove logo
        if t["logo_file"]:
            logo_path = config.LOGOS_DIR / t["logo_file"]
            if logo_path.exists():
                logo_path.unlink()
        # Remove receipts folder
        receipt_dir = config.RECEIPTS_DIR / t["token"]
        if receipt_dir.exists():
            shutil.rmtree(receipt_dir)
        database.delete_token(token_id)
        flash(f"Token for {t['company_name']} deleted.", "success")
    return redirect(url_for("admin.admin_tokens"))


# ---------------------------------------------------------------------------
# Labor Burden Update (BDB + company admins)
# ---------------------------------------------------------------------------

@admin_bp.route("/admin/labor-burden/update", methods=["POST"])
@login_required
def admin_update_labor_burden():
    h = _helpers()
    data = request.get_json()
    if not data:
        abort(400)
    token_str = data.get("token", "").strip()
    h._verify_token_access(token_str)
    # Only BDB admins and company admins can change burden
    if not current_user.is_bdb and current_user.role not in ("admin", "viewer"):
        abort(403)
    try:
        pct = float(data.get("labor_burden_pct", 0))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid percentage."}), 400
    database.update_token_burden(token_str, pct)
    return jsonify({"success": True, "labor_burden_pct": pct})


# ---------------------------------------------------------------------------
# Company User Management (BDB only)
# ---------------------------------------------------------------------------

@admin_bp.route("/admin/tokens/<int:token_id>/users/create", methods=["POST"])
@login_required
def admin_company_user_create(token_id):
    if not current_user.is_bdb or not current_user.is_admin:
        abort(403)
    t = database.get_token_by_id(token_id)
    if not t:
        abort(404)
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    role = request.form.get("role", "admin").strip()
    if role not in ("admin", "viewer", "scheduler"):
        role = "admin"
    if not username or not password:
        flash("Username and password are required.", "error")
    elif database.is_username_taken(username):
        flash(f"Username '{username}' is already taken.", "error")
    else:
        database.create_company_user(username, password, role, t["token"])
        flash(f"Company user '{username}' created for {t['company_name']}.", "success")
    return redirect(url_for("admin.admin_tokens"))


@admin_bp.route("/admin/company-users/<int:user_id>/delete", methods=["POST"])
@login_required
def admin_company_user_delete(user_id):
    if not current_user.is_bdb or not current_user.is_admin:
        abort(403)
    user = database.get_user_by_id(user_id)
    if not user or user.get("token") is None:
        flash("Cannot delete BDB users this way.", "error")
    else:
        database.delete_company_user(user_id)
        flash(f"Company user '{user['username']}' deleted.", "success")
    return redirect(url_for("admin.admin_tokens"))


@admin_bp.route("/admin/company-users/<int:user_id>/reset-password", methods=["POST"])
@login_required
def admin_company_user_reset_password(user_id):
    if not current_user.is_bdb or not current_user.is_admin:
        abort(403)
    user = database.get_user_by_id(user_id)
    if not user or user.get("token") is None:
        flash("Cannot reset BDB user passwords this way.", "error")
    else:
        new_password = request.form.get("new_password", "").strip()
        if not new_password:
            flash("New password is required.", "error")
        else:
            database.update_company_user_password(user_id, new_password)
            flash(f"Password reset for '{user['username']}'.", "success")
    return redirect(url_for("admin.admin_tokens"))


# ---------------------------------------------------------------------------
# Categories Management
# ---------------------------------------------------------------------------

@admin_bp.route("/admin/categories")
@login_required
def admin_categories():
    h = _helpers()
    tokens = h._get_tokens_for_user()
    token_str, selected_token = h._get_selected_token(tokens)
    categories = database.get_categories_by_token(token_str) if token_str else []
    return render_template(
        "admin/categories.html",
        tokens=tokens, selected_token=selected_token, categories=categories,
    )


@admin_bp.route("/admin/categories/create", methods=["POST"])
@login_required
def admin_category_create():
    h = _helpers()
    token_str = request.form.get("token", "").strip()
    h._verify_token_access(token_str)
    name = request.form.get("name", "").strip()
    sort_order = request.form.get("sort_order", "0").strip()
    if not name or not token_str:
        flash("Category name and company are required.", "error")
    else:
        try:
            sort_order_int = int(sort_order)
        except (ValueError, TypeError):
            sort_order_int = 0
        database.create_category(name, token_str, sort_order_int)
        flash(f"Category '{name}' created.", "success")
    return redirect(url_for("admin.admin_categories", token=token_str))


@admin_bp.route("/admin/categories/<int:cat_id>/update", methods=["POST"])
@login_required
def admin_category_update(cat_id):
    h = _helpers()
    cat = database.get_category(cat_id)
    if not cat:
        abort(404)
    h._verify_token_access(cat["token"])

    data = request.get_json()
    if not data:
        abort(400)
    name = data.get("name", "").strip()
    sort_order = data.get("sort_order")
    if not name:
        return jsonify({"success": False, "error": "Name is required."}), 400
    try:
        sort_order_int = int(sort_order) if sort_order is not None else None
    except (ValueError, TypeError):
        sort_order_int = None
    database.update_category(cat_id, name, sort_order_int)
    return jsonify({"success": True})


@admin_bp.route("/admin/categories/<int:cat_id>/toggle", methods=["POST"])
@login_required
def admin_category_toggle(cat_id):
    h = _helpers()
    cat = database.get_category(cat_id)
    if cat:
        h._verify_token_access(cat["token"])
    database.toggle_category(cat_id)
    flash("Category status toggled.", "success")
    return redirect(url_for("admin.admin_categories", token=cat["token"] if cat else ""))


# ---------------------------------------------------------------------------
# Common Tasks Management (for scheduling notes)
# ---------------------------------------------------------------------------

@admin_bp.route("/admin/common-tasks")
@login_required
def admin_common_tasks():
    h = _helpers()
    tokens = h._get_tokens_for_user()
    token_str, selected_token = h._get_selected_token(tokens)
    tasks = database.get_common_tasks_by_token(token_str) if token_str else []
    return render_template(
        "admin/common_tasks.html",
        tokens=tokens, selected_token=selected_token, common_tasks=tasks,
    )


@admin_bp.route("/admin/common-tasks/create", methods=["POST"])
@login_required
def admin_common_task_create():
    h = _helpers()
    token_str = request.form.get("token", "").strip()
    h._verify_token_access(token_str)
    name = request.form.get("name", "").strip()
    sort_order = request.form.get("sort_order", "0").strip()
    if not name or not token_str:
        flash("Task name and company are required.", "error")
    else:
        try:
            sort_order_int = int(sort_order)
        except (ValueError, TypeError):
            sort_order_int = 0
        database.create_common_task(name, token_str, sort_order_int)
        flash(f"Common task '{name}' created.", "success")
    return redirect(url_for("admin.admin_common_tasks", token=token_str))


@admin_bp.route("/admin/common-tasks/<int:task_id>/update", methods=["POST"])
@login_required
def admin_common_task_update(task_id):
    h = _helpers()
    task = database.get_common_task(task_id)
    if not task:
        abort(404)
    h._verify_token_access(task["token"])

    data = request.get_json()
    if not data:
        abort(400)
    name = data.get("name", "").strip()
    sort_order = data.get("sort_order")
    if not name:
        return jsonify({"success": False, "error": "Name is required."}), 400
    try:
        sort_order_int = int(sort_order) if sort_order is not None else None
    except (ValueError, TypeError):
        sort_order_int = None
    database.update_common_task(task_id, name, sort_order_int)
    return jsonify({"success": True})


@admin_bp.route("/admin/common-tasks/<int:task_id>/toggle", methods=["POST"])
@login_required
def admin_common_task_toggle(task_id):
    h = _helpers()
    task = database.get_common_task(task_id)
    if task:
        h._verify_token_access(task["token"])
    database.toggle_common_task(task_id)
    flash("Common task status toggled.", "success")
    return redirect(url_for("admin.admin_common_tasks", token=task["token"] if task else ""))


# ---------------------------------------------------------------------------
# Message Snippets Management
# ---------------------------------------------------------------------------

@admin_bp.route("/admin/message-snippets")
@login_required
def admin_message_snippets():
    h = _helpers()
    tokens = h._get_tokens_for_user()
    token_str, selected_token = h._get_selected_token(tokens)
    snippets = database.get_message_snippets_by_token(token_str) if token_str else []
    return render_template(
        "admin/message_snippets.html",
        tokens=tokens, selected_token=selected_token, snippets=snippets,
    )


@admin_bp.route("/admin/message-snippets/create", methods=["POST"])
@login_required
def admin_message_snippet_create():
    h = _helpers()
    token_str = request.form.get("token", "").strip()
    h._verify_token_access(token_str)
    name = request.form.get("name", "").strip()
    sort_order = request.form.get("sort_order", "0").strip()
    if not name or not token_str:
        flash("Message text and company are required.", "error")
    else:
        try:
            sort_order_int = int(sort_order)
        except (ValueError, TypeError):
            sort_order_int = 0
        database.create_message_snippet(name, token_str, sort_order_int)
        flash("Message snippet created.", "success")
    return redirect(url_for("admin.admin_message_snippets", token=token_str))


@admin_bp.route("/admin/message-snippets/<int:snippet_id>/update", methods=["POST"])
@login_required
def admin_message_snippet_update(snippet_id):
    h = _helpers()
    snippet = database.get_message_snippet(snippet_id)
    if not snippet:
        abort(404)
    h._verify_token_access(snippet["token"])

    data = request.get_json()
    if not data:
        abort(400)
    name = data.get("name", "").strip()
    sort_order = data.get("sort_order")
    if not name:
        return jsonify({"success": False, "error": "Message text is required."}), 400
    try:
        sort_order_int = int(sort_order) if sort_order is not None else None
    except (ValueError, TypeError):
        sort_order_int = None
    database.update_message_snippet(snippet_id, name, sort_order_int)
    return jsonify({"success": True})


@admin_bp.route("/admin/message-snippets/<int:snippet_id>/toggle", methods=["POST"])
@login_required
def admin_message_snippet_toggle(snippet_id):
    h = _helpers()
    snippet = database.get_message_snippet(snippet_id)
    if snippet:
        h._verify_token_access(snippet["token"])
    database.toggle_message_snippet(snippet_id)
    flash("Message snippet status toggled.", "success")
    return redirect(url_for("admin.admin_message_snippets", token=snippet["token"] if snippet else ""))


# ---------------------------------------------------------------------------
# Products & Services Management
# ---------------------------------------------------------------------------

@admin_bp.route("/admin/products-services")
@login_required
def admin_products_services():
    h = _helpers()
    tokens = h._get_tokens_for_user()
    token_str, selected_token = h._get_selected_token(tokens)
    products = database.get_products_services_by_token(token_str) if token_str else []
    return render_template(
        "admin/products_services.html",
        tokens=tokens, selected_token=selected_token, products=products,
    )


@admin_bp.route("/admin/products-services/create", methods=["POST"])
@login_required
def admin_product_service_create():
    h = _helpers()
    token_str = request.form.get("token", "").strip()
    h._verify_token_access(token_str)
    name = request.form.get("name", "").strip()
    unit_price_str = request.form.get("unit_price", "0").strip()
    sort_order = request.form.get("sort_order", "0").strip()
    if not name or not token_str:
        flash("Product/service name and company are required.", "error")
    else:
        try:
            unit_price = float(unit_price_str)
        except (ValueError, TypeError):
            unit_price = 0
        try:
            sort_order_int = int(sort_order)
        except (ValueError, TypeError):
            sort_order_int = 0
        try:
            unit_cost = float(request.form.get("unit_cost", "0").strip())
        except (ValueError, TypeError):
            unit_cost = 0
        item_type = request.form.get("item_type", "product").strip()
        if item_type not in ("product", "service"):
            item_type = "product"
        database.create_product_service(name, unit_price, token_str, sort_order_int, unit_cost, item_type)
        flash(f"Product/service '{name}' created.", "success")
    return redirect(url_for("admin.admin_products_services", token=token_str))


@admin_bp.route("/admin/products-services/<int:ps_id>/update", methods=["POST"])
@login_required
def admin_product_service_update(ps_id):
    h = _helpers()
    ps = database.get_product_service(ps_id)
    if not ps:
        abort(404)
    h._verify_token_access(ps["token"])

    data = request.get_json()
    if not data:
        abort(400)
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"success": False, "error": "Name is required."}), 400
    try:
        unit_price = float(data["unit_price"]) if "unit_price" in data else None
    except (ValueError, TypeError):
        unit_price = None
    try:
        unit_cost = float(data["unit_cost"]) if "unit_cost" in data else None
    except (ValueError, TypeError):
        unit_cost = None
    try:
        sort_order_int = int(data["sort_order"]) if "sort_order" in data else None
    except (ValueError, TypeError):
        sort_order_int = None
    item_type = data.get("item_type")
    if item_type not in (None, "product", "service"):
        item_type = "product"
    updates = {"name": name}
    if unit_price is not None:
        updates["unit_price"] = unit_price
    if unit_cost is not None:
        updates["unit_cost"] = unit_cost
    if sort_order_int is not None:
        updates["sort_order"] = sort_order_int
    if item_type is not None:
        updates["item_type"] = item_type
    database.update_product_service(ps_id, **updates)
    return jsonify({"success": True})


@admin_bp.route("/admin/products-services/<int:ps_id>/toggle", methods=["POST"])
@login_required
def admin_product_service_toggle(ps_id):
    h = _helpers()
    ps = database.get_product_service(ps_id)
    if ps:
        h._verify_token_access(ps["token"])
    database.toggle_product_service(ps_id)
    flash("Product/service status toggled.", "success")
    return redirect(url_for("admin.admin_products_services", token=ps["token"] if ps else ""))


# ---------------------------------------------------------------------------
# Shift Types Management
# ---------------------------------------------------------------------------

@admin_bp.route("/admin/shift-types")
@login_required
def admin_shift_types():
    h = _helpers()
    tokens = h._get_tokens_for_user()
    token_str, selected_token = h._get_selected_token(tokens)
    shifts = database.get_shift_types_by_token(token_str) if token_str else []
    return render_template(
        "admin/shift_types.html",
        tokens=tokens, selected_token=selected_token, shift_types=shifts,
    )


@admin_bp.route("/admin/shift-types/create", methods=["POST"])
@login_required
def admin_shift_type_create():
    h = _helpers()
    token_str = request.form.get("token", "").strip()
    h._verify_token_access(token_str)
    name = request.form.get("name", "").strip()
    start_time = request.form.get("start_time", "07:00").strip()
    end_time = request.form.get("end_time", "17:00").strip()
    sort_order = request.form.get("sort_order", "0").strip()
    if not name or not token_str:
        flash("Shift name and company are required.", "error")
    elif not start_time or not end_time:
        flash("Start time and end time are required.", "error")
    else:
        try:
            sort_order_int = int(sort_order)
        except (ValueError, TypeError):
            sort_order_int = 0
        database.create_shift_type(name, start_time, end_time, token_str, sort_order_int)
        flash(f"Shift type '{name}' created.", "success")
    return redirect(url_for("admin.admin_shift_types", token=token_str))


@admin_bp.route("/admin/shift-types/<int:shift_id>/update", methods=["POST"])
@login_required
def admin_shift_type_update(shift_id):
    h = _helpers()
    shift = database.get_shift_type(shift_id)
    if not shift:
        abort(404)
    h._verify_token_access(shift["token"])

    data = request.get_json()
    if not data:
        abort(400)
    name = data.get("name", "").strip()
    start_time = data.get("start_time", "").strip()
    end_time = data.get("end_time", "").strip()
    if not name:
        return jsonify({"success": False, "error": "Name is required."}), 400
    if not start_time or not end_time:
        return jsonify({"success": False, "error": "Start and end times are required."}), 400
    try:
        sort_order_int = int(data["sort_order"]) if "sort_order" in data else None
    except (ValueError, TypeError):
        sort_order_int = None
    database.update_shift_type(shift_id, name, start_time, end_time, sort_order_int)
    return jsonify({"success": True})


@admin_bp.route("/admin/shift-types/<int:shift_id>/toggle", methods=["POST"])
@login_required
def admin_shift_type_toggle(shift_id):
    h = _helpers()
    shift = database.get_shift_type(shift_id)
    if shift:
        h._verify_token_access(shift["token"])
    database.toggle_shift_type(shift_id)
    flash("Shift type status toggled.", "success")
    return redirect(url_for("admin.admin_shift_types", token=shift["token"] if shift else ""))
