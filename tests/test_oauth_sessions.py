from http.cookies import SimpleCookie
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlsplit

import pytest
import main
from services.oauth_state import cookie_name
from test_integration_workflows import api


@pytest.fixture(autouse=True)
def isolated_rate_limits(monkeypatch):
    monkeypatch.setattr(main.limiter, 'enabled', False)


def response_cookies(response):
    cookies = SimpleCookie()
    for header in response.headers.get_list('set-cookie'):
        cookies.load(header)
    return cookies


def assert_session_cookie(cookie):
    assert cookie['samesite'].lower() == 'lax'
    assert cookie['secure'] and cookie['httponly']
    assert cookie['path'] == '/' and not cookie['domain']
    assert int(cookie['max-age']) == 7 * 24 * 60 * 60


def test_login_sets_oauth_compatible_session_but_keeps_strict_csrf(api):
    client, db = api
    db.authenticate_user.return_value = {'id': 7, 'user_type': 'tenant_user'}
    db.create_session.return_value = 'synthetic-login-session'
    client.cookies.clear()
    response = client.post('/api/login', data={'email': 'fictional@example.invalid', 'password': 'synthetic-only'})
    assert response.status_code == 200
    cookies = response_cookies(response)
    assert_session_cookie(cookies['session_token'])
    assert cookies['session_token'].value == 'synthetic-login-session'
    assert cookies['csrf_token']['samesite'].lower() == 'strict'
    assert cookies['csrf_token']['secure']
    db.create_session.assert_called_once()


@pytest.mark.parametrize('provider', ['microsoft', 'google'])
def test_oauth_start_upgrades_existing_cookie_without_creating_a_new_session(api, provider):
    client, db = api
    response = client.get('/api/oauth/' + provider + '/start', follow_redirects=False)
    assert response.status_code == 302
    cookies = response_cookies(response)
    assert_session_cookie(cookies['session_token'])
    assert cookies['session_token'].value == 'synthetic-session'
    state = cookies[cookie_name(provider)]
    assert state['secure'] and state['httponly'] and state['samesite'].lower() == 'lax'
    params = parse_qs(urlsplit(response.headers['location']).query)
    assert params['code_challenge_method'] == ['S256']
    assert response.headers['cache-control'] == 'no-store'
    db.create_session.assert_not_called()


@pytest.mark.parametrize('provider', ['microsoft', 'google'])
@pytest.mark.parametrize('session', [None, 'synthetic-expired-session'])
def test_callback_missing_or_expired_login_requires_reauthentication_without_exchange(api, monkeypatch, provider, session):
    client, db = api
    client.cookies.clear()
    if session:
        client.cookies.set('session_token', session)
    db.verify_session.return_value = None
    post = MagicMock()
    monkeypatch.setattr(main.requests, 'post', post)
    response = client.get('/api/oauth/' + provider + '/callback',
        params={'code': 'synthetic-code-must-not-be-reused', 'state': 'synthetic-state'}, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers['location'] == '/login?integration=' + provider + '&status=session_expired'
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['referrer-policy'] == 'no-referrer'
    assert response_cookies(response)[cookie_name(provider)]['max-age'] == '0'
    assert 'synthetic-code' not in response.headers['location']
    assert 'synthetic-state' not in response.headers['location']
    post.assert_not_called()
    db.save_oauth_token.assert_not_called()
    page = client.get(response.headers['location'])
    assert page.status_code == 200
    assert 'Your SmartHR session expired or is unavailable in this browser.' in page.text
    assert 'role="alert"' in page.text


@pytest.mark.parametrize('provider', ['microsoft', 'google'])
def test_callback_does_not_treat_auth_service_failure_as_expired_login(api, monkeypatch, provider):
    client, _db = api
    monkeypatch.setattr(main, 'get_db_manager', lambda: None)
    response = client.get('/api/oauth/' + provider + '/callback', params={'code': 'synthetic'}, follow_redirects=False)
    assert response.status_code == 503


@pytest.mark.parametrize('provider', ['microsoft', 'google'])
def test_callback_never_bypasses_blocked_account_roles(api, provider):
    client, db = api
    db.verify_session.return_value = {'id': 7, 'user_type': 'unknown-role'}
    response = client.get('/api/oauth/' + provider + '/callback', params={'code': 'synthetic'}, follow_redirects=False)
    assert response.status_code == 403
    db.save_oauth_token.assert_not_called()


@pytest.mark.parametrize('provider', ['microsoft', 'google'])
def test_changed_login_session_still_rejects_callback_before_provider_io(api, monkeypatch, provider):
    client, db = api
    start = client.get('/api/oauth/' + provider + '/start', follow_redirects=False)
    state = parse_qs(urlsplit(start.headers['location']).query)['state'][0]
    signed_cookie = response_cookies(start)[cookie_name(provider)].value
    client.cookies.clear()
    client.cookies.set('session_token', 'different-synthetic-session')
    client.cookies.set(cookie_name(provider), signed_cookie)
    post = MagicMock()
    monkeypatch.setattr(main.requests, 'post', post)
    response = client.get('/api/oauth/' + provider + '/callback', params={'code': 'synthetic', 'state': state}, follow_redirects=False)
    assert response.status_code == 400
    post.assert_not_called()
    db.save_oauth_token.assert_not_called()


@pytest.mark.parametrize('origin,csrf,expected', [
    ('https://untrusted.invalid', 'synthetic-csrf', 403),
    ('https://testserver', None, 403),
    ('https://testserver', 'synthetic-csrf', 200),
])
def test_cookie_policy_does_not_remove_unsafe_request_csrf_checks(api, origin, csrf, expected):
    client, db = api
    client.headers.pop('X-CSRF-Token')
    headers = {'Origin': origin}
    if csrf:
        headers['X-CSRF-Token'] = csrf
    response = client.post('/api/oauth/microsoft/disconnect', headers=headers)
    assert response.status_code == expected
    if expected == 200:
        db.delete_oauth_token.assert_called_once_with(7, 'microsoft')
    else:
        db.delete_oauth_token.assert_not_called()


@pytest.mark.parametrize('query', ['', '?status=session_expired&integration=untrusted',
                                 '?status=other&integration=microsoft'])
def test_login_notice_only_accepts_fixed_oauth_recovery_flags(api, query):
    client, _db = api
    response = client.get('/login' + query)
    assert response.status_code == 200
    assert 'Your SmartHR session expired or is unavailable in this browser.' not in response.text
