"""QuickBooks Online OAuth2 + push routes."""

import base64
import secrets
from datetime import datetime, timedelta

import requests
from flask import Blueprint, abort, flash, redirect, request, session, url_for
from flask_login import current_user, login_required

import config
import database
import qbo_crypto
import qbo_service

qbo_bp = Blueprint("qbo", __name__)


from routes._shared import helpers as _helpers


def _require_admin_with_token():
    """Common guard: logged-in admin with a selected token. Returns token_str."""
    h = _helpers()
    if not current_user.is_admin:
        abort(403)
    tokens = h._get_tokens_for_user()
    token_str, _ = h._get_selected_token(tokens)
    if not token_str:
        abort(404)
    h._verify_token_access(token_str)
    return token_str


# ---------------------------------------------------------------------------
# OAuth2 Connect
# ---------------------------------------------------------------------------

_AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"


@qbo_bp.route("/admin/qbo/connect")
@login_required
def qbo_connect():
    token_str = _require_admin_with_token()

    if not config.QBO_CLIENT_ID or not config.QBO_REDIRECT_URI:
        flash("QuickBooks integration is not configured. Set QBO_CLIENT_ID and QBO_REDIRECT_URI in .env.", "error")
        return redirect(url_for("admin.admin_settings", token=token_str))

    nonce = secrets.token_urlsafe(32)
    state = f"{token_str}:{nonce}"
    session["qbo_oauth_state"] = nonce

    params = {
        "client_id": config.QBO_CLIENT_ID,
        "response_type": "code",
        "scope": "com.intuit.quickbooks.accounting",
        "redirect_uri": config.QBO_REDIRECT_URI,
        "state": state,
    }
    qs = "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in params.items())
    return redirect(f"{_AUTH_URL}?{qs}")


# ---------------------------------------------------------------------------
# OAuth2 Callback
# ---------------------------------------------------------------------------

@qbo_bp.route("/admin/qbo/callback")
@login_required
def qbo_callback():
    h = _helpers()
    if not current_user.is_admin:
        abort(403)

    error = request.args.get("error")
    if error:
        flash(f"QuickBooks authorization was declined: {error}", "error")
        return redirect(url_for("admin.admin_settings"))

    code = request.args.get("code", "")
    realm_id = request.args.get("realmId", "")
    state = request.args.get("state", "")

    # Validate state nonce
    if ":" not in state:
        flash("Invalid OAuth state.", "error")
        return redirect(url_for("admin.admin_settings"))

    token_str, nonce = state.split(":", 1)
    stored_nonce = session.pop("qbo_oauth_state", None)
    if not stored_nonce or nonce != stored_nonce:
        flash("OAuth state mismatch — please try connecting again.", "error")
        return redirect(url_for("admin.admin_settings", token=token_str))

    h._verify_token_access(token_str)

    # Exchange code for tokens
    creds = f"{config.QBO_CLIENT_ID}:{config.QBO_CLIENT_SECRET}"
    b64_creds = base64.b64encode(creds.encode()).decode()

    resp = requests.post(
        _TOKEN_URL,
        headers={
            "Authorization": f"Basic {b64_creds}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.QBO_REDIRECT_URI,
        },
        timeout=15,
    )

    if resp.status_code != 200:
        flash(f"Failed to connect to QuickBooks (token exchange error {resp.status_code}).", "error")
        return redirect(url_for("admin.admin_settings", token=token_str))

    data = resp.json()
    access_token_enc = qbo_crypto.encrypt(data["access_token"])
    refresh_token_enc = qbo_crypto.encrypt(data["refresh_token"])
    expires_at = (datetime.now() + timedelta(seconds=data.get("expires_in", 3600))).isoformat()

    # Try to fetch QBO company name
    company_name_qbo = ""
    try:
        base = "https://sandbox-quickbooks.api.intuit.com" if config.QBO_ENVIRONMENT == "sandbox" \
            else "https://quickbooks.api.intuit.com"
        info_resp = requests.get(
            f"{base}/v3/company/{realm_id}/companyinfo/{realm_id}",
            headers={
                "Authorization": f"Bearer {data['access_token']}",
                "Accept": "application/json",
            },
            timeout=10,
        )
        if info_resp.status_code == 200:
            company_name_qbo = info_resp.json().get("CompanyInfo", {}).get("CompanyName", "")
    except Exception:
        pass

    database.save_qbo_connection(
        token_str, realm_id, access_token_enc, refresh_token_enc,
        expires_at, company_name_qbo,
    )

    display = company_name_qbo or "QuickBooks"
    flash(f"Connected to {display} successfully!", "success")
    return redirect(url_for("admin.admin_settings", token=token_str))


# ---------------------------------------------------------------------------
# Disconnect
# ---------------------------------------------------------------------------

@qbo_bp.route("/admin/qbo/disconnect", methods=["POST"])
@login_required
def qbo_disconnect():
    token_str = _require_admin_with_token()

    qbo_service.revoke_token(token_str)
    database.delete_qbo_connection(token_str)

    flash("Disconnected from QuickBooks.", "success")
    return redirect(url_for("admin.admin_settings", token=token_str))


# ---------------------------------------------------------------------------
# Push estimate
# ---------------------------------------------------------------------------

@qbo_bp.route("/admin/qbo/push-estimate/<int:estimate_id>", methods=["POST"])
@login_required
def qbo_push_estimate(estimate_id):
    h = _helpers()
    if not current_user.is_admin:
        abort(403)

    est = database.get_estimate(estimate_id)
    if not est:
        abort(404)
    h._verify_token_access(est["token"])

    conn = database.get_qbo_connection(est["token"])
    if not conn:
        flash("QuickBooks is not connected for this company.", "error")
        return redirect(url_for("estimates.admin_estimate_detail", estimate_id=estimate_id))

    try:
        qbo_id = qbo_service.push_estimate_to_qbo(est["token"], estimate_id)
        action = "Updated" if est.get("qbo_estimate_id") else "Sent"
        flash(f"{action} estimate in QuickBooks (QBO ID: {qbo_id}).", "success")
    except Exception as e:
        flash(f"QuickBooks sync failed: {e}", "error")

    return redirect(url_for("estimates.admin_estimate_detail", estimate_id=estimate_id))


# ---------------------------------------------------------------------------
# Push invoice
# ---------------------------------------------------------------------------

@qbo_bp.route("/admin/qbo/push-invoice/<int:invoice_id>", methods=["POST"])
@login_required
def qbo_push_invoice(invoice_id):
    h = _helpers()
    if not current_user.is_admin:
        abort(403)

    inv = database.get_invoice(invoice_id)
    if not inv:
        abort(404)
    h._verify_token_access(inv["token"])

    conn = database.get_qbo_connection(inv["token"])
    if not conn:
        flash("QuickBooks is not connected for this company.", "error")
        return redirect(url_for("invoices.admin_invoice_detail", invoice_id=invoice_id))

    try:
        qbo_id = qbo_service.push_invoice_to_qbo(inv["token"], invoice_id)
        action = "Updated" if inv.get("qbo_invoice_id") else "Sent"
        flash(f"{action} invoice in QuickBooks (QBO ID: {qbo_id}).", "success")
    except Exception as e:
        flash(f"QuickBooks sync failed: {e}", "error")

    return redirect(url_for("invoices.admin_invoice_detail", invoice_id=invoice_id))
