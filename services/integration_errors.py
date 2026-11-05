"""Public integration errors must not include remote bodies or credentials."""


def provider_failure(provider: str, operation: str, *, status_code: int | None = None,
                     uncertain: bool | None = None) -> dict:
    labels = {"smtp": "SMTP", "microsoft": "Microsoft Graph", "gmail": "Gmail",
              "teams": "Microsoft calendar", "meet": "Google Calendar", "unknown": "Email service"}
    label = labels[provider]
    if operation not in {"email", "calendar"}:
        raise ValueError("Unknown integration operation")
    if uncertain is None:
        uncertain = status_code is None or status_code >= 500
    prefix = label + (f" (HTTP {status_code})" if status_code is not None else "")
    result = {"success": False, "provider": provider}
    if uncertain:
        check = "Sent Items and the recipient's inbox" if operation == "email" else "the organizer's calendar"
        result["error"] = f"{prefix}: the {operation} outcome is unknown. Check {check} before retrying to avoid duplicates."
        result["delivery_unknown" if operation == "email" else "calendar_event_maybe_created"] = True
    elif status_code in (401, 403):
        result["error"] = f"{prefix}: access was rejected. Check the connected account, permissions and organization policy."
    elif status_code == 429:
        result["error"] = f"{prefix}: the provider rate limit was reached. Wait before trying again."
    elif status_code is None:
        result["error"] = f"{prefix}: the request could not start. Check the account and transport configuration."
    else:
        result["error"] = f"{prefix}: the request was rejected. Check the account configuration and request details."
    return result
