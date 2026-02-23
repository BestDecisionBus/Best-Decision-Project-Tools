from pathlib import Path

from fpdf import FPDF
from PIL import Image, ImageOps


def fix_image_orientation(image_path):
    """Apply EXIF orientation and overwrite the file."""
    image_path = Path(image_path)
    try:
        img = Image.open(image_path)
        fixed = ImageOps.exif_transpose(img)
        if fixed is not img:
            fixed.save(image_path, "JPEG", quality=85)
        else:
            img.close()
    except Exception:
        pass


def generate_web_thumbnail(image_path, thumb_path, max_width=1200):
    """Create a web-optimized version of the image for fast viewing."""
    try:
        with Image.open(image_path) as img:
            w, h = img.size
            if w > max_width:
                ratio = max_width / w
                new_size = (max_width, int(h * ratio))
                img = img.resize(new_size, Image.LANCZOS)
            img.save(str(thumb_path), "JPEG", quality=75)
            return True
    except Exception:
        return False


def _get_image_dimensions(image_path):
    """Return (width, height) in pixels, or None on failure."""
    try:
        with Image.open(image_path) as img:
            return img.size
    except Exception:
        return None


def generate_receipt_pdf(output_path, image_path, transcription, company_name,
                         timestamp, token, job_name=None, category_names=None):
    """Generate a single-page PDF with the receipt image and transcription text.

    Optionally includes job name and category names in header area.
    """
    image_path = Path(image_path)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    usable_width = pdf.w - pdf.l_margin - pdf.r_margin

    # --- Header ---
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, company_name, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, f"Date: {timestamp}    Token: {token}", new_x="LMARGIN", new_y="NEXT")

    # Job and category info
    if job_name:
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 5, f"Job: {job_name}", new_x="LMARGIN", new_y="NEXT")
    if category_names:
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 9)
        cats = ", ".join(c for c in category_names if c)
        if cats:
            pdf.cell(0, 5, f"Category: {cats}", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(2)

    # --- Receipt Image ---
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Receipt Image", new_x="LMARGIN", new_y="NEXT")

    image_placed = False
    if image_path.exists():
        dims = _get_image_dimensions(image_path)
        if dims:
            img_w_px, img_h_px = dims
            aspect = img_h_px / img_w_px

            y_before_image = pdf.get_y()
            page_bottom = pdf.h - 15

            trans_text = transcription or "[No transcription available]"
            chars_per_line = 95
            num_lines = max(1, -(-len(trans_text) // chars_per_line))
            num_lines = max(num_lines, trans_text.count('\n') + 1)
            trans_height = 6 + 2 + (num_lines * 4.5) + 4

            available_height = page_bottom - y_before_image - trans_height - 3

            display_w = usable_width
            display_h = display_w * aspect

            if display_h > available_height and available_height > 20:
                display_h = available_height
                display_w = display_h / aspect

            x_pos = pdf.l_margin + (usable_width - display_w) / 2

            try:
                y_img = pdf.get_y()
                pdf.image(str(image_path), x=x_pos, y=y_img, w=display_w, h=display_h)
                pdf.set_y(y_img + display_h + 3)
                image_placed = True
            except Exception:
                pass

    if not image_placed:
        pdf.set_font("Helvetica", "I", 9)
        pdf.cell(0, 6, "[Image could not be loaded]", new_x="LMARGIN", new_y="NEXT")

    # --- Transcription ---
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Voice Memo Transcription", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)

    pdf.set_font("Helvetica", "", 9)
    if transcription:
        pdf.multi_cell(0, 4.5, transcription)
    else:
        pdf.set_font("Helvetica", "I", 9)
        pdf.multi_cell(0, 4.5, "[No transcription available]")

    pdf.output(str(output_path))


def generate_estimate_pdf(output_path, estimate, job_name, photos=None, tasks=None,
                          company_name=""):
    """Generate an estimate report PDF with photos, transcription, and tasks."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    usable_width = pdf.w - pdf.l_margin - pdf.r_margin

    # --- Header ---
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Estimate Report", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 100, 100)
    if company_name:
        pdf.cell(0, 5, company_name, new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Job: {job_name}    Date: {estimate['created_at'][:10]}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # --- Description / Caption ---
    if estimate.get("title"):
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Description", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 4.5, estimate["title"])
        pdf.ln(4)

    # --- Transcription ---
    if estimate.get("transcription"):
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Voice Memo Transcription", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 4.5, estimate["transcription"])
        pdf.ln(4)

    # --- Notes ---
    if estimate.get("notes"):
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Additional Notes", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 4.5, estimate["notes"])
        pdf.ln(4)

    # --- Tasks ---
    if tasks:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Extracted Tasks", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
        pdf.set_font("Helvetica", "", 9)
        for i, task in enumerate(tasks, 1):
            name = task["name"] if isinstance(task, dict) else str(task)
            pdf.cell(0, 5, f"  {i}. {name}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    # --- Photos ---
    _embed_photos(pdf, photos, usable_width)

    pdf.output(str(output_path))


def _embed_photos(pdf, photos, usable_width):
    """Embed a list of job site photos into the PDF. Shared by all estimate report types."""
    import tempfile as _tmpmod
    import os as _os
    import config as _cfg

    temp_files = []
    if photos:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Job Site Photos", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        for photo in photos:
            image_path = Path(_cfg.JOB_PHOTOS_DIR) / photo["image_file"]
            if not image_path.exists():
                continue

            try:
                img = Image.open(image_path)
                img = ImageOps.exif_transpose(img) or img
                w, h = img.size
                if w > 1600:
                    ratio = 1600 / w
                    img = img.resize((1600, int(h * ratio)), Image.LANCZOS)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                tmp_img = _tmpmod.NamedTemporaryFile(suffix=".jpg", delete=False)
                img.save(tmp_img.name, "JPEG", quality=70)
                img.close()
                temp_files.append(tmp_img.name)
                embed_path = tmp_img.name
            except Exception:
                embed_path = str(image_path)

            dims = _get_image_dimensions(embed_path)
            if not dims:
                continue

            img_w_px, img_h_px = dims
            aspect = img_h_px / img_w_px
            display_w = usable_width
            display_h = display_w * aspect

            caption_h = 7 if photo.get("caption") else 0
            if pdf.get_y() + display_h + caption_h + 15 > pdf.h - 15:
                pdf.add_page()

            y_start = pdf.get_y()
            try:
                pdf.image(embed_path, x=pdf.l_margin, w=display_w, h=display_h)
                pdf.set_y(y_start + display_h + 2)
            except Exception:
                pass

            if photo.get("caption"):
                pdf.set_font("Helvetica", "I", 8)
                pdf.cell(0, 4, photo["caption"], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)

    for tf in temp_files:
        try:
            _os.unlink(tf)
        except OSError:
            pass


def _safe_latin1(text):
    """Replace non-latin-1 characters so FPDF Helvetica won't crash.

    Handles smart quotes, em/en dashes, and other common Unicode from mobile
    keyboards.  Falls back to '?' for truly exotic characters.
    """
    if not text:
        return text
    replacements = {
        "\u2018": "'", "\u2019": "'",   # smart single quotes
        "\u201c": '"', "\u201d": '"',   # smart double quotes
        "\u2013": "-", "\u2014": "-",   # en-dash, em-dash
        "\u2026": "...",                 # ellipsis
        "\u00a0": " ",                  # non-breaking space
        "\u2022": "*",                  # bullet
    }
    for orig, repl in replacements.items():
        text = text.replace(orig, repl)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def generate_scope_of_work_pdf(output_path, estimate, job, items, company_name="", photos=None):
    """Generate a Scope of Work PDF with client info, description, transcription,
    notes, and products/services with quantities and checkboxes (no pricing)."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    usable_width = pdf.w - pdf.l_margin - pdf.r_margin

    s = _safe_latin1  # shorthand for sanitizing user text

    # --- Header ---
    pdf.set_font("Helvetica", "B", 16)
    if company_name:
        pdf.cell(0, 10, s(company_name), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, "Scope of Work", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    if job:
        job_line = job.get("job_name", "")
        if job.get("job_address"):
            job_line += f"  -  {job['job_address']}"
        pdf.cell(0, 5, s(job_line), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Date: {estimate['created_at'][:10]}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # --- Divider ---
    y_div = pdf.get_y()
    pdf.set_draw_color(200, 200, 200)
    pdf.line(pdf.l_margin, y_div, pdf.l_margin + usable_width, y_div)
    pdf.ln(4)

    # --- Client Info ---
    has_client = any(estimate.get(f) for f in ("customer_name", "customer_phone", "customer_email"))
    if has_client:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Client Information", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
        pdf.set_font("Helvetica", "", 10)
        if estimate.get("customer_name"):
            pdf.cell(0, 5, s(estimate["customer_name"]), new_x="LMARGIN", new_y="NEXT")
        if estimate.get("customer_phone"):
            pdf.cell(0, 5, s(estimate["customer_phone"]), new_x="LMARGIN", new_y="NEXT")
        if estimate.get("customer_email"):
            pdf.cell(0, 5, s(estimate["customer_email"]), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    # --- Description / Caption ---
    if estimate.get("title"):
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Description", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 4.5, s(estimate["title"]))
        pdf.ln(4)

    # --- Transcription ---
    if estimate.get("transcription"):
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Transcription", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 4.5, s(estimate["transcription"]))
        pdf.ln(4)

    # --- Additional Notes ---
    if estimate.get("notes"):
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Additional Notes", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 4.5, s(estimate["notes"]))
        pdf.ln(4)

    # --- Products & Services (with checkboxes, no pricing) ---
    if items:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Products & Services", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        # Column widths: checkbox(10), description(rest), qty(20)
        col_check = 10
        col_qty = 20
        col_desc = usable_width - col_check - col_qty
        row_h = 7

        # Header row
        pdf.set_fill_color(50, 50, 70)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_x(pdf.l_margin)
        pdf.cell(col_check, row_h, "", border=1, fill=True, align="C")
        pdf.cell(col_desc, row_h, "Description", border=1, fill=True)
        pdf.cell(col_qty, row_h, "Qty", border=1, fill=True, align="C",
                 new_x="LMARGIN", new_y="NEXT")

        # Data rows
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 9)
        for i, item in enumerate(items):
            if i % 2 == 0:
                pdf.set_fill_color(245, 245, 250)
                fill = True
            else:
                fill = False

            y_before = pdf.get_y()
            x_start = pdf.l_margin

            pdf.set_x(x_start)
            # Checkbox cell — draw empty square
            pdf.cell(col_check, row_h, "", border=1, fill=fill, align="C")
            # Draw checkbox rect inside
            box_size = 3.5
            box_x = x_start + (col_check - box_size) / 2
            box_y = y_before + (row_h - box_size) / 2
            pdf.set_draw_color(80, 80, 80)
            pdf.rect(box_x, box_y, box_size, box_size)
            pdf.set_draw_color(0, 0, 0)

            pdf.cell(col_desc, row_h, s(str(item.get("description", ""))[:80]), border=1, fill=fill)
            pdf.cell(col_qty, row_h, str(item.get("quantity", 0)), border=1, fill=fill, align="C",
                     new_x="LMARGIN", new_y="NEXT")

    # --- Photos ---
    if photos:
        pdf.ln(4)
    _embed_photos(pdf, photos, usable_width)

    pdf.output(str(output_path))


def generate_client_estimate_pdf(output_path, estimate, job, items, token_data, photos=None):
    """Generate a professional client-facing estimate PDF with line items and totals."""
    import config as _cfg

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    usable_width = pdf.w - pdf.l_margin - pdf.r_margin
    company_name = token_data["company_name"] if token_data else ""

    # --- Header: Logo + Company + Estimate Info ---
    logo_placed = False
    if token_data and token_data.get("logo_file"):
        logo_path = Path(_cfg.LOGOS_DIR) / token_data["logo_file"]
        if logo_path.exists():
            try:
                pdf.image(str(logo_path), x=pdf.l_margin, y=pdf.get_y(), w=40)
                logo_placed = True
            except Exception:
                pass

    # Right-aligned estimate info
    right_x = pdf.l_margin + usable_width - 80
    top_y = pdf.get_y()

    pdf.set_xy(right_x, top_y)
    doc_label = "PROJECT" if estimate.get("approval_status", "pending") not in ("pending", "declined") else "ESTIMATE"
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(80, 10, doc_label, align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    est_num = estimate.get("estimate_number") or str(estimate["id"])
    pdf.set_x(right_x)
    pdf.cell(80, 5, f"{doc_label.title()} #{est_num}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(right_x)
    pdf.cell(80, 5, f"Date: {estimate['created_at'][:10]}", align="R", new_x="LMARGIN", new_y="NEXT")
    if estimate.get("date_accepted"):
        pdf.set_x(right_x)
        pdf.cell(80, 5, f"Accepted: {estimate['date_accepted']}", align="R", new_x="LMARGIN", new_y="NEXT")
    if estimate.get("expected_completion"):
        pdf.set_x(right_x)
        pdf.cell(80, 5, f"Expected: {estimate['expected_completion']}", align="R", new_x="LMARGIN", new_y="NEXT")

    # Company name under logo
    if logo_placed:
        pdf.set_y(top_y + 42)
    else:
        pdf.set_y(top_y)
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(usable_width / 2, 8, company_name, new_x="LMARGIN", new_y="NEXT")
        pdf.set_y(max(pdf.get_y(), top_y + 30))

    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # --- Divider ---
    y_div = pdf.get_y()
    pdf.set_draw_color(200, 200, 200)
    pdf.line(pdf.l_margin, y_div, pdf.l_margin + usable_width, y_div)
    pdf.ln(4)

    # --- Bill To + Job Info ---
    col_w = usable_width / 2
    start_y = pdf.get_y()

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(col_w, 6, "BILL TO:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(0, 0, 0)
    if estimate.get("customer_name"):
        pdf.cell(col_w, 5, estimate["customer_name"], new_x="LMARGIN", new_y="NEXT")
    if estimate.get("customer_phone"):
        pdf.cell(col_w, 5, estimate["customer_phone"], new_x="LMARGIN", new_y="NEXT")
    if estimate.get("customer_email"):
        pdf.cell(col_w, 5, estimate["customer_email"], new_x="LMARGIN", new_y="NEXT")

    left_end_y = pdf.get_y()

    # Job info on the right
    pdf.set_xy(pdf.l_margin + col_w, start_y)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(col_w, 6, "JOB:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(pdf.l_margin + col_w)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(0, 0, 0)
    if job:
        pdf.cell(col_w, 5, job.get("job_name", ""), new_x="LMARGIN", new_y="NEXT")
        if job.get("job_address"):
            pdf.set_x(pdf.l_margin + col_w)
            pdf.cell(col_w, 5, job["job_address"], new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(max(left_end_y, pdf.get_y()) + 6)

    # --- Divider ---
    y_div = pdf.get_y()
    pdf.line(pdf.l_margin, y_div, pdf.l_margin + usable_width, y_div)
    pdf.ln(4)

    # --- Line Items Table ---
    if items:
        # Column widths: #, Description, Qty, Price, Total
        col_num = 12
        col_desc = usable_width - 12 - 20 - 30 - 30
        col_qty = 20
        col_price = 30
        col_total = 30
        row_h = 7

        # Header row
        pdf.set_fill_color(50, 50, 70)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 9)
        x = pdf.l_margin
        pdf.set_x(x)
        pdf.cell(col_num, row_h, "#", border=1, fill=True, align="C")
        pdf.cell(col_desc, row_h, "Product / Service", border=1, fill=True)
        pdf.cell(col_qty, row_h, "Qty", border=1, fill=True, align="C")
        pdf.cell(col_price, row_h, "Price", border=1, fill=True, align="R")
        pdf.cell(col_total, row_h, "Total", border=1, fill=True, align="R",
                 new_x="LMARGIN", new_y="NEXT")

        # Data rows with alternating shading
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 9)
        for i, item in enumerate(items, 1):
            if i % 2 == 0:
                pdf.set_fill_color(245, 245, 250)
                fill = True
            else:
                fill = False

            pdf.set_x(pdf.l_margin)
            pdf.cell(col_num, row_h, str(i), border=1, fill=fill, align="C")
            pdf.cell(col_desc, row_h, str(item.get("description", ""))[:60], border=1, fill=fill)
            pdf.cell(col_qty, row_h, str(item.get("quantity", 0)), border=1, fill=fill, align="C")
            pdf.cell(col_price, row_h, f"${item.get('unit_price', 0):,.2f}", border=1, fill=fill, align="R")
            pdf.cell(col_total, row_h, f"${item.get('total', 0):,.2f}", border=1, fill=fill, align="R",
                     new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)

    # --- Totals ---
    subtotal = sum(item.get("total", 0) for item in items)
    tax_rate = estimate.get("sales_tax_rate", 0) or 0
    taxable_total = sum(item.get("total", 0) for item in items if item.get("taxable"))
    sales_tax = taxable_total * (tax_rate / 100)
    grand_total = subtotal + sales_tax

    totals_x = pdf.l_margin + usable_width - 80
    pdf.set_font("Helvetica", "", 10)
    pdf.set_x(totals_x)
    pdf.cell(40, 6, "Subtotal:", align="R")
    pdf.cell(40, 6, f"${subtotal:,.2f}", align="R", new_x="LMARGIN", new_y="NEXT")

    if tax_rate > 0:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_x(pdf.l_margin)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(totals_x - pdf.l_margin, 6, f"Tax Rate: {tax_rate:.2f}%")
        pdf.set_text_color(0, 0, 0)
        pdf.set_x(totals_x)
        pdf.cell(40, 6, "Sales Tax:", align="R")
        pdf.cell(40, 6, f"${sales_tax:,.2f}", align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 12)
    pdf.set_x(totals_x)
    pdf.cell(40, 8, "TOTAL:", align="R")
    pdf.cell(40, 8, f"${grand_total:,.2f}", align="R", new_x="LMARGIN", new_y="NEXT")

    # --- Customer Message ---
    msg = (estimate.get("customer_message") or "").strip()
    if msg:
        pdf.ln(6)
        y_msg = pdf.get_y()
        pdf.set_draw_color(200, 200, 200)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, "Message:", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(usable_width, 4.5, msg)
        y_end = pdf.get_y()
        pdf.rect(pdf.l_margin - 1, y_msg - 1, usable_width + 2, y_end - y_msg + 2)

    # --- Photos ---
    if photos:
        pdf.ln(6)
    _embed_photos(pdf, photos, usable_width)

    pdf.output(str(output_path))
