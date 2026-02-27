import io
import mimetypes
import os
import re
import secrets
import zipfile
from datetime import datetime
from pathlib import Path

from flask import (
    Blueprint, abort, flash, jsonify, redirect, render_template, request,
    send_file, session, url_for,
)
from flask_login import current_user, login_required

import config
import database

job_photos_bp = Blueprint('job_photos', __name__)

# Magic-byte signatures for allowed image types
IMAGE_SIGNATURES = [b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"RIFF"]

# Extensions considered "images" — everything else goes to Job Files
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


# ---------------------------------------------------------------------------
# Lazy import of app-level helpers to avoid circular imports
# ---------------------------------------------------------------------------

def _helpers():
    import app as _app
    return _app


# ---------------------------------------------------------------------------
# Scheduler role: block from admin photo routes
# ---------------------------------------------------------------------------

_SCHEDULER_BLOCKED_PHOTOS = frozenset({
    'job_photos.admin_job_photos',
    'job_photos.admin_photo_detail',
    'job_photos.admin_delete_photo',
    'job_photos.download_zip',
    'job_photos.download_pdf',
})


@job_photos_bp.before_request
def _check_scheduler_access():
    """Block scheduler role from admin photo routes."""
    if not current_user.is_authenticated:
        return
    if current_user.is_scheduler and not current_user.is_bdb:
        if request.endpoint in _SCHEDULER_BLOCKED_PHOTOS:
            abort(403)


# ---------------------------------------------------------------------------
# Image processing helpers
# ---------------------------------------------------------------------------

def _fix_image_orientation(img):
    """Fix EXIF orientation so the image displays upright."""
    try:
        from PIL import ImageOps
        fixed = ImageOps.exif_transpose(img)
        return fixed if fixed is not None else img
    except Exception:
        return img


def _generate_thumbnail(img, max_size=(400, 400)):
    """Return a thumbnail copy of *img*."""
    thumb = img.copy()
    thumb.thumbnail(max_size)
    return thumb


def _build_gps_exif(lat, lng):
    """Build a piexif GPS IFD dict from decimal lat/lng."""
    import piexif

    def _to_deg_min_sec(decimal):
        decimal = abs(decimal)
        deg = int(decimal)
        min_float = (decimal - deg) * 60
        minute = int(min_float)
        sec = round((min_float - minute) * 60 * 10000)
        return ((deg, 1), (minute, 1), (sec, 10000))

    lat_ref = b"N" if lat >= 0 else b"S"
    lng_ref = b"E" if lng >= 0 else b"W"

    return {
        piexif.GPSIFD.GPSLatitudeRef: lat_ref,
        piexif.GPSIFD.GPSLatitude: _to_deg_min_sec(lat),
        piexif.GPSIFD.GPSLongitudeRef: lng_ref,
        piexif.GPSIFD.GPSLongitude: _to_deg_min_sec(lng),
    }


def _get_exif_bytes(raw_bytes, lat=None, lng=None):
    """Extract EXIF from raw image bytes, inject GPS if provided, return bytes."""
    import piexif
    try:
        exif_dict = piexif.load(raw_bytes)
    except Exception:
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}

    # Remove orientation tag (we already applied exif_transpose)
    exif_dict["0th"].pop(piexif.ImageIFD.Orientation, None)

    # Inject or overwrite GPS from browser coordinates
    if lat is not None and lng is not None:
        exif_dict["GPS"] = _build_gps_exif(lat, lng)

    # Remove thumbnail data to avoid size issues
    exif_dict.pop("thumbnail", None)
    exif_dict["1st"] = {}

    try:
        return piexif.dump(exif_dict)
    except Exception:
        return b""


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _sanitize_job_name(name):
    """Replace non-alphanumeric characters with hyphens and strip edges."""
    sanitized = re.sub(r"[^a-zA-Z0-9]+", "-", name)
    return sanitized.strip("-")


def _week_folder_for_date(dt=None):
    """Return ISO week string like '2026-W07'."""
    if dt is None:
        dt = datetime.now()
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _validate_image_bytes(data: bytes) -> bool:
    """Check leading bytes against known image signatures."""
    for sig in IMAGE_SIGNATURES:
        if data[:len(sig)] == sig:
            return True
    return False


def _validate_token(token_str):
    """Return token dict if the token is valid and active, else None."""
    if not token_str:
        return None
    token_data = database.get_token(token_str)
    if not token_data or not token_data["is_active"]:
        return None
    return token_data


# ---------------------------------------------------------------------------
# 1. Capture page  -- GET /job-photos?token=X
# ---------------------------------------------------------------------------

