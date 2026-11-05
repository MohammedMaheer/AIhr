from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

import main
import database
from services import calendar_service as calendar
from services import email_service as email
from services import oauth_state


@pytest.mark.parametrize("template", [
    "{{ cycler.__init__.__globals__.os.name }}",
    "{{ ''.__class__.__mro__ }}", "{{ candidate_name.upper() }}",
    "{{ 'x' * 999999999 }}", "{{ 9 ** 99999999 }}",
    "{% for n in range(10000000) %}x{% endfor %}",
    "{{ candidate_name | attr('__class__') }}", "{% include 'config.json' %}",
    "{{ candidate_name | safe }}",
])
def test_email_template_rejects_execution_and_expansion(template):
    with pytest.raises(ValueError):
        email.render_template("Subject", template, {"candidate_name": "QA"})


@pytest.mark.parametrize("template", email.DEFAULT_TEMPLATES)
def test_default_templates_preserve_rendering_and_escape_html(template):
    ctx = email.build_default_context(candidate_name="<QA>", candidate_email="qa@example.invalid",
                                      position="R&D", custom_message="<script>bad</script>")
    subject, body = email.render_template(template["subject"], template["body"], ctx)
    assert "R&D" in subject
    assert "&lt;QA&gt;" in body
    assert "<script>" not in body
    assert "{{" not in body and "{%" not in body


def test_email_template_bounds_and_context():
    for subject, body, ctx in [("x" * 32769, "", {}), ("", "{{ x }}", {"x": object()}),
                               ("hello\nBcc: bad", "", {})]:
        with pytest.raises(ValueError):
            email.render_template(subject, body, ctx)


def test_smtp_tls_failure_never_logs_in_or_sends_plaintext():
    smtp = MagicMock()
    smtp.__enter__.return_value = smtp
    smtp.starttls.side_effect = email.smtplib.SMTPException("TLS unavailable")
    with patch.object(email, "email_config", return_value={"smtp": {
        "host": "smtp.example.invalid", "from": "qa@example.invalid", "user": "qa",
        "password": "fake", "use_tls": True,
    }}), patch.object(email.smtplib, "SMTP", return_value=smtp):
        result = email._send_via_smtp("qa@example.invalid", "QA", "<p>QA</p>")
    assert not result["success"]
    smtp.login.assert_not_called()
    smtp.sendmail.assert_not_called()


@pytest.mark.parametrize("provider", ["google", "microsoft"])
def test_oauth_signed_state_bound_to_provider_session_user_and_config(monkeypatch, provider):
    monkeypatch.setenv("SECRET_KEY", "test-only-signing-key-" * 3)
    cfg = {"client_id": "qa-client", "redirect_uri": "https://qa.invalid/callback"}
    state, cookie, challenge = oauth_state.issue(provider, 7, "qa-session", cfg)
    verifier = oauth_state.validate(cookie, state, provider, 7, "qa-session", cfg)
    assert len(verifier) >= 43 and len(challenge) == 43
    for changed_cookie, changed_state, changed_provider, user, session, config in [
        (cookie + "0", state, provider, 7, "qa-session", cfg),
        ("forged:999", state, provider, 7, "qa-session", cfg),
        (cookie, "wrong-state", provider, 7, "qa-session", cfg),
        (cookie, state, provider, 999, "qa-session", cfg),
        (cookie, state, provider, 7, "other-session", cfg),
        (cookie, state, "google" if provider == "microsoft" else "microsoft", 7, "qa-session", cfg),
        (cookie, state, provider, 7, "qa-session", {**cfg, "client_id": "other-client"}),
    ]:
        with pytest.raises(main.HTTPException):
            oauth_state.validate(changed_cookie, changed_state, changed_provider, user, session, config)
    with patch.object(oauth_state.time, "time", return_value=oauth_state.time.time() + 601):
        with pytest.raises(main.HTTPException):
            oauth_state.validate(cookie, state, provider, 7, "qa-session", cfg)


