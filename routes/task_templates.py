"""Admin blueprint — Task Templates management (two-level: templates → items)."""

import csv
import io

from flask import (
    Blueprint, Response, abort, flash, redirect, render_template, request,
    url_for,
)
from flask_login import current_user, login_required

import database

task_templates_bp = Blueprint("task_templates", __name__)


def _helpers():
    import app as _app
    return _app


def _require_admin():
    """Abort 403 if the current user is not an admin or BDB user."""
    if not current_user.is_admin and not current_user.is_bdb:
        abort(403)


# ---------------------------------------------------------------------------
# Template list
# ---------------------------------------------------------------------------

@task_templates_bp.route("/admin/task-templates")
@login_required
def admin_task_templates():
    _app = _helpers()
    tokens = _app._get_tokens_for_user()
    if not current_user.is_bdb:
        token_str = current_user.token
    else:
        token_str = request.args.get("token", "")
        if not token_str and tokens:
            token_str = tokens[0]["token"]
    selected_token = database.get_token(token_str) if token_str else None
    templates = database.get_task_templates(token_str) if token_str else []
    return render_template(
        "admin/task_templates.html",
        tokens=tokens,
        selected_token=selected_token,
        templates=templates,
    )


# ---------------------------------------------------------------------------
# Create template
# ---------------------------------------------------------------------------

@task_templates_bp.route("/admin/task-templates/create", methods=["POST"])
@login_required
def admin_task_template_create():
    _require_admin()
    _app = _helpers()
    token_str = request.form.get("token", "").strip()
    _app._verify_token_access(token_str)
    name = request.form.get("name", "").strip()
    if not name:
        flash("Template name is required.", "error")
    else:
        database.create_task_template(name, token_str)
        flash("Template created.", "success")
    return redirect(url_for("task_templates.admin_task_templates", token=token_str))


# ---------------------------------------------------------------------------
# Template detail (items list)
# ---------------------------------------------------------------------------

@task_templates_bp.route("/admin/task-templates/<int:template_id>")
@login_required
def admin_task_template_detail(template_id):
    _app = _helpers()
    tokens = _app._get_tokens_for_user()
    token_str = current_user.token if not current_user.is_bdb else request.args.get("token", "")
    template = database.get_task_template(template_id, token_str or None)
    if not template:
        abort(404)
    items = database.get_template_items(template_id)
    selected_token = database.get_token(template["token"])
    return render_template(
        "admin/task_template_detail.html",
        template=template,
        items=items,
        tokens=tokens,
        selected_token=selected_token,
    )


# ---------------------------------------------------------------------------
# Edit template name
# ---------------------------------------------------------------------------

@task_templates_bp.route("/admin/task-templates/<int:template_id>/edit", methods=["POST"])
@login_required
def admin_task_template_edit(template_id):
    _require_admin()
    _app = _helpers()
    token_str = request.form.get("token", "").strip()
    _app._verify_token_access(token_str)
    template = database.get_task_template(template_id, token_str)
    if not template:
        abort(404)
    name = request.form.get("name", "").strip()
    if not name:
        flash("Template name is required.", "error")
    else:
        database.update_task_template(template_id, name)
        flash("Template updated.", "success")
    return redirect(url_for("task_templates.admin_task_template_detail",
                            template_id=template_id, token=token_str))


# ---------------------------------------------------------------------------
# Toggle template active/inactive
# ---------------------------------------------------------------------------

@task_templates_bp.route("/admin/task-templates/<int:template_id>/toggle", methods=["POST"])
@login_required
def admin_task_template_toggle(template_id):
    _require_admin()
    _app = _helpers()
    token_str = request.form.get("token", "").strip()
    _app._verify_token_access(token_str)
    template = database.get_task_template(template_id, token_str)
    if not template:
        abort(404)
    database.toggle_task_template(template_id)
    return redirect(url_for("task_templates.admin_task_templates", token=token_str))


# ---------------------------------------------------------------------------
# Sort template
# ---------------------------------------------------------------------------

@task_templates_bp.route("/admin/task-templates/<int:template_id>/sort", methods=["POST"])
@login_required
def admin_task_template_sort(template_id):
    _require_admin()
    _app = _helpers()
    template = database.get_task_template(template_id)
    if not template:
        abort(404)
    _app._verify_token_access(template["token"])
    try:
        sort_order = int(request.form.get("sort_order", 0))
    except ValueError:
        sort_order = 0
    database.update_task_template_sort(template_id, sort_order)
    return ("", 204)


# ---------------------------------------------------------------------------
# Delete template
# ---------------------------------------------------------------------------

@task_templates_bp.route("/admin/task-templates/<int:template_id>/delete", methods=["POST"])
@login_required
def admin_task_template_delete(template_id):
    _require_admin()
    _app = _helpers()
    token_str = request.form.get("token", "").strip()
    _app._verify_token_access(token_str)
    success = database.delete_task_template(template_id)
    if not success:
        flash("Cannot delete — template still has active items.", "error")
    else:
        flash("Template deleted.", "success")
    return redirect(url_for("task_templates.admin_task_templates", token=token_str))


# ---------------------------------------------------------------------------
# Create item
# ---------------------------------------------------------------------------

@task_templates_bp.route("/admin/task-templates/<int:template_id>/items/create", methods=["POST"])
@login_required
def admin_template_item_create(template_id):
    _require_admin()
    _app = _helpers()
    token_str = request.form.get("token", "").strip()
    _app._verify_token_access(token_str)
    template = database.get_task_template(template_id, token_str)
    if not template:
        abort(404)
    description = request.form.get("description", "").strip()
    if not description:
        flash("Task description is required.", "error")
    else:
        database.create_template_item(template_id, description, token_str)
        flash("Task added.", "success")
    return redirect(url_for("task_templates.admin_task_template_detail",
                            template_id=template_id, token=token_str))


