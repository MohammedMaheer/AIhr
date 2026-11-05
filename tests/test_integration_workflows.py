from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
import main
from services import calendar_service as calendar
from services.integration_status import connection_status
from test_candidate_state import oauth_db
from test_durable_search import queue_db


@pytest.fixture
def api(monkeypatch):
    db = MagicMock()
    db.verify_session.return_value = {'id': 7, 'user_type': 'tenant_user', 'company': {'company_id': 1}}
    db.get_oauth_token.return_value = None
    db.schedule_interview.return_value = 12
    db.list_email_templates.return_value = []
    db.log_email_sent.return_value = 1
    monkeypatch.setattr(main, 'get_db_manager', lambda: db)
    monkeypatch.setenv('SECRET_KEY', 'synthetic-signing-key-' * 4)
    cfg = {'client_id': 'synthetic-client', 'client_secret': 'synthetic-secret',
           'tenant_id': '017c0c22-31fd-41c8-b159-d421376db3f2',
           'redirect_uri': 'https://testserver/api/oauth/microsoft/callback'}
    monkeypatch.setattr(calendar, 'calendar_config', lambda: {'microsoft': cfg, 'google': {
        **cfg, 'redirect_uri': 'https://testserver/api/oauth/google/callback'}})
    client = TestClient(main.app, base_url='https://testserver')
    client.cookies.set('session_token', 'synthetic-session')
    client.cookies.set('csrf_token', 'synthetic-csrf')
    client.headers['X-CSRF-Token'] = 'synthetic-csrf'
    return client, db


def saved_row(**changes):
    return {'access_token': 'private-access-marker', 'refresh_token': 'private-refresh-marker',
            'email': 'fictional@example.invalid', 'scope': 'User.Read Mail.Read Mail.Send Calendars.ReadWrite',
            'expires_at': datetime.now(timezone.utc) + timedelta(hours=1), **changes}


@pytest.mark.parametrize('changes,required', [({}, False), ({'scope': 'Mail.Read'}, True),
    ({'scope': None}, True), ({'email': None}, True),
    ({'expires_at': '2000-01-01T00:00:00Z', 'refresh_token': None}, True),
    ({'expires_at': '2000-01-01T00:00:00Z'}, False)])
def test_metadata_reports_reconnect_without_live_provider_calls(changes, required):
    result = connection_status('microsoft', saved_row(**changes))
    assert result['reconnect_required'] is required
    assert result['verification'] == 'not_tested'
    assert 'private-access-marker' not in str(result)
    assert 'private-refresh-marker' not in str(result)


def test_status_is_current_user_scoped_non_mutating_and_contains_no_tokens(api, monkeypatch):
    client, db = api
    db.get_oauth_token.side_effect = lambda uid, provider: saved_row() if provider == 'microsoft' else None
    monkeypatch.setattr(calendar.requests, 'post', lambda *a, **k: pytest.fail('No provider probes in status'))
    response = client.get('/api/integrations/status')
    assert response.status_code == 200
    assert response.json()['microsoft']['capabilities'] == {'mail_import': True, 'email': True, 'calendar': True}
    assert all(call.args[0] == 7 for call in db.get_oauth_token.call_args_list)
    assert 'private-access-marker' not in response.text
    assert 'private-refresh-marker' not in response.text
    db.save_oauth_token.assert_not_called()


def test_status_failure_is_503_not_disconnected_or_provider_fallback(api):
    client, db = api
    db.get_oauth_token.side_effect = RuntimeError('private-db-details')
    response = client.get('/api/integrations/status')
    assert response.status_code == 503
    assert 'private-db-details' not in response.text


