"""
calendar_service.py
====================

Create Microsoft Teams or Google Meet calendar events for interview
scheduling, returning a join URL the app can store and email to the
candidate.

The whole module is dependency-light — uses `requests` and stdlib only.
SDKs (msgraph-sdk, google-api-python-client) are NOT required.

How auth works
--------------
- **Microsoft Teams (Graph API):** Either
    (a) per-recruiter delegated OAuth (token stored in `oauth_tokens` table
        with provider='microsoft'), OR
    (b) tenant-wide app-only client_credentials (config.calendar.microsoft.{
        tenant_id, client_id, client_secret, sender_user_id }).
- **Google Meet (Calendar API):** Per-recruiter delegated OAuth only —
  service-account creating events on behalf of a workspace user requires
  domain-wide delegation, which we don't assume. Token in `oauth_tokens`
  with provider='google'.

If neither is configured the service still works — it just returns a
"missing credentials" error and the interview is saved without a link.

Public surface
--------------
- `create_meeting(provider, *, subject, start_iso, duration_minutes,
                  attendee_email, organizer_user_id, db) -> dict`
    Returns: {"success": bool, "provider": str, "join_url": str|None,
              "event_id": str|None, "error": str|None}
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import requests

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------
def _load_calendar_config() -> dict:
    """Read config.json calendar section, with env-var overrides."""
    cfg: dict = {}
    try:
        with open("config.json", "r") as f:
            cfg = (json.load(f) or {}).get("calendar", {}) or {}
    except Exception:
        cfg = {}

    # Env-var overrides (preferred in production).
    # Treat empty strings as "not set" so they don't blank out config.json values.
    def _env(name: str, fallback):
        v = os.getenv(name)
        return v if (v is not None and v != "") else fallback

    ms = cfg.setdefault("microsoft", {})
    ms["tenant_id"]      = _env("MS_TENANT_ID",      ms.get("tenant_id"))
    ms["client_id"]      = _env("MS_CLIENT_ID",      ms.get("client_id"))
    ms["client_secret"]  = _env("MS_CLIENT_SECRET",  ms.get("client_secret"))
    ms["redirect_uri"]   = _env("MS_REDIRECT_URI",   ms.get("redirect_uri"))
    ms["sender_user_id"] = _env("MS_SENDER_USER_ID", ms.get("sender_user_id"))

    gg = cfg.setdefault("google", {})
    gg["client_id"]     = _env("GOOGLE_CLIENT_ID",     gg.get("client_id"))
    gg["client_secret"] = _env("GOOGLE_CLIENT_SECRET", gg.get("client_secret"))
    gg["redirect_uri"]  = _env("GOOGLE_REDIRECT_URI",  gg.get("redirect_uri"))
    return cfg


def calendar_config() -> dict:
    return _load_calendar_config()


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.send",
    "openid", "email", "profile",
]
MICROSOFT_SCOPES = [
    "offline_access",
    "OnlineMeetings.ReadWrite",
    "Calendars.ReadWrite",
    "Mail.Send",
    "User.Read",
]


def _is_expired(expires_at) -> bool:
    if not expires_at:
        return True
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at)
        except ValueError:
            return True
    # 60s clock skew buffer.
    now = datetime.now(expires_at.tzinfo) if expires_at.tzinfo else datetime.now()
    return expires_at <= now + timedelta(seconds=60)


def _refresh_google_token(refresh_token: str, cfg: dict) -> Optional[dict]:
    g = cfg.get("google") or {}
    if not (g.get("client_id") and g.get("client_secret") and refresh_token):
        return None
    try:
        r = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": g["client_id"],
                "client_secret": g["client_secret"],
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=15,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning(f"google token refresh failed: {e}")
        return None


def _refresh_microsoft_token(refresh_token: str, cfg: dict) -> Optional[dict]:
    m = cfg.get("microsoft") or {}
    tenant = m.get("tenant_id") or "common"
    if not (m.get("client_id") and m.get("client_secret") and refresh_token):
        return None
    try:
        r = requests.post(
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            data={
                "client_id": m["client_id"],
                "client_secret": m["client_secret"],
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "scope": " ".join(MICROSOFT_SCOPES),
            },
            timeout=15,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning(f"microsoft token refresh failed: {e}")
        return None


def _microsoft_app_only_token(cfg: dict) -> Optional[str]:
    """Get app-only Graph token via client_credentials. Useful when no per-user
    OAuth is configured but the tenant has app-only consent. Requires
    `sender_user_id` to be set so we know whose calendar to act on."""
    m = cfg.get("microsoft") or {}
    if not (m.get("tenant_id") and m.get("client_id") and m.get("client_secret")
            and m.get("sender_user_id")):
        return None
    try:
        r = requests.post(
            f"https://login.microsoftonline.com/{m['tenant_id']}/oauth2/v2.0/token",
            data={
                "client_id": m["client_id"],
                "client_secret": m["client_secret"],
                "grant_type": "client_credentials",
                "scope": "https://graph.microsoft.com/.default",
            },
            timeout=15,
        )
        r.raise_for_status()
        return r.json().get("access_token")
    except Exception as e:
        log.warning(f"microsoft client_credentials failed: {e}")
        return None


def _get_valid_token(provider: str, user_id: int, db) -> tuple[Optional[str], Optional[str]]:
    """Return (access_token, acting_user_or_email) or (None, None).
    For Microsoft, falls back to app-only token + configured sender_user_id
    when no per-user token exists.
    """
    cfg = calendar_config()
    row = None
    try:
        row = db.get_oauth_token(user_id, provider)
    except Exception as e:
        log.warning(f"get_oauth_token failed for {provider}: {e}")

    if row and row.get("access_token"):
        if _is_expired(row.get("expires_at")) and row.get("refresh_token"):
            refresh_fn = _refresh_google_token if provider == "google" else _refresh_microsoft_token
            new = refresh_fn(row["refresh_token"], cfg)
            if new and new.get("access_token"):
                expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=int(new.get("expires_in", 3600))
                )
                try:
                    db.save_oauth_token(
                        user_id, provider,
                        access_token=new["access_token"],
                        refresh_token=new.get("refresh_token") or row["refresh_token"],
                        expires_at=expires_at,
                        scope=new.get("scope"),
                        email=row.get("email"),
                    )
                except Exception:
                    pass
                return new["access_token"], row.get("email")
        return row["access_token"], row.get("email")

    # Microsoft fallback: app-only token + configured sender mailbox.
    if provider == "microsoft":
        tok = _microsoft_app_only_token(cfg)
        if tok:
            return tok, (cfg.get("microsoft") or {}).get("sender_user_id")

    return None, None


# ---------------------------------------------------------------------------
# Provider-specific meeting creation
# ---------------------------------------------------------------------------
def _create_google_meet(token: str, *, subject: str, start_iso: str,
                        duration_minutes: int, attendee_email: str,
                        organizer_email: Optional[str]) -> dict:
    """Create a Google Calendar event with a Meet conference. Uses the
    organizer's primary calendar.
    """
    try:
        start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
    except ValueError:
        return {"success": False, "error": f"Invalid start time: {start_iso!r}"}
    end = start + timedelta(minutes=duration_minutes)

    body = {
        "summary": subject,
        "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
        "end":   {"dateTime": end.isoformat(),   "timeZone": "UTC"},
        "attendees": [{"email": attendee_email}] if attendee_email else [],
        "conferenceData": {
            "createRequest": {
                "requestId": f"smarthr-{int(time.time())}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }
    try:
        r = requests.post(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events"
            "?conferenceDataVersion=1&sendUpdates=all",
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
            data=json.dumps(body),
            timeout=20,
        )
        if r.status_code >= 400:
            return {"success": False,
                    "error": f"Google Calendar API {r.status_code}: {r.text[:300]}"}
        ev = r.json()
        meet_url = ev.get("hangoutLink")
        if not meet_url:
            entry = ((ev.get("conferenceData") or {}).get("entryPoints") or [])
            meet_url = next((e.get("uri") for e in entry if e.get("entryPointType") == "video"), None)
        return {"success": True, "provider": "meet",
                "join_url": meet_url, "event_id": ev.get("id")}
    except Exception as e:
        return {"success": False, "error": f"Google Meet creation failed: {e}"}


def _create_teams_meeting(token: str, *, subject: str, start_iso: str,
                          duration_minutes: int, attendee_email: str,
                          organizer_user: Optional[str]) -> dict:
    """Create a Teams meeting via Graph API. organizer_user is either
    'me' (delegated) or a userPrincipalName / object ID (app-only)."""
    try:
        start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
    except ValueError:
        return {"success": False, "error": f"Invalid start time: {start_iso!r}"}
    end = start + timedelta(minutes=duration_minutes)

    who = organizer_user or "me"
    base = (f"https://graph.microsoft.com/v1.0/users/{who}"
            if who != "me" else "https://graph.microsoft.com/v1.0/me")

    event_body = {
        "subject": subject,
        "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
        "end":   {"dateTime": end.isoformat(),   "timeZone": "UTC"},
        "isOnlineMeeting": True,
        "onlineMeetingProvider": "teamsForBusiness",
        "attendees": ([{"emailAddress": {"address": attendee_email},
                        "type": "required"}]
                      if attendee_email else []),
    }
    try:
        r = requests.post(
            f"{base}/events",
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
            data=json.dumps(event_body),
            timeout=20,
        )
        if r.status_code >= 400:
            return {"success": False,
                    "error": f"Microsoft Graph {r.status_code}: {r.text[:300]}"}
        ev = r.json()
        join_url = ((ev.get("onlineMeeting") or {}).get("joinUrl")
                    or ev.get("onlineMeetingUrl"))
        return {"success": True, "provider": "teams",
                "join_url": join_url, "event_id": ev.get("id")}
    except Exception as e:
        return {"success": False, "error": f"Teams meeting creation failed: {e}"}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def create_meeting(provider: str, *, subject: str, start_iso: str,
                   duration_minutes: int, attendee_email: str,
                   organizer_user_id: int, db) -> dict:
    """Create a meeting and return {success, provider, join_url, event_id, error}.

    `provider`: "teams" | "meet" | "google" | "microsoft" | "" / None.
    If the provider is empty or "none", returns success=True with no link.
    """
    if not provider or provider.lower() in ("none", "in_person", "in-person", "phone"):
        return {"success": True, "provider": provider or "none",
                "join_url": None, "event_id": None, "error": None}

    p = provider.lower()
    if p in ("meet", "google", "google_meet", "google-meet"):
        token, email = _get_valid_token("google", organizer_user_id, db)
        if not token:
            return {"success": False, "provider": "meet", "join_url": None,
                    "event_id": None,
                    "error": ("Google account not connected. Recruiter must "
                              "connect Google via /api/oauth/google/start.")}
        return _create_google_meet(
            token, subject=subject, start_iso=start_iso,
            duration_minutes=duration_minutes,
            attendee_email=attendee_email, organizer_email=email,
        )
    if p in ("teams", "microsoft", "ms_teams", "ms-teams"):
        token, who = _get_valid_token("microsoft", organizer_user_id, db)
        if not token:
            return {"success": False, "provider": "teams", "join_url": None,
                    "event_id": None,
                    "error": ("Microsoft account not connected. Recruiter must "
                              "connect Microsoft via /api/oauth/microsoft/start, "
                              "or set MS_TENANT_ID / MS_CLIENT_ID / "
                              "MS_CLIENT_SECRET / MS_SENDER_USER_ID for app-only.")}
        return _create_teams_meeting(token, subject=subject, start_iso=start_iso,
                                     duration_minutes=duration_minutes,
                                     attendee_email=attendee_email,
                                     organizer_user=who)
    return {"success": False, "provider": provider, "join_url": None,
            "event_id": None,
            "error": f"Unknown meeting provider: {provider!r}"}
