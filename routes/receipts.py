import uuid
from datetime import datetime
from pathlib import Path

from flask import (
    Blueprint, jsonify, redirect, render_template, request, session, url_for,
)

import config
import database

receipts_bp = Blueprint('receipts', __name__)


# ---------------------------------------------------------------------------
# Lazy import of app-level helpers to avoid circular imports
# ---------------------------------------------------------------------------

def _helpers():
    import app as _app
    return _app


# ---------------------------------------------------------------------------
# File validation (magic bytes)
# ---------------------------------------------------------------------------

IMAGE_SIGNATURES = [
    b"\xff\xd8\xff",       # JPEG
    b"\x89PNG\r\n\x1a\n",  # PNG
    b"RIFF",               # WebP (RIFF container)
]
AUDIO_SIGNATURES = [
    b"\x1a\x45\xdf\xa3",  # WebM (Matroska/EBML)
    b"OggS",               # Ogg Vorbis/Opus
    b"\x00\x00\x00",       # MP4/M4A (ftyp box — first 3 bytes are size, 4th varies)
    b"ftyp",               # MP4/M4A alternate (some start at offset 4)
]


def _validate_audio_file(file_storage):
    """Check audio file with relaxed validation for iOS MP4/M4A recordings."""
    header = file_storage.read(32)
    file_storage.seek(0)
    # Standard signature check
    for sig in AUDIO_SIGNATURES:
        if header.startswith(sig):
            return True
    # MP4/M4A: ftyp box can appear at byte 4
    if b"ftyp" in header[:16]:
        return True
    return False


def _validate_file_signature(file_storage, allowed_signatures):
    """Check if the file starts with one of the allowed magic byte signatures."""
    header = file_storage.read(16)
    file_storage.seek(0)
    return any(header.startswith(sig) for sig in allowed_signatures)


# ---------------------------------------------------------------------------
# Public capture page
# ---------------------------------------------------------------------------

@receipts_bp.route("/capture")
def capture():
    token_str = request.args.get("token", "")
    token_data = database.get_token(token_str)
    if not token_data or not token_data["is_active"]:
        return render_template("errors/invalid_token.html"), 404

    # Require employee session
    _app = _helpers()
    employee = _app._require_employee_session(token_str)
    if not employee:
        return redirect(url_for("company_home", token_str=token_str))

    logo_url = ""
    if token_data["logo_file"]:
        logo_url = f"/static/logos/{token_data['logo_file']}"

    return render_template(
        "capture.html",
        company_name=token_data["company_name"],
        token=token_str,
        logo_url=logo_url,
    )


# ---------------------------------------------------------------------------
# Upload API
# ---------------------------------------------------------------------------

@receipts_bp.route("/api/upload", methods=["POST"])
def api_upload():
    h = _helpers()

    token_str = request.form.get("token", "")
    token_data = database.get_token(token_str)
    if not token_data or not token_data["is_active"]:
        return jsonify({"error": "Invalid or inactive token"}), 403

    if h._is_rate_limited(token_str, h._rate_limits, config.RATE_LIMIT, 60):
        return jsonify({"error": "Rate limit exceeded. Try again later."}), 429

    image = request.files.get("image")
    audio = request.files.get("audio")
    if not image or not audio:
        return jsonify({"error": "Image and audio are both required"}), 400

    # Validate file types by magic bytes
    if not _validate_file_signature(image, IMAGE_SIGNATURES):
        return jsonify({"error": "Invalid image file. Only JPEG, PNG, and WebP are accepted."}), 400
    if not _validate_audio_file(audio):
        return jsonify({"error": "Invalid audio file."}), 400

    # Build file paths with unique ID to prevent collisions
    now = datetime.now()
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    month_folder = now.strftime("%Y-%m")
    base_name = f"receipt_{timestamp_str}_{unique_id}"

    folder = config.RECEIPTS_DIR / token_str / month_folder
    folder.mkdir(parents=True, exist_ok=True)

    image_filename = f"{base_name}.jpg"
    # Determine audio extension from uploaded filename
    audio_ext = "webm"
    if audio.filename:
        ext = audio.filename.rsplit(".", 1)[-1].lower() if "." in audio.filename else ""
        if ext in ("mp4", "m4a", "ogg", "wav", "webm"):
            audio_ext = ext
    audio_filename = f"{base_name}.{audio_ext}"

    image_path = folder / image_filename
    audio_path = folder / audio_filename

    image.save(str(image_path))
    audio.save(str(audio_path))

    # Optional category / job fields
    job_id = request.form.get("job_id") or None
    category_1_id = request.form.get("category_1_id") or None
    category_2_id = request.form.get("category_2_id") or None

    # Coerce to int if provided
    if job_id is not None:
        try:
            job_id = int(job_id)
        except (ValueError, TypeError):
            job_id = None
    if category_1_id is not None:
        try:
            category_1_id = int(category_1_id)
        except (ValueError, TypeError):
            category_1_id = None
    if category_2_id is not None:
        try:
            category_2_id = int(category_2_id)
        except (ValueError, TypeError):
            category_2_id = None

    # Create DB record (status='processing' -- background worker picks it up)
    submitted_ip = request.remote_addr or ""
    submission_id = database.create_submission(
        token=token_str,
        company_name=token_data["company_name"],
        image_file=image_filename,
        audio_file=audio_filename,
        submitted_ip=submitted_ip,
        job_id=job_id,
        category_1_id=category_1_id,
        category_2_id=category_2_id,
    )

    return jsonify({"submission_id": submission_id, "status": "processing"}), 202


