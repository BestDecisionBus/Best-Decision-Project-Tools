"""
Scheduling routes — scheduler dashboard, schedule CRUD, admin/employee views.
"""

from datetime import datetime
from functools import wraps

from flask import (
    Blueprint, abort, flash, jsonify, redirect, render_template, request,
    session, url_for,
)
from flask_login import current_user, login_required, login_user

import database

# ---------------------------------------------------------------------------
# Lazy import for app-level helpers
# ---------------------------------------------------------------------------

def _helpers():
    import app as _app
    return _app


# ---------------------------------------------------------------------------
# Blueprint
# ---------------------------------------------------------------------------

scheduling_bp = Blueprint("scheduling", __name__)


def _build_composite_notes(common_task_ids, job_task_id, custom_note, fallback_notes=""):
    """Build composite notes string from 3-tier task fields for backward-compatible display.
    common_task_ids may be a list of IDs or a single int/str (legacy)."""
    parts = []
    if common_task_ids:
        ids = common_task_ids if isinstance(common_task_ids, list) else [common_task_ids]
        for ctid in ids:
            ct = database.get_common_task(int(ctid))
            if ct:
                parts.append(ct["name"])
    if job_task_id:
        jt = database.get_job_task(int(job_task_id))
        if jt:
            parts.append(jt["name"])
    if custom_note:
        parts.append(custom_note)
    if parts:
        return " | ".join(parts)
    return fallback_notes


# ---------------------------------------------------------------------------
# Quick-select shift presets
# ---------------------------------------------------------------------------

def _resolve_shift(shift_type, start_time, end_time):
    """Resolve shift times from a DB shift type ID or 'custom'.
    Returns (start_time, end_time, error_msg_or_None)."""
    if shift_type == "custom":
        if not start_time or not end_time:
            return None, None, "Custom shifts require start_time and end_time"
        return start_time, end_time, None
    # Try numeric DB shift type
    try:
        shift_id = int(shift_type)
        st = database.get_shift_type(shift_id)
        if st:
            return st["start_time"], st["end_time"], None
    except (ValueError, TypeError):
        pass
    # Unknown shift type — treat as custom
    if not start_time or not end_time:
        return None, None, "Unknown shift type and no custom times provided"
    return start_time, end_time, None


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

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
# Scheduler login
# ---------------------------------------------------------------------------

