import io
import logging
import re
import zipfile
from pathlib import Path

from flask import (
    Blueprint, abort, flash, jsonify, redirect, render_template, request,
    send_file, url_for,
)
from flask_login import current_user, login_required

import config
import database
import qbo_service

log = logging.getLogger(__name__)

from routes._shared import helpers as _helpers, gate_admin_feature

receipt_admin_bp = Blueprint('receipt_admin', __name__)


@receipt_admin_bp.before_request
def _enforce_admin_on_writes():
    """Require admin role for all POST requests."""
    if request.method == "POST":
        if not current_user.is_authenticated:
            abort(401)
        if not current_user.is_admin and not current_user.is_bdb:
            abort(403)


@receipt_admin_bp.before_request
def _check_scheduler_access():
    """Block scheduler role from all receipt admin routes."""
    if not current_user.is_authenticated:
        return
    if current_user.is_scheduler and not current_user.is_bdb:
        abort(403)


@receipt_admin_bp.before_request
def _gate_receipts_feature():
    return gate_admin_feature("feature_receipts", "Receipt Capture")


# ---------------------------------------------------------------------------
# Receipt Dashboard (recent submissions for selected company)
# ---------------------------------------------------------------------------

@receipt_admin_bp.route("/admin/receipts")
@login_required
def receipt_dashboard():
    h = _helpers()
    tokens = h._get_tokens_for_user()
    token_str, selected_token = h._get_selected_token(tokens)

    submissions = []
    if token_str:
        submissions = database.get_recent_submissions(50, token_str=token_str)

    return render_template(
        "admin/receipt_dashboard.html",
        tokens=tokens,
        selected_token=selected_token,
        submissions=submissions,
    )


# ---------------------------------------------------------------------------
# Browse receipts by company / month
# ---------------------------------------------------------------------------

@receipt_admin_bp.route("/admin/receipts/browse")
@login_required
def receipt_browse():
    h = _helpers()
    tokens = h._get_tokens_for_user()
    return render_template(
        "admin/receipt_browse.html",
        tokens=tokens,
        selected_token=None,
        months=None,
        selected_month=None,
        submissions=None,
    )


@receipt_admin_bp.route("/admin/receipts/browse/<token_str>")
@login_required
def receipt_browse_token(token_str):
    h = _helpers()
    h._verify_token_access(token_str)
    tokens = h._get_tokens_for_user()
    months = database.get_submissions_by_token(token_str)
    token_data = database.get_token(token_str)
    return render_template(
        "admin/receipt_browse.html",
        tokens=tokens,
        selected_token=token_data,
        months=months,
        selected_month=None,
        submissions=None,
    )


@receipt_admin_bp.route("/admin/receipts/browse/<token_str>/<month>")
@login_required
def receipt_browse_month(token_str, month):
    h = _helpers()
    h._verify_token_access(token_str)
    tokens = h._get_tokens_for_user()
    months = database.get_submissions_by_token(token_str)
    submissions = database.get_submissions_by_token_month(token_str, month)
    token_data = database.get_token(token_str)
    return render_template(
        "admin/receipt_browse.html",
        tokens=tokens,
        selected_token=token_data,
        months=months,
        selected_month=month,
        submissions=submissions,
    )


# ---------------------------------------------------------------------------
# Receipt detail
# ---------------------------------------------------------------------------

@receipt_admin_bp.route("/admin/receipts/<int:submission_id>")
@login_required
def receipt_detail(submission_id):
    sub = database.get_submission(submission_id)
    if not sub:
        abort(404)

    h = _helpers()
    h._verify_token_access(sub["token"])

    sub_categories = database.get_submission_categories(submission_id)
    all_categories = database.get_categories_by_token(sub["token"], active_only=True)
    all_jobs = database.get_jobs_by_token(sub["token"], active_only=True)

    # QBO data for expense push
    qbo_connection = database.get_qbo_connection(sub["token"])
    qbo_bank_accounts = []
    if qbo_connection:
        try:
            qbo_bank_accounts = qbo_service.fetch_qbo_bank_accounts(sub["token"])
        except Exception:
            log.warning("Failed to fetch QBO bank accounts for receipt %s", submission_id, exc_info=True)

    return render_template(
        "admin/receipt_detail.html",
        sub=sub,
        sub_categories=sub_categories,
        all_categories=all_categories,
        all_jobs=all_jobs,
        qbo_connection=qbo_connection,
        qbo_bank_accounts=qbo_bank_accounts,
    )


@receipt_admin_bp.route("/admin/receipts/<int:submission_id>/update", methods=["POST"])
@login_required
def receipt_update(submission_id):
    sub = database.get_submission(submission_id)
    if not sub:
        abort(404)

    h = _helpers()
    h._verify_token_access(sub["token"])

    data = request.get_json(force=True)
    vendor = data.get("vendor", "")
    categories = data.get("categories", [])
    job_id = data.get("job_id")
    payment_amount = data.get("payment_amount", None)
    receipt_date = data.get("receipt_date", None)

    database.update_submission_vendor(submission_id, vendor)
    database.set_submission_categories(submission_id, categories)
    database.update_submission_job(submission_id, job_id)
    if payment_amount is not None:
        database.update_submission_payment_amount(submission_id, payment_amount)
    if receipt_date is not None:
        if receipt_date and not re.match(r'^\d{4}-\d{2}-\d{2}$', receipt_date):
            receipt_date = ""
        database.update_submission_receipt_date(submission_id, receipt_date)

    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Toggle processed flag