# ---------------------------------------------------------------------------
# Edit item
# ---------------------------------------------------------------------------

@task_templates_bp.route("/admin/task-templates/<int:template_id>/items/<int:item_id>/edit",
                         methods=["POST"])
@login_required
def admin_template_item_edit(template_id, item_id):
    _require_admin()
    _app = _helpers()
    token_str = request.form.get("token", "").strip()
    _app._verify_token_access(token_str)
    description = request.form.get("description", "").strip()
    if not description:
        flash("Task description is required.", "error")
    else:
        database.update_template_item(item_id, description)
        flash("Task updated.", "success")
    return redirect(url_for("task_templates.admin_task_template_detail",
                            template_id=template_id, token=token_str))


# ---------------------------------------------------------------------------
# Toggle item
# ---------------------------------------------------------------------------

@task_templates_bp.route("/admin/task-templates/<int:template_id>/items/<int:item_id>/toggle",
                         methods=["POST"])
@login_required
def admin_template_item_toggle(template_id, item_id):
    _require_admin()
    _app = _helpers()
    token_str = request.form.get("token", "").strip()
    _app._verify_token_access(token_str)
    database.toggle_template_item(item_id)
    return redirect(url_for("task_templates.admin_task_template_detail",
                            template_id=template_id, token=token_str))


# ---------------------------------------------------------------------------
# Sort item
# ---------------------------------------------------------------------------

@task_templates_bp.route("/admin/task-templates/<int:template_id>/items/<int:item_id>/sort",
                         methods=["POST"])
@login_required
def admin_template_item_sort(template_id, item_id):
    _require_admin()
    _app = _helpers()
    items = database.get_template_items(template_id)
    item = next((i for i in items if i["id"] == item_id), None)
    if not item:
        abort(404)
    _app._verify_token_access(item["token"])
    try:
        sort_order = int(request.form.get("sort_order", 0))
    except ValueError:
        sort_order = 0
    database.update_template_item_sort(item_id, sort_order)
    return ("", 204)


# ---------------------------------------------------------------------------
# Delete item
# ---------------------------------------------------------------------------

@task_templates_bp.route("/admin/task-templates/<int:template_id>/items/<int:item_id>/delete",
                         methods=["POST"])
@login_required
def admin_template_item_delete(template_id, item_id):
    _require_admin()
    _app = _helpers()
    token_str = request.form.get("token", "").strip()
    _app._verify_token_access(token_str)
    database.delete_template_item(item_id)
    flash("Task deleted.", "success")
    return redirect(url_for("task_templates.admin_task_template_detail",
                            template_id=template_id, token=token_str))


# ---------------------------------------------------------------------------
# CSV sample download
# ---------------------------------------------------------------------------

@task_templates_bp.route("/admin/task-templates/csv-sample")
@login_required
def admin_task_templates_csv_sample():
    content = (
        "template_name,task_description\n"
        "Standard Office Clean,Vacuum all floors\n"
        "Standard Office Clean,Empty all trash bins\n"
        "Standard Office Clean,Wipe all countertops\n"
        "Deck Build Checklist,Set ledger board\n"
        "Deck Build Checklist,Install joists\n"
    )
    return Response(
        content, mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=task_templates_sample.csv"},
    )


# ---------------------------------------------------------------------------
# CSV import
# ---------------------------------------------------------------------------

@task_templates_bp.route("/admin/task-templates/csv-import", methods=["POST"])
@login_required
def admin_task_templates_csv_import():
    _require_admin()
    _app = _helpers()
    token_str = request.form.get("token", "").strip()
    _app._verify_token_access(token_str)
    mode = request.form.get("import_mode", "append")
    file = request.files.get("csv_file")
    if not file or not file.filename.lower().endswith(".csv"):
        flash("Please upload a .csv file.", "error")
        return redirect(url_for("task_templates.admin_task_templates", token=token_str))
    raw = file.stream.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    reader = csv.DictReader(io.StringIO(text))

    if mode == "replace":
        for t in database.get_task_templates(token_str):
            if t["is_active"]:
                database.toggle_task_template(t["id"])

    template_map = {}
    imported_templates = imported_items = skipped = 0
    for row in reader:
        t_name = (row.get("template_name") or "").strip()
        i_desc = (row.get("task_description") or "").strip()
        if not t_name or not i_desc:
            skipped += 1
            continue
        if t_name not in template_map:
            tid = database.create_task_template(t_name, token_str)
            template_map[t_name] = tid
            imported_templates += 1
        database.create_template_item(template_map[t_name], i_desc, token_str)
        imported_items += 1

    flash(
        f"Imported {imported_templates} template(s) with {imported_items} task(s).",
        "success",
    )
    return redirect(url_for("task_templates.admin_task_templates", token=token_str))


# ---------------------------------------------------------------------------
# Task completion history
# ---------------------------------------------------------------------------

@task_templates_bp.route("/admin/task-completions")
@login_required
def admin_task_completions():
    _app = _helpers()
    tokens = _app._get_tokens_for_user()
    token_str, selected_token = _app._get_selected_token(tokens)
    job_id = request.args.get("job_id", type=int)
    days_back = request.args.get("days_back", 30, type=int)
    completions = database.get_completions_for_admin(token_str, job_id=job_id, days_back=days_back) if token_str else []
    jobs = database.get_jobs_by_token(token_str, active_only=False) if token_str else []
    return render_template(
        "admin/task_completions.html",
        tokens=tokens,
        selected_token=selected_token,
        completions=completions,
        jobs=jobs,
        job_id=job_id,
        days_back=days_back,
    )
