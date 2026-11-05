import base64
import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

from services import microsoft_consent as consent


CFG = {
    "tenant_id": "017c0c22-31fd-41c8-b159-d421376db3f2",
    "client_id": "8265f455-0545-4cd3-966a-1a9f11cdd861",
    "redirect_uri": "https://effortsairecruiter.tech/api/oauth/microsoft/callback",
}


@pytest.fixture(autouse=True)
def signing_key(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-signing-secret-not-a-production-key-1234")


def started_request(**overrides):
    response = consent.start_consent(CFG)
    params = parse_qs(urlsplit(response.headers["location"]).query)
    cookie = response.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]
    query = {"state": params["state"][0], "admin_consent": "True", "tenant": CFG["tenant_id"]}
    query.update(overrides)
    return SimpleNamespace(cookies={consent.COOKIE_NAME: cookie}, query_params=query)


def test_start_uses_only_explicit_scopes_and_secure_signed_state():
    response = consent.start_consent(CFG)
    params = parse_qs(urlsplit(response.headers["location"]).query)
    assert params["scope"][0].split() == list(consent.SCOPES)
    assert ".default" not in params["scope"][0]
    assert params["redirect_uri"] == [CFG["redirect_uri"]]
    assert params["state"][0].startswith(consent.STATE_PREFIX)
    cookie = response.headers["set-cookie"]
    assert all(flag in cookie for flag in ("Secure", "HttpOnly", "SameSite=lax", "Path=/"))
    assert "Domain=" not in cookie
    assert response.headers["cache-control"] == "no-store"


def test_calendar_teams_scope_matches_recruiter_connection_and_review_page():
    from pathlib import Path
    from services.calendar_service import MICROSOFT_SCOPES

    names = {scope.rsplit("/", 1)[-1] for scope in consent.SCOPES}
    assert names == set(MICROSOFT_SCOPES)
    assert "Calendars.ReadWrite" in names
    assert "OnlineMeetings.ReadWrite" not in names
    page = (Path(__file__).resolve().parents[1] / "static/review/microsoft-approval.html").read_text()
    for scope in names:
        assert f"<td>{scope}</td>" in page
    assert "Calendar and Teams interviews" in page
    assert "Outlook calendars" in page
    assert "Microsoft Teams meeting links" in page
    assert 'href="/api/oauth/microsoft/admin-consent/start"' in page
    assert "SmartHR_AI_Cost_Brief.pdf" not in page


def test_teams_interview_is_calendar_backed_not_standalone(monkeypatch):
    from services import calendar_service

    sent = []

    def fake_post(url, **kwargs):
        sent.append((url, kwargs))
        return SimpleNamespace(status_code=201, json=lambda: {
            "id": "synthetic-event", "onlineMeeting": {"joinUrl": "https://teams.microsoft.com/synthetic"},
        })

    monkeypatch.setattr(calendar_service.requests, "post", fake_post)
    result = calendar_service._create_teams_meeting(
        "synthetic-token", subject="Synthetic interview", start_iso="2030-01-02T10:00:00+00:00",
        duration_minutes=30, attendee_email="fictional@example.invalid", organizer_user=None,
    )
    assert result["success"] is True
    assert result["join_url"] == "https://teams.microsoft.com/synthetic"
    assert len(sent) == 1
    url, options = sent[0]
    assert url == "https://graph.microsoft.com/v1.0/me/events"
    body = json.loads(options["data"])
    assert body["isOnlineMeeting"] is True
    assert body["onlineMeetingProvider"] == "teamsForBusiness"
    assert body["attendees"][0]["emailAddress"]["address"] == "fictional@example.invalid"
    assert body["end"]["dateTime"] == "2030-01-02T10:30:00+00:00"


def test_valid_response_is_a_receipt_not_an_account_connection():
    response = consent.finish_consent(started_request(), CFG)
    assert response.status_code == 200
    assert b"Microsoft returned an approval response" in response.body
    assert b"does not connect a recruiter mailbox" in response.body
    assert b"access_token" not in response.body
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("changes", [{"state": "wrong"}, {"tenant": "another-tenant"}, {"admin_consent": "False"}])
def test_state_tenant_and_approval_mismatch_fail(changes):
    response = consent.finish_consent(started_request(**changes), CFG)
    assert response.status_code == 400
    assert b"Microsoft returned an approval response" not in response.body


def test_missing_or_forged_cookie_is_rejected():
    req = started_request()
    req.cookies = {}
    assert consent.finish_consent(req, CFG).status_code == 400
    req.cookies = {consent.COOKIE_NAME: "forged.invalid"}
    assert consent.finish_consent(req, CFG).status_code == 400


def test_expired_cookie_is_rejected(monkeypatch):
    monkeypatch.setattr(consent.time, "time", lambda: 1000)
    req = started_request()
    monkeypatch.setattr(consent.time, "time", lambda: 1601)
    assert consent.finish_consent(req, CFG).status_code == 400


def test_error_text_is_not_reflected_as_html():
    response = consent.finish_consent(started_request(error="<script>bad()</script>"), CFG)
    assert response.status_code == 200
    assert b"Permission approval was not completed" in response.body
    assert b"<script>" not in response.body


def test_admin_request_configuration_fails_closed(monkeypatch):
    with pytest.raises(Exception) as exc:
        consent.start_consent({**CFG, "tenant_id": "common"})
    assert exc.value.status_code == 503
    with pytest.raises(Exception):
        consent.start_consent({**CFG, "redirect_uri": "http://example.com/callback"})
    monkeypatch.delenv("SECRET_KEY")
    with pytest.raises(Exception) as exc:
        consent.start_consent(CFG)
    assert exc.value.status_code == 503


def test_changed_signed_payload_is_rejected():
    req = started_request()
    cookie, signature = req.cookies[consent.COOKIE_NAME].rsplit(".", 1)
    data = json.loads(base64.urlsafe_b64decode(cookie))
    data["tenant"] = "another-tenant"
    changed = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
    req.cookies[consent.COOKIE_NAME] = changed + "." + signature
    assert consent.finish_consent(req, CFG).status_code == 400


def test_existing_callback_handles_admin_consent_without_database_or_token_exchange(monkeypatch):
    import main
    from fastapi.testclient import TestClient
    from services import calendar_service

    monkeypatch.setattr(calendar_service, "calendar_config", lambda: {"microsoft": CFG})
    monkeypatch.setattr(main, "get_db_manager", lambda: pytest.fail("must not use database"))
    monkeypatch.setattr(main.requests, "post", lambda *a, **kw: pytest.fail("must not exchange token"))
    client = TestClient(main.app, base_url="https://effortsairecruiter.tech")
    response = client.get("/api/oauth/microsoft/admin-consent/start", follow_redirects=False)
    state = parse_qs(urlsplit(response.headers["location"]).query)["state"][0]
    response = client.get("/api/oauth/microsoft/callback", params={
        "state": state, "tenant": CFG["tenant_id"], "admin_consent": "True",
    }, follow_redirects=False)
    assert response.status_code == 200
    assert "Microsoft returned an approval response" in response.text
