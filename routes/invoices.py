"""Admin routes for Invoices."""

import tempfile

from flask import (
    Blueprint, abort, flash, jsonify, redirect, render_template, request, send_file, url_for,
)
from flask_login import login_required

import database

invoices_bp = Blueprint("invoices", __name__)


def _helpers():
    import app as _app
    return _app


# ---------------------------------------------------------------------------
# LIST
# ---------------------------------------------------------------------------

@invoices_bp.route("/admin/invoices")
@login_required
def admin_invoices():
    _app = _helpers()
    tokens = _app._get_tokens_for_user()
    token_str, selected_token = _app._get_selected_token(tokens)
    status_filter = request.args.get("status", "")
    invoices = []
    if token_str:
        invoices = database.get_invoices_by_token(token_str, status=status_filter or None)
    return render_template(
        "admin/invoices.html",
        tokens=tokens,
        selected_token=selected_token,
        invoices=invoices,
        status_filter=status_filter,
    )


# ---------------------------------------------------------------------------
# CREATE (from an accepted estimate)
# ---------------------------------------------------------------------------

@invoices_bp.route("/admin/invoices/create", methods=["POST"])
@login_required
def admin_invoice_create():
    _app = _helpers()
    token_str = request.form.get("token", "").strip()
    _app._verify_token_access(token_str)

    estimate_id = request.form.get("estimate_id", type=int)
    if not estimate_id:
        flash("Estimate ID is required.", "error")
        return redirect(url_for("invoices.admin_invoices", token=token_str))

    estimate = database.get_estimate(estimate_id)
    if not estimate or estimate["token"] != token_str:
        abort(404)

    # Prevent duplicate invoices for the same estimate
    existing = database.get_invoices_by_token(token_str)
    for inv in existing:
        if inv["estimate_id"] == estimate_id and inv["status"] != "void":
            flash("An invoice already exists for this estimate.", "error")
            return redirect(url_for("invoices.admin_invoice_detail", invoice_id=inv["id"]))

    amount_due = estimate.get("estimate_value") or 0
    customer_id = estimate.get("customer_id")
    job_id = estimate.get("job_id")

    inv = database.create_invoice(
        token_str,
        estimate_id=estimate_id,
        customer_id=customer_id,
        job_id=job_id,
        amount_due=amount_due,
    )
    flash(f"Invoice {inv['invoice_number']} created.", "success")
    return redirect(url_for("invoices.admin_invoice_detail", invoice_id=inv["id"]))


# ---------------------------------------------------------------------------
# DETAIL / EDIT
# ---------------------------------------------------------------------------

@invoices_bp.route("/admin/invoices/<int:invoice_id>")
@login_required
def admin_invoice_detail(invoice_id):
    _app = _helpers()
    tokens = _app._get_tokens_for_user()
    token_str, selected_token = _app._get_selected_token(tokens)

    inv = database.get_invoice(invoice_id)
    if not inv:
        abort(404)
    _app._verify_token_access(inv["token"])

    estimate = database.get_estimate(inv["estimate_id"]) if inv.get("estimate_id") else None
    invoice_items = database.get_invoice_items(invoice_id)
    customer = database.get_customer(inv["customer_id"]) if inv.get("customer_id") else None
    job = database.get_job(inv["job_id"]) if inv.get("job_id") else None
    snippets = database.get_message_snippets_by_token(inv["token"], active_only=True)

    return render_template(
        "admin/invoice_detail.html",
        inv=inv,
        estimate=estimate,
        invoice_items=invoice_items,
        customer=customer,
        job=job,
        snippets=snippets,
        tokens=tokens,
        selected_token=selected_token,
    )


@invoices_bp.route("/admin/invoices/<int:invoice_id>/edit", methods=["POST"])
@login_required
def admin_invoice_edit(invoice_id):
    _app = _helpers()
    token_str = request.form.get("token", "").strip()
    _app._verify_token_access(token_str)

    inv = database.get_invoice(invoice_id, token_str)
    if not inv:
        abort(404)

    due_date       = request.form.get("due_date", "").strip()
    notes          = request.form.get("notes", "").strip()
    client_message = request.form.get("client_message", "").strip()
    try:
        amount_due = float(request.form.get("amount_due", inv["amount_due"]))
    except (ValueError, TypeError):
        amount_due = inv["amount_due"]

    database.update_invoice(invoice_id, token_str, due_date=due_date, notes=notes,
                            amount_due=amount_due, client_message=client_message)
    flash("Invoice updated.", "success")
    return redirect(url_for("invoices.admin_invoice_detail", invoice_id=invoice_id))


