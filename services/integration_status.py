"""Describe saved connection metadata without contacting a provider."""
from services.calendar_service import _is_expired


REQUIRED = {
    "microsoft": {"mail_import": {"Mail.Read"}, "email": {"Mail.Send"},
                  "calendar": {"Calendars.ReadWrite"}},
    "google": {"email": {"https://www.googleapis.com/auth/gmail.send"},
               "calendar": {"https://www.googleapis.com/auth/calendar.events"}},
}


def connection_status(provider: str, row: dict | None) -> dict:
    required = REQUIRED[provider]
    row = row or {}
    connected = bool(row.get("access_token"))
    scopes = set(str(row.get("scope") or "").split())
    if provider == "microsoft":
        scopes = {scope.removeprefix("https://graph.microsoft.com/") for scope in scopes}
    known = bool(scopes)
    capabilities = {name: (needs <= scopes if known else None) for name, needs in required.items()}
    missing = sorted(set().union(*required.values()) - scopes) if known else []
    expired = connected and _is_expired(row.get("expires_at"))
    reconnect = connected and (not row.get("email") or not known or bool(missing)
                              or (expired and not row.get("refresh_token")))
    return {
        "connected": connected,
        "account_email": row.get("email") if connected else None,
        "permissions_known": known,
        "missing_permissions": missing,
        "capabilities": capabilities,
        "reconnect_required": bool(reconnect),
        "verification": "not_tested",  # Stored consent is not a live mailbox/calendar check.
    }