# ---------------------------------------------------------------------------

@receipt_admin_bp.route("/admin/receipts/<int:submission_id>/toggle-processed", methods=["POST"])
@login_required
def receipt_toggle_processed(submission_id):
    sub = database.get_submission(submission_id)
    if not sub:
        abort(404)

    h = _helpers()
    h._verify_token_access(sub["token"])

    if sub.get("qbo_purchase_id"):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": "Cannot toggle — receipt is synced to QuickBooks."}), 400
        flash("Cannot toggle — receipt is synced to QuickBooks.", "error")
        return redirect(request.referrer or url_for("receipt_admin.receipt_dashboard"))

    new_val = database.toggle_processed(submission_id)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"processed": new_val})
    return redirect(request.referrer or url_for("receipt_admin.receipt_dashboard"))


# ---------------------------------------------------------------------------
# Delete receipt
# ---------------------------------------------------------------------------

@receipt_admin_bp.route("/admin/receipts/<int:submission_id>/delete", methods=["POST"])
@login_required
def receipt_delete(submission_id):
    sub = database.get_submission(submission_id)
    if not sub:
        abort(404)

    h = _helpers()
    h._verify_token_access(sub["token"])

    deleted = database.delete_submission(submission_id)
    if deleted:
        # Delete files from disk (including thumbnail)
        folder = config.RECEIPTS_DIR / deleted["token"] / deleted["month_folder"]
        for key in ("image_file", "audio_file", "pdf_file"):
            if deleted.get(key):
                fpath = folder / deleted[key]
                if fpath.exists():
                    fpath.unlink()
        # Also delete thumbnail if it exists
        if deleted.get("image_file"):
            thumb_name = Path(deleted["image_file"]).stem + "_thumb.jpg"
            thumb_path = folder / thumb_name
            if thumb_path.exists():
                thumb_path.unlink()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": bool(deleted)})
    flash("Receipt deleted." if deleted else "Receipt not found.",
          "success" if deleted else "error")
    return redirect(request.referrer or url_for("receipt_admin.receipt_dashboard"))


# ---------------------------------------------------------------------------
# Download individual file
# ---------------------------------------------------------------------------

@receipt_admin_bp.route("/admin/receipts/download/<int:submission_id>/<filetype>")
@login_required
def receipt_download(submission_id, filetype):
    sub = database.get_submission(submission_id)
    if not sub:
        abort(404)

    h = _helpers()
    h._verify_token_access(sub["token"])

    file_map = {
        "image": sub["image_file"],
        "audio": sub["audio_file"],
        "pdf": sub["pdf_file"],
    }
    filename = file_map.get(filetype)
    if not filename:
        abort(404)

    file_path = config.RECEIPTS_DIR / sub["token"] / sub["month_folder"] / filename
    if not file_path.exists():
        abort(404)

    return send_file(str(file_path), as_attachment=True)


# ---------------------------------------------------------------------------
# Serve image / thumbnail for inline viewing
# ---------------------------------------------------------------------------

@receipt_admin_bp.route("/admin/receipts/image/<int:submission_id>")
@login_required
def receipt_image(submission_id):
    """Serve a web-optimized thumbnail for fast admin viewing.

    Falls back to the original image if no thumbnail exists yet.
    """
    sub = database.get_submission(submission_id)
    if not sub or not sub["image_file"]:
        abort(404)

    h = _helpers()
    h._verify_token_access(sub["token"])

    folder = config.RECEIPTS_DIR / sub["token"] / sub["month_folder"]

    # Try thumbnail first (much smaller / faster)
    thumb_name = Path(sub["image_file"]).stem + "_thumb.jpg"
    thumb_path = folder / thumb_name
    if thumb_path.exists():
        return send_file(str(thumb_path), mimetype="image/jpeg")

    # Fall back to original
    original_path = folder / sub["image_file"]
    if not original_path.exists():
        abort(404)
    return send_file(str(original_path), mimetype="image/jpeg")


# ---------------------------------------------------------------------------
# Download ZIP of PDFs for a company / month
# ---------------------------------------------------------------------------

@receipt_admin_bp.route("/admin/receipts/download-zip/<token_str>/<month>")
@login_required
def receipt_download_zip(token_str, month):
    import tempfile
    import atexit
    import os

    h = _helpers()
    h._verify_token_access(token_str)

    folder = config.RECEIPTS_DIR / token_str / month
    if not folder.exists():
        abort(404)

    # Write to a temp file (better cross-platform compatibility)
    # Only include PDFs (combined image + transcription)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED) as zf:
            for f in sorted(folder.iterdir()):
                if f.is_file() and f.suffix.lower() == ".pdf":
                    zf.write(str(f), f.name)
        tmp.close()

        zip_name = f"{token_str}_{month}.zip"
        return send_file(
            tmp.name,
            as_attachment=True,
            download_name=zip_name,
            mimetype="application/zip",
        )
    finally:
        # Clean up temp file after response is sent
        atexit.register(
            lambda path=tmp.name: os.unlink(path) if os.path.exists(path) else None
        )
