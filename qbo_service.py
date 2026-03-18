"""QuickBooks Online API service — token refresh, customer/estimate/invoice push."""

import base64
import json as _json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import requests

import config
import database
import qbo_crypto

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# QBO API base URLs
# ---------------------------------------------------------------------------

_BASE_URLS = {
    "sandbox":    "https://sandbox-quickbooks.api.intuit.com",
    "production": "https://quickbooks.api.intuit.com",
}
_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
_REVOKE_URL = "https://developer.api.intuit.com/v2/oauth2/tokens/revoke"


def _base_url():
    return _BASE_URLS.get(config.QBO_ENVIRONMENT, _BASE_URLS["sandbox"])


def _basic_auth_header():
    """Return HTTP Basic auth header for Intuit token endpoints."""
    creds = f"{config.QBO_CLIENT_ID}:{config.QBO_CLIENT_SECRET}"
    b64 = base64.b64encode(creds.encode()).decode()
    return f"Basic {b64}"


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------

def _refresh_if_needed(token_str):
    """Refresh QBO access token if expiring within 5 minutes. Returns connection dict."""
    conn = database.get_qbo_connection(token_str)
    if not conn:
        raise RuntimeError("No QBO connection for this company")

    expires_at = conn["token_expires_at"]
    if expires_at:
        try:
            exp_dt = datetime.fromisoformat(expires_at)
            if datetime.now() < exp_dt - timedelta(minutes=5):
                return conn  # Still fresh
        except ValueError:
            pass  # Parse error — refresh anyway

    # Refresh
    refresh_tok = qbo_crypto.decrypt(conn["refresh_token"])
    resp = requests.post(
        _TOKEN_URL,
        headers={
            "Authorization": _basic_auth_header(),
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_tok,
        },
        timeout=15,
    )
    if resp.status_code != 200:
        log.error("QBO token refresh failed: %s %s", resp.status_code, resp.text)
        raise RuntimeError(f"QBO token refresh failed ({resp.status_code})")

    data = resp.json()
    new_access = qbo_crypto.encrypt(data["access_token"])
    new_refresh = qbo_crypto.encrypt(data["refresh_token"])
    new_expires = (datetime.now() + timedelta(seconds=data.get("expires_in", 3600))).isoformat()

    database.update_qbo_tokens(token_str, new_access, new_refresh, new_expires)

    conn["access_token"] = new_access
    conn["refresh_token"] = new_refresh
    conn["token_expires_at"] = new_expires
    return conn


# ---------------------------------------------------------------------------
# Authenticated API call with retry on 401
# ---------------------------------------------------------------------------

def _qbo_api_call(token_str, method, endpoint, payload=None):
    """Make an authenticated QBO API call. Auto-refreshes on 401."""
    conn = _refresh_if_needed(token_str)
    realm_id = conn["realm_id"]
    access_token = qbo_crypto.decrypt(conn["access_token"])

    url = f"{_base_url()}/v3/company/{realm_id}/{endpoint}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    resp = requests.request(method, url, json=payload, headers=headers, timeout=20)

    # Retry once on 401 (token may have just expired)
    if resp.status_code == 401:
        conn = _refresh_if_needed(token_str)
        access_token = qbo_crypto.decrypt(conn["access_token"])
        headers["Authorization"] = f"Bearer {access_token}"
        resp = requests.request(method, url, json=payload, headers=headers, timeout=20)

    # Log intuit_tid for troubleshooting with Intuit support
    tid = resp.headers.get("intuit_tid", "")
    if tid:
        log.info("QBO %s %s → %s (intuit_tid: %s)", method, endpoint, resp.status_code, tid)
    if resp.status_code >= 400 and tid:
        log.error("QBO error on %s %s — intuit_tid: %s — %s", method, endpoint, tid, resp.text[:300])

    return resp


# ---------------------------------------------------------------------------
# Upload file attachment to QBO entity
# ---------------------------------------------------------------------------

