"""Employee-facing timekeeper routes (clock in/out, login, help)."""

from datetime import datetime

from flask import (
    Blueprint, flash, jsonify, redirect, render_template, request,
    session, url_for,
)

import database

timekeeper_bp = Blueprint('timekeeper', __name__)


# ---------------------------------------------------------------------------
# Lazy import helpers to avoid circular imports
# ---------------------------------------------------------------------------

def _helpers():
    import app as _app
    return _app


# ---------------------------------------------------------------------------
# Employee Login / Logout
# ---------------------------------------------------------------------------

@timekeeper_bp.route("/timekeeper/login")
def timekeeper_login():
    """Redirect to company home for login."""
    token_str = request.args.get("token", "")
    if token_str:
        return redirect(url_for("company_home", token_str=token_str))
    return redirect(url_for("login"))


@timekeeper_bp.route("/timekeeper/logout")
def timekeeper_logout():
    token_str = session.get("employee_token", "")
    session.pop("employee_id", None)
    session.pop("employee_token", None)
    session.pop("employee_name", None)
    if token_str:
        return redirect(url_for("company_home", token_str=token_str))
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Timekeeper Page (employee clock in/out interface)
# ---------------------------------------------------------------------------

@timekeeper_bp.route("/timekeeper")
def timekeeper_page():
    emp_id = session.get("employee_id")
    token_str = session.get("employee_token", "")

    if not emp_id or not token_str:
        token_param = request.args.get("token", "")
        if token_param:
            return redirect(url_for("company_home", token_str=token_param))
        return redirect(url_for("login"))

    token_data = database.get_token(token_str)
    if not token_data or not token_data["is_active"]:
        session.pop("employee_id", None)
        session.pop("employee_token", None)
        return render_template("errors/invalid_token.html"), 403

    employee = database.get_employee(emp_id)
    if not employee or not employee["is_active"] or employee["token"] != token_str:
        session.pop("employee_id", None)
        session.pop("employee_token", None)
        return redirect(url_for("company_home", token_str=token_str))

    jobs = database.get_jobs_by_token(token_str, active_only=True)

    return render_template(
        "employee/timekeeper.html",
        token=token_data, employee=employee, jobs=jobs,
    )


# ---------------------------------------------------------------------------
# Help Page
# ---------------------------------------------------------------------------

@timekeeper_bp.route("/help")
def timekeeper_help():
    _app = _helpers()
    token_str = request.args.get("token", "") or session.get("employee_token", "")
    token_data = database.get_token(token_str) if token_str else None
    employee = _app._require_employee_session(token_str) if token_str else None
    return render_template("employee/help.html", token=token_data, employee=employee)


# ---------------------------------------------------------------------------
# Employee Tasks Checklist
# ---------------------------------------------------------------------------

@timekeeper_bp.route("/tasks")
def employee_tasks():
    _app = _helpers()
    token_str = request.args.get("token", "") or session.get("employee_token", "")
    token_data = database.get_token(token_str) if token_str else None
    if not token_data or not token_data["is_active"]:
        abort(404)

    employee = _app._require_employee_session(token_str)
    if not employee:
        return redirect(url_for("company_home", token_str=token_str))

    if not employee.get("tasks_access"):
        abort(403)

    today = datetime.now().strftime("%Y-%m-%d")

    # Jobs from today's schedule
    schedules = database.get_schedules_for_employee_date(employee["id"], token_str, today)
    # Also check active time entry
    active_entry = database.get_active_time_entry_for_employee(employee["id"], token_str)

    # Build deduplicated job_id list (active entry first)
    job_ids = []
    seen = set()
    if active_entry and active_entry.get("job_id"):
        jid = active_entry["job_id"]
        if jid not in seen:
            job_ids.append(jid)
            seen.add(jid)
    for s in schedules:
        if s.get("job_id") and s["job_id"] not in seen:
            job_ids.append(s["job_id"])
            seen.add(s["job_id"])

    # Get the estimate_id for each job (use most recent completed estimate)
    jobs_tasks = []
    for job_id in job_ids:
        job = database.get_job(job_id)
        if not job or job["token"] != token_str:
            continue
        # Look up estimate_id from schedule if available
        est_id = None
        for s in schedules:
            if s.get("job_id") == job_id and s.get("estimate_id"):
                est_id = s["estimate_id"]
                break
        tasks = database.get_merged_tasks_for_job(token_str, job_id, est_id, today)
        jobs_tasks.append({"job": job, "tasks": tasks, "estimate_id": est_id})

    return render_template(
        "employee/tasks.html",
        token=token_data,
        employee=employee,
        today=today,
        jobs_tasks=jobs_tasks,
    )