# ---------------------------------------------------------------------------
# Status API
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Receipt Library (employee-facing)
# ---------------------------------------------------------------------------

@receipts_bp.route("/receipt-library")
def receipt_library():
    token_str = request.args.get("token", "")
    token_data = database.get_token(token_str)
    if not token_data or not token_data["is_active"]:
        return render_template("errors/invalid_token.html"), 404
    _app = _helpers()
    employee = _app._require_employee_session(token_str)
    if not employee:
        return redirect(url_for("company_home", token_str=token_str))

    job_id = request.args.get("job_id", "").strip()
    search = request.args.get("search", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    jobs = database.get_jobs_by_token(token_str, active_only=False)
    receipts = []
    selected_job = None
    if job_id:
        receipts = database.get_receipts_for_library(
            token_str, search=search or None,
            date_from=date_from or None, date_to=date_to or None,
            job_id=job_id,
        )
        for j in jobs:
            if str(j["id"]) == job_id:
                selected_job = j
                break

    logo_url = f"/static/logos/{token_data['logo_file']}" if token_data["logo_file"] else ""
    return render_template("receipt_library.html",
        token=token_str, token_data=token_data, receipts=receipts, jobs=jobs,
        job_id=job_id, selected_job=selected_job,
        search=search, date_from=date_from, date_to=date_to, logo_url=logo_url)


@receipts_bp.route("/receipt-library/<int:receipt_id>")
def receipt_library_detail(receipt_id):
    token_str = request.args.get("token", "")
    token_data = database.get_token(token_str)
    if not token_data or not token_data["is_active"]:
        return render_template("errors/invalid_token.html"), 404
    _app = _helpers()
    employee = _app._require_employee_session(token_str)
    if not employee:
        return redirect(url_for("company_home", token_str=token_str))

    receipt = database.get_submission(receipt_id)
    if not receipt or receipt["token"] != token_str:
        return render_template("errors/404.html"), 404

    # Look up job and category names
    job_name = None
    if receipt.get("job_id"):
        job = database.get_job(receipt["job_id"])
        if job:
            job_name = job["job_name"]
    cat_names = []
    for cat_field in ("category_1_id", "category_2_id"):
        if receipt.get(cat_field):
            cat = database.get_category(receipt[cat_field])
            if cat:
                cat_names.append(cat["name"])

    logo_url = f"/static/logos/{token_data['logo_file']}" if token_data["logo_file"] else ""
    return render_template("receipt_library_detail.html",
        token=token_str, token_data=token_data, receipt=receipt,
        job_name=job_name, cat_names=cat_names, logo_url=logo_url)


@receipts_bp.route("/api/receipt-image/<int:receipt_id>")
def api_receipt_image(receipt_id):
    from flask import send_file
    token_str = request.args.get("token", "")
    _app = _helpers()
    employee = _app._require_employee_session(token_str)
    if not employee:
        return jsonify({"error": "Not authorized"}), 403

    receipt = database.get_submission(receipt_id)
    if not receipt or receipt["token"] != token_str:
        return jsonify({"error": "Not found"}), 404

    want_thumb = request.args.get("thumb", "0") == "1"
    folder = config.RECEIPTS_DIR / receipt["token"] / receipt["month_folder"]

    if want_thumb:
        base_name = Path(receipt["image_file"]).stem
        thumb_path = folder / f"{base_name}_thumb.jpg"
        if thumb_path.exists():
            return send_file(str(thumb_path), mimetype="image/jpeg")

    image_path = folder / receipt["image_file"]
    if not image_path.exists():
        return jsonify({"error": "File not found"}), 404
    return send_file(str(image_path), mimetype="image/jpeg")


# ---------------------------------------------------------------------------
# Status API
# ---------------------------------------------------------------------------

@receipts_bp.route("/api/status/<int:submission_id>")
def api_status(submission_id):
    token_str = request.args.get("token", "")
    _app = _helpers()
    employee = _app._require_employee_session(token_str)
    if not employee:
        return jsonify({"error": "Not authorized"}), 403

    sub = database.get_submission(submission_id)
    if not sub or sub["token"] != token_str:
        return jsonify({"error": "Not found"}), 404

    # Both 'processing' and 'transcribing' mean it is still in progress
    status = sub["status"]
    if status == "transcribing":
        status = "processing"

    return jsonify({
        "id": sub["id"],
        "status": status,
        "transcription": sub["transcription"] if sub["status"] == "complete" else "",
    })
