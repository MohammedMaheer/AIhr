"""Tenant-specific administrator consent, separate from recruiter account linking."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from urllib.parse import urlencode, urlsplit
from uuid import UUID

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse


COOKIE_NAME = "__Host-ms_admin_consent"
STATE_PREFIX = "ms-admin-"
MAX_AGE = 600
SCOPES = (
    "offline_access",
    "https://graph.microsoft.com/User.Read",
    "https://graph.microsoft.com/Mail.Read",
    "https://graph.microsoft.com/Mail.Send",
    "https://graph.microsoft.com/Calendars.ReadWrite",
)


def _secret() -> bytes:
    secret = os.environ.get("SECRET_KEY", "")
    if len(secret) < 32:
        raise HTTPException(status_code=503, detail="Administrator consent state signing is not configured.")
    return hmac.new(secret.encode(), b"smarthr-ms-admin-consent-v1", hashlib.sha256).digest()


def _config_identity(cfg: dict) -> tuple[str, str, str]:
    try:
        tenant = str(UUID(cfg.get("tenant_id", "")))
        client = str(UUID(cfg.get("client_id", "")))
        redirect = cfg["redirect_uri"]
        parsed = urlsplit(redirect)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.fragment:
            raise ValueError("Invalid callback")
    except (ValueError, TypeError, KeyError, AttributeError):
        raise HTTPException(status_code=503, detail="Tenant-specific Microsoft consent is not configured.")
    return tenant, client, redirect


def start_consent(cfg: dict) -> RedirectResponse:
    tenant, client, redirect = _config_identity(cfg)
    state = STATE_PREFIX + secrets.token_urlsafe(32)
    payload = {"state": state, "expires": int(time.time()) + MAX_AGE,
               "tenant": tenant, "client": client, "redirect": redirect}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    signature = hmac.new(_secret(), encoded.encode(), hashlib.sha256).hexdigest()
    response = RedirectResponse(
        "https://login.microsoftonline.com/" + tenant + "/v2.0/adminconsent?" + urlencode({
            "client_id": client, "redirect_uri": redirect,
            "scope": " ".join(SCOPES), "state": state,
        }), status_code=302,
    )
    response.set_cookie(COOKIE_NAME, encoded + "." + signature, max_age=MAX_AGE,
                        secure=True, httponly=True, samesite="lax", path="/")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def finish_consent(request: Request, cfg: dict) -> HTMLResponse:
    tenant, client, redirect = _config_identity(cfg)
    cookie = request.cookies.get(COOKIE_NAME, "")
    valid = False
    if cookie and len(cookie) <= 2048:
        try:
            encoded, signature = cookie.rsplit(".", 1)
            expected = hmac.new(_secret(), encoded.encode(), hashlib.sha256).hexdigest()
            if hmac.compare_digest(signature, expected):
                data = json.loads(base64.urlsafe_b64decode(encoded))
                now = int(time.time())
                expiry = data.get("expires")
                valid = (
                    isinstance(expiry, int) and now < expiry <= now + MAX_AGE
                    and data.get("tenant") == tenant and data.get("client") == client
                    and data.get("redirect") == redirect
                    and isinstance(data.get("state"), str)
                    and hmac.compare_digest(data["state"], request.query_params.get("state", ""))
                )
        except (ValueError, TypeError, KeyError, UnicodeError):
            valid = False
    error = request.query_params.get("error")
    approved_response = (
        valid and not error
        and request.query_params.get("admin_consent", "").lower() == "true"
        and request.query_params.get("tenant", "").lower() == tenant
    )
    if not valid:
        title = "Approval session expired or invalid"
        message = "Return to the review page and start again in this browser. No account connection was created."
        status = 400
    elif error:
        title = "Permission approval was not completed"
        message = "Microsoft returned an error or the request was declined. Your Microsoft 365 administrator can review the app in Entra."
        status = 200
    elif approved_response:
        title = "Microsoft returned an approval response"
        message = "Confirm the final permission grant in Microsoft Entra. Administrator consent does not connect a recruiter mailbox or certify that the integration is ready."
        status = 200
    else:
        title = "Approval could not be confirmed"
        message = "The response did not match this organization's request. Check the permission grant in Microsoft Entra before continuing."
        status = 400
    # This receipt never authenticates a user, saves tokens, or activates mail access.
    response = HTMLResponse(f'''<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SmartHR Microsoft Approval</title><style>
body{{margin:0;font:16px/1.6 Arial,sans-serif;color:#20252b;background:#f5f6f8}}
header{{background:#171c25;padding:22px max(24px,calc((100% - 760px)/2))}}
header img{{width:180px;height:auto}}main{{max-width:760px;margin:44px auto;padding:0 24px}}
h1{{font-size:25px;line-height:1.3}}a{{color:#145c98}}p{{max-width:680px}}
</style></head><body><header><img src="/static/review/efforts-solutions-logo.png" alt="Efforts Solutions"></header>
<main><h1>{title}</h1><p>{message}</p><p><a href="/microsoft-approval">Return to the permission review</a></p></main></body></html>''', status_code=status)
    response.delete_cookie(COOKIE_NAME, path="/", secure=True, httponly=True, samesite="lax")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; "
        "base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
    )
    return response
