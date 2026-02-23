"""Database-backed single-worker task queue for GPU-bound processing.

Uses the submissions table (status column) as the queue instead of an
in-memory Queue.  This works correctly with Gunicorn's pre-fork model:
every worker process starts a polling thread, but a file lock ensures
only ONE thread across all processes runs GPU work at any given time.
"""

import fcntl
import logging
import threading
import time
from pathlib import Path

import config
import database
import transcriber
import pdf_generator

logger = logging.getLogger(__name__)

_worker_thread = None
_lock_path = config.INSTANCE_DIR / "gpu_worker.lock"

POLL_INTERVAL = 2


def _worker():
    """Background worker: polls DB for pending tasks, processes one at a time."""
    lock_fd = open(_lock_path, "w")
    while True:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            try:
                _poll_and_process()
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            time.sleep(POLL_INTERVAL)
        except Exception as e:
            logger.error(f"Worker loop error: {e}")
            time.sleep(POLL_INTERVAL)


def _poll_and_process():
    """Check for one pending submission or estimate and process it."""
    row = database.claim_next_pending()
    if row is None:
        _poll_and_process_estimate()
        _poll_and_process_append()
        return

    submission_id = row["id"]
    logger.info(f"Processing submission {submission_id} for {row['company_name']}")

    try:
        token = row["token"]
        company_name = row["company_name"]
        month_folder = row["month_folder"]
        image_file = row["image_file"]
        audio_file = row["audio_file"]
        timestamp = row["timestamp"]

        folder = config.RECEIPTS_DIR / token / month_folder
        audio_path = folder / audio_file
        image_path = folder / image_file

        base_name = Path(image_file).stem
        pdf_filename = f"{base_name}.pdf"
        thumb_filename = f"{base_name}_thumb.jpg"

        # Fix EXIF orientation
        pdf_generator.fix_image_orientation(image_path)

        # Generate thumbnail
        thumb_path = folder / thumb_filename
        pdf_generator.generate_web_thumbnail(image_path, thumb_path)

        # Transcribe audio
        text = transcriber.transcribe(audio_path)

        # Look up job name and category names for PDF
        job_name = None
        category_names = []
        if row.get("job_id"):
            job = database.get_job(row["job_id"])
            if job:
                job_name = job["job_name"]
        for cat_field in ("category_1_id", "category_2_id"):
            if row.get(cat_field):
                cat = database.get_category(row[cat_field])
                if cat:
                    category_names.append(cat["name"])

        # Generate combined PDF
        pdf_path = folder / pdf_filename
        pdf_generator.generate_receipt_pdf(
            output_path=pdf_path,
            image_path=image_path,
            transcription=text,
            company_name=company_name,
            timestamp=timestamp,
            token=token,
            job_name=job_name,
            category_names=category_names if category_names else None,
        )

        database.update_submission_transcription(submission_id, text, pdf_filename)
        logger.info(f"Completed submission {submission_id} for {company_name}")

    except Exception as e:
        logger.error(f"Task failed for submission {submission_id}: {e}")
        try:
            database.update_submission_error(submission_id, f"Error: {e}")
        except Exception:
            pass


def _poll_and_process_estimate():
    """Check for one pending estimate and process it."""
    est = database.claim_next_pending_estimate()
    if est is None:
        return

    estimate_id = est["id"]
    logger.info(f"Processing estimate {estimate_id} for job {est.get('job_name', '?')}")

    try:
        token = est["token"]
        audio_file = est.get("audio_file", "")

        if audio_file:
            # Audio stored under receipts/{token}/estimates/
            audio_path = config.RECEIPTS_DIR / token / "estimates" / audio_file
            if audio_path.exists():
                text = transcriber.transcribe(audio_path)
            else:
                text = f"(audio file not found: {audio_file})"
        else:
            text = ""

        database.update_estimate_transcription(estimate_id, text)

        # Refresh estimate with transcription for task extraction
        est["transcription"] = text
        est["status"] = "complete"

        # Run AI task extraction (non-blocking on failure)
        try:
            import task_extractor
            task_extractor.process_estimate_tasks(est)
        except Exception as e:
            logger.warning(f"Task extraction failed for estimate {estimate_id}: {e}")

        logger.info(f"Completed estimate {estimate_id}")

    except Exception as e:
        logger.error(f"Estimate processing failed for {estimate_id}: {e}")
        try:
            database.update_estimate_error(estimate_id, f"Error: {e}")
        except Exception:
            pass


def _poll_and_process_append():
    """Check for one estimate needing append transcription and process it."""
    est = database.claim_next_appending_estimate()
    if est is None:
        return

    estimate_id = est["id"]
    logger.info(f"Appending transcription for estimate {estimate_id}")

    try:
        audio_path_str = est.get("append_audio_file", "")
        if not audio_path_str:
            database.update_estimate(estimate_id, status="complete", append_audio_file="")
            return

        audio_path = Path(audio_path_str)
        if audio_path.exists():
            text = transcriber.transcribe(audio_path)
        else:
            text = f"(append audio file not found: {audio_path_str})"

        database.update_estimate_append_transcription(estimate_id, text)
        logger.info(f"Completed append transcription for estimate {estimate_id}")

    except Exception as e:
        logger.error(f"Append transcription failed for estimate {estimate_id}: {e}")
        try:
            database.update_estimate(estimate_id, status="complete", append_audio_file="")
        except Exception:
            pass


def start_worker():
    """Start the background worker thread (safe to call from every Gunicorn worker)."""
    global _worker_thread
    if _worker_thread is None or not _worker_thread.is_alive():
        _worker_thread = threading.Thread(target=_worker, daemon=True)
        _worker_thread.start()
        logger.info("Task queue worker started (DB-polling mode)")
