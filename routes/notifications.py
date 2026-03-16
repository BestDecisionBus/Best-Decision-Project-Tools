"""Push notification infrastructure — subscriptions, bell API, and notify helpers.

notify_admins() and notify_employee() are imported by other blueprints/task_queue.
They are feature-gated (tokens.feature_push_notify), window-gated (notify_window_*),
and employee-pref-gated where applicable.
"""

import json
import logging
from datetime import datetime

from flask import Blueprint, jsonify, request, session
from flask_login import current_user

import config
import database

logger = logging.getLogger(__name__)

notifications_bp = Blueprint("notifications", __name__)


# ---------------------------------------------------------------------------
# Window check
# ---------------------------------------------------------------------------

def _within_notify_window(token_data, category="general"):
    """Return True if the current server time is within the push window for category."""
    try:
        now_t = datetime.now().time()
        if category in ("shift_reminder", "clock_out"):
            start_str = token_data.get("notify_window_start", "06:00")
            end_str = token_data.get("notify_clockout_end", "23:59")
        elif category in ("chat_message",):
            start_str = token_data.get("notify_chat_start", "06:00")
            end_str = token_data.get("notify_chat_end", "21:00")
        else:
            start_str = token_data.get("notify_window_start", "06:00")
            end_str = token_data.get("notify_window_end", "21:00")
        start_h, start_m = map(int, start_str.split(":"))
        end_h, end_m = map(int, end_str.split(":"))
        from datetime import time as dtime
        start = dtime(start_h, start_m)
        end = dtime(end_h, end_m)
        return start <= now_t <= end
    except Exception:
        return True  # fail open


# ---------------------------------------------------------------------------
# Push send helper
# ---------------------------------------------------------------------------

def send_push_notification(sub, title, body, url="/", category="info"):
    """Send a Web Push message to one subscription. Returns (success, error_str)."""
    if not config.VAPID_PRIVATE_KEY or not config.VAPID_PUBLIC_KEY:
        return False, "VAPID keys not configured"
    try:
        from pywebpush import webpush, WebPushException
        data = json.dumps({"title": title, "body": body, "url": url, "category": category})
        webpush(
            subscription_info={
                "endpoint": sub["endpoint"],
                "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
            },
            data=data,
            vapid_private_key=config.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": f"mailto:{config.VAPID_CLAIMS_EMAIL}"},
        )
        return True, ""
    except Exception as exc:
        # Check if it's a WebPushException with an expired/gone response
        try:
            from pywebpush import WebPushException
            if isinstance(exc, WebPushException):
                if exc.response is not None and exc.response.status_code in (404, 410):
                    return False, "expired"
        except ImportError:
            pass
        logger.warning(f"Push send failed for endpoint {sub.get('endpoint','')[:40]}: {exc}")
        return False, str(exc)


# ---------------------------------------------------------------------------
# Notify helpers (imported by routes and task_queue)
# ---------------------------------------------------------------------------

def notify_admins(token_str, category, title, body, url=""):
    """Create an all_admins notification and send push to subscribed admin browsers."""
    try:
        token_data = database.get_token(token_str)
        if not token_data or not token_data.get("feature_push_notify", 0):
            return
        database.create_notification(token_str, "all_admins", None, category, title, body, url)
        if not _within_notify_window(token_data, category):
            return
        subs = database.get_all_admin_push_subscriptions(token_str)
        for sub in subs:
            success, error = send_push_notification(sub, title, body, url, category)
            if error == "expired":
                database.delete_push_subscription_by_endpoint(sub["endpoint"])
    except Exception as e:
        logger.error(f"notify_admins error for token {token_str}: {e}")


def notify_employee(token_str, employee_id, category, title, body, url=""):
    """Create an employee notification and send push, respecting their preferences."""
    try:
        token_data = database.get_token(token_str)
        if not token_data or not token_data.get("feature_push_notify", 0):
            return
        # Check employee pref for this category
        prefs = database.get_employee_notification_prefs(employee_id, token_str)
        if not prefs.get("push_enabled", 1):
            return
        cat_map = {
            "job_update": "cat_job_updates",
            "photo": "cat_job_updates",
            "task": "cat_job_updates",
            "shift_reminder": "cat_shift_remind",
            "schedule": "cat_schedule",
            "chat_message": "cat_chat",
        }
        pref_key = cat_map.get(category)
        if pref_key and not prefs.get(pref_key, 1):
            return
        database.create_notification(token_str, "employee", employee_id, category, title, body, url)
        if not _within_notify_window(token_data, category):
            return
        subs = database.get_push_subscriptions_for_recipients(token_str, "employee", [employee_id])
        for sub in subs:
            success, error = send_push_notification(sub, title, body, url, category)
            if error == "expired":
                database.delete_push_subscription_by_endpoint(sub["endpoint"])
    except Exception as e:
        logger.error(f"notify_employee error for token {token_str}, employee {employee_id}: {e}")