@pytest.mark.parametrize("provider", ["google", "microsoft"])
def test_oauth_callbacks_reject_old_forged_state_without_provider_calls(provider):
    db = MagicMock()
    db.verify_session.return_value = None
    with patch.object(main, "get_db_manager", return_value=db), patch.object(main.requests, "post") as post:
        client = TestClient(main.app, base_url="https://testserver")
        client.cookies.set("oauth_state_" + provider, "forged:987654")
        response = client.get(f"/api/oauth/{provider}/callback?code=fake&state=forged", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers['location'] == f'/login?integration={provider}&status=session_expired'
    db.save_oauth_token.assert_not_called()
    post.assert_not_called()


@pytest.mark.parametrize("provider", ["google", "microsoft"])
def test_oauth_callback_validates_and_uses_pkce_before_saving(monkeypatch, provider):
    monkeypatch.setenv("SECRET_KEY", "test-only-signing-key-" * 3)
    cfg = {"client_id": "qa", "client_secret": "fake", "tenant_id": "qa",
           "redirect_uri": f"https://testserver/api/oauth/{provider}/callback"}
    db = MagicMock()
    db.verify_session.return_value = {"id": 7, "user_type": "super_admin"}
    token = MagicMock()
    token.json.return_value = {"access_token": "fake-access", "expires_in": 3600}
    account = MagicMock()
    account.json.return_value = {"email": "qa@example.invalid", "mail": "qa@example.invalid",
                                 "id": "synthetic-account", "sub": "synthetic-account"}
    with patch.object(main, "get_db_manager", return_value=db), \
         patch.object(calendar, "calendar_config", return_value={provider: cfg}), \
         patch.object(main.requests, "post", return_value=token) as post, \
         patch.object(main.requests, "get", return_value=account):
        client = TestClient(main.app, base_url="https://testserver")
        client.cookies.set("session_token", "qa-session")
        start = client.get(f"/api/oauth/{provider}/start", follow_redirects=False)
        assert start.status_code == 302
        params = parse_qs(urlsplit(start.headers["location"]).query)
        assert params["code_challenge_method"] == ["S256"]
        state = params["state"][0]
        cookie = client.cookies.get(oauth_state.cookie_name(provider))
        expected = oauth_state.validate(cookie, state, provider, 7, "qa-session", cfg)
        response = client.get(f"/api/oauth/{provider}/callback", params={"code": "fake", "state": state},
                              follow_redirects=False)
    assert response.status_code == 302
    assert post.call_args.kwargs["data"]["code_verifier"] == expected
    assert db.save_oauth_token.call_args.args == (7, provider)
    assert db.save_oauth_token.call_args.kwargs['extra'] == {'account_id': 'synthetic-account'}
    assert "max-age=0" in response.headers["set-cookie"].lower()


@pytest.mark.parametrize("refresh", [None, "fake-refresh"])
def test_expired_token_never_returned_after_failed_refresh(refresh):
    db = MagicMock()
    db.get_oauth_token.return_value = {"access_token": "expired", "refresh_token": refresh,
        "expires_at": datetime.now(timezone.utc) - timedelta(hours=1)}
    with patch.object(calendar, "calendar_config", return_value={}), \
         patch.object(calendar, "_refresh_microsoft_token", return_value=None), \
         patch.object(calendar, "_microsoft_app_only_token") as fallback:
        assert calendar._get_valid_token("microsoft", 7, db) == (None, None)
    fallback.assert_not_called()


def test_expiry_treats_naive_database_timestamp_as_utc():
    assert calendar._is_expired(datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1))
    assert not calendar._is_expired(datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1))
    assert calendar._is_expired("invalid")


def test_cursor_creation_failure_returns_connection_without_masking_error():
    db = database.DatabaseManager.__new__(database.DatabaseManager)
    db.pool = MagicMock()
    conn = db.pool.getconn.return_value
    conn.cursor.side_effect = RuntimeError("cursor failed")
    with pytest.raises(RuntimeError, match="cursor failed"):
        with db.get_cursor():
            pass
    conn.rollback.assert_called_once()
    db.pool.putconn.assert_called_once_with(conn)


@pytest.mark.parametrize("llm", [False, True])
def test_public_health_never_calls_ai_even_when_requested(tmp_path, monkeypatch, llm):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    cursor = MagicMock()
    cursor.fetchone.side_effect = [(1,), (4001,)]
    db = MagicMock()
    db.get_cursor.return_value.__enter__.return_value = (cursor, None)
    with patch.object(database, "get_db_manager", return_value=db), \
         patch.object(main, "_gemini_ping_cached") as ping, \
         patch.object(main, "gemini_client") as client:
        response = TestClient(main.app).get("/health/deep", params={"llm": str(llm).lower()})
    assert response.status_code == 200
    assert response.json()["checks"]["llm"]["status"] == "skipped"
    ping.assert_not_called()
    client.assert_not_called()