# ---------------------------------------------------------------------------
# UPDATE STATUS
# ---------------------------------------------------------------------------

@invoices_bp.route("/admin/invoices/<int:invoice_id>/status", methods=["POST"])
@login_required
def admin_invoice_update_status(invoice_id):
    _app = _helpers()
    token_str = request.form.get("token", "").strip()
    _app._verify_token_access(token_str)

    inv = database.get_invoice(invoice_id, token_str)
    if not inv:
        abort(404)

    new_status = request.form.get("status", "").strip()
    if new_status not in ("draft", "sent", "paid", "void"):
        flash("Invalid status.", "error")
        return redirect(url_for("invoices.admin_invoice_detail", invoice_id=invoice_id))

    updates = {"status": new_status}
    if new_status == "paid":
        updates["amount_paid"] = inv["amount_due"]
    database.update_invoice(invoice_id, token_str, **updates)
    flash(f"Invoice marked as {new_status}.", "success")
    return redirect(url_for("invoices.admin_invoice_detail", invoice_id=invoice_id))


# ---------------------------------------------------------------------------
# RECORD PARTIAL PAYMENT
# ---------------------------------------------------------------------------

@invoices_bp.route("/admin/invoices/<int:invoice_id>/payment", methods=["POST"])
@login_required
def admin_invoice_record_payment(invoice_id):
    _app = _helpers()
    token_str = request.form.get("token", "").strip()
    _app._verify_token_access(token_str)

    inv = database.get_invoice(invoice_id, token_str)
    if not inv:
        abort(404)

    try:
        amount_paid = float(request.form.get("amount_paid", 0))
    except (ValueError, TypeError):
        flash("Invalid payment amount.", "error")
        return redirect(url_for("invoices.admin_invoice_detail", invoice_id=invoice_id))

    new_status = "paid" if amount_paid >= inv["amount_due"] else "sent"
    database.update_invoice(invoice_id, token_str, amount_paid=amount_paid, status=new_status)
    flash(f"Payment of ${amount_paid:,.2f} recorded.", "success")
    return redirect(url_for("invoices.admin_invoice_detail", invoice_id=invoice_id))


# ---------------------------------------------------------------------------
# SYNC NEW ESTIMATE ITEMS → DRAFT INVOICE
# ---------------------------------------------------------------------------

@invoices_bp.route("/admin/invoices/<int:invoice_id>/sync-estimate", methods=["POST"])
@login_required
def admin_invoice_sync_estimate(invoice_id):
    _app = _helpers()
    token_str = request.form.get("token", "").strip()
    _app._verify_token_access(token_str)

    inv = database.get_invoice(invoice_id, token_str)
    if not inv:
        abort(404)
    if not inv.get("estimate_id"):
        flash("No estimate linked to this invoice.", "error")
        return redirect(url_for("invoices.admin_invoice_detail", invoice_id=invoice_id))

    added = database.sync_estimate_items_to_invoice(invoice_id, inv["estimate_id"], token_str)
    if added:
        flash(f"{added} new line item(s) pulled from estimate.", "success")
    else:
        flash("Invoice already has all estimate line items — nothing new to sync.", "info")
    return redirect(url_for("invoices.admin_invoice_detail", invoice_id=invoice_id))


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

@invoices_bp.route("/admin/invoices/<int:invoice_id>/delete", methods=["POST"])
@login_required
def admin_invoice_delete(invoice_id):
    _app = _helpers()
    token_str = request.form.get("token", "").strip()
    _app._verify_token_access(token_str)

    inv = database.get_invoice(invoice_id, token_str)
    if not inv:
        abort(404)

    database.delete_invoice(invoice_id, token_str)
    flash("Invoice deleted.", "success")
    return redirect(url_for("invoices.admin_invoices", token=token_str))