@scheduling_bp.route("/scheduler/login", methods=["GET", "POST"])
def scheduler_login():
    if current_user.is_authenticated:
        if current_user.is_scheduler or current_user.is_admin:
            return redirect(url_for("scheduling.scheduler_dashboard"))
        return redirect(url_for("admin.admin_dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = database.verify_user(username, password)
        if user:
            if user.get("token"):
                token_data = database.get_token(user["token"])
                if not token_data or not token_data["is_active"]:
                    flash("Your company account is currently deactivated.", "error")
                    return render_template("scheduler/login.html")
            helpers = _helpers()
            login_user(helpers.User(user))
            if user["role"] == "scheduler":
                return redirect(url_for("scheduling.scheduler_dashboard"))
            return redirect(url_for("admin.admin_dashboard"))
        flash("Invalid credentials.", "error")

    return render_template("scheduler/login.html")


# ---------------------------------------------------------------------------
# Scheduler dashboard
# ---------------------------------------------------------------------------

@scheduling_bp.route("/scheduler")
@scheduler_allowed
def scheduler_dashboard():
    helpers = _helpers()

    tokens = helpers._get_tokens_for_user()
    selected_token, token_data = helpers._get_selected_token(tokens)

    employees = []
    jobs = []
    shift_types = []
    if token_data:
        employees = database.get_employees_by_token(selected_token, active_only=True)
        jobs = database.get_jobs_by_token(selected_token, active_only=True)
        shift_types = database.get_shift_types_by_token(selected_token, active_only=True)

    return render_template(
        "scheduler/schedule.html",
        tokens=tokens,
        selected_token=selected_token,
        token_data=token_data,
        employees=employees,
        jobs=jobs,
        shift_types=shift_types,
    )


# ---------------------------------------------------------------------------
# Schedule CRUD API
# ---------------------------------------------------------------------------

@scheduling_bp.route("/scheduler/api/schedules", methods=["POST"])
@scheduler_allowed
def api_create_schedule():
    helpers = _helpers()
    data = request.get_json(silent=True) or {}

    employee_id = data.get("employee_id")
    job_id = data.get("job_id")
    estimate_id = data.get("estimate_id") or None
    token_str = data.get("token", "")
    date = data.get("date", "")
    shift_type = data.get("shift_type", "custom")
    start_time = data.get("start_time", "")
    end_time = data.get("end_time", "")
    notes = data.get("notes", "")

    # Derive job_id from estimate if not provided
    if estimate_id and not job_id:
        est = database.get_estimate(int(estimate_id))
        if est and est.get("job_id"):
            job_id = est["job_id"]

    # 3-tier task fields
    common_task_ids = data.get("common_task_ids") or []
    if not common_task_ids and data.get("common_task_id"):
        common_task_ids = [data.get("common_task_id")]  # legacy single-value compat
    common_task_id = int(common_task_ids[0]) if common_task_ids else None  # for DB column
    job_task_id = data.get("job_task_id") or None
    custom_note = data.get("custom_note", "").strip()

    # Build composite notes from 3 tiers (backward-compatible display)
    notes = _build_composite_notes(common_task_ids, job_task_id, custom_note, notes)

    # Validate required fields
    if not all([employee_id, job_id, token_str, date]):
        return jsonify({"error": "Missing required fields"}), 400

    # Resolve shift times from DB or custom
    start_time, end_time, shift_err = _resolve_shift(shift_type, start_time, end_time)
    if shift_err:
        return jsonify({"error": shift_err}), 400

    # Validate date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    # Verify token access
    helpers._verify_token_access(token_str)

    try:
        schedule_id = database.create_schedule(
            employee_id=int(employee_id),
            job_id=int(job_id),
            token_str=token_str,
            date=date,
            start_time=start_time,
            end_time=end_time,
            shift_type=shift_type,
            notes=notes,
            created_by=current_user.username,
            common_task_id=int(common_task_id) if common_task_id else None,
            job_task_id=int(job_task_id) if job_task_id else None,
            custom_note=custom_note,
            estimate_id=int(estimate_id) if estimate_id else None,
        )
    except Exception as e:
        return jsonify({"error": f"Database error: {e}"}), 500

    # Save task list assignments for this schedule entry
    raw_task_ids = data.get("task_template_ids", [])
    include_pt = 1 if "project_tasks" in [str(x) for x in raw_task_ids] else 0
    tmpl_ids = [int(x) for x in raw_task_ids if str(x) != "project_tasks"]
    if include_pt:
        database.update_schedule_project_tasks_flag(schedule_id, include_pt)
    if tmpl_ids:
        database.set_task_links_for_schedule(schedule_id, tmpl_ids, token_str)

    # Save common task (standard task) links
    if common_task_ids:
        database.set_common_task_links_for_schedule(schedule_id, [int(x) for x in common_task_ids], token_str)

    schedule = database.get_schedule(schedule_id)
    return jsonify(schedule), 201


@scheduling_bp.route("/scheduler/api/schedules/<int:schedule_id>", methods=["PUT"])
@scheduler_allowed
def api_update_schedule(schedule_id):
    helpers = _helpers()
    data = request.get_json(silent=True) or {}

    existing = database.get_schedule(schedule_id)
    if not existing:
        return jsonify({"error": "Schedule not found"}), 404

    # Verify token access
    helpers._verify_token_access(existing["token"])

    employee_id = data.get("employee_id", existing["employee_id"])
    job_id = data.get("job_id", existing["job_id"])
    estimate_id = data.get("estimate_id", existing.get("estimate_id")) or None
    # Derive job_id from estimate if changed and job_id not explicitly given
    if estimate_id and "estimate_id" in data and "job_id" not in data:
        est = database.get_estimate(int(estimate_id))
        if est and est.get("job_id"):
            job_id = est["job_id"]
    date = data.get("date", existing["date"])
    shift_type = data.get("shift_type", existing["shift_type"])
    start_time = data.get("start_time", existing["start_time"])
    end_time = data.get("end_time", existing["end_time"])
    notes = data.get("notes", existing["notes"])

    # 3-tier task fields
    common_task_ids = data.get("common_task_ids") or []
    if not common_task_ids and data.get("common_task_id"):
        common_task_ids = [data.get("common_task_id")]
    if not common_task_ids and existing.get("common_task_id"):
        common_task_ids = [existing.get("common_task_id")]
    common_task_id = int(common_task_ids[0]) if common_task_ids else None
    job_task_id = data.get("job_task_id", existing.get("job_task_id")) or None
    custom_note = data.get("custom_note", existing.get("custom_note", "")).strip()

    # Build composite notes
    notes = _build_composite_notes(common_task_ids, job_task_id, custom_note, notes)

    # Resolve shift times from DB or custom
    start_time, end_time, shift_err = _resolve_shift(shift_type, start_time, end_time)
    if shift_err:
        return jsonify({"error": shift_err}), 400

    # Validate date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    database.update_schedule(
        schedule_id=schedule_id,
        employee_id=int(employee_id),
        job_id=int(job_id),
        date=date,
        start_time=start_time,
        end_time=end_time,
        shift_type=shift_type,
        notes=notes,
        common_task_id=int(common_task_id) if common_task_id else None,
        job_task_id=int(job_task_id) if job_task_id else None,
        custom_note=custom_note,
        estimate_id=int(estimate_id) if estimate_id else None,
    )

    token_str = existing["token"]

    # Update task list assignments if provided in this request
    if "task_template_ids" in data:
        raw_task_ids = data.get("task_template_ids", [])
        include_pt = 1 if "project_tasks" in [str(x) for x in raw_task_ids] else 0
        tmpl_ids = [int(x) for x in raw_task_ids if str(x) != "project_tasks"]
        database.update_schedule_project_tasks_flag(schedule_id, include_pt)
        database.set_task_links_for_schedule(schedule_id, tmpl_ids, token_str)

    # Update common task links if provided in this request
    if "common_task_ids" in data:
        database.set_common_task_links_for_schedule(
            schedule_id, [int(x) for x in data.get("common_task_ids", [])], token_str
        )

    updated = database.get_schedule(schedule_id)
    return jsonify(updated), 200


@scheduling_bp.route("/scheduler/api/schedules/<int:schedule_id>", methods=["DELETE"])
@scheduler_allowed
def api_delete_schedule(schedule_id):
    helpers = _helpers()

    existing = database.get_schedule(schedule_id)
    if not existing:
        return jsonify({"error": "Schedule not found"}), 404

    # Verify token access
    helpers._verify_token_access(existing["token"])

    database.delete_schedule(schedule_id)
    return jsonify({"success": True}), 200


@scheduling_bp.route("/scheduler/api/schedules/<int:schedule_id>/task-links", methods=["GET"])
@scheduler_allowed
def api_get_schedule_task_links(schedule_id):
    """Return task link IDs for a schedule entry (for edit pre-population)."""
    helpers = _helpers()
    existing = database.get_schedule(schedule_id)
    if not existing:
        return jsonify({"error": "Schedule not found"}), 404
    helpers._verify_token_access(existing["token"])
    tmpl_ids = database.get_task_link_ids_for_schedule(schedule_id)
    include_pt = existing.get("include_project_tasks", 0)
    result = []
    if include_pt:
        result.append("project_tasks")
    result.extend(str(tid) for tid in tmpl_ids)
    return jsonify(result)


@scheduling_bp.route("/scheduler/api/schedules/<int:schedule_id>/common-task-links", methods=["GET"])
@scheduler_allowed
def api_get_schedule_common_task_links(schedule_id):
    """Return common task IDs assigned to a schedule entry (for edit pre-population)."""
    helpers = _helpers()
    existing = database.get_schedule(schedule_id)
    if not existing:
        return jsonify({"error": "Schedule not found"}), 404
    helpers._verify_token_access(existing["token"])
    ids = database.get_common_task_link_ids_for_schedule(schedule_id)
    return jsonify([str(i) for i in ids])


@scheduling_bp.route("/scheduler/api/schedules", methods=["GET"])
@login_required
def api_get_schedules():
    helpers = _helpers()

    week_start = request.args.get("week_start", "")
    week_end = request.args.get("week_end", "")

    if not week_start or not week_end:
        return jsonify({"error": "week_start and week_end are required (YYYY-MM-DD)"}), 400

    # Validate date formats
    try:
        datetime.strptime(week_start, "%Y-%m-%d")
        datetime.strptime(week_end, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    # Determine which token to query
    _, token_data = helpers._get_selected_token(helpers._get_tokens_for_user())
    if not token_data:
        return jsonify([])

    token_str = token_data["token"]
    schedules = database.get_schedules_for_week(token_str, week_start, week_end)
    return jsonify(schedules), 200


# ---------------------------------------------------------------------------
# Scheduler API — add employees & jobs
# ---------------------------------------------------------------------------

@scheduling_bp.route("/scheduler/api/employees", methods=["POST"])
@scheduler_allowed
def api_add_employee():
    helpers = _helpers()
    data = request.get_json(silent=True) or {}

    name = data.get("name", "").strip()
    employee_id_str = data.get("employee_id", "").strip()
    token_str = data.get("token", "")

    if not name or not employee_id_str or not token_str:
        return jsonify({"error": "name, employee_id, and token are required"}), 400

    # Verify token access
    helpers._verify_token_access(token_str)

    database.create_employee(name, employee_id_str, token_str)

    return jsonify({"success": True, "name": name}), 201


@scheduling_bp.route("/scheduler/api/jobs", methods=["POST"])
@scheduler_allowed
def api_add_job():
    helpers = _helpers()
    data = request.get_json(silent=True) or {}

    job_name = data.get("job_name", "").strip()
    job_address = data.get("job_address", "").strip()
    token_str = data.get("token", "")
    latitude = data.get("latitude")
    longitude = data.get("longitude")

    if not job_name or not job_address or not token_str:
        return jsonify({"error": "job_name, job_address, and token are required"}), 400

    # Verify token access
    helpers._verify_token_access(token_str)

    database.create_job(job_name, job_address, latitude, longitude, token_str)

    return jsonify({"success": True, "job_name": job_name}), 201


@scheduling_bp.route("/scheduler/api/job-estimates")
@scheduler_allowed
def api_job_estimates():
    """Return active estimates/projects for a job (for scheduler project dropdown)."""
    helpers = _helpers()
    job_id = request.args.get("job_id", type=int)
    token_str = request.args.get("token", "")
    if not job_id or not token_str:
        return jsonify([])
    helpers._verify_token_access(token_str)
    estimates = database.get_estimates_by_job(job_id)
    result = []
    for e in estimates:
        if e.get("token") != token_str:
            continue
        display = database.get_project_display_name(e)
        result.append({"id": e["id"], "name": display})
    return jsonify(result)


@scheduling_bp.route("/scheduler/api/estimate-templates")
@scheduler_allowed
def api_estimate_templates():
    """Return task lists (templates + project tasks flag) available for a project."""
    helpers = _helpers()
    token_str = request.args.get("token", "")
    estimate_id = request.args.get("estimate_id", type=int)
    if not token_str or not estimate_id:
        return jsonify([])
    helpers._verify_token_access(token_str)
    templates = database.get_templates_for_estimate(estimate_id, token_str)
    project_tasks = database.get_project_tasks_by_estimate(estimate_id, token_str)
    result = []
    if project_tasks:
        result.append({"id": "project_tasks", "name": "Project Specific Tasks"})
    result.extend({"id": t["id"], "name": t["name"]} for t in templates)
    return jsonify(result)


# ---------------------------------------------------------------------------
# Admin schedule view
# ---------------------------------------------------------------------------

@scheduling_bp.route("/admin/schedules")
@login_required
def admin_schedules():
    helpers = _helpers()

    tokens = helpers._get_tokens_for_user()
    selected_token, token_data = helpers._get_selected_token(tokens)

    employees = []
    jobs = []
    shift_types = []
    if token_data:
        employees = database.get_employees_by_token(selected_token, active_only=True)
        jobs = database.get_jobs_by_token(selected_token, active_only=True)
        shift_types = database.get_shift_types_by_token(selected_token, active_only=True)

    return render_template(
        "admin/schedules.html",
        tokens=tokens,
        selected_token=selected_token,
        token_data=token_data,
        employees=employees,
        jobs=jobs,
        shift_types=shift_types,
    )


# ---------------------------------------------------------------------------
# Employee schedule view
# ---------------------------------------------------------------------------

@scheduling_bp.route("/schedule")
def employee_schedule():
    token_str = request.args.get("token", "")
    if not token_str:
        abort(404)

    token_data = database.get_token(token_str)
    if not token_data or not token_data["is_active"]:
        abort(404)

    # Require employee session
    h = _helpers()
    employee = h._require_employee_session(token_str)
    if not employee:
        return redirect(url_for("company_home", token_str=token_str))

    schedules = database.get_employee_upcoming_schedules(employee["id"], days=14)

    return render_template(
        "employee/my_schedule.html",
        token=token_data,
        employee=employee,
        schedules=schedules,
    )
