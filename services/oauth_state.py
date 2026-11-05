"""Signed, expiring recruiter OAuth state bound to the current login session."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from fastapi import HTTPException


MAX_AGE = 600


def cookie_name(provider: str) -> str:
    if provider not in ("google", "microsoft"):
        raise ValueError("Unknown OAuth provider.")
    return "__Host-oauth-" + provider


def _key() -> bytes:
    secret = os.getenv("SECRET_KEY", "")
    if len(secret) < 32:
        raise HTTPException(status_code=503, detail="OAuth state signing is not configured.")
    return hmac.new(secret.encode(), b"smarthr-recruiter-oauth-v1", hashlib.sha256).digest()


def _session_digest(session: str) -> str:
    if not session:
        raise HTTPException(status_code=401, detail="Sign in before connecting an account.")
    return hmac.new(_key(), session.encode(), hashlib.sha256).hexdigest()


def issue(provider: str, user_id: int, session: str, cfg: dict) -> tuple[str, str, str]:
    cookie_name(provider)
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    payload = {"provider": provider, "user_id": user_id, "state": state,
               "session": _session_digest(session), "expires": int(time.time()) + MAX_AGE,
               "client": cfg.get("client_id"), "redirect": cfg.get("redirect_uri"),
               "verifier": verifier}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    signature = hmac.new(_key(), encoded.encode(), hashlib.sha256).hexdigest()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return state, encoded + "." + signature, challenge


def validate(cookie: str, state: str, provider: str, user_id: int, session: str, cfg: dict) -> str:
    cookie_name(provider)
    if not cookie or len(cookie) > 4096 or not state:
        raise HTTPException(status_code=400, detail="Missing OAuth state; reconnect the account.")
    try:
        encoded, signature = cookie.rsplit(".", 1)
        expected = hmac.new(_key(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid signature")
        payload = json.loads(base64.urlsafe_b64decode(encoded))
        now = int(time.time())
        expiry = payload.get("expires")
        if not (type(expiry) is int and now < expiry <= now + MAX_AGE
                and payload.get("provider") == provider and payload.get("user_id") == user_id
                and hmac.compare_digest(payload.get("session", ""), _session_digest(session))
                and hmac.compare_digest(payload.get("state", ""), state)
                and payload.get("client") == cfg.get("client_id")
                and payload.get("redirect") == cfg.get("redirect_uri")
                and isinstance(payload.get("verifier"), str) and 43 <= len(payload["verifier"]) <= 128):
            raise ValueError("OAuth state mismatch")
        return payload["verifier"]
    except (ValueError, TypeError, KeyError, UnicodeError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state; reconnect the account.")


def callback_response(provider: str, status: str):
    from fastapi.responses import RedirectResponse
    name = cookie_name(provider)
    if status not in ('connected', 'failed', 'session_expired'):
        raise ValueError('Invalid callback outcome')
    path = '/login' if status == 'session_expired' else '/'
    response = RedirectResponse(path + '?integration=' + provider + '&status=' + status, status_code=302)
    response.delete_cookie(name, path='/', secure=True, httponly=True, samesite='lax')
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response
