import base64
from unittest.mock import MagicMock, patch

import pytest

import main
from services import calendar_service as calendar
from services import graph_mail as graph
from services.token_crypto import seal, open_token


def result(data, status=200, headers=None):
    response = MagicMock(status_code=status, headers=headers or {})
    response.json.return_value = data
    return response


def message(identity):
    return {"id": identity, "subject": "CV application", "body": {"content": "Please see resume"}}


def attachment(identity):
    return {"id": identity, "name": "QA Candidate.pdf", "contentBytes": base64.b64encode(b"synthetic CV").decode()}


def test_graph_paginates_messages_and_attachments_and_reuses_inline_bytes():
    session = MagicMock()
    session.__enter__.return_value = session
    session.get.side_effect = [
        result({"value": [message("m1")], "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/messages?$skip=1"}),
        result({"value": [attachment("a1")], "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/messages/m1/attachments?$skip=1"}),
        result({"value": [attachment("a2")]}),
        result({"value": [message("m2")]}),
        result({"value": [attachment("a3")]}),
    ]
    with patch.object(graph.requests, "Session", return_value=session):
        emails = graph.collect_resume_mail("fake", 5, include_attachment=lambda *_: True,
                                          classify_context=lambda *_: True)
    assert len(emails) == 2
    assert len(emails[0]["attachments"]) == 2
    assert session.get.call_count == 5
    assert emails[0]["attachments"][0]["filename"] != emails[0]["attachments"][1]["filename"]


def test_attachment_query_keeps_all_dates_and_satisfies_graph_sort_filter_rules():
    session = MagicMock()
    session.__enter__.return_value = session

    def get(url, **kwargs):
        params = kwargs['params']
        # Emulate the Graph InefficientFilter rejection observed in production.
        valid = (params['$orderby'] == 'receivedDateTime desc'
                 and params['$filter'].startswith('receivedDateTime ge 0001-01-01T00:00:00Z and ')
                 and params['$filter'].endswith('hasAttachments eq true'))
        return result({'value': []}, 200 if valid else 400)

    session.get.side_effect = get
    with patch.object(graph.requests, 'Session', return_value=session):
        assert graph.collect_resume_mail('fake', 3, include_attachment=lambda *_: True,
                                         classify_context=lambda *_: True) == []
    assert session.get.call_count == 1


@pytest.mark.parametrize("url", ["https://evil.invalid/v1.0/me", "http://graph.microsoft.com/v1.0/me",
    "https://graph.microsoft.com.evil.invalid/v1.0/me", "https://user@graph.microsoft.com/v1.0/me"])
def test_graph_rejects_untrusted_nextlink_before_sending_tokens(url):
    session = MagicMock()
    with pytest.raises(ValueError):
        list(graph._pages(session, url))
    session.get.assert_not_called()


@pytest.mark.parametrize("status", [401, 403, 500, 302])
def test_graph_errors_are_not_reported_as_empty_mailbox(status):
    session = MagicMock()
    session.get.return_value = result({}, status)
    with pytest.raises(RuntimeError):
        graph._get(session, "https://graph.microsoft.com/v1.0/me/messages")


def test_graph_throttling_has_bounded_retry():
    session = MagicMock()
    session.get.side_effect = [result({}, 429, {"Retry-After": "0"}), result({"value": []})]
    with patch.object(graph.time, "sleep") as sleep:
        assert graph._get(session, "https://graph.microsoft.com/v1.0/me/messages") == {"value": []}
    assert session.get.call_count == 2
    sleep.assert_called_once_with(0)


def test_connected_mailbox_path_uses_oauth_and_rejects_different_mailbox():
    db = MagicMock()
    db.get_oauth_token.return_value = {"access_token": "fake"}
    with patch.object(main, "get_db_manager", return_value=db), \
         patch.object(calendar, "_get_valid_token", return_value=("fake", "qa@example.invalid")), \
         patch.object(graph, "collect_resume_mail", return_value=[]) as collect:
        assert main.scrape_outlook_attachments("qa@example.invalid", None, 10, 7) == []
        with pytest.raises(RuntimeError, match="does not match"):
            main.scrape_outlook_attachments("other@example.invalid", None, 10, 7)
    collect.assert_called_once()


def test_unconnected_passwordless_outlook_fails_before_external_auth():
    db = MagicMock()
    db.get_oauth_token.return_value = None
    with patch.object(main, "get_db_manager", return_value=db), \
         patch.object(main.msal, "ConfidentialClientApplication") as auth, \
         patch.object(main, "scrape_imap_resume_attachments") as imap:
        with pytest.raises(RuntimeError, match="Connect your Microsoft mailbox"):
            main.scrape_outlook_attachments("qa@example.invalid", None, 10, 7)
    auth.assert_not_called()
    imap.assert_not_called()


def test_microsoft_connect_scopes_match_manager_review_request():
    from services.microsoft_consent import SCOPES
    normalize = lambda value: value.removeprefix("https://graph.microsoft.com/")
    assert {normalize(scope) for scope in SCOPES} == set(calendar.MICROSOFT_SCOPES)
    assert "OnlineMeetings.ReadWrite" not in calendar.MICROSOFT_SCOPES


def test_provider_tokens_encrypted_and_owner_bound(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-only-secret-" * 4)
    kwargs = {"user_id": 7, "provider": "microsoft", "field": "access"}
    encrypted = seal("fake-access-token", **kwargs)
    assert "fake-access-token" not in encrypted and encrypted.startswith("enc:v1:")
    assert open_token(encrypted, **kwargs) == "fake-access-token"
    for change in [{"user_id": 8}, {"provider": "google"}, {"field": "refresh"}]:
        with pytest.raises(ValueError):
            open_token(encrypted, **{**kwargs, **change})
    with pytest.raises(ValueError):
        open_token(encrypted + "changed", **kwargs)


def test_provider_token_key_rotation_requires_reconnect(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-only-secret-" * 4)
    args = {"user_id": 7, "provider": "google", "field": "refresh"}
    encrypted = seal("fake-refresh", **args)
    monkeypatch.setenv("SECRET_KEY", "different-test-secret-" * 4)
    with pytest.raises(ValueError):
        open_token(encrypted, **args)