def _qbo_upload_attachment(token_str, entity_type, entity_id, file_path, filename, mime_type="image/jpeg"):
    """Upload a file attachment to QBO linked to an entity (e.g. Purchase).

    Uses QBO Upload API: POST /v3/company/{realm_id}/upload with multipart/form-data.
    Returns the QBO Attachable ID string, or None on failure.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        log.warning("Attachment file not found: %s", file_path)
        return None

    conn = _refresh_if_needed(token_str)
    realm_id = conn["realm_id"]
    access_token = qbo_crypto.decrypt(conn["access_token"])

    url = f"{_base_url()}/v3/company/{realm_id}/upload"

    metadata = {
        "AttachableRef": [
            {
                "EntityRef": {
                    "type": entity_type,
                    "value": str(entity_id),
                },
                "IncludeOnSend": False,
            }
        ],
        "FileName": filename,
        "ContentType": mime_type,
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    def _do_upload():
        with open(file_path, "rb") as f:
            files = {
                "file_metadata_0": ("metadata.json", _json.dumps(metadata), "application/json"),
                "file_content_0": (filename, f, mime_type),
            }
            return requests.post(url, headers=headers, files=files, timeout=60)

    resp = _do_upload()

    # Retry once on 401 (token may have expired)
    if resp.status_code == 401:
        conn = _refresh_if_needed(token_str)
        access_token = qbo_crypto.decrypt(conn["access_token"])
        headers["Authorization"] = f"Bearer {access_token}"
        resp = _do_upload()

    tid = resp.headers.get("intuit_tid", "")
    if tid:
        log.info("QBO upload attachment → %s (intuit_tid: %s)", resp.status_code, tid)

    if resp.status_code in (200, 201):
        data = resp.json()
        attachable = data.get("AttachableResponse", [{}])[0].get("Attachable", {})
        attachable_id = attachable.get("Id")
        log.info("QBO attachment created: ID=%s for %s/%s", attachable_id, entity_type, entity_id)
        return attachable_id

    log.error("QBO attachment upload failed: %s %s", resp.status_code, resp.text[:300])
    return None


# ---------------------------------------------------------------------------
# Revoke token
# ---------------------------------------------------------------------------

def revoke_token(token_str):
    """Revoke the refresh token at Intuit."""
    conn = database.get_qbo_connection(token_str)
    if not conn:
        return
    try:
        refresh_tok = qbo_crypto.decrypt(conn["refresh_token"])
        requests.post(
            _REVOKE_URL,
            headers={
                "Authorization": _basic_auth_header(),
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={"token": refresh_tok},
            timeout=10,
        )
    except Exception:
        log.warning("QBO revoke failed (non-critical)", exc_info=True)


# ---------------------------------------------------------------------------
# Ensure generic "Services" item exists in QBO
# ---------------------------------------------------------------------------

def _ensure_default_item(token_str):
    """Create or return a generic 'Services' item in QBO for line items."""
    conn = database.get_qbo_connection(token_str)
    if conn and conn["default_item_id"]:
        return conn["default_item_id"]

    # Try to find existing "Services" item via query (1 READ)
    resp = _qbo_api_call(
        token_str, "GET",
        "query?query=SELECT * FROM Item WHERE Name = 'Services' MAXRESULTS 1",
    )
    if resp.status_code == 200:
        data = resp.json()
        items = data.get("QueryResponse", {}).get("Item", [])
        if items:
            item_id = str(items[0]["Id"])
            database.update_qbo_default_item(token_str, item_id)
            return item_id

    # Create it (free POST)
    payload = {
        "Name": "Services",
        "Type": "Service",
        "IncomeAccountRef": {"value": "1"},  # Default income account
    }
    resp = _qbo_api_call(token_str, "POST", "item", payload)
    if resp.status_code in (200, 201):
        item_id = str(resp.json()["Item"]["Id"])
        database.update_qbo_default_item(token_str, item_id)
        return item_id

    # If creation fails (e.g. account ref issue), try with a query for any Service item
    resp2 = _qbo_api_call(
        token_str, "GET",
        "query?query=SELECT * FROM Item WHERE Type = 'Service' MAXRESULTS 1",
    )
    if resp2.status_code == 200:
        items = resp2.json().get("QueryResponse", {}).get("Item", [])
        if items:
            item_id = str(items[0]["Id"])
            database.update_qbo_default_item(token_str, item_id)
            return item_id

    raise RuntimeError("Could not create or find a Service item in QuickBooks")


# ---------------------------------------------------------------------------
# Fetch QBO items into local cache
# ---------------------------------------------------------------------------

def fetch_qbo_items(token_str):
    """Pull all active items from QBO into the local qbo_items cache. Returns count."""
    database.clear_qbo_items(token_str)
    start_pos = 1
    total = 0
    while True:
        resp = _qbo_api_call(
            token_str, "GET",
            f"query?query=SELECT * FROM Item WHERE Active = true STARTPOSITION {start_pos} MAXRESULTS 1000",
        )
        if resp.status_code != 200:
            log.error("QBO item fetch failed: %s %s", resp.status_code, resp.text[:200])
            break
        items = resp.json().get("QueryResponse", {}).get("Item", [])
        if not items:
            break
        for item in items:
            database.upsert_qbo_item(
                token_str,
                qbo_id=str(item["Id"]),
                name=item.get("Name", ""),
                item_type=item.get("Type", ""),
                active=1,
            )
            total += 1
        if len(items) < 1000:
            break
        start_pos += 1000
    return total


# ---------------------------------------------------------------------------
# Ensure a local P&S item exists in QBO (auto-create if needed)
# ---------------------------------------------------------------------------

def fetch_qbo_accounts(token_str):
    """Pull Income/COGS/Expense accounts from QBO into local cache. Returns count."""
    database.clear_qbo_accounts(token_str)
    total = 0
    for acct_type in ("Income", "Cost of Goods Sold", "Expense"):
        safe_type = acct_type.replace("'", "\\'")
        start_pos = 1
        while True:
            resp = _qbo_api_call(
                token_str, "GET",
                f"query?query=SELECT * FROM Account WHERE AccountType = '{safe_type}' STARTPOSITION {start_pos} MAXRESULTS 1000",
            )
            if resp.status_code != 200:
                log.error("QBO account fetch failed for %s: %s %s", acct_type, resp.status_code, resp.text[:200])
                break
            accounts = resp.json().get("QueryResponse", {}).get("Account", [])
            if not accounts:
                break
            for acct in accounts:
                database.upsert_qbo_account(
                    token_str,
                    qbo_id=str(acct["Id"]),
                    name=acct.get("Name", ""),
                    acct_type=acct.get("AccountType", ""),
                )
                total += 1
            if len(accounts) < 1000:
                break
            start_pos += 1000
    return total


def sync_qbo_expense_categories(token_str):
    """Create categories from cached Expense + COGS accounts. Returns count of newly created."""
    accounts = (
        database.get_qbo_accounts(token_str, acct_type="Expense")
        + database.get_qbo_accounts(token_str, acct_type="Cost of Goods Sold")
    )
    existing = database.get_categories_by_token(token_str)
    existing_qbo_ids = {c.get("qbo_account_id") for c in existing if c.get("qbo_account_id")}
    existing_names = {c["name"].strip().lower() for c in existing}

    created = 0
    for acct in accounts:
        qbo_id = acct["qbo_id"]
        name = acct["name"].strip()
        if qbo_id in existing_qbo_ids:
            continue
        if name.lower() in existing_names:
            continue
        new_id = database.create_category(name, token_str, sort_order=0, account_code="")
        if new_id:
            database.update_category_qbo_account(new_id, qbo_id)
        created += 1
    return created


def _find_income_account(token_str):
    """Find an Income account in QBO to use as IncomeAccountRef for new items."""
    resp = _qbo_api_call(
        token_str, "GET",
        "query?query=SELECT * FROM Account WHERE AccountType = 'Income' MAXRESULTS 1",
    )
    if resp.status_code == 200:
        accounts = resp.json().get("QueryResponse", {}).get("Account", [])
        if accounts:
            return {"value": str(accounts[0]["Id"]), "name": accounts[0].get("Name", "")}
    return None


def ensure_item_in_qbo(token_str, ps_name, ps_type="Service", income_account_id=None):
    """Find or create a QBO item matching the local P&S name. Returns QBO item ID string.

    If income_account_id is provided, it is used as the IncomeAccountRef when creating
    a new item. Otherwise falls back to auto-discovering the first Income account.
    """
    # Query QBO for existing item with this name
    safe_name = ps_name.replace("'", "\\'")
    resp = _qbo_api_call(
        token_str, "GET",
        f"query?query=SELECT * FROM Item WHERE Name = '{safe_name}' MAXRESULTS 1",
    )
    if resp.status_code == 200:
        items = resp.json().get("QueryResponse", {}).get("Item", [])
        if items:
            return str(items[0]["Id"])

    # Determine income account ref
    if income_account_id:
        income_acct = {"value": income_account_id}
    else:
        income_acct = _find_income_account(token_str)
    if not income_acct:
        log.error("No Income account found in QBO — cannot create item '%s'", ps_name)
        return None

    # Create it — map local type to QBO type
    qbo_type = "Service" if ps_type.lower() == "service" else "NonInventory"
    payload = {
        "Name": ps_name[:100],
        "Type": qbo_type,
        "IncomeAccountRef": income_acct,
    }
    if qbo_type == "NonInventory":
        # NonInventory items also need an ExpenseAccountRef
        exp_resp = _qbo_api_call(
            token_str, "GET",
            "query?query=SELECT * FROM Account WHERE AccountType = 'Cost of Goods Sold' MAXRESULTS 1",
        )
        if exp_resp.status_code == 200:
            exp_accounts = exp_resp.json().get("QueryResponse", {}).get("Account", [])
            if exp_accounts:
                payload["ExpenseAccountRef"] = {"value": str(exp_accounts[0]["Id"]), "name": exp_accounts[0].get("Name", "")}
            else:
                # Fallback: try Expense type
                exp_resp2 = _qbo_api_call(
                    token_str, "GET",
                    "query?query=SELECT * FROM Account WHERE AccountType = 'Expense' MAXRESULTS 1",
                )
                if exp_resp2.status_code == 200:
                    exp_accounts2 = exp_resp2.json().get("QueryResponse", {}).get("Account", [])
                    if exp_accounts2:
                        payload["ExpenseAccountRef"] = {"value": str(exp_accounts2[0]["Id"]), "name": exp_accounts2[0].get("Name", "")}

    resp = _qbo_api_call(token_str, "POST", "item", payload)
    if resp.status_code in (200, 201):
        return str(resp.json()["Item"]["Id"])

    # If creation failed with duplicate, look it up
    if resp.status_code == 400 and "Duplicate" in resp.text:
        resp2 = _qbo_api_call(
            token_str, "GET",
            f"query?query=SELECT * FROM Item WHERE Name = '{safe_name}' MAXRESULTS 1",
        )
        if resp2.status_code == 200:
            items = resp2.json().get("QueryResponse", {}).get("Item", [])
            if items:
                return str(items[0]["Id"])

    log.error("Failed to create QBO item '%s': %s %s", ps_name, resp.status_code, resp.text[:200])
    return None


# ---------------------------------------------------------------------------
# Customer sync
# ---------------------------------------------------------------------------

def ensure_customer_in_qbo(token_str, customer_id):
    """Ensure a local customer exists in QBO. Returns the QBO customer ID string."""
    customer = database.get_customer(customer_id)
    if not customer:
        raise ValueError("Customer not found")

    # Already synced?
    if customer.get("qbo_customer_id"):
        return customer["qbo_customer_id"]

    display_name = customer["company_name"] or customer["customer_name"] or f"Customer {customer_id}"

    payload = {
        "DisplayName": display_name[:500],
    }
    if customer.get("customer_name"):
        parts = customer["customer_name"].strip().split(" ", 1)
        payload["GivenName"] = parts[0][:100]
        if len(parts) > 1:
            payload["FamilyName"] = parts[1][:100]
    if customer.get("phone"):
        payload["PrimaryPhone"] = {"FreeFormNumber": customer["phone"][:30]}
    if customer.get("email"):
        payload["PrimaryEmailAddr"] = {"Address": customer["email"][:100]}

    resp = _qbo_api_call(token_str, "POST", "customer", payload)

    if resp.status_code in (200, 201):
        qbo_id = str(resp.json()["Customer"]["Id"])
        database.update_customer_qbo_sync(customer_id, qbo_id)
        return qbo_id

    # Handle duplicate name — QBO returns 400 with "Duplicate Name Exists Error"
    if resp.status_code == 400 and "Duplicate" in resp.text:
        safe_name = display_name.replace("'", "\\'")
        query_resp = _qbo_api_call(
            token_str, "GET",
            f"query?query=SELECT * FROM Customer WHERE DisplayName = '{safe_name}' MAXRESULTS 1",
        )
        if query_resp.status_code == 200:
            customers = query_resp.json().get("QueryResponse", {}).get("Customer", [])
            if customers:
                qbo_id = str(customers[0]["Id"])
                database.update_customer_qbo_sync(customer_id, qbo_id)
                return qbo_id

    raise RuntimeError(f"Failed to create customer in QBO: {resp.status_code} — {resp.text[:200]}")


# ---------------------------------------------------------------------------
# Push estimate
# ---------------------------------------------------------------------------

def push_estimate_to_qbo(token_str, estimate_id):
    """Push or update an estimate in QBO. Returns the QBO estimate ID."""
    est = database.get_estimate(estimate_id)
    if not est:
        raise ValueError("Estimate not found")
    if est["token"] != token_str:
        raise ValueError("Token mismatch")

    items = database.get_estimate_items(estimate_id)
    default_item_id = _ensure_default_item(token_str)

    # Ensure customer
    qbo_customer_id = None
    if est.get("customer_id"):
        qbo_customer_id = ensure_customer_in_qbo(token_str, est["customer_id"])

    # Build QBO line items — auto-create QBO items as needed
    lines = []
    for i, item in enumerate(items):
        line_amount = round(float(item.get("total", 0) or 0), 2)
        item_ref = item.get("qbo_item_id") or ""

        # If no QBO item mapped, auto-find/create one based on item_name (or description as fallback)
        ps_lookup_name = (item.get("item_name") or item.get("description") or "").strip()
        if not item_ref and ps_lookup_name:
            item_type = item.get("item_type", "product")
            # Look up matching P&S to get assigned income account
            income_acct_id = None
            ps_list = database.get_products_services_by_token(token_str, active_only=False)
            for ps in ps_list:
                if ps["name"].strip().lower() == ps_lookup_name.lower():
                    income_acct_id = ps.get("qbo_income_account_id") or None
                    break
            qbo_id = ensure_item_in_qbo(token_str, ps_lookup_name, item_type, income_account_id=income_acct_id)
            if qbo_id:
                item_ref = qbo_id
                # Store it back so future pushes reuse this mapping
                database.update_estimate_item(item["id"], qbo_item_id=qbo_id)

        item_ref = item_ref or default_item_id
        line = {
            "LineNum": i + 1,
            "Amount": line_amount,
            "DetailType": "SalesItemLineDetail",
            "Description": item.get("description", "")[:4000],
            "SalesItemLineDetail": {
                "ItemRef": {"value": item_ref},
                "Qty": float(item.get("quantity", 1) or 1),
                "UnitPrice": round(float(item.get("unit_price", 0) or 0), 2),
            },
        }
        lines.append(line)

    if not lines:
        lines.append({
            "LineNum": 1,
            "Amount": 0,
            "DetailType": "SalesItemLineDetail",
            "Description": "No line items",
            "SalesItemLineDetail": {
                "ItemRef": {"value": default_item_id},
                "Qty": 1,
                "UnitPrice": 0,
            },
        })

    payload = {
        "Line": lines,
        "DocNumber": str(est.get("estimate_number") or est["id"])[:21],
    }
    if qbo_customer_id:
        payload["CustomerRef"] = {"value": qbo_customer_id}
    if est.get("customer_message"):
        payload["CustomerMemo"] = {"value": est["customer_message"][:1000]}
    if est.get("expected_completion"):
        payload["ExpirationDate"] = est["expected_completion"]

    # Update or create?
    existing_qbo_id = est.get("qbo_estimate_id")
    if existing_qbo_id:
        # Sparse update — need SyncToken
        payload["Id"] = existing_qbo_id
        payload["SyncToken"] = est.get("qbo_sync_token", "0")
        payload["sparse"] = True
        resp = _qbo_api_call(token_str, "POST", "estimate", payload)
        # If update fails (deleted in QBO), retry as new create
        if resp.status_code not in (200, 201):
            log.warning("QBO estimate update failed (may be deleted in QBO), retrying as new: %s", resp.status_code)
            payload.pop("Id", None)
            payload.pop("SyncToken", None)
            payload.pop("sparse", None)
            resp = _qbo_api_call(token_str, "POST", "estimate", payload)
    else:
        resp = _qbo_api_call(token_str, "POST", "estimate", payload)

    if resp.status_code in (200, 201):
        data = resp.json()["Estimate"]
        qbo_id = str(data["Id"])
        sync_token = str(data["SyncToken"])
        database.update_estimate_qbo_sync(estimate_id, qbo_id, sync_token)
        database.clear_estimate_qbo_error(estimate_id)
        return qbo_id

    error_msg = f"{resp.status_code}: {resp.text[:300]}"
    database.set_estimate_qbo_error(estimate_id, error_msg)
    raise RuntimeError(f"QBO estimate push failed — {error_msg}")


# ---------------------------------------------------------------------------
# Push invoice
# ---------------------------------------------------------------------------

def push_invoice_to_qbo(token_str, invoice_id):
    """Push or update an invoice in QBO. Returns the QBO invoice ID."""
    inv = database.get_invoice(invoice_id)
    if not inv:
        raise ValueError("Invoice not found")
    if inv["token"] != token_str:
        raise ValueError("Token mismatch")

    items = database.get_invoice_items(invoice_id)
    default_item_id = _ensure_default_item(token_str)

    # Ensure customer
    qbo_customer_id = None
    if inv.get("customer_id"):
        qbo_customer_id = ensure_customer_in_qbo(token_str, inv["customer_id"])

    # Build QBO line items — auto-create QBO items as needed
    lines = []
    for i, item in enumerate(items):
        line_amount = round(float(item.get("billed_amount", 0) or 0), 2)
        item_ref = item.get("qbo_item_id") or ""

        # If no QBO item mapped, auto-find/create one based on item_name (or description as fallback)
        ps_lookup_name = (item.get("item_name") or item.get("description") or "").strip()
        if not item_ref and ps_lookup_name:
            # Look up matching P&S to get assigned income account
            income_acct_id = None
            ps_list = database.get_products_services_by_token(token_str, active_only=False)
            for ps in ps_list:
                if ps["name"].strip().lower() == ps_lookup_name.lower():
                    income_acct_id = ps.get("qbo_income_account_id") or None
                    break
            qbo_id = ensure_item_in_qbo(token_str, ps_lookup_name, "Service", income_account_id=income_acct_id)
            if qbo_id:
                item_ref = qbo_id
                database.update_invoice_item(item["id"], qbo_item_id=qbo_id)

        item_ref = item_ref or default_item_id
        line = {
            "LineNum": i + 1,
            "Amount": line_amount,
            "DetailType": "SalesItemLineDetail",
            "Description": item.get("description", "")[:4000],
            "SalesItemLineDetail": {
                "ItemRef": {"value": item_ref},
                "Qty": float(item.get("quantity", 1) or 1),
                "UnitPrice": round(float(item.get("unit_price", 0) or 0), 2),
            },
        }
        lines.append(line)

    if not lines:
        lines.append({
            "LineNum": 1,
            "Amount": 0,
            "DetailType": "SalesItemLineDetail",
            "Description": "No line items",
            "SalesItemLineDetail": {
                "ItemRef": {"value": default_item_id},
                "Qty": 1,
                "UnitPrice": 0,
            },
        })

    payload = {
        "Line": lines,
        "DocNumber": str(inv.get("invoice_number") or inv["id"])[:21],
    }
    if qbo_customer_id:
        payload["CustomerRef"] = {"value": qbo_customer_id}
    if inv.get("due_date"):
        payload["DueDate"] = inv["due_date"]
    if inv.get("client_message"):
        payload["CustomerMemo"] = {"value": inv["client_message"][:1000]}

    # Update or create?
    existing_qbo_id = inv.get("qbo_invoice_id")
    if existing_qbo_id:
        payload["Id"] = existing_qbo_id
        payload["SyncToken"] = inv.get("qbo_sync_token", "0")
        payload["sparse"] = True
        resp = _qbo_api_call(token_str, "POST", "invoice", payload)
        # If update fails (deleted in QBO), retry as new create
        if resp.status_code not in (200, 201):
            log.warning("QBO invoice update failed (may be deleted in QBO), retrying as new: %s", resp.status_code)
            payload.pop("Id", None)
            payload.pop("SyncToken", None)
            payload.pop("sparse", None)
            resp = _qbo_api_call(token_str, "POST", "invoice", payload)
    else:
        resp = _qbo_api_call(token_str, "POST", "invoice", payload)

    if resp.status_code in (200, 201):
        data = resp.json()["Invoice"]
        qbo_id = str(data["Id"])
        sync_token = str(data["SyncToken"])
        database.update_invoice_qbo_sync(invoice_id, qbo_id, sync_token)
        database.clear_invoice_qbo_error(invoice_id)
        return qbo_id

    error_msg = f"{resp.status_code}: {resp.text[:300]}"
    database.set_invoice_qbo_error(invoice_id, error_msg)
    raise RuntimeError(f"QBO invoice push failed — {error_msg}")


# ---------------------------------------------------------------------------
# Vendor sync (for receipt expense push)
# ---------------------------------------------------------------------------

def ensure_vendor_in_qbo(token_str, vendor_name, submission_id=None):
    """Find or create a QBO Vendor by display name. Returns QBO vendor ID string."""
    if not vendor_name or not vendor_name.strip():
        return None

    display_name = vendor_name.strip()[:500]
    safe_name = display_name.replace("'", "\\'")

    # Search QBO for existing vendor
    resp = _qbo_api_call(
        token_str, "GET",
        f"query?query=SELECT * FROM Vendor WHERE DisplayName = '{safe_name}' MAXRESULTS 1",
    )
    if resp.status_code == 200:
        vendors = resp.json().get("QueryResponse", {}).get("Vendor", [])
        if vendors:
            qbo_id = str(vendors[0]["Id"])
            if submission_id:
                database.update_submission_qbo_vendor(submission_id, qbo_id)
            return qbo_id

    # Create new vendor
    payload = {"DisplayName": display_name}
    resp = _qbo_api_call(token_str, "POST", "vendor", payload)
    if resp.status_code in (200, 201):
        qbo_id = str(resp.json()["Vendor"]["Id"])
        if submission_id:
            database.update_submission_qbo_vendor(submission_id, qbo_id)
        return qbo_id

    # Handle duplicate
    if resp.status_code == 400 and "Duplicate" in resp.text:
        resp2 = _qbo_api_call(
            token_str, "GET",
            f"query?query=SELECT * FROM Vendor WHERE DisplayName = '{safe_name}' MAXRESULTS 1",
        )
        if resp2.status_code == 200:
            vendors = resp2.json().get("QueryResponse", {}).get("Vendor", [])
            if vendors:
                qbo_id = str(vendors[0]["Id"])
                if submission_id:
                    database.update_submission_qbo_vendor(submission_id, qbo_id)
                return qbo_id

    log.error("Failed to find/create QBO Vendor '%s': %s %s",
              vendor_name, resp.status_code, resp.text[:200])
    return None


# ---------------------------------------------------------------------------
# Fetch Bank / Credit Card accounts (for receipt payment account dropdown)
# ---------------------------------------------------------------------------

def fetch_qbo_bank_accounts(token_str):
    """Query QBO for Bank + Credit Card accounts. Returns list of dicts."""
    accounts = []
    for acct_type in ("Bank", "Credit Card"):
        safe_type = acct_type.replace("'", "\\'")
        resp = _qbo_api_call(
            token_str, "GET",
            f"query?query=SELECT * FROM Account WHERE AccountType = '{safe_type}' AND Active = true MAXRESULTS 100",
        )
        if resp.status_code == 200:
            for a in resp.json().get("QueryResponse", {}).get("Account", []):
                accounts.append({
                    "id": str(a["Id"]),
                    "name": a.get("Name", ""),
                    "type": acct_type,
                })
    return accounts


def find_qbo_customer_by_name(token_str, display_name):
    """Query QBO for a Customer with an exact DisplayName match.
    Returns the QBO customer ID string if found, else None.
    Does NOT create a customer if none is found.
    """
    if not display_name or not display_name.strip():
        return None
    safe_name = display_name.strip().replace("'", "\\'")
    resp = _qbo_api_call(
        token_str, "GET",
        f"query?query=SELECT * FROM Customer WHERE DisplayName = '{safe_name}' MAXRESULTS 1",
    )
    if resp.status_code == 200:
        customers = resp.json().get("QueryResponse", {}).get("Customer", [])
        if customers:
            return str(customers[0]["Id"])
    return None


# ---------------------------------------------------------------------------
# Push receipt to QBO as Purchase (expense)
# ---------------------------------------------------------------------------

def push_receipt_to_qbo(token_str, submission_id, payment_account_id,
                        payment_account_type=""):
    """Push a receipt submission to QBO as a Purchase (expense). Returns QBO Purchase ID."""
    sub = database.get_submission(submission_id)
    if not sub:
        raise ValueError("Submission not found")
    if sub["token"] != token_str:
        raise ValueError("Token mismatch")

    # Validate payment amount
    payment_amount = float(sub.get("payment_amount", 0) or 0)
    if payment_amount <= 0:
        raise ValueError("Payment amount is required before pushing to QuickBooks.")

    categories = database.get_submission_categories(submission_id)
    category_sum = round(sum(float(c.get("amount", 0) or 0) for c in categories), 2)
    if abs(payment_amount - category_sum) > 0.01:
        raise ValueError(
            f"Payment amount (${payment_amount:.2f}) does not match "
            f"category total (${category_sum:.2f}). Please correct before syncing."
        )

    if not payment_account_id:
        raise ValueError("Please select a payment account (Bank or Credit Card).")

    # Find or create QBO vendor
    qbo_vendor_id = sub.get("qbo_vendor_id") or None
    if not qbo_vendor_id and sub.get("vendor"):
        qbo_vendor_id = ensure_vendor_in_qbo(token_str, sub["vendor"], submission_id)

    # Pre-fetch all category details and fallback expense account (avoid N+1)
    cat_ids = [c["category_id"] for c in categories]
    cat_lookup = {}
    for cid in cat_ids:
        cat_lookup[cid] = database.get_category(cid)
    fallback_expense_accts = database.get_qbo_accounts(token_str, acct_type="Expense")
    fallback_ref = {"value": fallback_expense_accts[0]["qbo_id"]} if fallback_expense_accts else None

    # Build line items from submission_categories
    lines = []
    for i, cat_row in enumerate(categories):
        line_amount = round(float(cat_row.get("amount", 0) or 0), 2)

        full_cat = cat_lookup.get(cat_row["category_id"])
        account_ref = None
        if full_cat and full_cat.get("qbo_account_id"):
            account_ref = {"value": full_cat["qbo_account_id"]}
        elif fallback_ref:
            account_ref = fallback_ref

        if not account_ref:
            raise ValueError(
                f"Category '{cat_row.get('category_name', '')}' has no QBO expense account mapped. "
                "Map categories to QBO accounts on the Categories page, then sync QBO items & accounts."
            )

        line = {
            "LineNum": i + 1,
            "Amount": line_amount,
            "DetailType": "AccountBasedExpenseLineDetail",
            "Description": cat_row.get("category_name", "")[:4000],
            "AccountBasedExpenseLineDetail": {
                "AccountRef": account_ref,
            },
        }
        lines.append(line)

    if not lines:
        raise ValueError("Receipt has no category line items to push.")

    # Determine payment type from the selected account
    if payment_account_type == "Credit Card":
        payment_type = "CreditCard"
    elif payment_account_type:
        payment_type = "Cash"
    else:
        # Fallback: query QBO if type not passed by caller
        payment_type = "Cash"
        for ba in fetch_qbo_bank_accounts(token_str):
            if ba["id"] == payment_account_id:
                payment_type = "CreditCard" if ba["type"] == "Credit Card" else "Cash"
                break

    payload = {
        "PaymentType": payment_type,
        "AccountRef": {"value": payment_account_id},
        "Line": lines,
    }

    # Add vendor reference
    if qbo_vendor_id:
        payload["EntityRef"] = {"value": qbo_vendor_id, "type": "Vendor"}

    # Transaction date: prefer receipt_date, fall back to submission timestamp
    receipt_date = sub.get("receipt_date") or ""
    if receipt_date:
        payload["TxnDate"] = receipt_date[:10]
    elif sub.get("timestamp"):
        try:
            payload["TxnDate"] = sub["timestamp"][:10]
        except Exception:
            pass

    # Fetch job once for CustomerRef + PrivateNote
    job = None
    if sub.get("job_id"):
        job = database.get_job(sub["job_id"])

    # Map job's customer to QBO CustomerRef (for job costing)
    qbo_customer_id = None
    if job and job.get("customer_id"):
        # Path A: Job has a local customer — sync that customer to QBO
        try:
            qbo_customer_id = ensure_customer_in_qbo(token_str, job["customer_id"])
        except Exception:
            log.warning("Could not sync customer for receipt %s", submission_id, exc_info=True)
    elif job and not job.get("customer_id"):
        # Path B: Job has no local customer — try to match job name to QBO customer
        if job.get("qbo_customer_id"):
            qbo_customer_id = job["qbo_customer_id"]
        else:
            try:
                matched_id = find_qbo_customer_by_name(token_str, job.get("job_name", ""))
                if matched_id:
                    qbo_customer_id = matched_id
                    database.update_job_qbo_customer(job["id"], matched_id)
                    log.info("Matched job '%s' (id=%s) to QBO customer %s by name",
                             job.get("job_name"), job["id"], matched_id)
                else:
                    log.debug("No QBO customer found matching job name '%s'",
                              job.get("job_name", ""))
            except Exception:
                log.warning("QBO customer name lookup failed for job '%s'",
                            job.get("job_name", ""), exc_info=True)
    if qbo_customer_id:
        payload["CustomerRef"] = {"value": qbo_customer_id}

    # Build PrivateNote: job name + transcription
    memo_parts = []
    if job:
        memo_parts.append(f"Job: {job.get('job_name', '')}")
    if sub.get("transcription"):
        memo_parts.append(sub["transcription"])
    if memo_parts:
        payload["PrivateNote"] = "\n".join(memo_parts)[:4000]

    # Save the payment account choice
    database.update_submission_qbo_payment_account(submission_id, payment_account_id)

    # Update or create?
    existing_qbo_id = sub.get("qbo_purchase_id")
    if existing_qbo_id:
        payload["Id"] = existing_qbo_id
        payload["SyncToken"] = sub.get("qbo_sync_token", "0")
        payload["sparse"] = True
        resp = _qbo_api_call(token_str, "POST", "purchase", payload)
        if resp.status_code not in (200, 201):
            log.warning("QBO purchase update failed, retrying as new: %s", resp.status_code)
            payload.pop("Id", None)
            payload.pop("SyncToken", None)
            payload.pop("sparse", None)
            resp = _qbo_api_call(token_str, "POST", "purchase", payload)
    else:
        resp = _qbo_api_call(token_str, "POST", "purchase", payload)

    if resp.status_code in (200, 201):
        data = resp.json()["Purchase"]
        qbo_id = str(data["Id"])
        sync_token = str(data["SyncToken"])
        database.update_submission_qbo_sync(submission_id, qbo_id, sync_token)
        database.clear_submission_qbo_error(submission_id)

        # Upload receipt image as attachment (non-blocking — failure does not roll back)
        if sub.get("image_file"):
            try:
                image_path = config.RECEIPTS_DIR / sub["token"] / sub["month_folder"] / sub["image_file"]
                ext = sub["image_file"].rsplit(".", 1)[-1].lower() if "." in sub["image_file"] else "jpeg"
                mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
                mime_type = mime_map.get(ext, "image/jpeg")
                _qbo_upload_attachment(
                    token_str,
                    entity_type="Purchase",
                    entity_id=qbo_id,
                    file_path=image_path,
                    filename=sub["image_file"],
                    mime_type=mime_type,
                )
            except Exception:
                log.warning("Failed to upload receipt image to QBO for submission %s",
                            submission_id, exc_info=True)

        return qbo_id

    error_msg = f"{resp.status_code}: {resp.text[:300]}"
    database.set_submission_qbo_error(submission_id, error_msg)
    raise RuntimeError(f"QBO expense push failed — {error_msg}")
