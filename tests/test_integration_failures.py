import smtplib
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests

from services import calendar_service as calendar, email_service as email
from services.integration_errors import provider_failure


PRIVATE = "synthetic-private-credential-and-mailbox-marker"


@pytest.mark.parametrize("row", [{}, {"access_token": None}, {"access_token": ""},
                                  {"refresh_token": "synthetic-refresh"}])
def test_unusable_saved_account_never_falls_back_to_shared_mailbox(monkeypatch, row):
    db = MagicMock()
    db.get_oauth_token.return_value = row
    fallback = MagicMock(return_value="synthetic-app-token")
    monkeypatch.setattr(calendar, "_microsoft_app_only_token", fallback)
    assert calendar._get_valid_token("microsoft", 7, db, delegated_actor=True) == (None, None)
    fallback.assert_not_called()
    db.oauth_refresh_lock.assert_not_called()


def call_provider(provider):
    if provider == "microsoft":
        return email._send_via_graph("synthetic-token", "me", "fictional@example.invalid", "Synthetic", "Synthetic")
    if provider == "gmail":
        return email._send_via_gmail("synthetic-token", "fictional@example.invalid", "fictional@example.invalid", "Synthetic", "Synthetic")
    kwargs = dict(subject="Synthetic", start_iso="2030-01-02T10:00:00+00:00",
                  duration_minutes=30, attendee_email="fictional@example.invalid")
    if provider == "teams":
        return calendar._create_teams_meeting("synthetic-token", organizer_user="me", **kwargs)
    return calendar._create_google_meet("synthetic-token", organizer_email=None, **kwargs)


@pytest.mark.parametrize("provider", ["microsoft", "gmail", "teams", "meet"])
@pytest.mark.parametrize("status", [401, 403, 429, 503])
def test_provider_error_bodies_are_never_read_or_exposed(monkeypatch, caplog, provider, status):
    class Response:
        status_code = status

        @property
        def text(self):
            pytest.fail("Private response bodies must not be read")

    post = MagicMock(return_value=Response())
    monkeypatch.setattr(requests, "post", post)
    result = call_provider(provider)
    assert result["success"] is False
    assert str(status) in result["error"]
    assert result.get("delivery_unknown", result.get("calendar_event_maybe_created", False)) is (status >= 500)
    assert PRIVATE not in str(result) + caplog.text
    post.assert_called_once()


@pytest.mark.parametrize("provider", ["microsoft", "gmail", "teams", "meet"])
@pytest.mark.parametrize("error_type", [requests.Timeout, requests.ConnectionError, ValueError])
def test_timeout_outcomes_are_unknown_without_exception_detail(monkeypatch, caplog, provider, error_type):
    post = MagicMock(side_effect=error_type(PRIVATE))
    monkeypatch.setattr(requests, "post", post)
    result = call_provider(provider)
    assert result["success"] is False
    assert result.get("delivery_unknown", result.get("calendar_event_maybe_created")) is True
    assert "before retrying" in result["error"]
    assert PRIVATE not in str(result) + caplog.text
    post.assert_called_once()


@pytest.mark.parametrize("refresh", [calendar._refresh_google_token, calendar._refresh_microsoft_token,
                                    calendar._microsoft_app_only_token])
def test_token_endpoint_exception_details_are_not_logged(monkeypatch, caplog, refresh):
    monkeypatch.setattr(requests, "post", MagicMock(side_effect=requests.Timeout(PRIVATE)))
    cfg = {provider: dict(client_id="synthetic-client", client_secret=PRIVATE,
                         tenant_id="synthetic-tenant", sender_user_id="synthetic-user")
           for provider in ("google", "microsoft")}
    result = refresh(cfg) if refresh is calendar._microsoft_app_only_token else refresh("synthetic-refresh", cfg)
    assert result is None
    assert PRIVATE not in caplog.text


@pytest.mark.parametrize("provider", ["microsoft", "gmail", "teams", "meet"])
def test_successful_provider_behavior_is_unchanged(monkeypatch, provider):
    monkeypatch.setattr(requests, "post", MagicMock(return_value=SimpleNamespace(status_code=201,
        json=lambda: {"id": "synthetic-event", "hangoutLink": "https://meet.google.com/synthetic",
                      "onlineMeeting": {"joinUrl": "https://teams.microsoft.com/synthetic"}})))
    assert call_provider(provider)["success"] is True


@pytest.mark.parametrize("prefer", ["auto", "microsoft"])
def test_unknown_delivery_never_falls_back_to_another_transport(monkeypatch, prefer):
    monkeypatch.setattr(calendar, "_get_valid_token", lambda *a, **kw: ("synthetic-token", "me"))
    gmail = MagicMock(return_value=provider_failure("gmail", "email"))
    graph = MagicMock(return_value=provider_failure("microsoft", "email", status_code=503))
    smtp = MagicMock(return_value={"success": True, "provider": "smtp"})
    monkeypatch.setattr(email, "_send_via_gmail", gmail)
    monkeypatch.setattr(email, "_send_via_graph", graph)
    monkeypatch.setattr(email, "_send_via_smtp", smtp)
    result = email.send_email(to="fictional@example.invalid", subject="Synthetic", body_html="Synthetic",
                              prefer=prefer, organizer_user_id=7, db=object())
    assert result["delivery_unknown"] is True
    smtp.assert_not_called()
    if prefer == "auto":
        gmail.assert_called_once()
        graph.assert_not_called()
    else:
        gmail.assert_not_called()
        graph.assert_called_once()


def test_definite_rejection_keeps_existing_transport_fallback(monkeypatch):
    monkeypatch.setattr(calendar, "_get_valid_token", lambda *a, **kw: ("synthetic-token", "me"))
    monkeypatch.setattr(email, "_send_via_gmail", lambda *a: provider_failure("gmail", "email", status_code=403))
    graph = MagicMock(return_value={"success": True, "provider": "microsoft"})
    smtp = MagicMock()
    monkeypatch.setattr(email, "_send_via_graph", graph)
    monkeypatch.setattr(email, "_send_via_smtp", smtp)
    result = email.send_email(to="fictional@example.invalid", subject="Synthetic", body_html="Synthetic",
                              organizer_user_id=7, db=object())
    assert result == {"success": True, "provider": "microsoft"}
    graph.assert_called_once()
    smtp.assert_not_called()


@pytest.mark.parametrize("port", [465, 587])
@pytest.mark.parametrize("outcome", ["connect_error", "timeout", "rejected", "cleanup_error", "success"])
def test_smtp_distinguishes_rejection_uncertainty_and_accepted_cleanup(monkeypatch, caplog, port, outcome):
    monkeypatch.setattr(email, "email_config", lambda: {"smtp": {
        "host": "synthetic.invalid", "from": "sender@example.invalid", "port": port}})

    class SMTP:
        def __init__(self, *args, **kwargs):
            if outcome == "connect_error":
                raise OSError(PRIVATE)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            if outcome == "cleanup_error":
                raise OSError(PRIVATE)

        def ehlo(self):
            pass

        def starttls(self, **kwargs):
            pass

        def sendmail(self, *args):
            if outcome == "timeout":
                raise TimeoutError(PRIVATE)
            if outcome == "rejected":
                raise smtplib.SMTPDataError(550, PRIVATE.encode())

    monkeypatch.setattr(smtplib, "SMTP", SMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", SMTP)
    result = email._send_via_smtp("fictional@example.invalid", "Synthetic", "Synthetic")
    assert result["success"] is (outcome in {"success", "cleanup_error"})
    assert result.get("delivery_unknown", False) is (outcome == "timeout")
    assert PRIVATE not in str(result) + caplog.text