@pytest.mark.parametrize('provider', ['microsoft', 'google'])
@pytest.mark.parametrize('outcome', ['ok', 'lookup_error', 'missing_email', 'missing_id', 'exchange_error', 'save_error'])
def test_callback_requires_account_identity_and_safe_success_or_failure(api, monkeypatch, provider, outcome):
    client, db = api
    start = client.get('/api/oauth/' + provider + '/start', follow_redirects=False)
    assert start.status_code == 302
    state = parse_qs(urlsplit(start.headers['location']).query)['state'][0]

    def post(*args, **kwargs):
        if outcome == 'exchange_error':
            raise RuntimeError('private-provider-error-marker')
        assert kwargs['data']['code_verifier']
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {
            'access_token': 'synthetic-access', 'refresh_token': 'synthetic-refresh',
            'expires_in': 3600, 'scope': 'Mail.Read Mail.Send Calendars.ReadWrite User.Read'})

    def get(*args, **kwargs):
        if outcome == 'lookup_error':
            raise RuntimeError('private-provider-error-marker')
        data = {'mail': 'fictional@example.invalid', 'email': 'fictional@example.invalid'}
        if outcome != 'missing_id': data.update(id='synthetic-account', sub='synthetic-account')
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {} if outcome == 'missing_email' else data)

    monkeypatch.setattr(main.requests, 'post', post)
    monkeypatch.setattr(main.requests, 'get', get)
    if outcome == 'save_error': db.save_oauth_token.side_effect = RuntimeError('private-db-marker')
    response = client.get('/api/oauth/' + provider + '/callback', params={'state': state, 'code': 'synthetic'}, follow_redirects=False)
    assert response.status_code == 302
    expected = 'connected' if outcome == 'ok' else 'failed'
    assert response.headers['location'] == '/?integration=' + provider + '&status=' + expected
    assert response.headers['cache-control'] == 'no-store'
    assert 'Max-Age=0' in response.headers['set-cookie']
    assert 'private-' not in response.headers['location']
    if outcome in ('lookup_error', 'missing_email', 'missing_id', 'exchange_error'):
        db.save_oauth_token.assert_not_called()


def test_delegated_graph_actor_is_me_but_mailbox_identity_is_retained(monkeypatch):
    db = MagicMock()
    db.get_oauth_token.return_value = saved_row(email='smtp-alias@example.invalid')
    assert calendar._get_valid_token('microsoft', 7, db) == ('private-access-marker', 'smtp-alias@example.invalid')
    assert calendar._get_valid_token('microsoft', 7, db, delegated_actor=True) == ('private-access-marker', 'me')
    db.get_oauth_token.return_value = None
    monkeypatch.setattr(calendar, 'calendar_config', lambda: {'microsoft': {'sender_user_id': 'configured-mailbox'}})
    monkeypatch.setattr(calendar, '_microsoft_app_only_token', lambda cfg: 'synthetic-app-token')
    assert calendar._get_valid_token('microsoft', 7, db, delegated_actor=True) == ('synthetic-app-token', 'configured-mailbox')


@pytest.mark.parametrize('provider', ['teams', 'meet'])
@pytest.mark.parametrize('join_url', [None, 'javascript:bad()', 'http://unsafe.invalid', 'https://user:secret@example.invalid/'])
def test_missing_or_unsafe_join_link_is_partial_calendar_creation(monkeypatch, provider, join_url):
    monkeypatch.setattr(calendar.requests, 'post', lambda *a, **kw: SimpleNamespace(status_code=201, json=lambda: {
        'id': 'created-event', 'onlineMeeting': {'joinUrl': join_url}, 'hangoutLink': join_url}))
    kwargs = dict(subject='Synthetic', start_iso='2030-01-02T10:00:00+00:00', duration_minutes=30,
                  attendee_email='fictional@example.invalid')
    result = calendar._create_teams_meeting('synthetic', organizer_user='me', **kwargs) if provider == 'teams' else \
        calendar._create_google_meet('synthetic', organizer_email='fictional@example.invalid', **kwargs)
    assert result['success'] is False
    assert result['calendar_event_created'] is True
    assert result['event_id'] == 'created-event'
    assert result['join_url'] is None


def test_meet_conference_ids_are_unique_even_in_the_same_second(monkeypatch):
    import json
    payloads = []
    def post(*args, **kwargs):
        payloads.append(json.loads(kwargs['data']))
        return SimpleNamespace(status_code=201, json=lambda: {'id': 'synthetic', 'hangoutLink': 'https://meet.google.com/synthetic'})
    monkeypatch.setattr(calendar.requests, 'post', post)
    for _ in range(2):
        assert calendar._create_google_meet('synthetic', subject='Synthetic', start_iso='2030-01-02T10:00:00+00:00',
            duration_minutes=30, attendee_email='', organizer_email=None)['success']
    assert payloads[0]['conferenceData']['createRequest']['requestId'] != payloads[1]['conferenceData']['createRequest']['requestId']


