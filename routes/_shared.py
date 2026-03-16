"""Shared helpers for route blueprints — avoids circular imports via lazy loading."""

from flask import flash, redirect, request, session, url_for
from flask_login import current_user
import database


def helpers():
    """Lazy import of app module to avoid circular imports."""
    import app as _app
    return _app


def gate_employee_feature(feature_key):
    """Feature gate for employee-facing before_request hooks.
    Returns a redirect Response if the feature is disabled, or None to continue.
    """
    token_str = request.args.get("token", "") or session.get("employee_token", "")
    if not token_str:
        return None
    token_data = database.get_token(token_str)
    if token_data and not token_data.get(feature_key, 1):
        return redirect(url_for("company_home", token_str=token_str))
    return None


def gate_admin_feature(feature_key, feature_label):
    """Feature gate for admin before_request hooks.
    Returns a redirect Response if the feature is disabled, or None to continue.
    """
    if not current_user.is_authenticated:
        return None
    h = helpers()
    tokens = h._get_tokens_for_user()
    token_str, selected_token = h._get_selected_token(tokens)
    if not token_str or not selected_token:
        return None
    if not selected_token.get(feature_key, 1):
        flash(f"{feature_label} is not enabled for this company.", "error")
        return redirect(url_for("admin.admin_dashboard"))
    return None


def safe_latin1(text):
    """Replace non-latin-1 chars for PDF generation (FPDF Helvetica)."""
    return str(text).encode("latin-1", "replace").decode("latin-1")