@job_photos_bp.route("/job-photos")
def capture_page():
    token_str = request.args.get("token", "")
    token_data = _validate_token(token_str)
    if not token_data:
        return render_template("errors/invalid_token.html"), 404

    # Require employee session
    h = _helpers()
    employee = h._require_employee_session(token_str)
    if not employee:
        return redirect(url_for("company_home", token_str=token_str))

    jobs = database.get_jobs_by_token(token_str, active_only=True)
    return render_template(
        "job_photos/capture.html",
        token=token_data,
        jobs=jobs,
    )


# ---------------------------------------------------------------------------
# Photo Library (employee-facing)
# ---------------------------------------------------------------------------

@job_photos_bp.route("/photo-library")
def photo_library():
    token_str = request.args.get("token", "")
    token_data = _validate_token(token_str)
    if not token_data:
        return render_template("errors/invalid_token.html"), 404
    h = _helpers()
    employee = h._require_employee_session(token_str)
    if not employee:
        return redirect(url_for("company_home", token_str=token_str))

    job_id = request.args.get("job_id", "").strip()
    search = request.args.get("search", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    jobs = database.get_jobs_by_token(token_str, active_only=False)
    photos = []
    selected_job = None
    if job_id:
        all_photos = database.get_job_photos_for_library(
            token_str, search=search or None,
            date_from=date_from or None, date_to=date_to or None,
            job_id=job_id,
        )
        photos = [p for p in all_photos if Path(p["image_file"]).suffix.lower() in _IMAGE_EXTENSIONS]
        for j in jobs:
            if str(j["id"]) == job_id:
                selected_job = j
                break

    return render_template("photo_library.html",
        token=token_data, photos=photos, jobs=jobs,
        job_id=job_id, selected_job=selected_job,
        search=search, date_from=date_from, date_to=date_to)


@job_photos_bp.route("/photo-library/<int:photo_id>")
def photo_library_detail(photo_id):
    token_str = request.args.get("token", "")
    token_data = _validate_token(token_str)
    if not token_data:
        return render_template("errors/invalid_token.html"), 404
    h = _helpers()
    employee = h._require_employee_session(token_str)
    if not employee:
        return redirect(url_for("company_home", token_str=token_str))

    photo = database.get_job_photo(photo_id)
    if not photo or photo["token"] != token_str:
        return render_template("errors/404.html"), 404

    return render_template("photo_library_detail.html",
        token=token_data, photo=photo)


# ---------------------------------------------------------------------------
# 2. Upload API  -- POST /api/job-photos/upload
# ---------------------------------------------------------------------------

@job_photos_bp.route("/api/job-photos/upload", methods=["POST"])
def upload_photo():
    token_str = request.form.get("token", "").strip()
    token_data = _validate_token(token_str)
    if not token_data:
        return jsonify({"error": "Invalid or inactive token"}), 403

    job_id = request.form.get("job_id", "").strip()
    if not job_id:
        return jsonify({"error": "job_id is required"}), 400
    try:
        job_id = int(job_id)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid job_id"}), 400

    job = database.get_job(job_id)
    if not job or job["token"] != token_str:
        return jsonify({"error": "Job not found for this token"}), 404

    caption = request.form.get("caption", "").strip()

    # GPS coordinates (optional)
    lat = request.form.get("latitude")
    lng = request.form.get("longitude")
    try:
        lat = float(lat) if lat else None
    except (ValueError, TypeError):
        lat = None
    try:
        lng = float(lng) if lng else None
    except (ValueError, TypeError):
        lng = None

    # Read uploaded file
    photo_file = request.files.get("image") or request.files.get("photo")
    if not photo_file or not photo_file.filename:
        return jsonify({"error": "No image file provided"}), 400

    raw_bytes = photo_file.read()
    if not raw_bytes:
        return jsonify({"error": "Empty file"}), 400

    if not _validate_image_bytes(raw_bytes):
        return jsonify({"error": "Invalid image file"}), 400

    # Process the image
    from PIL import Image
    img = Image.open(io.BytesIO(raw_bytes))

    # Build EXIF with GPS before orientation fix (read from original bytes)
    exif_bytes = _get_exif_bytes(raw_bytes, lat=lat, lng=lng)

    img = _fix_image_orientation(img)

    # Determine storage path
    now = datetime.now()
    week_folder = _week_folder_for_date(now)
    safe_job_name = _sanitize_job_name(job["job_name"])
    uid = secrets.token_hex(3)  # 6 hex chars
    date_str = now.strftime("%Y%m%d")
    base_name = f"photo_{date_str}_{uid}"

    folder_path = config.JOB_PHOTOS_DIR / token_str / safe_job_name / week_folder
    folder_path.mkdir(parents=True, exist_ok=True)

    # Save full image with EXIF (preserves GPS geotag)
    image_filename = f"{base_name}.jpg"
    full_path = folder_path / image_filename
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    save_kwargs = {"quality": 85}
    if exif_bytes:
        save_kwargs["exif"] = exif_bytes
    img.save(str(full_path), "JPEG", **save_kwargs)

    # Generate and save thumbnail (no EXIF needed for thumbs)
    thumb = _generate_thumbnail(img)
    thumb_filename = f"{base_name}_thumb.jpg"
    thumb_path = folder_path / thumb_filename
    thumb.save(str(thumb_path), "JPEG", quality=80)

    # Relative path stored in DB (from JOB_PHOTOS_DIR)
    rel_image = f"{token_str}/{safe_job_name}/{week_folder}/{image_filename}"
    rel_thumb = f"{token_str}/{safe_job_name}/{week_folder}/{thumb_filename}"

    photo_id = database.create_job_photo(
        job_id=job_id,
        token_str=token_str,
        week_folder=week_folder,
        image_file=rel_image,
        thumb_file=rel_thumb,
        caption=caption,
        taken_by="",
        latitude=lat,
        longitude=lng,
    )

    return jsonify({
        "success": True,
        "photo_id": photo_id,
        "image_url": url_for("job_photos.serve_photo", photo_id=photo_id),
        "thumb_url": url_for("job_photos.serve_photo", photo_id=photo_id, thumb="1"),
    }), 201


# ---------------------------------------------------------------------------
# 3. Serve photo  -- GET /api/job-photos/<id>
# ---------------------------------------------------------------------------

@job_photos_bp.route("/api/job-photos/<int:photo_id>")
def serve_photo(photo_id):
    photo = database.get_job_photo(photo_id)
    if not photo:
        abort(404)

    # Auth: require admin login OR valid employee session for this token
    if not current_user.is_authenticated:
        h = _helpers()
        employee = h._require_employee_session(photo["token"])
        if not employee:
            abort(403)

    want_thumb = request.args.get("thumb", "0") == "1"

    if want_thumb and photo.get("thumb_file"):
        file_path = config.JOB_PHOTOS_DIR / photo["thumb_file"]
    else:
        file_path = config.JOB_PHOTOS_DIR / photo["image_file"]

    if not file_path.exists():
        abort(404)

    mime, _ = mimetypes.guess_type(str(file_path))
    if not mime:
        mime = "application/octet-stream"
    return send_file(str(file_path), mimetype=mime)


# ---------------------------------------------------------------------------
# 3b. Update photo caption  -- POST /api/job-photos/<id>/caption
# ---------------------------------------------------------------------------

@job_photos_bp.route("/api/job-photos/<int:photo_id>/caption", methods=["POST"])
def api_update_photo_caption(photo_id):
    photo = database.get_job_photo(photo_id)
    if not photo:
        return jsonify({"error": "Not found"}), 404

    if not current_user.is_authenticated:
        h = _helpers()
        employee = h._require_employee_session(photo["token"])
        if not employee:
            return jsonify({"error": "Not authenticated"}), 401

    caption = (request.get_json() or {}).get("caption", "").strip()
    database.update_job_photo_caption(photo_id, caption)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# 3c. Delete photo API  -- POST /api/job-photos/<id>/delete
# ---------------------------------------------------------------------------

@job_photos_bp.route("/api/job-photos/<int:photo_id>/delete", methods=["POST"])
def api_delete_photo(photo_id):
    photo = database.get_job_photo(photo_id)
    if not photo:
        return jsonify({"error": "Not found"}), 404

    if not current_user.is_authenticated:
        h = _helpers()
        employee = h._require_employee_session(photo["token"])
        if not employee:
            return jsonify({"error": "Not authenticated"}), 401

    image_path = config.JOB_PHOTOS_DIR / photo["image_file"]
    thumb_path = config.JOB_PHOTOS_DIR / photo["thumb_file"] if photo.get("thumb_file") else None
    if image_path.exists():
        image_path.unlink()
    if thumb_path and thumb_path.exists():
        thumb_path.unlink()

    database.delete_job_photo(photo_id)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# 4. Admin browse  -- GET /admin/job-photos
#    Level 1: jobs with photos (no params)
#    Level 2: week folders for a job (?job_id=X)
#    Level 3: photo gallery for a week (?job_id=X&week=YYYY-Www)
# ---------------------------------------------------------------------------

@job_photos_bp.route("/admin/job-photos")
@login_required
def admin_job_photos():
    h = _helpers()
    tokens = h._get_tokens_for_user()
    token_str, selected_token = h._get_selected_token(tokens)

    job_id = request.args.get("job_id", type=int)
    week = request.args.get("week", "").strip()

    jobs_with_photos = []
    weeks = []
    photos = []
    selected_job = None

    if token_str:
        jobs_with_photos = database.get_jobs_with_photos(token_str)

        if job_id:
            # Verify the job belongs to this token
            selected_job = database.get_job(job_id)
            if not selected_job or selected_job["token"] != token_str:
                abort(404)

            weeks = database.get_job_photo_weeks(job_id)

            if week:
                photos = database.get_job_photos_by_job_week(job_id, week)

    return render_template(
        "admin/job_photos.html",
        tokens=tokens,
        selected_token=selected_token,
        jobs_with_photos=jobs_with_photos,
        selected_job=selected_job,
        job_id=job_id,
        weeks=weeks,
        week=week,
        photos=photos,
    )


# ---------------------------------------------------------------------------
# 5. Admin photo detail  -- GET /admin/job-photos/<id>
# ---------------------------------------------------------------------------

@job_photos_bp.route("/admin/job-photos/<int:photo_id>/detail")
@login_required
def admin_photo_detail(photo_id):
    h = _helpers()
    photo = database.get_job_photo(photo_id)
    if not photo:
        abort(404)
    h._verify_token_access(photo["token"])

    tokens = h._get_tokens_for_user()
    _, selected_token = h._get_selected_token(tokens)

    return render_template(
        "admin/job_photo_detail.html",
        photo=photo,
        tokens=tokens,
        selected_token=selected_token,
    )


# ---------------------------------------------------------------------------
# 6. Admin delete  -- POST /admin/job-photos/<id>/delete
# ---------------------------------------------------------------------------

@job_photos_bp.route("/admin/job-photos/<int:photo_id>/delete", methods=["POST"])
@login_required
def admin_delete_photo(photo_id):
    h = _helpers()
    photo = database.get_job_photo(photo_id)
    if not photo:
        abort(404)
    h._verify_token_access(photo["token"])
    if not current_user.is_admin and not current_user.is_bdb:
        abort(403)

    # Delete files from disk
    image_path = config.JOB_PHOTOS_DIR / photo["image_file"]
    thumb_path = config.JOB_PHOTOS_DIR / photo["thumb_file"] if photo.get("thumb_file") else None

    if image_path.exists():
        image_path.unlink()
    if thumb_path and thumb_path.exists():
        thumb_path.unlink()

    job_id = photo["job_id"]
    week = photo["week_folder"]

    database.delete_job_photo(photo_id)
    flash("Photo deleted.", "success")

    return redirect(url_for(
        "job_photos.admin_job_photos",
        job_id=job_id,
        week=week,
    ))


# ---------------------------------------------------------------------------
# 6. Download ZIP  -- GET /admin/job-photos/download-zip/<job_id>/<week>
# ---------------------------------------------------------------------------

@job_photos_bp.route("/admin/job-photos/download-zip/<int:job_id>/<week>")
@login_required
def download_zip(job_id, week):
    h = _helpers()
    job = database.get_job(job_id)
    if not job:
        abort(404)
    h._verify_token_access(job["token"])

    photos = database.get_job_photos_by_job_week(job_id, week)
    if not photos:
        flash("No photos found for this week.", "error")
        return redirect(url_for("job_photos.admin_job_photos", job_id=job_id))

    buf = io.BytesIO()
    safe_job_name = _sanitize_job_name(job["job_name"])
    zip_name = f"{safe_job_name}_{week}.zip"

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for photo in photos:
            file_path = config.JOB_PHOTOS_DIR / photo["image_file"]
            if file_path.exists():
                arcname = file_path.name
                zf.write(str(file_path), arcname)

    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=zip_name,
    )


