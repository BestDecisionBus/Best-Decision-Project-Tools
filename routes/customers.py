"""Admin routes for Customer master records."""

from flask import (
    Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for,
)

from flask_login import current_user, login_required

import database

customers_bp = Blueprint("customers", __name__)


# ---------------------------------------------------------------------------
# Lazy import helper to avoid circular imports
# ---------------------------------------------------------------------------

def _helpers():
    import app as _app
    return _app


# ---------------------------------------------------------------------------
# LIST
# ---------------------------------------------------------------------------

@customers_bp.route("/admin/customers")
@login_required
def admin_customers():
    _app = _helpers()
    tokens = _app._get_tokens_for_user()
    token_str, selected_token = _app._get_selected_token(tokens)
    customers = database.get_customers_by_token(token_str) if token_str else []
    return render_template(
        "admin/customers.html",
        tokens=tokens,
        selected_token=selected_token,
        customers=customers,
    )


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------

@customers_bp.route("/admin/customers/create", methods=["POST"])
@login_required
def admin_customer_create():
    _app = _helpers()
    token_str = request.form.get("token", "").strip()
    _app._verify_token_access(token_str)
    company_name  = request.form.get("company_name", "").strip()
    customer_name = request.form.get("customer_name", "").strip()
    phone  = request.form.get("phone", "").strip()
    email  = request.form.get("email", "").strip()
    notes  = request.form.get("notes", "").strip()
    if not customer_name:
        flash("Contact name is required.", "error")
        return redirect(url_for("customers.admin_customers", token=token_str))
    database.create_customer(company_name, customer_name, phone, email, notes, token_str)
    flash("Customer created.", "success")
    return redirect(url_for("customers.admin_customers", token=token_str))


# ---------------------------------------------------------------------------
# DETAIL / EDIT
# ---------------------------------------------------------------------------

@customers_bp.route("/admin/customers/<int:customer_id>")
@login_required
def admin_customer_detail(customer_id):
    _app = _helpers()
    tokens = _app._get_tokens_for_user()
    token_str, selected_token = _app._get_selected_token(tokens)
    customer = database.get_customer(customer_id, token_str or None)
    if not customer:
        abort(404)
    jobs = database.get_jobs_by_customer(customer_id, customer["token"])
    all_jobs = database.get_jobs_by_token(customer["token"], active_only=True)
    linked_job_ids = {j["id"] for j in jobs}
    linkable_jobs = [j for j in all_jobs if j["id"] not in linked_job_ids]
    job_estimate_summaries = database.get_estimate_counts_by_customer(customer_id, customer["token"])
    return render_template(
        "admin/customer_detail.html",
        customer=customer,
        jobs=jobs,
        linkable_jobs=linkable_jobs,
        job_estimate_summaries=job_estimate_summaries,
        tokens=tokens,
        selected_token=selected_token,
    )


@customers_bp.route("/admin/customers/<int:customer_id>/edit", methods=["POST"])
@login_required
def admin_customer_edit(customer_id):
    _app = _helpers()
    token_str = request.form.get("token", "").strip()
    _app._verify_token_access(token_str)
    customer = database.get_customer(customer_id, token_str)
    if not customer:
        abort(404)
    company_name  = request.form.get("company_name", "").strip()
    customer_name = request.form.get("customer_name", "").strip()
    phone  = request.form.get("phone", "").strip()
    email  = request.form.get("email", "").strip()
    notes  = request.form.get("notes", "").strip()
    if not customer_name:
        flash("Contact name is required.", "error")
    else:
        database.update_customer(customer_id, company_name, customer_name, phone, email, notes, token_str)
        flash("Customer updated.", "success")
    return redirect(url_for("customers.admin_customer_detail", customer_id=customer_id))


# ---------------------------------------------------------------------------
# TOGGLE ACTIVE / INACTIVE
# ---------------------------------------------------------------------------

@customers_bp.route("/admin/customers/<int:customer_id>/toggle", methods=["POST"])
@login_required
def admin_customer_toggle(customer_id):
    _app = _helpers()
    token_str = request.form.get("token", "").strip()
    _app._verify_token_access(token_str)
    customer = database.get_customer(customer_id, token_str)
    if not customer:
        abort(404)
    database.toggle_customer(customer_id, token_str)
    return redirect(url_for("customers.admin_customers", token=token_str))


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