def notify_clocked_in_employees(token_str, job_id, category, title, body, url=""):
    """Notify all employees currently clocked into a given job."""
    try:
        token_data = database.get_token(token_str)
        if not token_data or not token_data.get("feature_push_notify", 0):
            return
        employees = database.get_clocked_in_employees_for_job(token_str, job_id)
        for emp in employees:
            notify_employee(token_str, emp["employee_id"], category, title, body, url)
    except Exception as e:
        logger.error(f"notify_clocked_in_employees error for job {job_id}: {e}")


# ---------------------------------------------------------------------------
# VAPID public key endpoint
# ---------------------------------------------------------------------------

@notifications_bp.route("/api/push/vapid-public-key")
def vapid_public_key():
    return jsonify({"publicKey": config.VAPID_PUBLIC_KEY})


# ---------------------------------------------------------------------------
# Subscribe / Unsubscribe
# ---------------------------------------------------------------------------

@notifications_bp.route("/api/push/subscribe", methods=["POST"])
def push_subscribe():
    data = request.get_json() or {}
    sub = data.get("subscription", {})
    endpoint = sub.get("endpoint", "")
    keys = sub.get("keys", {})
    p256dh = keys.get("p256dh", "")
    auth = keys.get("auth", "")
    recipient_type = data.get("recipient_type", "")
    recipient_id = data.get("recipient_id")
    token_str = data.get("token", "")

    if not endpoint or not p256dh or not auth:
        return jsonify({"error": "Invalid subscription"}), 400
    if not endpoint.startswith("https://"):
        return jsonify({"error": "Endpoint must be HTTPS"}), 400
    if recipient_type not in ("employee", "admin"):
        return jsonify({"error": "Invalid recipient_type"}), 400

    # Validate session matches the claimed identity
    if recipient_type == "employee":
        if session.get("employee_id") != recipient_id:
            return jsonify({"error": "Unauthorized"}), 403
        if session.get("employee_token", "") != token_str:
            return jsonify({"error": "Token mismatch"}), 403
    else:
        if not current_user.is_authenticated:
            return jsonify({"error": "Not logged in"}), 401
        recipient_id = current_user.id

    user_agent = request.headers.get("User-Agent", "")[:255]
    database.upsert_push_subscription(
        token_str, recipient_type, recipient_id, endpoint, p256dh, auth, user_agent
    )
    return jsonify({"success": True})


@notifications_bp.route("/api/push/unsubscribe", methods=["POST"])
def push_unsubscribe():
    data = request.get_json() or {}
    endpoint = data.get("endpoint", "")
    if not endpoint:
        return jsonify({"error": "Missing endpoint"}), 400
    # Require authentication — must be logged-in admin or employee with session
    if not current_user.is_authenticated and not session.get("employee_id"):
        return jsonify({"error": "Not authenticated"}), 401
    database.delete_push_subscription_by_endpoint(endpoint)
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# Notification bell API
# ---------------------------------------------------------------------------

@notifications_bp.route("/api/notifications/unread")
def notifications_unread():
    recipient_type = request.args.get("recipient_type", "")
    token_str = request.args.get("token", "")

    if recipient_type == "employee":
        employee_id = session.get("employee_id")
        if not employee_id:
            return jsonify({"error": "Not logged in"}), 401
        if session.get("employee_token", "") != token_str:
            return jsonify({"error": "Token mismatch"}), 403
        notifs = database.get_unread_notifications(token_str, "employee", employee_id)
    elif recipient_type == "admin":
        if not current_user.is_authenticated:
            return jsonify({"error": "Not logged in"}), 401
        notifs = database.get_unread_notifications(token_str, "admin", current_user.id)
    else:
        return jsonify({"error": "Invalid recipient_type"}), 400

    return jsonify({"unread": len(notifs), "notifications": notifs})


@notifications_bp.route("/api/notifications/mark-read", methods=["POST"])
def notifications_mark_read():
    data = request.get_json() or {}
    recipient_type = data.get("recipient_type", "")
    token_str = data.get("token", "")
    notification_ids = data.get("ids")  # None means mark all

    if recipient_type == "employee":
        employee_id = session.get("employee_id")
        if not employee_id:
            return jsonify({"error": "Not logged in"}), 401
        database.mark_notifications_read(token_str, "employee", employee_id, notification_ids)
    elif recipient_type == "admin":
        if not current_user.is_authenticated:
            return jsonify({"error": "Not logged in"}), 401
        database.mark_notifications_read(token_str, "admin", current_user.id, notification_ids)
    else:
        return jsonify({"error": "Invalid recipient_type"}), 400

    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# Employee notification preferences
# ---------------------------------------------------------------------------

@notifications_bp.route("/api/notifications/prefs", methods=["GET", "POST"])
def notification_prefs():
    employee_id = session.get("employee_id")
    token_str = session.get("employee_token", "")
    if not employee_id:
        return jsonify({"error": "Not logged in"}), 401

    if request.method == "GET":
        prefs = database.get_employee_notification_prefs(employee_id, token_str)
        return jsonify(prefs)

    data = request.get_json() or {}
    allowed = {"push_enabled", "cat_job_updates", "cat_shift_remind", "cat_schedule", "cat_chat"}
    updates = {k: int(bool(v)) for k, v in data.items() if k in allowed}
    database.update_employee_notification_prefs(employee_id, token_str, **updates)
    return jsonify({"success": True})