# ---------------------------------------------------------------------------
# 7. Download PDF  -- GET /admin/job-photos/download-pdf/<job_id>/<week>
# ---------------------------------------------------------------------------

@job_photos_bp.route("/admin/job-photos/download-pdf/<int:job_id>/<week>")
@login_required
def download_pdf(job_id, week):
    h = _helpers()
    job = database.get_job(job_id)
    if not job:
        abort(404)
    h._verify_token_access(job["token"])

    token_data = database.get_token(job["token"])
    company = token_data["company_name"] if token_data else "Unknown"

    photos = database.get_job_photos_by_job_week(job_id, week)
    if not photos:
        flash("No photos found for this week.", "error")
        return redirect(url_for("job_photos.admin_job_photos", job_id=job_id))

    from fpdf import FPDF

    def _safe(text):
        return str(text).encode("latin-1", "replace").decode("latin-1")

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)

    for photo in photos:
        file_path = config.JOB_PHOTOS_DIR / photo["image_file"]
        if not file_path.exists():
            continue

        pdf.add_page()

        # Header
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 8, _safe(f"{company} — {job['job_name']}"), ln=True, align="C")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 5, _safe(f"Week: {week}"), ln=True, align="C")
        pdf.ln(4)

        # Photo — fit to page width with aspect ratio
        page_w = pdf.w - pdf.l_margin - pdf.r_margin
        max_h = 160  # mm max height for photo
        try:
            from PIL import Image as PILImage
            with PILImage.open(str(file_path)) as img:
                w_px, h_px = img.size
            aspect = h_px / w_px
            img_w = page_w
            img_h = page_w * aspect
            if img_h > max_h:
                img_h = max_h
                img_w = max_h / aspect
            x = pdf.l_margin + (page_w - img_w) / 2
            pdf.image(str(file_path), x=x, y=pdf.get_y(), w=img_w, h=img_h)
            pdf.set_y(pdf.get_y() + img_h + 4)
        except Exception:
            pdf.cell(0, 10, "[Image could not be loaded]", ln=True, align="C")

        # Caption
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, "Caption:", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, _safe(photo.get("caption") or "No caption"))
        pdf.ln(2)

        # Date
        pdf.set_font("Helvetica", "", 9)
        date_str = photo.get("created_at", "")[:19] if photo.get("created_at") else "—"
        pdf.cell(0, 5, _safe(f"Date: {date_str}"), ln=True)

        # GPS
        if photo.get("latitude") and photo.get("longitude"):
            lat = photo["latitude"]
            lng = photo["longitude"]
            pdf.cell(0, 5, _safe(f"GPS: {lat:.6f}, {lng:.6f}"), ln=True)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(37, 99, 235)
            pdf.cell(0, 5, _safe(f"https://maps.google.com/?q={lat},{lng}"), ln=True)
            pdf.set_text_color(0, 0, 0)

        # Footer note
        pdf.ln(4)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 4, _safe("Photo contains embedded GPS geotag metadata. Download original for Google posting."), ln=True, align="C")
        pdf.set_text_color(0, 0, 0)

    output = io.BytesIO()
    pdf.output(output)
    output.seek(0)

    safe_job_name = _sanitize_job_name(job["job_name"])
    filename = f"{safe_job_name}_{week}_photos.pdf"

    return send_file(
        output,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


# ---------------------------------------------------------------------------
# Job Files (employee-facing) — non-image files (PDFs, etc.)
# ---------------------------------------------------------------------------

@job_photos_bp.route("/job-files")
def job_files():
    token_str = request.args.get("token", "")
    token_data = _validate_token(token_str)
    if not token_data:
        return render_template("errors/invalid_token.html"), 404
    h = _helpers()
    employee = h._require_employee_session(token_str)
    if not employee:
        return redirect(url_for("company_home", token_str=token_str))

    job_id = request.args.get("job_id", "").strip()
    jobs = database.get_jobs_by_token(token_str, active_only=False)
    files = []
    selected_job = None
    if job_id:
        all_records = database.get_job_photos_for_library(token_str, job_id=job_id)
        files = [r for r in all_records if Path(r["image_file"]).suffix.lower() not in _IMAGE_EXTENSIONS]
        for j in jobs:
            if str(j["id"]) == job_id:
                selected_job = j
                break

    return render_template("job_files.html",
        token=token_data, files=files, jobs=jobs,
        job_id=job_id, selected_job=selected_job)


@job_photos_bp.route("/job-files/<int:file_id>")
def job_file_detail(file_id):
    token_str = request.args.get("token", "")
    token_data = _validate_token(token_str)
    if not token_data:
        return render_template("errors/invalid_token.html"), 404
    h = _helpers()
    employee = h._require_employee_session(token_str)
    if not employee:
        return redirect(url_for("company_home", token_str=token_str))

    photo = database.get_job_photo(file_id)
    if not photo or photo["token"] != token_str:
        return render_template("errors/404.html"), 404

    return render_template("job_file_detail.html",
        token=token_data, file=photo)