@timekeeper_bp.route("/api/tasks/check", methods=["POST"])
def api_tasks_check():
    _app = _helpers()
    data = request.get_json(silent=True) or {}
    token_str = data.get("token", "")

    if not token_str:
        return jsonify({"error": "Missing token"}), 400

    token_data = database.get_token(token_str)
    if not token_data or not token_data["is_active"]:
        return jsonify({"error": "Invalid token"}), 403

    employee = _app._require_employee_session(token_str)
    if not employee:
        return jsonify({"error": "Not authenticated"}), 401

    job_id = data.get("job_id")
    task_source = data.get("task_source")
    task_ref_id = data.get("task_ref_id")
    task_description = data.get("task_description", "")
    checked = data.get("checked", True)
    shift_date = data.get("shift_date", datetime.now().strftime("%Y-%m-%d"))
    estimate_id = data.get("estimate_id") or None

    if not all([job_id, task_source, task_ref_id is not None]):
        return jsonify({"error": "Missing required fields"}), 400

    # Validate task_source (security: Gap 3)
    if task_source not in ("job_task", "estimate_task", "template_item"):
        return jsonify({"error": "invalid source"}), 400

    # Validate job ownership (security: Gap 2)
    job = database.get_job(int(job_id))
    if not job or job["token"] != token_str:
        return jsonify({"error": "invalid job"}), 403

    if checked:
        database.log_task_completion(
            token_str=token_str,
            job_id=int(job_id),
            estimate_id=int(estimate_id) if estimate_id else None,
            schedule_id=None,
            task_source=task_source,
            task_ref_id=int(task_ref_id),
            task_description=task_description,
            employee_id=employee["id"],
            employee_name=employee["name"],
            shift_date=shift_date,
        )
    else:
        database.remove_task_completion(
            token_str=token_str,
            job_id=int(job_id),
            task_source=task_source,
            task_ref_id=int(task_ref_id),
            task_description=task_description,
            employee_id=employee["id"],
            shift_date=shift_date,
        )

    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# API - Clock In
# ---------------------------------------------------------------------------

@timekeeper_bp.route("/api/clock-in", methods=["POST"])
def api_clock_in():
    _app = _helpers()

    # Validate employee session
    session_emp_id = session.get("employee_id")
    session_token = session.get("employee_token", "")
    if not session_emp_id:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json() or {}
    employee_id = data.get("employee_id")
    job_id = data.get("job_id")
    lat = data.get("latitude")
    lng = data.get("longitude")

    if employee_id != session_emp_id:
        return jsonify({"error": "Employee mismatch"}), 403

    token_data = database.get_token(session_token)
    if not token_data or not token_data["is_active"]:
        return jsonify({"error": "Invalid token"}), 403

    import config
    if _app._is_rate_limited(session_token, _app._rate_limits, config.RATE_LIMIT, 60):
        return jsonify({"error": "Rate limit exceeded"}), 429

    if not employee_id or not job_id:
        return jsonify({"error": "Employee and job required"}), 400

    # Check for existing active entry
    active = database.get_active_entry_for_employee(employee_id)
    if active:
        return jsonify({"error": "Already clocked in", "active_entry": active}), 409

    now = datetime.now().isoformat()
    method = "mobile" if lat is not None else "system"

    entry_id = database.create_time_entry(
        employee_id, job_id, session_token, now, lat, lng, method,
    )

    # Audit
    database.add_audit_log(entry_id, session_token, "clock_in", None, None, now, "employee")

    return jsonify({"success": True, "entry_id": entry_id, "clock_in_time": now}), 201


# ---------------------------------------------------------------------------
# API - Clock Out
# ---------------------------------------------------------------------------

@timekeeper_bp.route("/api/clock-out", methods=["POST"])
def api_clock_out():
    # Validate employee session
    session_emp_id = session.get("employee_id")
    session_token = session.get("employee_token", "")
    if not session_emp_id:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json() or {}
    employee_id = data.get("employee_id")
    lat = data.get("latitude")
    lng = data.get("longitude")

    if employee_id != session_emp_id:
        return jsonify({"error": "Employee mismatch"}), 403

    token_data = database.get_token(session_token)
    if not token_data or not token_data["is_active"]:
        return jsonify({"error": "Invalid token"}), 403

    if not employee_id:
        return jsonify({"error": "Employee required"}), 400

    active = database.get_active_entry_for_employee(employee_id)
    if not active:
        return jsonify({"error": "No active clock-in found"}), 404

    now = datetime.now().isoformat()
    method = "mobile" if lat is not None else "system"

    total_hours = database.clock_out_entry(active["id"], now, lat, lng, method)

    # Audit
    database.add_audit_log(active["id"], session_token, "clock_out", None, None, now, "employee")

    return jsonify({
        "success": True, "entry_id": active["id"],
        "clock_out_time": now, "total_hours": total_hours,
    })


# ---------------------------------------------------------------------------
# API - Employee Status
# ---------------------------------------------------------------------------

@timekeeper_bp.route("/api/employee-status")
def api_employee_status():
    session_emp_id = session.get("employee_id")
    if not session_emp_id:
        return jsonify({"error": "Not logged in"}), 401

    employee_id = request.args.get("employee_id", type=int)
    if employee_id != session_emp_id:
        return jsonify({"error": "Employee mismatch"}), 403

    active = database.get_active_entry_for_employee(employee_id)
    today = database.get_today_entries_for_employee(employee_id)

    return jsonify({
        "active_entry": active,
        "today_entries": today,
    })