# ---------------------------------------------------------------------------
# INVOICE ITEMS — CRUD (JSON)
# ---------------------------------------------------------------------------

@invoices_bp.route("/admin/invoices/<int:invoice_id>/items/create", methods=["POST"])
@login_required
def admin_invoice_item_create(invoice_id):
    _app = _helpers()
    inv = database.get_invoice(invoice_id)
    if not inv:
        abort(404)
    _app._verify_token_access(inv["token"])

    data = request.get_json(silent=True) or {}
    description   = str(data.get("description", "")).strip()
    quantity      = float(data.get("quantity", 1) or 1)
    unit_price    = float(data.get("unit_price", 0) or 0)
    original_total = round(quantity * unit_price, 2)
    billed_pct    = float(data.get("billed_pct", 100) or 100)
    billed_amount = round(original_total * billed_pct / 100, 2)
    sort_order    = int(data.get("sort_order", 0) or 0)

    item = database.create_invoice_item(
        invoice_id, inv["token"], description,
        quantity=quantity, unit_price=unit_price,
        original_total=original_total, billed_pct=billed_pct,
        billed_amount=billed_amount, sort_order=sort_order,
    )
    inv_updated = database.get_invoice(invoice_id)
    return jsonify({"ok": True, "item": item, "amount_due": inv_updated["amount_due"]})


@invoices_bp.route("/admin/invoices/items/<int:item_id>/update", methods=["POST"])
@login_required
def admin_invoice_item_update(item_id):
    _app = _helpers()
    data = request.get_json(silent=True) or {}

    conn = database.get_db()
    row = conn.execute("SELECT * FROM invoice_items WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    if not row:
        abort(404)
    _app._verify_token_access(row["token"])

    allowed_keys = {"description", "quantity", "unit_price", "original_total",
                    "billed_pct", "billed_amount", "sort_order"}
    kwargs = {k: v for k, v in data.items() if k in allowed_keys}
    item = database.update_invoice_item(item_id, **kwargs)
    inv_updated = database.get_invoice(row["invoice_id"])
    return jsonify({"ok": True, "item": item, "amount_due": inv_updated["amount_due"] if inv_updated else 0})


@invoices_bp.route("/admin/invoices/items/<int:item_id>/delete", methods=["POST"])
@login_required
def admin_invoice_item_delete(item_id):
    _app = _helpers()
    conn = database.get_db()
    row = conn.execute("SELECT * FROM invoice_items WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    if not row:
        abort(404)
    _app._verify_token_access(row["token"])
    invoice_id = row["invoice_id"]
    database.delete_invoice_item(item_id)
    inv_updated = database.get_invoice(invoice_id)
    return jsonify({"ok": True, "amount_due": inv_updated["amount_due"] if inv_updated else 0})


# ---------------------------------------------------------------------------
# PDF EXPORT
# ---------------------------------------------------------------------------

@invoices_bp.route("/admin/invoices/<int:invoice_id>/pdf")
@login_required
def admin_invoice_pdf(invoice_id):
    _app = _helpers()
    tokens = _app._get_tokens_for_user()
    token_str, _ = _app._get_selected_token(tokens)

    inv = database.get_invoice(invoice_id)
    if not inv:
        abort(404)
    _app._verify_token_access(inv["token"])

    token_data = database.get_token(inv["token"])
    estimate = database.get_estimate(inv["estimate_id"]) if inv.get("estimate_id") else None
    invoice_items = database.get_invoice_items(invoice_id)
    customer = database.get_customer(inv["customer_id"]) if inv.get("customer_id") else None
    job = database.get_job(inv["job_id"]) if inv.get("job_id") else None

    import pdf_generator
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        pdf_generator.generate_invoice_pdf(
            tmp.name,
            inv=inv,
            estimate=estimate,
            items=invoice_items,
            customer=customer,
            job=job,
            token_data=token_data,
        )
        fname = f"invoice_{inv['invoice_number']}.pdf"
        return send_file(tmp.name, mimetype="application/pdf",
                         as_attachment=False, download_name=fname)