@customers_bp.route("/admin/customers/<int:customer_id>/delete", methods=["POST"])
@login_required
def admin_customer_delete(customer_id):
    _app = _helpers()
    token_str = request.form.get("token", "").strip()
    _app._verify_token_access(token_str)
    success = database.delete_customer(customer_id, token_str)
    if not success:
        flash("Cannot delete — this customer has linked jobs or estimates.", "error")
        return redirect(url_for("customers.admin_customer_detail", customer_id=customer_id))
    flash("Customer deleted.", "success")
    return redirect(url_for("customers.admin_customers", token=token_str))


# ---------------------------------------------------------------------------
# SORT ORDER (returns 204 — no page reload)
# ---------------------------------------------------------------------------

@customers_bp.route("/admin/customers/<int:customer_id>/sort", methods=["POST"])
@login_required
def admin_customer_sort(customer_id):
    _app = _helpers()
    customer = database.get_customer(customer_id)
    if not customer:
        abort(404)
    _app._verify_token_access(customer["token"])
    data = request.get_json()
    try:
        sort_order = int(data.get("sort_order", 0))
    except (ValueError, TypeError):
        return jsonify({"success": False}), 400
    database.update_customer_sort_order(customer_id, sort_order, customer["token"])
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# LINK JOB TO CUSTOMER
# ---------------------------------------------------------------------------

@customers_bp.route("/admin/customers/link-job", methods=["POST"])
@login_required
def admin_link_job_to_customer():
    _app = _helpers()
    token_str   = request.form.get("token", "").strip()
    job_id      = request.form.get("job_id", type=int)
    customer_id = request.form.get("customer_id", type=int)
    _app._verify_token_access(token_str)
    if not job_id or not customer_id:
        flash("Job and customer are required.", "error")
    else:
        database.link_job_to_customer(job_id, customer_id, token_str)
        flash("Job linked to customer.", "success")
    return redirect(
        request.referrer or url_for("customers.admin_customer_detail", customer_id=customer_id)
    )


# ---------------------------------------------------------------------------
# CREATE JOB DIRECTLY FROM CUSTOMER CONTEXT
# ---------------------------------------------------------------------------

@customers_bp.route("/admin/customers/<int:customer_id>/jobs/create", methods=["POST"])
@login_required
def admin_customer_job_create(customer_id):
    _app = _helpers()
    token_str = request.form.get("token", "").strip()
    _app._verify_token_access(token_str)
    customer = database.get_customer(customer_id, token_str)
    if not customer:
        abort(404)
    job_name    = request.form.get("job_name", "").strip()
    job_address = request.form.get("job_address", "").strip()
    if not job_name:
        flash("Job name is required.", "error")
        return redirect(url_for("customers.admin_customer_detail", customer_id=customer_id))
    database.create_job(job_name, job_address, None, None, token_str, customer_id=customer_id)
    flash(f"Job '{job_name}' created.", "success")
    return redirect(url_for("customers.admin_customer_detail", customer_id=customer_id))


# ---------------------------------------------------------------------------
# LINK ESTIMATE TO CUSTOMER
# ---------------------------------------------------------------------------

@customers_bp.route("/admin/customers/link-estimate", methods=["POST"])
@login_required
def admin_link_estimate_to_customer():
    _app = _helpers()
    token_str   = request.form.get("token", "").strip()
    estimate_id = request.form.get("estimate_id", type=int)
    customer_id = request.form.get("customer_id", type=int)
    _app._verify_token_access(token_str)
    if not estimate_id or not customer_id:
        flash("Estimate and customer are required.", "error")
    else:
        database.link_estimate_to_customer(estimate_id, customer_id, token_str)
        flash("Estimate linked to customer.", "success")
    return redirect(
        request.referrer or url_for("customers.admin_customer_detail", customer_id=customer_id)
    )


# ---------------------------------------------------------------------------
# JSON endpoint (for estimate auto-fill)
# ---------------------------------------------------------------------------

@customers_bp.route("/admin/customers/<int:customer_id>/json")
@login_required
def admin_customer_json(customer_id):
    _app = _helpers()
    tokens = _app._get_tokens_for_user()
    token_str, _ = _app._get_selected_token(tokens)
    customer = database.get_customer(customer_id, token_str or None)
    if not customer:
        abort(404)
    return {
        "id":            customer["id"],
        "company_name":  customer["company_name"],
        "customer_name": customer["customer_name"],
        "phone":         customer["phone"],
        "email":         customer["email"],
    }