def interview_body(**changes):
    return {'candidate_name': 'Synthetic Candidate', 'candidate_email': 'fictional@example.invalid', 'position': 'Backend Engineer',
        'interview_date': '2030-01-02', 'interview_time': '10:00', 'time_zone': 'UTC',
        'duration': 30, 'meeting_provider': 'teams', 'send_invite_email': True, **changes}


def test_partial_meeting_is_saved_without_sending_blank_link_email(api, monkeypatch):
    from services import email_service
    client, db = api
    monkeypatch.setattr(calendar, 'create_meeting', lambda *a, **kw: {
        'success': False, 'event_id': 'partial-event', 'error': 'Link unavailable', 'calendar_event_created': True})
    sender = MagicMock()
    monkeypatch.setattr(email_service, 'send_email', sender)
    response = client.post('/api/schedule-interview', json=interview_body())
    assert response.status_code == 200
    assert response.json()['success']
    assert response.json()['email']['skipped']
    assert db.schedule_interview.call_args.args[0]['meeting_event_id'] == 'partial-event'
    sender.assert_not_called()
    db.save_candidate_action.assert_not_called()


@pytest.mark.parametrize('changes', [{'meeting_provider': 7}, {'meeting_provider': 'unknown'},
    {'candidate_name': '   '}, {'candidate_name': []}, {'candidate_name': 'x'*256},
    {'candidate_email': 'bad\r\nBcc: fake@example.invalid'}, {'candidate_email': 'not-an-email'},
    {'send_invite_email': 'false'}, {'candidate_email': '', 'send_invite_email': True}])
def test_invalid_interview_inputs_never_reach_provider_or_database(api, monkeypatch, changes):
    client, db = api
    create = MagicMock()
    monkeypatch.setattr(calendar, 'create_meeting', create)
    response = client.post('/api/schedule-interview', json=interview_body(**changes))
    assert response.status_code == 422
    create.assert_not_called()
    db.schedule_interview.assert_not_called()


def test_approval_serves_current_page_without_cached_static_redirect(api):
    client, _ = api
    response = client.get('/microsoft-approval', follow_redirects=False)
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert 'Calendar and Teams interviews' in response.text
    assert 'SmartHR_AI_Cost_Brief.pdf' not in response.text


def test_postgres_switching_account_never_keeps_old_refresh_or_scope(oauth_db):
    db = oauth_db
    db.save_oauth_token(7, 'microsoft', access_token='account-a-access', refresh_token='account-a-refresh',
                       scope='Mail.Read', email='account-a@example.invalid')
    db.save_oauth_token(7, 'microsoft', access_token='account-a-new-access', email='ACCOUNT-A@example.invalid')
    assert db.get_oauth_token(7, 'microsoft')['refresh_token'] == 'account-a-refresh'
    db.save_oauth_token(7, 'microsoft', access_token='account-b-access', email='account-b@example.invalid')
    row = db.get_oauth_token(7, 'microsoft')
    assert row['refresh_token'] is None
    assert row['scope'] is None
    assert row['email'] == 'account-b@example.invalid'
    db.save_oauth_token(7, 'microsoft', access_token='account-b-access', refresh_token='account-b-refresh',
                       email='account-b@example.invalid', extra={'account_id': 'stable-b'})
    db.save_oauth_token(7, 'microsoft', access_token='account-c-access', email='account-b@example.invalid',
                       extra={'account_id': 'stable-c'})
    row = db.get_oauth_token(7, 'microsoft')
    assert row['refresh_token'] is None
    assert row['extra']['account_id'] == 'stable-c'


PROTECTED_ROUTES = [(method, route.path) for route in main.app.routes
    if hasattr(route, 'dependant') and any(getattr(dep.call, '__name__', '') in
        {'require_auth', 'require_super_admin', 'require_tenant_admin'} for dep in route.dependant.dependencies)
    for method in route.methods if method in {'GET', 'POST', 'PUT', 'PATCH', 'DELETE'}]


@pytest.mark.parametrize('method,path', PROTECTED_ROUTES)
def test_every_declared_authenticated_route_rejects_anonymous_before_io(monkeypatch, method, path):
    import re
    monkeypatch.setattr(main, 'get_db_manager', lambda: pytest.fail('Anonymous request reached database'))
    path = re.sub(r'\{[^}]+\}', lambda match: 'microsoft' if match.group() == '{provider}' else '1', path)
    response = TestClient(main.app).request(method, path, json={})
    assert response.status_code == 401
